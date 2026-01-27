"""
Search URL configuration.
"""
from django.urls import path
from .views import (
    SearchView,
    SearchHistoryView,
    RecentViewProductsView,
    RecentViewProductDeleteView,
    AutocompleteView,
    PopularSearchView,
    RecentSearchView,
    LLMRecommendationView,
    QuestionsView,
    ShoppingResearchView,
)
app_name = 'search'

urlpatterns = [
    path('', SearchView.as_view(), name='search'),
    path('history/', SearchHistoryView.as_view(), name='search-history'),
    path('recent-views/', RecentViewProductsView.as_view(), name='recent-views'),
    path('recent-views/<str:danawa_product_id>/', RecentViewProductDeleteView.as_view(), name='recent-view-delete'),

    # 검색어 자동완성
    path('autocomplete/', AutocompleteView.as_view(), name='autocomplete'),
    path('popular/', PopularSearchView.as_view(), name='popular-search'),

    path('recent/', RecentSearchView.as_view(), name='search-recent'),

    # LLM 기반 상품 추천 검색
    path('llm-recommendation/', LLMRecommendationView.as_view(), name='llm-recommendation'),

    # 쇼핑 리서치 API (2단계 대화형 추천)
    path('questions/', QuestionsView.as_view(), name='shopping-research-questions'),
    path('shopping-research/', ShoppingResearchView.as_view(), name='shopping-research'),
]