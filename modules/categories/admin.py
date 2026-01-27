"""
Categories admin configuration.
"""
from django.contrib import admin

from .models import CategoryModel


@admin.register(CategoryModel)
class CategoryAdmin(admin.ModelAdmin):
    """Admin for categories."""

    list_display = [
        'id',
        'name',
        'parent',
        'created_at',
        'deleted_at',
    ]
    list_filter = ['parent', 'created_at']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['name']

    fieldsets = (
        (None, {
            'fields': ('name', 'parent')
        }),
        ('Soft Delete', {
            'fields': ('deleted_at',)
        }),
        ('Info', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
