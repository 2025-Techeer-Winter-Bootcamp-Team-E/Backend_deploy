"""
Search models based on ERD.
"""
from django.db import models


class SearchModel(models.Model):
    """User search history."""

    SEARCH_MODE_CHOICES = [
        ('basic', '기본'),
        ('llm', 'LLM'),
        ('shopping_research', '쇼핑 리서치'),
    ]

    query = models.TextField(
        verbose_name='검색어'
    )
    search_mode = models.CharField(
        max_length=20,
        choices=SEARCH_MODE_CHOICES,
        verbose_name='검색 모드',
        help_text='기본/LLM/쇼핑 리서치'
    )
    searched_at = models.DateTimeField(
        verbose_name='검색 일시'
    )
    user = models.ForeignKey(
        'users.UserModel',
        on_delete=models.CASCADE,
        related_name='searches',
        verbose_name='회원번호'
    )
    danawa_product_id = models.CharField(
        max_length=15,
        verbose_name='상품번호',
        help_text='다나와 상품 고유 번호'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='생성시각'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='수정시각'
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='논리적삭제플래그'
    )

    class Meta:
        db_table = 'search'
        verbose_name = 'Search'
        verbose_name_plural = 'Searches'
        ordering = ['-searched_at']
        indexes = [
            models.Index(fields=['user', 'searched_at']),
            models.Index(fields=['danawa_product_id']),
        ]

    def __str__(self):
        return f"{self.query} ({self.search_mode})"

    @property
    def is_deleted(self) -> bool:
        """Check if search is soft deleted."""
        return self.deleted_at is not None


class RecentViewProductModel(models.Model):
    """Recently viewed products (최근 본 상품)."""

    user = models.ForeignKey(
        'users.UserModel',
        on_delete=models.CASCADE,
        related_name='recent_view_products',
        verbose_name='회원번호'
    )
    danawa_product_id = models.CharField(
        max_length=15,
        verbose_name='상품 고유 번호',
        help_text='다나와 상품 고유 번호'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='생성시각'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='수정시각'
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='논리적 삭제 플래그'
    )

    class Meta:
        db_table = 'recent_view_products'
        verbose_name = 'Recent View Product'
        verbose_name_plural = 'Recent View Products'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'updated_at']),
            models.Index(fields=['danawa_product_id']),
        ]

    def __str__(self):
        return f"User {self.user_id} viewed product {self.danawa_product_id}"

    @property
    def is_deleted(self) -> bool:
        """Check if recent view is soft deleted."""
        return self.deleted_at is not None
