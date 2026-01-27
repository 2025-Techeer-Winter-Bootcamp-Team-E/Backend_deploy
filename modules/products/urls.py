from django.urls import path
from .views import (
    ProductListView,
    ProductPriceTrendView,
    ProductDetailView,
    ProductMallInfoView,
    ProductReviewListView,
    ProductAIReviewSummaryView,
    ProductAIReviewGenerateView,
)

urlpatterns = [
    # 상품 목록 조회 및 검색 (루트 경로)
    path('', ProductListView.as_view(), name='product-list'),
    # 기존 URL들
    path('<str:product_code>/price-trend/', ProductPriceTrendView.as_view(), name='product-price-trend'),
    path('<str:product_code>/', ProductDetailView.as_view(), name='product_detail'),
    path('<str:product_code>/prices/', ProductMallInfoView.as_view(), name='product-mall_info'),
    # AI 리뷰 요약 (reviews/ 보다 먼저 배치)
    path('<str:product_code>/reviews/summary/generate/', ProductAIReviewGenerateView.as_view(), name='product-ai-review-generate'),
    path('<str:product_code>/reviews/summary/', ProductAIReviewSummaryView.as_view(), name='product-ai-review-summary'),
    path('<str:product_code>/reviews/', ProductReviewListView.as_view(), name='product-review-list'),
]

