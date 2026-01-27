"""
Products module serializers.
"""
from rest_framework import serializers
from .models import ProductModel, MallInformationModel
from modules.timers.models import PriceHistoryModel
from modules.orders.models import ReviewModel
class MallInformationSerializer(serializers.ModelSerializer):
    """Serializer for mall information."""
    price = serializers.IntegerField(source='current_price')

    class Meta:
        model = MallInformationModel
        fields = [
            'id',
            'mall_name',
            'price',
            'product_page_url',
            'seller_logo_url',
            'representative_image_url',
            'additional_image_urls',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ProductSerializer(serializers.ModelSerializer):
    """Serializer for product output."""
    product_code = serializers.CharField(source='danawa_product_id', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    mall_information = MallInformationSerializer(many=True, read_only=True)

    class Meta:
        model = ProductModel
        fields = [
            'id',
            #'danawa_product_id', 'product_code'로 대체
            'product_code',
            'name',
            'lowest_price',
            'brand',
            'detail_spec',
            'registration_month',
            'product_status',
            'category',
            'category_name',
            'mall_information',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductDetailSerializer(serializers.ModelSerializer):
    """상품 상세 정보 Serializer (API 명세서 규격)"""
    product_code = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='name')
    specs = serializers.SerializerMethodField()
    price = serializers.IntegerField(source='lowest_price')
    category = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    product_image_url_list = serializers.SerializerMethodField()
    product_detail_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductModel
        fields = [
            'product_code',
            'product_name',
            'brand',
            'specs',
            'price',
            'category',
            'thumbnail_url',
            'product_image_url_list',
            'product_detail_url',
        ]

    def get_product_code(self, obj):
        """product_code를 정수형으로 반환"""
        try:
            return int(obj.danawa_product_id)
        except (ValueError, TypeError):
            return obj.danawa_product_id

    def get_specs(self, obj):
        """specs를 간결한 key-value 형식으로 반환 (문자열 값만 포함)"""
        detail_spec = obj.detail_spec
        if not detail_spec:
            return {}

        # detail_spec이 'spec' 키를 가지고 있는 경우 그 내용을 사용
        spec_data = detail_spec.get('spec', detail_spec)

        # boolean이 아닌 문자열 값만 필터링하여 반환
        result = {}
        for key, value in spec_data.items():
            if isinstance(value, str) and value:
                result[key] = value

        return result

    def get_category(self, obj):
        """카테고리 이름 반환"""
        return obj.category.name if obj.category else None

    def get_thumbnail_url(self, obj):
        """첫 번째 판매처의 대표 이미지 URL 반환"""
        mall_info = obj.mall_information.filter(deleted_at__isnull=True).first()
        return mall_info.representative_image_url if mall_info else None

    def get_product_image_url_list(self, obj):
        """모든 판매처의 추가 이미지 URL 목록 반환"""
        mall_infos = obj.mall_information.filter(deleted_at__isnull=True)
        image_list = []
        for mall_info in mall_infos:
            if mall_info.representative_image_url:
                image_list.append(mall_info.representative_image_url)
            if mall_info.additional_image_urls:
                image_list.extend(mall_info.additional_image_urls)
        return image_list

    def get_product_detail_url(self, obj):
        """첫 번째 판매처의 상품 페이지 URL 반환"""
        mall_info = obj.mall_information.filter(deleted_at__isnull=True).first()
        return mall_info.product_page_url if mall_info else None


class ProductListSerializer(serializers.ModelSerializer):
    """Simplified serializer for product list."""

    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)

    class Meta:
        model = ProductModel
        fields = [
            'id',
            'danawa_product_id',
            'name',
            'lowest_price',
            'brand',
            'product_status',
            'category',
            'category_name',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

class ProductCreateSerializer(serializers.Serializer):
    """Serializer for product creation."""

    danawa_product_id = serializers.CharField(max_length=15)
    name = serializers.CharField(max_length=200)
    lowest_price = serializers.IntegerField(min_value=0)
    brand = serializers.CharField(max_length=50)
    detail_spec = serializers.JSONField(required=False, default=dict)
    registration_month = serializers.CharField(max_length=20, required=False, allow_blank=True)
    product_status = serializers.CharField(max_length=20, required=False, allow_blank=True)
    category_id = serializers.IntegerField(required=False, allow_null=True)


class ProductUpdateSerializer(serializers.Serializer):
    """Serializer for product update."""

    name = serializers.CharField(max_length=200, required=False)
    lowest_price = serializers.IntegerField(min_value=0, required=False)
    brand = serializers.CharField(max_length=50, required=False)
    detail_spec = serializers.JSONField(required=False)
    registration_month = serializers.CharField(max_length=20, required=False, allow_blank=True)
    product_status = serializers.CharField(max_length=20, required=False, allow_blank=True)
    category_id = serializers.IntegerField(required=False, allow_null=True)

#
class MallInformationCreateSerializer(serializers.Serializer):
    """Serializer for creating mall information."""

    mall_name = serializers.CharField(max_length=50)
    current_price = serializers.IntegerField(min_value=0)
    product_page_url = serializers.CharField(max_length=500, required=False, allow_blank=True)
    seller_logo_url = serializers.CharField(max_length=300, required=False, allow_blank=True)
    representative_image_url = serializers.CharField(max_length=500, required=False, allow_blank=True)
    additional_image_urls = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )

#과거 가격 시리얼 라이저(일 단위)
class PriceHistorySerializer(serializers.ModelSerializer):
    date = serializers.DateTimeField(source='recorded_at', format='%Y-%m-%d')
    price = serializers.IntegerField(source='lowest_price')

    class Meta:
        model = PriceHistoryModel
        fields = ['date', 'price']


#가격 추이 시리얼 라이저(기간)       
class ProductPriceTrendSerializer(serializers.Serializer):
    product_code = serializers.IntegerField()
    product_name = serializers.CharField()
    period_unit = serializers.CharField(default="month")
    selected_period = serializers.IntegerField()
    price_history = PriceHistorySerializer(many=True)

class ReviewDetailSerializer(serializers.ModelSerializer):
    review_id = serializers.IntegerField(source='id') # 모델의 PK 
    author_name = serializers.CharField(source='reviewer_name')
    
    class Meta:
        model = ReviewModel
        fields = [
            'review_id', 
            'review_images', 
            'author_name', 
            'rating', 
            'content', 
            'created_at'
        ]

class ReviewListResponseSerializer(serializers.Serializer):
    pagination = serializers.DictField(child=serializers.IntegerField())#리뷰 페이지 정보
    average_rating = serializers.FloatField()     # 상품 전체 평점
    reviews = ReviewDetailSerializer(many=True)    # 아까 만든 리뷰 개별 데이터 리스트
    has_next = serializers.BooleanField()


# ===== 카테고리별 상품 목록 조회 API용 Serializers =====

class MallPriceSerializer(serializers.Serializer):
    """판매처별 가격 정보 Serializer (mall_price 배열용)"""
    mall_name = serializers.CharField()
    price = serializers.IntegerField(source='current_price')
    url = serializers.CharField(source='product_page_url', allow_null=True)


class ProductListItemSerializer(serializers.ModelSerializer):
    """상품 목록 아이템 Serializer (API 명세서 규격)"""
    product_code = serializers.CharField(source='danawa_product_id')
    product_name = serializers.CharField(source='name')
    specs = serializers.JSONField(source='detail_spec')
    base_price = serializers.IntegerField(source='lowest_price')
    category = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    mall_price = serializers.SerializerMethodField()

    class Meta:
        model = ProductModel
        fields = [
            'product_code',
            'product_name',
            'brand',
            'specs',
            'base_price',
            'category',
            'thumbnail_url',
            'mall_price',
        ]

    def get_category(self, obj):
        """카테고리 이름 반환"""
        return obj.category.name if obj.category else None

    def get_thumbnail_url(self, obj):
        """첫 번째 판매처의 대표 이미지 URL 반환"""
        mall_info = obj.mall_information.filter(deleted_at__isnull=True).first()
        return mall_info.representative_image_url if mall_info else None

    def get_mall_price(self, obj):
        """판매처별 가격 정보 리스트 반환"""
        mall_infos = obj.mall_information.filter(deleted_at__isnull=True)[:5]
        return MallPriceSerializer(mall_infos, many=True).data


class PaginationResponseSerializer(serializers.Serializer):
    """페이지네이션 정보 Serializer"""
    current_page = serializers.IntegerField()
    size = serializers.IntegerField()
    count = serializers.IntegerField()
    total_pages = serializers.IntegerField()


class ProductListDataSerializer(serializers.Serializer):
    """상품 목록 응답 Data Serializer"""
    pagination = PaginationResponseSerializer()
    products = ProductListItemSerializer(many=True)


class ProductSearchResponseSerializer(serializers.Serializer):
    """상품 목록 조회 최종 응답 Serializer"""
    status = serializers.IntegerField()
    data = ProductListDataSerializer()


# ===== AI 통합 리뷰 조회 API용 Serializer =====

class ProductAIReviewSummarySerializer(serializers.Serializer):
    """AI 통합 리뷰 요약 응답 Serializer"""
    product_code = serializers.SerializerMethodField()
    total_review_count = serializers.IntegerField(source='analyzed_review_count')
    ai_summary = serializers.CharField(source='ai_review_summary', allow_null=True, default="")
    pros = serializers.JSONField(source='ai_positive_review_analysis', default=list)
    cons = serializers.JSONField(source='ai_negative_review_analysis', default=list)
    recommendation_score = serializers.IntegerField(source='ai_recommendation_score')
    score_reason = serializers.CharField(source='ai_review_analysis_basis', allow_null=True, default="")
    last_updated = serializers.DateTimeField(source='updated_at', format='%Y-%m-%dT%H:%M:%S')

    def get_product_code(self, obj):
        """product_code를 정수형으로 반환"""
        return int(obj.product.danawa_product_id)