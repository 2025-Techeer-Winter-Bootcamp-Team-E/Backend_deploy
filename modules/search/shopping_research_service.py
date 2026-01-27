"""
Shopping Research service for 2-step AI recommendation.

Step 1: Generate customized questions based on user query
Step 2: Analyze survey responses and recommend top 5 products with 90%+ similarity
"""
import json
import logging
import re
import uuid
from typing import List, Dict, Any, Optional

from django.core.cache import cache
from django.db.models import F
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Cast
from django.db.models import TextField
from pgvector.django import CosineDistance
from concurrent.futures import ThreadPoolExecutor
from modules.products.models import ProductModel, MallInformationModel
from modules.categories.models import CategoryModel
from shared.ai_clients import get_openai_client, get_gemini_client
from .prompts import (
    QUESTION_GENERATION_PROMPT,
    SHOPPING_RESEARCH_ANALYSIS_PROMPT,
    AI_REVIEW_SUMMARY_PROMPT,
    BATCH_PRODUCT_ANALYSIS_PROMPT,
    RECOMMENDATION_REASON_PROMPT,
)

logger = logging.getLogger(__name__)


class ShoppingResearchService:
    """Service for 2-step shopping research with AI-powered recommendations."""

    CACHE_TTL = 1800  # 30 minutes
    TOP_K = 5
    SEARCH_LIMIT = 50
    VECTOR_WEIGHT = 1.0  # Only vector score now
    MIN_SIMILARITY = 0.60  # 60% similarity threshold

    def __init__(self):
        self.openai_client = get_openai_client()
        self.gemini_client = get_gemini_client()

    def _generate_search_id(self, user_query: str) -> str:
        """
        Generate unique search_id and store in cache.

        Args:
            user_query: User's search query

        Returns:
            Generated search_id (format: sr-xxxxxxxx)
        """
        search_id = f"sr-{uuid.uuid4().hex[:8]}"
        cache_key = f"shopping_research:{search_id}"
        cache.set(cache_key, {"user_query": user_query}, timeout=self.CACHE_TTL)
        return search_id

    def _validate_search_id(self, search_id: str) -> Optional[Dict[str, Any]]:
        """
        Validate search_id and retrieve cached data.

        Args:
            search_id: The search ID to validate

        Returns:
            Cached data if valid, None otherwise
        """
        cache_key = f"shopping_research:{search_id}"
        return cache.get(cache_key)

    def generate_questions(self, user_query: str) -> Dict[str, Any]:
        """
        Step 1: Generate customized questions based on user query.

        Args:
            user_query: User's natural language search query

        Returns:
            Dict with search_id and questions list
        """
        # Generate search_id
        search_id = self._generate_search_id(user_query)

        # Generate questions using Gemini
        prompt = QUESTION_GENERATION_PROMPT.format(user_query=user_query)

        try:
            response = self.gemini_client.generate_content(prompt)

            # Parse JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(response)

            questions = result.get('questions', [])

            # Ensure question_id is present and convert options to object format
            for i, q in enumerate(questions, 1):
                if 'question_id' not in q:
                    q['question_id'] = i
                # Convert string options to object format {id, label}
                if 'options' in q and q['options']:
                    q['options'] = [
                        {"id": idx, "label": opt} if isinstance(opt, str) else opt
                        for idx, opt in enumerate(q['options'], 1)
                    ]

            return {
                "search_id": search_id,
                "questions": questions
            }

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"❌ 질문 생성 실패 원인: {str(e)}")
            logger.warning(f"Question generation failed: {e}. Using default questions.")
            return {
                "search_id": search_id,
                "questions": self._get_default_questions()
            }

    def _get_default_questions(self) -> List[Dict[str, Any]]:
        """Return default questions when AI generation fails."""
        return [
            {
                "question_id": 1,
                "question": "주요 사용 목적은 무엇인가요?",
                "options": [
                    {"id": 1, "label": "일반 업무"},
                    {"id": 2, "label": "영상 편집"},
                    {"id": 3, "label": "게임"},
                    {"id": 4, "label": "개발"}
                ]
            },
            {
                "question_id": 2,
                "question": "생각하시는 예산 범위는?",
                "options": [
                    {"id": 1, "label": "100만원 미만"},
                    {"id": 2, "label": "100~150만원"},
                    {"id": 3, "label": "150~200만원"},
                    {"id": 4, "label": "200만원 이상"}
                ]
            },
            {
                "question_id": 3,
                "question": "디스플레이에서 가장 중요한 점은?",
                "options": [
                    {"id": 1, "label": "해상도"},
                    {"id": 2, "label": "색재현율"},
                    {"id": 3, "label": "크기"},
                    {"id": 4, "label": "주사율"}
                ]
            },
            {
                "question_id": 4,
                "question": "휴대성을 어느 정도 고려하시나요?",
                "options": [
                    {"id": 1, "label": "매우 중요"},
                    {"id": 2, "label": "보통"},
                    {"id": 3, "label": "성능이 더 중요"}
                ]
            }
        ]

    def get_recommendations(
        self,
        search_id: str,
        user_query: str,
        survey_contents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Step 2: Analyze survey responses and recommend products.

        Args:
            search_id: Search session ID
            user_query: User's search query
            survey_contents: List of survey responses

        Returns:
            Dict with user_query and product recommendations
        """
        # Validate search_id (optional - for tracking purposes)
        cached_data = self._validate_search_id(search_id)
        if cached_data:
            logger.info(f"Valid search_id: {search_id}")

        # Fill in missing question texts from cached data
        if cached_data and 'questions' in cached_data:
            questions_map = {q['question_id']: q['question'] for q in cached_data['questions']}
            for survey in survey_contents:
                if not survey.get('question'):
                    survey['question'] = questions_map.get(survey['question_id'], f"질문 {survey['question_id']}")

        # Analyze survey responses
        # intent에는 search_query, keywords, priorities, user_needs, product_category, min_price, max_price가 포함됨
        intent = self._analyze_survey(user_query, survey_contents)

        logger.debug(f"Analyzed intent: {intent}")
        # 카테고리 ID 조회 (필터링용)
        category_id = None
        llm_category_name = intent.get('product_category')
        if llm_category_name:
            # TrigramSimilarity를 사용하여 DB에서 가장 유사한 카테고리 검색
            best_match = CategoryModel.objects.annotate(
                similarity=TrigramSimilarity('name', llm_category_name)
            ).filter(similarity__gt=0.3).order_by('-similarity').first()

            if best_match:
                category_id = best_match.id
                logger.info(f"LLM category '{llm_category_name}' mapped to DB category '{best_match.name}' (ID: {category_id})")
            else:
                logger.warning(f"LLM category '{llm_category_name}' could not be mapped to any DB category with similarity > 0.3. Category filter will not be applied.")

        min_price = intent.get('min_price')
        max_price = intent.get('max_price')

        # Perform hybrid search
        # Price range validation
        if min_price is not None and max_price is not None and min_price > max_price:
            logger.warning(f"Invalid price range from LLM: min_price({min_price}) > max_price({max_price}). Ignoring price filter.")
            min_price, max_price = None, None

        # Perform hybrid search with strict filters
        logger.info(f"Attempting search with strict filters: category_id={category_id}, price=[{min_price}-{max_price}], query='{intent['search_query']}'")
        vector_results = self._vector_search(intent['search_query'], category_id, min_price, max_price) # Only vector search
        logger.info(f"Vector search 결과: {len(vector_results)}개 상품 발견")
        
        fused_results = self._fuse_results(vector_results) # Pass only vector results
        logger.info(f"Fused results: {len(fused_results)}개")

        # Filter by minimum similarity (60%+)
        high_similarity_results = [
            r for r in fused_results if r['combined_score'] >= self.MIN_SIMILARITY
        ]
        logger.info(f"유사도 {self.MIN_SIMILARITY*100}% 이상 상품: {len(high_similarity_results)}개")

        # If not enough high-similarity results, use top results
        if len(high_similarity_results) < self.TOP_K:
            logger.info(f"Only {len(high_similarity_results)} products with {self.MIN_SIMILARITY*100}%+ similarity. Using top {self.TOP_K} results regardless of similarity.")
            high_similarity_results = fused_results[:self.TOP_K] if fused_results else []

        # Get top K products
        top_products = high_similarity_results[:self.TOP_K]
        
        logger.info(f"최종 선택된 상품 수: {len(top_products)}개 (요청: {self.TOP_K}개)")

        # 상품이 없으면 빈 배열 반환
        if not top_products:
            logger.warning(f"검색 결과 없음 - query: '{user_query}', category_id: {category_id}, price_range: [{min_price}-{max_price}]")
            return {
                "user_query": user_query,
                "product": []
            }

        # 3. 모든 상품의 가격 리스트 (최저가 여부 확인용)
        all_prices = [p['product'].lowest_price for p in top_products]

            # 1. Gemini에게 5개 상품 정보를 한꺼번에 던져서 분석 결과를 미리 다 받아옵니다.
        analysis_map = self._batch_analyze_products(
            user_query=user_query,
            user_needs=intent['user_needs'],
            products=top_products
        )

        # 2. 분석된 결과를 루프를 돌며 하나씩 조립만 합니다. (이제 AI 호출 없음)
        products = []
        for rank, p_data in enumerate(top_products, 1):
            p_code = str(p_data['product'].danawa_product_id)
            # 일괄 분석 결과 맵에서 해당 상품의 데이터를 꺼내옵니다.
            item_analysis = analysis_map.get(p_code)
            
            analyzed = self._analyze_product(
                product_data=p_data,
                user_query=user_query,
                user_needs=intent['user_needs'],
                rank=rank,
                all_prices=all_prices,
                pre_analysis=item_analysis  # 미리 분석한 데이터를 넘겨줍니다.
            )
            products.append(analyzed)

            logger.info(f"최종 반환 상품 수: {len(products)}개")
        return {
            "user_query": user_query,
            "product": products
        }
    

    def _analyze_survey(
        self,
        user_query: str,
        survey_contents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze survey responses to extract search intent."""
        # Format survey responses (handle missing question field)
        def format_survey_item(s):
            question_id = s['question_id']
            question_text = s.get('question') or f'질문 {question_id}'
            answer = s['answer']
            return f"Q{question_id}: {question_text} -> A: {answer}"

        survey_text = "\n".join([format_survey_item(s) for s in survey_contents])

        prompt = SHOPPING_RESEARCH_ANALYSIS_PROMPT.format(
            user_query=user_query,
            survey_responses=survey_text
        )

        try:
            response = self.gemini_client.generate_content(prompt)
            
            # 응답이 None이거나 빈 문자열인 경우 처리
            if not response:
                raise ValueError("Gemini API가 빈 응답을 반환했습니다.")

            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                intent = json.loads(json_match.group())
            else:
                intent = json.loads(response)

            min_price = intent.get('min_price')
            max_price = intent.get('max_price')

            return {
                'product_category': intent.get('product_category'),
                'search_query': intent.get('search_query', user_query),
                'keywords': intent.get('keywords', [user_query]),
                'priorities': intent.get('priorities', {}),
                'min_price': min_price if min_price is not None else None,
                'max_price': max_price if max_price is not None and max_price > 0 else None,
                'user_needs': intent.get('user_needs', user_query)
            }

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Survey analysis failed: {e}. Using fallback.")
            # Build search query from survey answers
            answers = [s['answer'] for s in survey_contents]
            combined_query = f"{user_query} {' '.join(answers)}"
            return {
                'product_category': None,
                'search_query': combined_query,
                'keywords': [user_query] + answers,
                'priorities': {},
                'min_price': None,
                'max_price': None,
                'user_needs': user_query
            }

    def _get_descendant_category_ids(self, category_id: int) -> List[int]:
        """Recursively get all descendant category IDs."""
        ids = [category_id]
        children = CategoryModel.objects.filter(parent_id=category_id, deleted_at__isnull=True)
        for child in children:
            ids.extend(self._get_descendant_category_ids(child.id))
        return ids

    def _vector_search(
        self,
        search_query: str,
        category_id: Optional[int] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Perform HNSW vector search."""
        try:
            query_embedding = self.openai_client.create_embedding(search_query)
        except Exception as e:
            logger.error(f"OpenAI embedding 생성 실패: {str(e)}")
            # Embedding 생성 실패 시 빈 결과 반환
            return []

        queryset = ProductModel.objects.filter(
            deleted_at__isnull=True,
            detail_spec_vector__isnull=False
        )

        # Apply hard filters
        if category_id:
            category_ids = self._get_descendant_category_ids(category_id)
            queryset = queryset.filter(category_id__in=category_ids)
        if min_price is not None:
            queryset = queryset.filter(lowest_price__gte=min_price)
        if max_price is not None:
            queryset = queryset.filter(lowest_price__lte=max_price)

        logger.debug(f"Vector search - after hard filters (category={category_id}, min_price={min_price}, max_price={max_price}): {queryset.count()} products remaining.")
        logger.debug(f"Vector search - after hard filters (category={category_id}, min_price={min_price}, max_price={max_price}): {queryset.count()} products remaining for query '{search_query}'.")
        products = queryset.exclude(
            product_status__in=['단종', '판매중지', '품절']
        ).annotate(
            distance=CosineDistance('detail_spec_vector', query_embedding)
        ).order_by('distance')[:self.SEARCH_LIMIT]

        results = []
        for product in products:
            similarity = max(0.0, 1.0 - (product.distance / 2.0))

            mall_info = MallInformationModel.objects.filter(
                product=product,
                deleted_at__isnull=True
            ).first()

            results.append({
                'product': product,
                'mall_info': mall_info,
                'vector_score': similarity,
            })

        return results

    def _fuse_results(
        self,
        vector_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Fuse vector and keyword search results with hybrid scoring."""
        results_map: Dict[str, Dict[str, Any]] = {}

        for item in vector_results:
            product_id = item['product'].danawa_product_id
            results_map[product_id] = {
                'product': item['product'],
                'mall_info': item['mall_info'],
                'vector_score': item['vector_score'],
            }

        fused_results = []
        for product_id, data in results_map.items():
            combined_score = self.VECTOR_WEIGHT * data['vector_score']
            fused_results.append({
                **data,
                'combined_score': combined_score
            })

        fused_results.sort(key=lambda x: (
            x['combined_score'],
            x['product'].review_count,
            x['product'].review_rating or 0
        ), reverse=True)

        return fused_results

    def _batch_analyze_products(
        self,
        user_query: str,
        user_needs: str,
        products: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, str]]:
        """
        상품 스펙 필터링 없이 detail_spec 내의 spec_summary를 직접 보냄
        """
        if not products:
            return {}

        products_info_lines = []
        for p_data in products:
            product = p_data['product']

            spec_summary_list = product.detail_spec.get('spec_summary', [])
            #리스트 형태를 텍스르토 바꿈
            specs_str = " / ".join(spec_summary_list) if spec_summary_list else "상세 정보 없음"

            # Format specs for prompt
            products_info_lines.append(
                f"- 상품코드: {product.danawa_product_id}\n"
                f"  상품명: {product.name}\n"
                f"  브랜드: {product.brand}\n"
                f"  가격: {product.lowest_price:,}원\n"
                f"  스펙: {specs_str}"
            )

        products_info = "\n\n".join(products_info_lines)

        prompt = BATCH_PRODUCT_ANALYSIS_PROMPT.format(
            user_query=user_query,
            user_needs=user_needs,
            products_info=products_info
        )

        try:
            response = self.gemini_client.generate_content(prompt)
            
            # 응답이 None이거나 빈 문자열인 경우 처리
            if not response:
                raise ValueError("Gemini API가 빈 응답을 반환했습니다.")
            
            json_match = re.search(r'\{[\s\S]*\}', response)
            result = json.loads(json_match.group()) if json_match else json.loads(response)
            analysis_map = {str(item.get('product_code')): item for item in result.get('results', [])}
            return analysis_map

        except Exception as e:
            logger.warning(f"Batch analysis failed: {e}. Falling back to individual generation.")
            return {}

    def _analyze_product(
        self,
        product_data: Dict[str, Any],
        user_query: str,
        user_needs: str,
        rank: int,
        all_prices: List[int],
        pre_analysis: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Analyze a single product and build recommendation response."""
        product = product_data['product']
        mall_info = product_data.get('mall_info')
        combined_score = product_data.get('combined_score', 0.0)

        # Extract specs
        spec_summary = product.detail_spec.get('spec_summary', [])
        specs_str = " / ".join(spec_summary) if spec_summary else "상세 정보 없음"
        specs_obj = {"summary": specs_str}
        
        # 2. 일괄 분석 결과(pre_analysis)가 있으면 사용하고, 없으면 직접 Gemini 호출(Fallback)
        if pre_analysis:
            # _batch_analyze_products에서 이미 생성된 값을 가져옵니다.
            recommendation_reason = pre_analysis.get('recommendation_reason')
            ai_review_summary = pre_analysis.get('ai_review_summary')
            
            # 혹시 분석 결과가 누락되었을 경우를 대비한 최소한의 방어 로직(테스트 중 해당 문구 뜨면 에러임)
            if not recommendation_reason:
                recommendation_reason = f"{product.brand} {product.name}은(는) 요구사항에 적합한 추천 제품입니다."
            if not ai_review_summary:
                ai_review_summary = f"{product.name}은(는) 사용자분들께 좋은 평가를 받고 있습니다."
        else:
            # 만약 일괄 분석 데이터가 전달되지 않았다면 기존처럼 개별 호출 수행
            recommendation_reason = self._generate_recommendation_reason(
                user_query=user_query,
                user_needs=user_needs,
                product_name=product.name,
                brand=product.brand,
                price=product.lowest_price,
                specs=specs_obj
            )
            ai_review_summary = self._generate_ai_review_summary(
                product_name=product.name,
                brand=product.brand,
                price=product.lowest_price,
                specs=specs_obj,
                user_needs=user_needs
            )

        # Calculate performance score (0.0 - 1.0)
        performance_score = self._calculate_performance_score(product, combined_score)

        # Check if lowest price among top products
        is_lowest_price = product.lowest_price == min(all_prices) if all_prices else False

        return {
            "similarity_score": round(combined_score, 2),
            "product_image_url": mall_info.representative_image_url if mall_info else None,
            "product_name": product.name,
            "product_code": int(product.danawa_product_id),
            "recommendation_reason": recommendation_reason,
            "price": product.lowest_price,
            "performance_score": round(performance_score, 2),
            "product_specs": {
                "summary": specs_str  # 구조를 단순화하여 전체 스펙 요약을 전달
            },
            "ai_review_summary": ai_review_summary,
            "product_detail_url": mall_info.product_page_url if mall_info else None,
            "optimal_product_info": {
                "match_rank": rank,
                "is_lowest_price": is_lowest_price
            }
        }
    #스펙 추출 기능 메서드 삭제 => 다양한 카테고리의 상품 포괄 못하기 때문.
    ''' 
    def _extract_product_specs(self, detail_spec: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Extract display specs from product detail_spec."""
        specs = {
            'cpu': None,
            'ram': None,
            'storage': None,
            'display': None,
            'weight': None,
            'gpu': None,
            'battery': None
        }

        if not detail_spec:
            return specs

        spec_data = detail_spec.get('spec', {})
        spec_summary = detail_spec.get('spec_summary', [])

        for item in spec_summary:
            item_lower = str(item).lower()

            if 'kg' in item_lower and not specs['weight']:
                specs['weight'] = str(item)
            elif ('cm' in item_lower or '인치' in item_lower) and not specs['display']:
                specs['display'] = str(item)
            elif '램' in item_lower or 'ram' in item_lower:
                if ':' in str(item):
                    specs['ram'] = str(item).split(':')[-1].strip()
                else:
                    specs['ram'] = str(item)
            elif 'tb' in item_lower or 'ssd' in item_lower:
                if ':' in str(item):
                    specs['storage'] = str(item).split(':')[-1].strip()
                else:
                    specs['storage'] = str(item)

        for key, value in spec_data.items():
            key_lower = key.lower()

            if ('코어' in key_lower or 'core' in key_lower or
                'i7' in key_lower or 'i5' in key_lower or 'i9' in key_lower or
                'ryzen' in key_lower or '울트라' in key_lower):
                if not specs['cpu']:
                    specs['cpu'] = key if value is True else str(value)
            elif ('rtx' in key_lower or 'gtx' in key_lower or
                  '지포스' in key_lower or 'radeon' in key_lower):
                if not specs['gpu']:
                    specs['gpu'] = key if value is True else str(value)
            elif '배터리' in key_lower or 'wh' in key_lower:
                if not specs['battery']:
                    specs['battery'] = key if value is True else str(value)
            elif '[구성]램' in key:
                if not specs['ram']:
                    specs['ram'] = str(value)
            elif '용량' in key:
                if not specs['storage']:
                    specs['storage'] = str(value)

        return specs
    '''
    def _generate_recommendation_reason(
        self,
        user_query: str,
        user_needs: str,
        product_name: str,
        brand: str,
        price: int,
        specs: Dict[str, Optional[str]]
    ) -> str:
        """Generate recommendation reason using Gemini."""
        spec_items = []
        for key, value in specs.items():
            if value:
                spec_items.append(f"{key}: {value}")
        specs_str = ', '.join(spec_items) if spec_items else '정보 없음'

        prompt = RECOMMENDATION_REASON_PROMPT.format(
            user_query=user_query,
            user_needs=user_needs,
            product_name=product_name,
            brand=brand,
            price=price,
            specs=specs_str
        )

        try:
            response = self.gemini_client.generate_content(prompt)
            return response.strip()
        except Exception as e:
            logger.warning(f"Recommendation reason generation failed: {e}")
            return f"{brand}의 {product_name}은(는) 사용자의 요구사항에 적합한 제품입니다."

    def _generate_ai_review_summary(
        self,
        product_name: str,
        brand: str,
        price: int,
        specs: Dict[str, Optional[str]],
        user_needs: str
    ) -> str:
        """Generate AI review summary using Gemini."""
        spec_items = []
        for key, value in specs.items():
            if value:
                spec_items.append(f"{key}: {value}")
        specs_str = ', '.join(spec_items) if spec_items else '정보 없음'

        prompt = AI_REVIEW_SUMMARY_PROMPT.format(
            product_name=product_name,
            brand=brand,
            price=price,
            specs=specs_str,
            user_needs=user_needs
        )

        try:
            response = self.gemini_client.generate_content(prompt)
            return response.strip()
        except Exception as e:
            logger.warning(f"AI review summary generation failed: {e}")
            return f"{product_name}은(는) 우수한 성능과 가성비를 제공합니다."

    def _calculate_performance_score(
        self,
        product: ProductModel,
        combined_score: float
    ) -> float:
        """
        Calculate performance score (0.0 - 1.0).

        Combines similarity score, review rating, and review count.
        """
        # Base score from similarity (0.0 - 1.0)
        base_score = combined_score

        # Review rating contribution (0 - 5 -> 0.0 - 0.2)
        rating_score = (product.review_rating or 0) / 25  # max 0.2

        # Review count contribution (normalized, max 0.1)
        review_score = min(product.review_count / 1000, 0.1)

        # Combined performance score (capped at 1.0)
        performance = min(1.0, base_score * 0.7 + rating_score + review_score)

        return performance
