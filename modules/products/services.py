"""
Products module service layer.
"""
from datetime import datetime
from typing import Optional, List
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db import models
from django.db.models import Q, Avg, Count
from modules.timers.models import PriceHistoryModel
from modules.orders.models import ReviewModel
from .models import ProductModel, MallInformationModel
from .exceptions import (
    ProductNotFoundError,
)
import math


class ProductService:
    """
    Product business logic service.
    """

    def get_product_by_id(self, product_id: int) -> Optional[ProductModel]:
        """Get product by ID."""
        try:
            return ProductModel.objects.get(id=product_id, deleted_at__isnull=True)
        except ProductModel.DoesNotExist:
            return None
    #이용자 서비스 용 get(product_code기반 호출)
    def get_product_by_code(self, product_code: str) -> Optional[ProductModel]:
        """Get product by Danawa product ID."""
        try:
            return ProductModel.objects.get(danawa_product_id=product_code, deleted_at__isnull=True)
        except ProductModel.DoesNotExist:
            return None

    def get_products_by_ids(self, product_ids: List[int]) -> List[ProductModel]:
        """Get multiple products by IDs."""
        return list(ProductModel.objects.filter(id__in=product_ids, deleted_at__isnull=True))

    def get_all_products(
        self,
        category_id: int = None,
        offset: int = 0,
        limit: int = 20,
    ) -> List[ProductModel]:
        """Get all active products."""
        queryset = ProductModel.objects.filter(deleted_at__isnull=True)
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return list(queryset.order_by('-created_at')[offset:offset + limit])

    def search_products(
        self,
        query: str,
        category_id: int = None,
        limit: int = 20,
    ) -> List[ProductModel]:
        """
        Search products by name, brand, or specifications.

        Args:
            query: Search query string
            category_id: Optional category filter
            limit: Maximum number of results

        Returns:
            List of matching ProductModel instances
        """
        if not query or len(query.strip()) < 1:
            return []

        query = query.strip()

        # Build search filter using Q objects
        search_filter = Q(deleted_at__isnull=True) & (
            Q(name__icontains=query) |
            Q(brand__icontains=query)
        )

        # Add category filter if provided
        if category_id:
            search_filter &= Q(category_id=category_id)

        # Execute search query
        results = ProductModel.objects.filter(search_filter).order_by(
            '-review_count',  # Popular products first
            '-created_at'
        )[:limit]

        return list(results)

    def search_by_embedding(
        self,
        embedding: List[float],
        limit: int = 10,
    ) -> List[ProductModel]:
        """Search products by semantic similarity using pgvector."""
        from pgvector.django import L2Distance

        return list(
            ProductModel.objects
            .filter(deleted_at__isnull=True, detail_spec_vector__isnull=False)
            .order_by(L2Distance('detail_spec_vector', embedding))[:limit]
        )

    def create_product(
        self,
        danawa_product_id: str,
        name: str,
        lowest_price: int,
        brand: str,
        detail_spec: dict = None,
        category_id: int = None,
        registration_month: str = None,
        product_status: str = None,
    ) -> ProductModel:
        """Create a new product."""
        product = ProductModel.objects.create(
            danawa_product_id=danawa_product_id,
            name=name,
            lowest_price=lowest_price,
            brand=brand,
            detail_spec=detail_spec or {},
            category_id=category_id,
            registration_month=registration_month,
            product_status=product_status,
        )
        return product

    def update_product(
        self,
        product_id: int,
        **kwargs
    ) -> ProductModel:
        """Update product information."""
        product = self.get_product_by_id(product_id)
        if not product:
            raise ProductNotFoundError(str(product_id))

        for key, value in kwargs.items():
            if hasattr(product, key) and value is not None:
                setattr(product, key, value)

        product.save()
        return product

    def delete_product(self, product_id: int) -> bool:
        """Soft delete a product."""
        product = self.get_product_by_id(product_id)
        if not product:
            return False

        product.deleted_at = datetime.now()
        product.save()
        return True

    def get_products_with_filters(
        self,
        query: str = None,
        main_cat: str = None,
        sub_cat: str = None,
        brand: str = None,
        min_price: int = None,
        max_price: int = None,
        sort: str = None,
        page: int = 1,
        page_size: int = 10,
    ) -> dict:
        """
        다중 조건 필터링 및 검색 기능이 포함된 상품 목록 조회.
        """
        from modules.categories.models import CategoryModel
        from django.db.models import Prefetch, Q
        import math

        queryset = ProductModel.objects.filter(deleted_at__isnull=True)

        # 1. 검색어 필터 (query)
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(brand__icontains=query)
            )

        # 2 & 3. 카테고리 필터 통합 (이름 매칭 대신 ID 직접 사용)
        target_id = sub_cat if sub_cat else main_cat

        if target_id:
            try:
                # 1. ID값을 숫자로 변환 후, 하위 카테고리 ID들을 싹 가져옴
                category_ids = self._get_descendant_category_ids(int(target_id))
                # 2. 해당 카테고리들에 속한 상품들만 필터링
                queryset = queryset.filter(category_id__in=category_ids)
            except (ValueError, TypeError):
                # ID가 숫자가 아니거나 잘못된 값일 경우 필터링 수행 안 함
                pass

        # 4. 브랜드 필터 (brand)
        if brand:
            queryset = queryset.filter(brand__icontains=brand)

        # 5. 가격 범위 필터 (min_price, max_price)
        if min_price is not None:
            queryset = queryset.filter(lowest_price__gte=min_price)
        if max_price is not None:
            queryset = queryset.filter(lowest_price__lte=max_price)

        # 6. 정렬 (sort)
        if sort == 'price_low':
            queryset = queryset.order_by('lowest_price')
        elif sort == 'price_high':
            queryset = queryset.order_by('-lowest_price')
        elif sort == 'popular':
            queryset = queryset.order_by('-review_count', '-review_rating')
        else:
            queryset = queryset.order_by('-created_at')

        # 7. 전체 개수 계산
        total_count = queryset.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

        # 8. N+1 쿼리 방지를 위한 prefetch
        queryset = queryset.select_related('category').prefetch_related(
            Prefetch(
                'mall_information',
                queryset=MallInformationModel.objects.filter(deleted_at__isnull=True)
            )
        )

        # 9. 페이지네이션 적용
        offset = (page - 1) * page_size
        products = list(queryset[offset:offset + page_size])

        return {
            'products': products,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages
        }

    def _get_descendant_category_ids(self, category_id: int) -> list:
        """
        특정 카테고리의 모든 하위 카테고리 ID를 재귀적으로 수집.

        Args:
            category_id: 시작 카테고리 ID

        Returns:
            list: 해당 카테고리 및 모든 하위 카테고리 ID 목록
        """
        from modules.categories.models import CategoryModel

        ids = [category_id]
        children = CategoryModel.objects.filter(
            parent_id=category_id,
            deleted_at__isnull=True
        )
        for child in children:
            ids.extend(self._get_descendant_category_ids(child.id))
        return ids

    def get_price_trend_data(self, product: ProductModel, months: int = 6): #views.py에서 탐색 기간 설정 조작가능
        start_date = timezone.now() - relativedelta(months=months)

        # 2. 필터 조건에 '날짜' 추가 (start_date 이후 데이터만!)
        histories = PriceHistoryModel.objects.filter(
            danawa_product_id=product.danawa_product_id,
            recorded_at__gte=start_date, # 탐색 기간 설정 로직
            deleted_at__isnull=True
        ).order_by('recorded_at')
        
        return {
            "product_code": product.danawa_product_id,
            "product_name": product.name,
            "period_unit": "month",
            "selected_period": months,
            "price_history": histories
        }
    def get_product_reviews(product_code, page=1, size=5):

        if not ProductModel.objects.filter(danawa_product_id=product_code).exists():
            return None
        
        queryset = ReviewModel.objects.filter(
            danawa_product_id=product_code,
            deleted_at__isnull=True
        )
    
        stats = queryset.aggregate(
            total_elements=models.Count('id'),
            average_rating=Avg('rating')
        )
        
        total_elements = stats['total_elements'] or 0
        average_rating = round(stats['average_rating'] or 0.0, 1) #평점 없을 경우 0점
        start = (page - 1) * size
        end = start + size
        reviews = queryset.all()[start:end] 

        total_pages = math.ceil(total_elements / size) if total_elements > 0 else 0
        has_next = page < total_pages
        
        return {
            "pagination": {
                "current_page": page,
                "size": size,
                "total_elements": total_elements,
                "total_pages": total_pages
            },
            "average_rating": average_rating,
            "reviews": reviews,
            "has_next": has_next
        }

    def get_ai_review_summary(self, product_code: str):
        """
        상품의 AI 리뷰 분석 결과를 조회합니다.

        Args:
            product_code: 다나와 상품 코드

        Returns:
            ProductAIReviewAnalysisModel 인스턴스 또는 None
        """
        from .models import ProductAIReviewAnalysisModel

        try:
            return ProductAIReviewAnalysisModel.objects.select_related('product').get(
                product__danawa_product_id=product_code,
                deleted_at__isnull=True
            )
        except ProductAIReviewAnalysisModel.DoesNotExist:
            return None

    def generate_ai_review_analysis(self, product_code: str):
        """
        Gemini를 사용하여 상품의 AI 리뷰 분석을 생성합니다.

        Args:
            product_code: 다나와 상품 코드

        Returns:
            ProductAIReviewAnalysisModel 인스턴스 또는 None
        """
        import json
        from .models import ProductAIReviewAnalysisModel
        from shared.ai_clients import get_gemini_client

        # 1. 상품 정보 조회
        product = self.get_product_by_code(product_code)
        if not product:
            return None

        # 2. 리뷰 데이터 조회
        reviews_data = ProductService.get_product_reviews(product_code, page=1, size=50)
        reviews = reviews_data.get('reviews', []) if reviews_data else []
        # ProductModel의 review_count 사용 (DB에 저장된 총 리뷰 수)
        review_count = product.review_count if product.review_count else 0

        # 3. Gemini 프롬프트 생성
        product_info = f"""
상품명: {product.name}
브랜드: {product.brand}
가격: {product.lowest_price:,}원
카테고리: {product.category.name if product.category else '미분류'}
스펙: {json.dumps(product.detail_spec, ensure_ascii=False) if product.detail_spec else '정보 없음'}
"""

        review_texts = ""
        if reviews:
            for i, review in enumerate(reviews[:20], 1):
                review_texts += f"\n리뷰 {i}: (평점: {review.rating}/5) {review.content[:200]}"
        else:
            review_texts = "\n(리뷰 데이터 없음 - 상품 정보 기반으로 분석)"

        prompt = f"""
다음 상품에 대한 리뷰 분석을 수행해주세요.

{product_info}

리뷰 데이터:
{review_texts}

반드시 아래 JSON 형식으로만 응답해주세요. 다른 텍스트는 포함하지 마세요:
{{
    "ai_summary": "상품에 대한 전체적인 요약 (2-3문장)",
    "pros": ["장점1", "장점2", "장점3"],
    "cons": ["단점1", "단점2"],
    "recommendation_score": 85,
    "score_reason": "추천 점수에 대한 근거 설명 (1-2문장)"
}}
"""

        try:
            # 4. Gemini API 호출
            gemini_client = get_gemini_client()
            response_text = gemini_client.generate_content(prompt)

            # 5. JSON 파싱
            # JSON 블록 추출
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            analysis_result = json.loads(response_text.strip())

            # 6. 기존 분석 결과가 있으면 업데이트, 없으면 생성
            ai_analysis, created = ProductAIReviewAnalysisModel.objects.update_or_create(
                product=product,
                defaults={
                    'ai_review_summary': analysis_result.get('ai_summary', ''),
                    'ai_positive_review_analysis': analysis_result.get('pros', []),
                    'ai_negative_review_analysis': analysis_result.get('cons', []),
                    'ai_recommendation_score': analysis_result.get('recommendation_score', 0),
                    'ai_review_analysis_basis': analysis_result.get('score_reason', ''),
                    'analyzed_review_count': review_count,
                    'deleted_at': None,
                }
            )

            return ai_analysis

        except Exception as e:
            print(f"AI 분석 생성 오류: {e}")
            return None

    def generate_ai_reviews_for_all_products_with_reviews(self):
        """
        리뷰가 있는 모든 상품에 대해 AI 리뷰 분석을 생성합니다.

        Returns:
            dict: {
                'success_count': int,
                'failed_count': int,
                'skipped_count': int,
                'results': list
            }
        """
        import time
        from .models import ProductAIReviewAnalysisModel

        # 리뷰가 있는 상품 조회 (review_count > 0)
        products_with_reviews = ProductModel.objects.filter(
            deleted_at__isnull=True,
            review_count__gt=0
        ).order_by('-review_count')

        results = {
            'success_count': 0,
            'failed_count': 0,
            'skipped_count': 0,
            'results': []
        }

        total = products_with_reviews.count()
        print(f"총 {total}개의 상품에 대해 AI 리뷰 분석을 생성합니다...")

        for i, product in enumerate(products_with_reviews, 1):
            product_code = product.danawa_product_id

            # 이미 분석 결과가 있는지 확인
            existing = ProductAIReviewAnalysisModel.objects.filter(
                product=product,
                deleted_at__isnull=True
            ).exists()

            if existing:
                results['skipped_count'] += 1
                results['results'].append({
                    'product_code': product_code,
                    'product_name': product.name,
                    'status': 'skipped',
                    'message': '이미 분석 결과가 존재합니다.'
                })
                print(f"[{i}/{total}] {product_code} - 건너뜀 (이미 존재)")
                continue

            try:
                ai_review = self.generate_ai_review_analysis(product_code)
                if ai_review:
                    results['success_count'] += 1
                    results['results'].append({
                        'product_code': product_code,
                        'product_name': product.name,
                        'status': 'success',
                        'recommendation_score': ai_review.ai_recommendation_score
                    })
                    print(f"[{i}/{total}] {product_code} - 성공 (추천점수: {ai_review.ai_recommendation_score})")
                else:
                    results['failed_count'] += 1
                    results['results'].append({
                        'product_code': product_code,
                        'product_name': product.name,
                        'status': 'failed',
                        'message': '생성 실패'
                    })
                    print(f"[{i}/{total}] {product_code} - 실패")

                # API 호출 간격 조절 (rate limit 방지)
                time.sleep(1)

            except Exception as e:
                results['failed_count'] += 1
                results['results'].append({
                    'product_code': product_code,
                    'product_name': product.name,
                    'status': 'failed',
                    'message': str(e)
                })
                print(f"[{i}/{total}] {product_code} - 오류: {e}")

        print(f"\n완료! 성공: {results['success_count']}, 실패: {results['failed_count']}, 건너뜀: {results['skipped_count']}")
        return results


class MallInformationService:
    """
    Mall information business logic service.
    """
    def get_mall_info_by_code(self, product_code: str) -> List[MallInformationModel]:
        """제품 코드(danawa_product_id)를 사용하여 판매처 정보를 조회합니다."""
        return list(
            MallInformationModel.objects.filter(
                product__danawa_product_id=product_code, # PK가 아닌 코드로 필터링
                deleted_at__isnull=True
            ).order_by('current_price')
        )

    def create_mall_info(
        self,
        product_id: int,
        mall_name: str,
        current_price: int,
        product_page_url: str = None,
        seller_logo_url: str = None,
        representative_image_url: str = None,
        additional_image_urls: list = None,
    ) -> MallInformationModel:
        """Create mall information."""
        return MallInformationModel.objects.create(
            product_id=product_id,
            mall_name=mall_name,
            current_price=current_price,
            product_page_url=product_page_url,
            seller_logo_url=seller_logo_url,
            representative_image_url=representative_image_url,
            additional_image_urls=additional_image_urls or [],
        )

    def update_mall_price(
        self,
        mall_info_id: int,
        current_price: int,
    ) -> MallInformationModel:
        """Update mall price."""
        try:
            mall_info = MallInformationModel.objects.get(
                id=mall_info_id,
                deleted_at__isnull=True
            )
            mall_info.current_price = current_price
            mall_info.save()
            return mall_info
        except MallInformationModel.DoesNotExist:
            return None

