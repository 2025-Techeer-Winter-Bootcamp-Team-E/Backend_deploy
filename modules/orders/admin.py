"""
Orders module admin configuration.
"""
from django.contrib import admin

from .models import (
    CartModel,
    CartItemModel,
    OrderModel,
    OrderItemModel,
    OrderHistoryModel,
    ReviewModel,
)


class CartItemInline(admin.TabularInline):
    """Inline admin for cart items."""
    model = CartItemModel
    extra = 0
    readonly_fields = ('product', 'quantity', 'created_at')


class OrderItemInline(admin.TabularInline):
    """Inline admin for order items."""
    model = OrderItemModel
    extra = 0
    readonly_fields = ('danawa_product_id', 'quantity', 'created_at')


@admin.register(CartModel)
class CartAdmin(admin.ModelAdmin):
    """Admin configuration for Cart model."""
    list_display = ('id', 'user', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__email',)
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [CartItemInline]


@admin.register(CartItemModel)
class CartItemAdmin(admin.ModelAdmin):
    """Admin configuration for Cart Item model."""
    list_display = ('id', 'cart', 'product', 'quantity', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('cart__user__email', 'product__name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OrderModel)
class OrderAdmin(admin.ModelAdmin):
    """Admin configuration for Order model."""
    list_display = ('id', 'user', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('user__email',)
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [OrderItemInline]


@admin.register(OrderItemModel)
class OrderItemAdmin(admin.ModelAdmin):
    """Admin configuration for Order Item model."""
    list_display = ('id', 'order', 'danawa_product_id', 'quantity', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('order__user__email', 'danawa_product_id')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OrderHistoryModel)
class OrderHistoryAdmin(admin.ModelAdmin):
    """Admin configuration for Order History model."""
    list_display = ('id', 'user', 'transaction_type', 'token_change', 'token_balance_after', 'transaction_at')
    list_filter = ('transaction_type', 'transaction_at')
    search_fields = ('user__email', 'danawa_product_id')
    ordering = ('-transaction_at',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ReviewModel)
class ReviewAdmin(admin.ModelAdmin):
    """Admin configuration for Review model."""
    list_display = ('id', 'danawa_product_id', 'user', 'reviewer_name', 'rating', 'mall_name', 'ai_recommendation_score', 'created_at')
    list_filter = ('rating', 'mall_name', 'created_at')
    search_fields = ('danawa_product_id', 'user__email', 'reviewer_name', 'content')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
