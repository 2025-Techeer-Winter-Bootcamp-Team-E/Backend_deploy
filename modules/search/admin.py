"""
Search admin configuration.
"""
from django.contrib import admin

from .models import SearchModel, RecentViewProductModel


@admin.register(SearchModel)
class SearchAdmin(admin.ModelAdmin):
    """Admin for search history."""

    list_display = [
        'id',
        'query',
        'search_mode',
        'searched_at',
        'user',
        'danawa_product_id',
        'created_at',
    ]
    list_filter = ['search_mode', 'searched_at', 'created_at']
    search_fields = ['query', 'danawa_product_id', 'user__email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-searched_at']


@admin.register(RecentViewProductModel)
class RecentViewProductAdmin(admin.ModelAdmin):
    """Admin for recent view products."""

    list_display = [
        'id',
        'user',
        'danawa_product_id',
        'created_at',
        'updated_at',
    ]
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__email', 'danawa_product_id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-updated_at']
