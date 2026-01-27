"""
Timers admin configuration.
"""
from django.contrib import admin

from .models import TimerModel, PriceHistoryModel


@admin.register(TimerModel)
class TimerAdmin(admin.ModelAdmin):
    """Admin for timers."""

    list_display = [
        'id',
        'danawa_product_id',
        'user',
        'target_price',
        'predicted_price',
        'prediction_date',
        'confidence_score',
        'is_notification_enabled',
        'created_at',
    ]
    list_filter = ['prediction_date', 'is_notification_enabled', 'created_at']
    search_fields = ['danawa_product_id', 'user__email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(PriceHistoryModel)
class PriceHistoryAdmin(admin.ModelAdmin):
    """Admin for price history."""

    list_display = [
        'id',
        'danawa_product_id',
        'lowest_price',
        'recorded_at',
        'created_at',
    ]
    list_filter = ['recorded_at', 'created_at']
    search_fields = ['danawa_product_id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-recorded_at']
