"""
Timers serializers.
"""
from rest_framework import serializers

from .models import TimerModel, PriceHistoryModel


class TimerSerializer(serializers.ModelSerializer):
    """Serializer for timer."""

    price_change = serializers.SerializerMethodField()
    change_percent = serializers.SerializerMethodField()

    class Meta:
        model = TimerModel
        fields = [
            'id',
            'danawa_product_id',
            'user',
            'target_price',
            'predicted_price',
            'prediction_date',
            'confidence_score',
            'purchase_suitability_score',
            'purchase_guide_message',
            'is_notification_enabled',
            'price_change',
            'change_percent',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_price_change(self, obj):
        """Calculate absolute price change."""
        if obj.target_price and obj.predicted_price:
            return obj.predicted_price - obj.target_price
        return 0

    def get_change_percent(self, obj):
        """Calculate percentage change."""
        if not obj.target_price or obj.target_price == 0:
            return 0
        if not obj.predicted_price:
            return 0
        change = (obj.predicted_price - obj.target_price) / obj.target_price * 100
        return round(float(change), 2)


class TimerCreateSerializer(serializers.Serializer):
    """Serializer for creating timer request."""

    # NOTE: API 스펙 상 product_code == ProductModel.danawa_product_id
    product_code = serializers.CharField(max_length=15)
    target_price = serializers.IntegerField(min_value=0)

    def validate_product_code(self, value):
        """Validate that product exists."""
        from modules.products.models import ProductModel
        
        exists = ProductModel.objects.filter(
            danawa_product_id=value,
            deleted_at__isnull=True,
        ).exists()
        
        if not exists:
            raise serializers.ValidationError("잘못된 상품 번호이거나 필수 값이 누락되었습니다.")
        
        return value


class TimerUpdateSerializer(serializers.Serializer):
    """Serializer for updating timer target price."""
    
    target_price = serializers.IntegerField(min_value=0, error_messages={
        'invalid': '유효하지 않은 가격 형식입니다.',
        'min_value': '유효하지 않은 가격 형식입니다.',
        'required': '유효하지 않은 가격 형식입니다.',
        'null': '유효하지 않은 가격 형식입니다.',
    })
    
    def validate_target_price(self, value):
        """Validate target price format."""
        if value is None:
            raise serializers.ValidationError("유효하지 않은 가격 형식입니다.")
        if value < 0:
            raise serializers.ValidationError("유효하지 않은 가격 형식입니다.")
        return value


class TimerListSerializer(serializers.ModelSerializer):
    """Simplified serializer for timer list."""

    class Meta:
        model = TimerModel
        fields = [
            'id',
            'danawa_product_id',
            'target_price',
            'predicted_price',
            'prediction_date',
            'confidence_score',
            'purchase_suitability_score',
            'is_notification_enabled',
            'created_at',
        ]


class TimerRetrieveSerializer(serializers.Serializer):
    """Serializer for timer retrieval response."""
    
    product_code = serializers.CharField()
    product_name = serializers.CharField()
    target_price = serializers.IntegerField()
    predicted_price = serializers.IntegerField()
    confidence_score = serializers.FloatField()
    recommendation_score = serializers.IntegerField()
    thumbnail_url = serializers.CharField(allow_blank=True)
    reason_message = serializers.CharField()
    predicted_at = serializers.DateTimeField()


class TimerListItemSerializer(serializers.Serializer):
    """Serializer for timer list item response."""
    
    timer_id = serializers.IntegerField()
    product_code = serializers.CharField()
    product_name = serializers.CharField()
    target_price = serializers.IntegerField()
    predicted_price = serializers.IntegerField()
    confidence_score = serializers.FloatField()
    recommendation_score = serializers.IntegerField()
    thumbnail_url = serializers.CharField(allow_blank=True)
    reason_message = serializers.CharField()
    predicted_at = serializers.DateTimeField()


class PriceHistorySerializer(serializers.ModelSerializer):
    """Serializer for price history."""

    class Meta:
        model = PriceHistoryModel
        fields = [
            'id',
            'danawa_product_id',
            'lowest_price',
            'recorded_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PriceHistoryCreateSerializer(serializers.Serializer):
    """Serializer for creating price history."""

    danawa_product_id = serializers.CharField(max_length=15)
    lowest_price = serializers.IntegerField(min_value=0)


class PriceTrendSerializer(serializers.Serializer):
    """Serializer for price trend analysis."""

    trend = serializers.CharField()
    change_percent = serializers.FloatField()
    data_points = serializers.IntegerField()
    min_price = serializers.IntegerField(required=False)
    max_price = serializers.IntegerField(required=False)
    avg_price = serializers.FloatField(required=False)
