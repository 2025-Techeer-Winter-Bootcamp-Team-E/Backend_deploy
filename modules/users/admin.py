"""
Users module admin configuration.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import UserModel


@admin.register(UserModel)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for User model."""
    list_display = ('email', 'nickname', 'token_balance', 'social_provider', 'is_active', 'created_at')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'social_provider', 'created_at')
    search_fields = ('email', 'nickname')
    ordering = ('-created_at',)
    filter_horizontal = ()  # PermissionsMixin 제거로 groups, user_permissions 없음

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('nickname', 'name', 'phone', 'token_balance')}),
        ('Social Login', {'fields': ('social_provider', 'social_id')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Soft Delete', {'fields': ('deleted_at',)}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nickname', 'name', 'phone', 'password1', 'password2'),
        }),
    )

    readonly_fields = ('created_at', 'updated_at', 'last_login')
