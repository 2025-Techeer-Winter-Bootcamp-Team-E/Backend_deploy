"""
Orders module serializers.
"""
from rest_framework import serializers


# Cart (장바구니) Serializers

class CartItemSerializer(serializers.Serializer):
    """Serializer for cart item output."""
    id = serializers.IntegerField(read_only=True)
    cart_id = serializers.IntegerField(read_only=True)
    product_code = serializers.CharField(read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class CartItemCreateSerializer(serializers.Serializer):
    """Serializer for adding item to cart."""
    product_code = serializers.CharField(max_length=15)
    quantity = serializers.IntegerField(min_value=1, default=1)


class CartItemUpdateSerializer(serializers.Serializer):
    """Serializer for updating cart item."""
    quantity = serializers.IntegerField(min_value=0)


class CartSerializer(serializers.Serializer):
    """Serializer for cart output."""
    id = serializers.IntegerField(read_only=True)
    user_id = serializers.IntegerField(read_only=True)
    items = CartItemSerializer(many=True, read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


# Order Serializers

class OrderItemSerializer(serializers.Serializer):
    """Serializer for order item output."""
    id = serializers.IntegerField(read_only=True)
    order_id = serializers.IntegerField(read_only=True)
    danawa_product_id = serializers.CharField(read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class OrderSerializer(serializers.Serializer):
    """Serializer for order output."""
    id = serializers.IntegerField(read_only=True)
    user_id = serializers.IntegerField(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


# Order History Serializers

class OrderHistorySerializer(serializers.Serializer):
    """Serializer for order history output."""
    id = serializers.IntegerField(read_only=True)
    transaction_type = serializers.CharField(read_only=True)
    token_change = serializers.IntegerField(read_only=True)
    token_balance_after = serializers.IntegerField(read_only=True)
    transaction_at = serializers.DateTimeField(read_only=True)
    danawa_product_id = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


# Review Serializers

class ReviewSerializer(serializers.Serializer):
    """Serializer for review output."""
    id = serializers.IntegerField(read_only=True)
    danawa_product_id = serializers.CharField(read_only=True)
    user_id = serializers.IntegerField(read_only=True)
    mall_name = serializers.CharField(read_only=True, allow_null=True)
    reviewer_name = serializers.CharField(read_only=True, allow_null=True)
    content = serializers.CharField(read_only=True, allow_null=True)
    rating = serializers.IntegerField(read_only=True, allow_null=True)
    ai_review_summary = serializers.CharField(read_only=True, allow_null=True)
    ai_positive_review_analysis = serializers.JSONField(read_only=True, allow_null=True)
    ai_negative_review_analysis = serializers.JSONField(read_only=True, allow_null=True)
    ai_recommendation_score = serializers.IntegerField(read_only=True, allow_null=True)
    ai_review_analysis_basis = serializers.CharField(read_only=True, allow_null=True)
    review_images = serializers.JSONField(read_only=True, allow_null=True)
    external_review_count = serializers.IntegerField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)


class ReviewCreateSerializer(serializers.Serializer):
    """Serializer for creating a review."""
    danawa_product_id = serializers.CharField(max_length=15)
    content = serializers.CharField(required=False, allow_blank=True)
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    mall_name = serializers.CharField(required=False, allow_blank=True)
    reviewer_name = serializers.CharField(required=False, allow_blank=True)


# Token Recharge Serializers

class TokenRechargeSerializer(serializers.Serializer):
    """Serializer for token recharge request."""
    recharge_token = serializers.IntegerField(min_value=1)


# Token Purchase Serializers

class TokenPurchaseSerializer(serializers.Serializer):
    """Serializer for token purchase request."""
    product_code = serializers.CharField(max_length=15)
    quantity = serializers.IntegerField(min_value=1)
    total_price = serializers.IntegerField(min_value=0)


# Cart Payment Serializers

class CartItemPaymentSerializer(serializers.Serializer):
    """Serializer for cart item in payment request."""
    cart_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class CartPaymentSerializer(serializers.Serializer):
    """Serializer for cart payment request."""
    items = CartItemPaymentSerializer(many=True)
    total_price = serializers.IntegerField(min_value=0)
