"""
Products module admin configuration.
"""
from django.contrib import admin

from .models import ProductModel, MallInformationModel


class MallInformationInline(admin.TabularInline):
    """Inline admin for mall information."""
    model = MallInformationModel
    extra = 0
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ProductModel)
class ProductAdmin(admin.ModelAdmin):
    """Admin configuration for Product model."""
    list_display = ('name', 'danawa_product_id', 'lowest_price', 'brand', 'category', 'product_status', 'created_at')
    list_filter = ('category', 'product_status', 'brand', 'created_at')
    search_fields = ('name', 'danawa_product_id', 'brand')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [MallInformationInline]

    fieldsets = (
        (None, {'fields': ('name', 'danawa_product_id', 'brand')}),
        ('Pricing', {'fields': ('lowest_price',)}),
        ('Details', {'fields': ('detail_spec', 'registration_month', 'product_status', 'category')}),
        ('Soft Delete', {'fields': ('deleted_at',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(MallInformationModel)
class MallInformationAdmin(admin.ModelAdmin):
    """Admin configuration for Mall Information model."""
    list_display = ('id', 'product', 'mall_name', 'current_price', 'created_at')
    list_filter = ('mall_name', 'created_at')
    search_fields = ('product__name', 'mall_name')
    ordering = ('current_price',)
    readonly_fields = ('created_at', 'updated_at')
