"""
Timers module Django ORM models based on ERD.
"""
from django.db import models


class TimerModel(models.Model):
    """Timer (가격 예측/알림) model."""

    target_price = models.IntegerField(
        verbose_name='목표가'
    )
    predicted_price = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='예측가격'
    )
    prediction_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='예측일자'
    )
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        verbose_name='구매 신뢰도',
        help_text='0.00~1.00 범위의 값'
    )
    purchase_suitability_score = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='구매 적합도 점수'
    )
    purchase_guide_message = models.TextField(
        null=True,
        blank=True,
        verbose_name='구매 가이드 메시지'
    )
    is_notification_enabled = models.BooleanField(
        default=True,
        verbose_name='구매 알림 활성화 여부'
    )
    danawa_product_id = models.CharField(
        max_length=15,
        verbose_name='상품 고유 번호',
        help_text='다나와 상품 고유 번호'
    )
    user = models.ForeignKey(
        'users.UserModel',
        on_delete=models.CASCADE,
        related_name='timers',
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
        db_table = 'timers'
        verbose_name = 'Timer'
        verbose_name_plural = 'Timers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['danawa_product_id', 'prediction_date']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"Timer for product {self.danawa_product_id}: target {self.target_price}"

    @property
    def is_deleted(self) -> bool:
        """Check if timer is soft deleted."""
        return self.deleted_at is not None


class PriceHistoryModel(models.Model):
    """Historical price data (가격 이력)."""

    recorded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='기록일시'
    )
    lowest_price = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='최저가'
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
        verbose_name='논리적삭제플래그'
    )

    class Meta:
        db_table = 'price_histories'
        verbose_name = 'Price History'
        verbose_name_plural = 'Price Histories'
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['danawa_product_id', 'recorded_at']),
        ]

    def __str__(self):
        return f"{self.danawa_product_id}: {self.lowest_price} at {self.recorded_at}"

    @property
    def is_deleted(self) -> bool:
        """Check if price history is soft deleted."""
        return self.deleted_at is not None
