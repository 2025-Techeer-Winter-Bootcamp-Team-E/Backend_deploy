import json
import logging
import re
import concurrent.futures
from typing import List, Dict, Any, Optional

from django.db.models import F
from django.contrib.postgres.search import TrigramSimilarity
from pgvector.django import L2Distance

from modules.products.models import ProductModel, MallInformationModel
from modules.categories.models import CategoryModel
from shared.ai_clients import get_openai_client, get_gemini_client
from .prompts import INTENT_EXTRACTION_PROMPT, COMBINED_RECOMMENDATION_PROMPT

logger = logging.getLogger(__name__)

class LLMRecommendationService:
    """
    ShoppingResearchService의 강력한 카테고리 필터링 로직을 이식한 완성형 서비스
    - TrigramSimilarity를 이용한 오차 없는 카테고리 ID 매핑
    - 재귀적 하위 카테고리 수집을 통한 계층 검색 지원
    - 카테고리 불일치 시 검색 원천 차단 (Safety Lock)
    """

    TOP_K = 5
    MIN_CAT_SIMILARITY = 0.3  # 카테고리 매칭 최소 유사도

    def __init__(self):
        self.openai_client = get_openai_client()
        self.gemini_client = get_gemini_client()
        
        # 프롬프트 힌트용 카테고리 명칭 로드
        cat_names = CategoryModel.objects.filter(deleted_at__isnull=True).values_list('name', flat=True)
        self._category_list_str = ", ".join(cat_names)

    def get_recommendations(self, user_query: str) -> Dict[str, Any]:
    # 1. 의도 추출 실행
        intent = self._extract_intent_pro(user_query)
        
        llm_category_name = intent.get('product_category', '기타').strip()
        category_id = None
        
        # [보완] 키워드 기반 카테고리 ID 강제 고정 (CPU와 노트북 혼선 방지)
        # categories.json의 실제 PK 값을 사용합니다.
        upper_query = user_query.upper()
        if "CPU" in upper_query or "프로세서" in upper_query:
            category_id = 21  # CPU 카테고리 PK
            llm_category_name = "CPU"
        elif "그래픽카드" in upper_query or "GPU" in upper_query:
            category_id = 24  # 그래픽카드 카테고리 PK
            llm_category_name = "그래픽카드"
        elif "모니터" in upper_query:
            category_id = 18  # 모니터 카테고리 PK
            llm_category_name = "모니터"
        elif "노트북" in upper_query:
            category_id = 2   # 노트북 카테고리 PK
            llm_category_name = "노트북"

        # [LOG] 최종 결정된 카테고리 출력
        logger.info(f"==== [STEP 1] LLM Intent Extraction ====")
        logger.info(f"User Query: {user_query}")
        logger.info(f"Fixed/LLM Category: {llm_category_name} (ID: {category_id})")

        # 2. 카테고리 매핑 로직 (위에서 ID가 고정되지 않은 경우에만 실행)
        if not category_id and llm_category_name and llm_category_name != '기타':
            logger.info(f"==== [STEP 2] Category Fuzzy Mapping ====")
            # 완전 일치 확인
            exact_match = CategoryModel.objects.filter(
                name=llm_category_name, 
                deleted_at__isnull=True
            ).first()
            
            if exact_match:
                category_id = exact_match.id
            else:
                # Trigram 유사도 확인
                best_match = CategoryModel.objects.annotate(
                    similarity=TrigramSimilarity('name', llm_category_name)
                ).filter(similarity__gt=self.MIN_CAT_SIMILARITY).order_by('-similarity').first()

                if best_match:
                    category_id = best_match.id

        # 3. 최종 검색 범위 설정 (재귀적으로 하위 카테고리 포함)
        # CPU(21)를 선택하면 인텔(23), AMD(22)가 자동으로 포함됩니다.
        target_category_ids = self._get_descendant_category_ids(category_id) if category_id else []
        logger.info(f"Final Category IDs for Filter: {target_category_ids}")
        
        # 4. 병렬 DB 검색 (target_category_ids가 비어있지 않으면 강력한 필터링 작동)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f_vec = executor.submit(self._vector_search, intent.get('search_query', user_query), target_category_ids)
            f_key = executor.submit(self._keyword_search, intent.get('keywords', [user_query]), target_category_ids)
            vector_results, keyword_results = f_vec.result(), f_key.result()

        # 5. 하이브리드 결합 및 재랭킹 (이후 로직 동일)
        fused_results = self._fuse_results(vector_results, keyword_results)[:8]

        if not fused_results:
            return {
                "analysis_message": f"'{llm_category_name}' 카테고리에서 조건에 맞는 상품을 찾지 못했습니다.",
                "recommended_products": []
            }

        final_products = self._rerank_with_fallback(user_query, intent, fused_results)

        return {
            "analysis_message": intent.get('analysis_message', f"{llm_category_name} 추천 결과입니다."),
            "recommended_products": final_products
        }

    def _get_descendant_category_ids(self, category_id: int) -> List[int]:
        """[ShoppingResearchService 이식] 자식 카테고리 ID를 재귀적으로 모두 수집"""
        ids = [category_id]
        children = CategoryModel.objects.filter(parent_id=category_id, deleted_at__isnull=True)
        for child in children:
            ids.extend(self._get_descendant_category_ids(child.id)) #
        return ids

    def _extract_intent_pro(self, user_query: str) -> Dict[str, Any]:
        """LLM의 날것(Raw) 그대로의 답변을 로깅합니다."""
        full_prompt = INTENT_EXTRACTION_PROMPT.format(
            category_list=self._category_list_str, 
            user_query=user_query
        )
        
        try:
            resp = self.gemini_client.generate_content(full_prompt)
            
            # [LOG] LLM의 Raw Response 출력 (파싱 전)
            logger.debug(f"==== [DEBUG] LLM Raw Response ====")
            logger.debug(resp.text)
            
            text = re.sub(r'```json\s*|```', '', resp.text)
            match = re.search(r'\{[\s\S]*\}', text)
            
            if match:
                res = json.loads(match.group())
                return res
            else:
                logger.error("Failed to find JSON block in LLM response")
                return {"product_category": "기타"}
        except Exception as e:
            logger.error(f"Intent Extraction Error: {str(e)}")
            return {"product_category": "기타"}

    def _vector_search(self, query, category_ids):
        """벡터 검색 시 카테고리 필터 강제 적용"""
        embedding = self.openai_client.create_embedding(query)
        qs = ProductModel.objects.filter(deleted_at__isnull=True, detail_spec_vector__isnull=False)
        
        # [Safety Lock] 카테고리 ID 리스트가 있으면 강력하게 필터링
        if category_ids:
            qs = qs.filter(category_id__in=category_ids) #
        elif any(k in query for k in ["CPU", "노트북", "그래픽카드"]):
            # 카테고리가 안 잡혔는데 주요 하드웨어를 물어본 경우, 사고 방지를 위해 검색 안함
            return []

        products = qs.exclude(product_status__in=['단종', '판매중지', '품절']).annotate(
            distance=L2Distance('detail_spec_vector', embedding)
        ).order_by('distance')[:20]
        
        p_list = list(products)
        mall_map = self._get_mall_map([p.id for p in p_list])
        return [{'product': p, 'mall_info': mall_map.get(p.id), 'score': max(0, 1-(p.distance/2))} for p in p_list]

    # modules/search/services/llm_service.py

    def _rerank_with_fallback(self, user_query, intent, fused_results):
        candidates = []
        for item in fused_results:
            p = item['product']
            spec = self._parse_specs_to_string(p.detail_spec)
            candidates.append(f"- ID:{p.danawa_product_id} | 품명:{p.name} | 스펙:{spec}")
        
        prompt = COMBINED_RECOMMENDATION_PROMPT.format(
            user_query=user_query,
            user_needs=intent.get('user_needs', user_query),
            product_category=intent.get('product_category', '상품'),
            product_list="\n".join(candidates)
        )

        reason_map = {}
        try:
            resp = self.gemini_client.generate_content(prompt)
            # [수정] 1. 응답 텍스트를 안전하게 가져옴
            raw_text = resp.text if hasattr(resp, 'text') else str(resp)
            
            # [수정] 2. JSON 코드 블록(```json) 및 불필요한 줄바꿈 제거
            clean_text = re.sub(r'```(?:json)?', '', raw_text).strip()
            # [수정] 3. 가장 바깥쪽 { } 괄호 안의 내용만 정확히 추출
            json_match = re.search(r'\{[\s\S]*\}', clean_text)
            
            if json_match:
                data = json.loads(json_match.group())
                results = data.get('results', [])
                for r in results:
                    # [수정] 4. ID 매칭 시 문자열/숫자 차이 방지를 위해 str() 처리
                    p_code = str(r.get('product_code'))
                    reason_map[p_code] = r.get('recommendation_reason')
                
                logger.info(f"✅ [REASONING] Successfully parsed {len(reason_map)} product reasons.")
            else:
                logger.warning(f"⚠️ [PARSING FAILED] No JSON block found in: {raw_text[:100]}...")

        except Exception as e:
            logger.error(f"❌ [RERANK ERROR] {str(e)}")

        final = []
        for item in fused_results[:self.TOP_K]:
            p = item['product']
            p_id = str(p.danawa_product_id)
            
            # 매칭된 사유가 있으면 사용, 없으면 Fallback 생성 함수 사용
            final_reason = reason_map.get(p_id) or self._generate_fallback_reason(p)
            
            final.append({
                'product_code': p.danawa_product_id,
                'name': p.name,
                'brand': p.brand,
                'price': p.lowest_price,
                'thumbnail_url': item['mall_info'].representative_image_url if item['mall_info'] else None,
                'recommendation_reason': final_reason,
                'specs': p.detail_spec.get('spec', {}) if isinstance(p.detail_spec, dict) else {},
                'review_count': p.review_count,
                'review_rating': p.review_rating,
            })
        return final

    def _parse_specs_to_string(self, detail_spec):
        """ 스펙 데이터를 텍스트 요약"""
        if not detail_spec: return "정보 없음"
        if isinstance(detail_spec, dict) and 'spec_summary' in detail_spec:
            return " | ".join(map(str, detail_spec['spec_summary']))
        return str(detail_spec)[:150]

    def _generate_fallback_reason(self, p):
        return f"{p.brand}의 신뢰도 높은 모델로, 사용자의 요구 성능을 충실히 만족하는 제품입니다."

    def _keyword_search(self, keywords, category_ids):
        if not keywords: return []
        qs = ProductModel.objects.filter(deleted_at__isnull=True)
        if category_ids:
            qs = qs.filter(category_id__in=category_ids) #
        qs = qs.annotate(sim=TrigramSimilarity('name', ' '.join(keywords))).filter(sim__gt=0.05).order_by('-sim')[:20]
        p_list = list(qs)
        mall_map = self._get_mall_map([p.id for p in p_list])
        return [{'product': p, 'mall_info': mall_map.get(p.id), 'score': float(p.sim)} for p in p_list]

    def _fuse_results(self, vec, key):
        res = {i['product'].danawa_product_id: i for i in vec}
        for i in key:
            pid = i['product'].danawa_product_id
            if pid in res: res[pid]['score'] = res[pid]['score'] * 0.7 + i['score'] * 0.3
            else: res[pid] = i
        return sorted(res.values(), key=lambda x: x['score'], reverse=True)

    def _get_mall_map(self, ids):
        mall_infos = MallInformationModel.objects.filter(product_id__in=ids, deleted_at__isnull=True).order_by('product_id', '-created_at').distinct('product_id')
        return {mi.product_id: mi for mi in mall_infos}