"""
Orders module Django ORM models based on ERD.
"""
from django.db import models


class CartModel(models.Model):
    """Cart (장바구니) model."""

    user = models.ForeignKey(
        'users.UserModel',
        on_delete=models.CASCADE,
        related_name='carts',
        verbose_name='회원번호'
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
        db_table = 'carts'
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'
        ordering = ['-created_at']

    def __str__(self):
        return f"Cart {self.id} - User {self.user_id}"

    @property
    def is_deleted(self) -> bool:
        """Check if cart is soft deleted."""
        return self.deleted_at is not None


class CartItemModel(models.Model):
    """Cart item (장바구니 상세) model."""

    cart = models.ForeignKey(
        CartModel,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='장바구니번호'
    )
    product = models.ForeignKey(
        'products.ProductModel',
        on_delete=models.CASCADE,
        to_field='danawa_product_id',
        db_column='danawa_product_id',
        related_name='cart_items',
        verbose_name='상품번호'
    )
    quantity = models.IntegerField(
        verbose_name='수량'
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
        db_table = 'cart_items'
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
        ordering = ['-created_at']

    def __str__(self):
        return f"Cart {self.cart_id} - Product {self.product_id} x {self.quantity}"

    @property
    def is_deleted(self) -> bool:
        """Check if cart item is soft deleted."""
        return self.deleted_at is not None


class OrderModel(models.Model):
    """Order (구매) model."""

    user = models.ForeignKey(
        'users.UserModel',
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name='회원번호'
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
        db_table = 'order'
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.id} by user {self.user_id}"

    @property
    def is_deleted(self) -> bool:
        """Check if order is soft deleted."""
        return self.deleted_at is not None


class OrderItemModel(models.Model):
    """Order item (구매 상품) model."""

    order = models.ForeignKey(
        OrderModel,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='구매번호'
    )
    danawa_product_id = models.CharField(
        max_length=15,
        verbose_name='상품 고유 번호',
        help_text='다나와 상품 고유 번호'
    )
    quantity = models.IntegerField(
        verbose_name='수량'
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
        db_table = 'order_items'
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.order_id} - Product {self.danawa_product_id} x {self.quantity}"

    @property
    def is_deleted(self) -> bool:
        """Check if order item is soft deleted."""
        return self.deleted_at is not None


class OrderHistoryModel(models.Model):
    """Order history (결제 이력) model - token transactions."""

    TRANSACTION_TYPE_CHOICES = [
        ('charge', '충전'),
        ('payment', '결제'),
    ]

    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
        verbose_name='유형',
        help_text='충전/결제'
    )
    token_change = models.IntegerField(
        verbose_name='변동된 토큰양',
        help_text='충전은+/결제는-'
    )
    token_balance_after = models.IntegerField(
        verbose_name='잔액 토큰양',
        help_text='0보다 커야 함'
    )
    transaction_at = models.DateTimeField(
        verbose_name='거래일시'
    )
    danawa_product_id = models.CharField(
        max_length=15,
        verbose_name='상품번호',
        help_text='다나와 상품 고유 번호'
    )
    user = models.ForeignKey(
        'users.UserModel',
        on_delete=models.CASCADE,
        related_name='order_histories',
        verbose_name='회원번호',
        db_column='token_owner_id'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='수정시각'
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
        db_table = 'token_histories'
        verbose_name = 'token History'
        verbose_name_plural = 'token Histories'
        ordering = ['-transaction_at']
        indexes = [
            models.Index(fields=['user', 'transaction_at']),
        ]

    def __str__(self):
        return f"{self.transaction_type}: {self.token_change} tokens"

    @property
    def is_deleted(self) -> bool:
        """Check if order history is soft deleted."""
        return self.deleted_at is not None


class ReviewModel(models.Model):
    """Product review (리뷰) model."""

    mall_name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='리뷰 쇼핑몰명'
    )
    reviewer_name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='리뷰 작성자'
    )
    content = models.TextField(
        null=True,
        blank=True,
        verbose_name='내용'
    )
    rating = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='평점'
    )
    ai_review_summary = models.TextField(
        null=True,
        blank=True,
        verbose_name='AI 리뷰 요약'
    )
    ai_positive_review_analysis = models.JSONField(
        null=True,
        blank=True,
        verbose_name='AI 긍정 리뷰 분석'
    )
    ai_negative_review_analysis = models.JSONField(
        null=True,
        blank=True,
        verbose_name='AI 부정 리뷰 분석'
    )
    ai_recommendation_score = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='AI 추천점수',
        help_text='0~100점 구매 추천 점수'
    )
    ai_review_analysis_basis = models.TextField(
        null=True,
        blank=True,
        verbose_name='AI 리뷰 분석 근거'
    )
    review_images = models.JSONField(
        null=True,
        blank=True,
        verbose_name='리뷰 이미지'
    )
    external_review_count = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='외부 쇼핑몰 리뷰 총합'
    )
    danawa_product_id = models.CharField(
        max_length=15,
        verbose_name='상품 고유 번호',
        help_text='다나와 상품 고유 번호'
    )
    user = models.ForeignKey(
        'users.UserModel',
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='회원번호'
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
        db_table = 'reviews'
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['danawa_product_id', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"Review by {self.reviewer_name} - Rating: {self.rating}"

    @property
    def is_deleted(self) -> bool:
        """Check if review is soft deleted."""
        return self.deleted_at is not None
