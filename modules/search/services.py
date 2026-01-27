"""
Search business logic services.
"""
import logging
from typing import List, Optional

from django.db.models import Count
from django.utils import timezone

from .models import SearchModel, RecentViewProductModel

logger = logging.getLogger(__name__)


class SearchService:
    """Service for search operations."""

    def search_products(
        self,
        query: str,
        search_mode: str = 'basic',
        user_id: int = None,
        danawa_product_id: str = '',
    ) -> dict:
        """
        Search products.

        Args:
            query: Search query string
            search_mode: 'basic', 'llm', or 'shopping_research'
            user_id: User ID for history tracking
            danawa_product_id: Danawa product ID if applicable
        """
        from modules.products.services import ProductService
        from modules.products.serializers import ProductListSerializer
        product_service = ProductService()

        # Perform search
        product_results = product_service.search_products(query, limit=20)

        # Serialize results
        serializer = ProductListSerializer(product_results, many=True)
        results = serializer.data

        # Record search history if user is logged in
        if user_id:
            self.record_search(
                user_id=user_id,
                query=query,
                search_mode=search_mode,
                danawa_product_id=danawa_product_id,
            )

        return {
            'results': results,
            'total': len(results),
            'query': query,
            'search_mode': search_mode
        }

    def record_search(
        self,
        user_id: int,
        query: str,
        search_mode: str,
        danawa_product_id: str = '',
    ) -> SearchModel:
        """Record search in history."""
        return SearchModel.objects.create(
            user_id=user_id,
            query=query,
            search_mode=search_mode,
            searched_at=timezone.now(),
            danawa_product_id=danawa_product_id,
        )

    def get_user_search_history(
        self,
        user_id: int,
        limit: int = 20
    ) -> List[SearchModel]:
        """Get user's recent search history."""
        return list(
            SearchModel.objects.filter(
                user_id=user_id,
                deleted_at__isnull=True
            ).order_by('-searched_at')[:limit]
        )

    def get_autocomplete_suggestions(self, keyword: str, limit: int = 5) -> List[str]:
        """
        사용자가 입력 중인 키워드와 관련된 추천 검색어 리스트를 반환합니다. 
        """
        
        # 데이터로 테스트 완료
        # #mock_data = [
        #     # '삼성' 관련
        #     "삼성전자 DDR5 16GB",
        #     "삼성전자 오디세이 G5",
        #     "삼성 갤럭시 S24",
        #     "갤럭시 S25",
        #     # 'RTX' 관련
        #     "NVIDIA RTX 4070 SUPER",
        #     "NVIDIA RTX 4080",
        #     "NVIDIA RTX 4090",
        #     # '인텔' 관련
        #     "인텔 코어 i7-14700K",
        #     "인텔 코어 i9-14900K",
        #     # 'LG' 관련
        #     "LG 울트라기어 모니터",
        #     "LG 그램 16"
        # ]
        if not keyword or len(keyword) < 2:  # 최소 2자 이상일 때만 검색 (Serializer 기준 준수)
            return []

        # 1. SearchModel에서 query 필드에 keyword가 포함된 항목 조회
        # 2. 삭제되지 않은(deleted_at__isnull=True) 항목만 필터링
        # 3. 중복 제거(distinct) 후 최신순 혹은 알파벳순으로 정렬하여 제한된 개수만큼 반환
        suggestions = SearchModel.objects.filter(
            query__icontains=keyword,
            deleted_at__isnull=True
        ).values_list('query', flat=True).distinct()[:limit]
        # 4. Mock 데이터에서 키워드가 포함된 것만 필터링해서 반환
    
        #results = [item for item in mock_data if keyword.lower() in item.lower()]
    
        # SearchService 내부
        #return {"suggestions": results[:limit]}
        return list(suggestions)
    
    def get_popular_terms(self, limit: int = 10):
        """
        가장 많이 검색된 상위 키워드 리스트를 반환합니다.
        """
        # 1. query별로 개수를 세고(Count), 내림차순 정렬
        popular_data = SearchModel.objects.filter(deleted_at__isnull=True) \
            .values('query') \
            .annotate(count=Count('query')) \
            .order_by('-count')[:limit] 

        return [
            {"rank": i + 1, "term": item['query']}
            for i, item in enumerate(popular_data)
        ]
    
    

class RecentViewProductService:
    """Service for recent view product operations."""

    def record_view(
        self,
        user_id: int,
        danawa_product_id: str,
    ) -> RecentViewProductModel:
        """Record a product view."""
        recent_view, created = RecentViewProductModel.objects.get_or_create(
            user_id=user_id,
            danawa_product_id=danawa_product_id,
        )

        if not created:
            recent_view.save()  # Update updated_at

        return recent_view

    def get_user_recent_views(
        self,
        user_id: int,
        limit: int = 20
    ) -> List[RecentViewProductModel]:
        """Get user's recently viewed products."""
        return list(
            RecentViewProductModel.objects.filter(
                user_id=user_id,
                deleted_at__isnull=True
            ).order_by('-updated_at')[:limit]
        )

    def delete_recent_view(
        self,
        user_id: int,
        danawa_product_id: str,
    ) -> bool:
        """Delete a recent view (soft delete)."""
        try:
            recent_view = RecentViewProductModel.objects.get(
                user_id=user_id,
                danawa_product_id=danawa_product_id,
                deleted_at__isnull=True
            )
            recent_view.deleted_at = datetime.now()
            recent_view.save()
            return True
        except RecentViewProductModel.DoesNotExist:
            return False
