"""
Categories URL configuration.
"""
from django.urls import path

from .views import (
    CategoryListCreateView,
    CategoryDetailView,
    CategoryTreeView,
    CategorySubcategoriesView,
    ProductFilterCategoriesView,
)

app_name = 'categories'

urlpatterns = [
    path('', CategoryListCreateView.as_view(), name='category-list-create'),
    path('tree/', CategoryTreeView.as_view(), name='category-tree'),
    path('filter/', ProductFilterCategoriesView.as_view(), name='product-filter-categories'),
    path('<int:category_id>/', CategoryDetailView.as_view(), name='category-detail'),
    path('<int:category_id>/subcategories/', CategorySubcategoriesView.as_view(), name='category-subcategories'),
]
