"""
Products module API views.
"""
from drf_spectacular.utils import extend_schema, OpenApiParameter,OpenApiResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import ProductService, MallInformationService
from .serializers import (
    ProductSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ProductCreateSerializer,
    ProductUpdateSerializer,
    ProductPriceTrendSerializer,
    MallInformationSerializer,
    MallInformationCreateSerializer,
    MallPriceSerializer,
    ReviewListResponseSerializer,
    ProductListItemSerializer,
    ProductSearchResponseSerializer,
    ProductAIReviewSummarySerializer,
)


product_service = ProductService()
mall_info_service = MallInformationService()


@extend_schema(tags=['Products'])
class ProductListView(APIView):
    """
    카테고리별 상품 목록 조회 및 검색 API.

    GET /api/v1/products/
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="상품 목록 조회 및 검색",
        description="대분류, 중분류, 브랜드, 가격 범위 등 다양한 조건으로 상품을 검색합니다.",
        parameters=[
            OpenApiParameter(name='q', type=str, required=False, description='검색어 (상품명, 브랜드)'),
            OpenApiParameter(name='main_cat', type=str, required=False, description='대분류 카테고리 이름'),
            OpenApiParameter(name='sub_cat', type=str, required=False, description='중분류 카테고리 이름'),
            OpenApiParameter(name='brand', type=str, required=False, description='제조사/브랜드'),
            OpenApiParameter(name='min_price', type=int, required=False, description='최소 가격'),
            OpenApiParameter(name='max_price', type=int, required=False, description='최대 가격'),
            OpenApiParameter(name='sort', type=str, required=False, description='정렬 (price_low, price_high, popular)'),
            OpenApiParameter(name='page', type=int, required=False, description='페이지 번호 (기본값: 1)'),
            OpenApiParameter(name='page_size', type=int, required=False, description='페이지 크기 (기본값: 10)'),
        ],
        responses={
            200: ProductSearchResponseSerializer,
            404: OpenApiResponse(description='상품이 존재하지 않습니다.'),
            500: OpenApiResponse(description='서버 내부 오류가 발생했습니다.'),
        }
    )
    def get(self, request):
        try:
            # Query Parameters 추출
            q = request.query_params.get('q')
            main_cat = request.query_params.get('main_cat')
            sub_cat = request.query_params.get('sub_cat')
            brand = request.query_params.get('brand')
            min_price = request.query_params.get('min_price')
            max_price = request.query_params.get('max_price')
            sort = request.query_params.get('sort')
            page = request.query_params.get('page', 1)
            page_size = request.query_params.get('page_size', 10)

            # 타입 변환
            page = int(page)
            page_size = int(page_size)
            min_price = int(min_price) if min_price else None
            max_price = int(max_price) if max_price else None

            # 서비스 호출
            result = product_service.get_products_with_filters(
                query=q,
                main_cat=main_cat,
                sub_cat=sub_cat,
                brand=brand,
                min_price=min_price,
                max_price=max_price,
                sort=sort,
                page=page,
                page_size=page_size,
            )

            # 결과가 없는 경우 404
            if result['total_count'] == 0:
                return Response({
                    "status": 404,
                    "message": "상품이 존재하지 않습니다."
                }, status=status.HTTP_404_NOT_FOUND)

            # Serializer를 통한 응답 구성
            products_data = ProductListItemSerializer(
                result['products'],
                many=True
            ).data

            response_data = {
                "status": 200,
                "data": {
                    "pagination": {
                        "current_page": result['page'],
                        "size": result['page_size'],
                        "count": result['total_count'],
                        "total_pages": result['total_pages']
                    },
                    "products": products_data
                }
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({
                "status": 400,
                "message": "잘못된 파라미터입니다."
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "status": 500,
                "message": "서버 내부 오류가 발생했습니다."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=['Products'])
class ProductListCreateView(APIView):
    """Product list and create endpoint."""

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminUser()]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='category_id', type=int, required=False),
            OpenApiParameter(name='limit', type=int, required=False),
            OpenApiParameter(name='offset', type=int, required=False),
        ],
        responses={200: ProductListSerializer(many=True)},
        summary="List products",
    )
    def get(self, request):
        category_id = request.query_params.get('category_id')
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))

        products = product_service.get_all_products(
            category_id=int(category_id) if category_id else None,
            offset=offset,
            limit=limit,
        )

        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)

    @extend_schema(
        request=ProductCreateSerializer,
        responses={201: ProductSerializer},
        summary="Create a product",
    )
    def post(self, request):
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        product = product_service.create_product(
            danawa_product_id=data['danawa_product_id'],
            name=data['name'],
            lowest_price=data['lowest_price'],
            brand=data['brand'],
            detail_spec=data.get('detail_spec', {}),
            category_id=data.get('category_id'),
            registration_month=data.get('registration_month'),
            product_status=data.get('product_status'),
        )

        output = ProductSerializer(product)
        return Response(output.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Products'])
class ProductDetailView(APIView):
    """Product detail endpoint."""

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminUser()]

    @extend_schema(
        responses={200: ProductDetailSerializer},
        summary="Get product detail",
    )
    def get(self, request, product_code: str):
        product = product_service.get_product_by_code(product_code)
        if not product:
            return Response({
                'status': 404,
                'message': '상품을 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductDetailSerializer(product)
        return Response({
            'status': 200,
            'data': serializer.data
        })

    @extend_schema(
        request=ProductUpdateSerializer,
        responses={200: ProductSerializer},
        summary="Update a product",
    )
    def patch(self, request, product_id: int):
        serializer = ProductUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        product = product_service.update_product(
            product_id=product_id,
            **serializer.validated_data
        )

        output = ProductSerializer(product)
        return Response(output.data)

    @extend_schema(summary="Delete a product")
    def delete(self, request, product_id: int):
        deleted = product_service.delete_product(product_id)
        if not deleted:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=['Products'])
class ProductMallInfoView(APIView):
    """Product mall information endpoint."""

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminUser()]

    @extend_schema(
        responses={200: MallPriceSerializer(many=True)},
        summary="Get mall information for a product",
    )
    def get(self, request, product_code: str):
        mall_info = mall_info_service.get_mall_info_by_code(product_code)
        # 프론트엔드가 기대하는 형식: { mall_name, price, url }
        serializer = MallPriceSerializer(mall_info, many=True)
        return Response({
            'status': 200,
            'data': serializer.data
        })

    @extend_schema(
        request=MallInformationCreateSerializer,
        responses={201: MallInformationSerializer},
        summary="Add mall information to a product",
    )
    def post(self, request, product_id: int):
        serializer = MallInformationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        mall_info = mall_info_service.create_mall_info(
            product_id=product_id,
            mall_name=data['mall_name'],
            current_price=data['current_price'],
            product_page_url=data.get('product_page_url'),
            seller_logo_url=data.get('seller_logo_url'),
            representative_image_url=data.get('representative_image_url'),
            additional_image_urls=data.get('additional_image_urls', []),
        )

        output = MallInformationSerializer(mall_info)
        return Response(output.data, status=status.HTTP_201_CREATED)

@extend_schema(tags=['Products'])
class ProductPriceTrendView(APIView):
    """상품의 월별 최저가 추이를 조회하는 API입니다."""
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Get product price trend",
        responses={
            200: ProductPriceTrendSerializer,
            400: OpenApiResponse(description="지원하지 않는 조회 기간입니다. (6, 12, 24 중 선택 가능)"), #
            404: OpenApiResponse(description="상품 가격 이력 데이터를 찾을 수 없습니다.") #
        }
    )
    def get(self, request, product_code: str):
        # 1. 조회 기간(months) 검증 (명세서 400 에러 대응)
        try:
            months = int(request.query_params.get('months', 6))
        except ValueError:
            months = 0 # 숫자가 아니면 아래 조건에서 걸러지게 함

        if months not in [6, 12, 24]:
            return Response({
                "status": 400,
                "message": "지원하지 않는 조회 기간입니다. (6, 12, 24 중 선택 가능)"
            }, status=status.HTTP_400_BAD_REQUEST) #

        # 2. 상품 존재 여부 확인
        product = product_service.get_product_by_code(product_code)
        if not product:
            return Response({
                "status": 404,
                "message": "상품 가격 이력 데이터를 찾을 수 없습니다."
            }, status=status.HTTP_404_NOT_FOUND) #
        
        # 3. 데이터 조회 및 응답
        trend_data = product_service.get_price_trend_data(product, months=months)
        serializer = ProductPriceTrendSerializer(trend_data)
        
        # 성공 시 응답 구조도 status를 포함하고 싶다면 아래처럼 보낼 수 있습니다.
        return Response({
            "status": 200,
            "data": serializer.data
        })
@extend_schema(tags=['Products'])
class ProductReviewListView(APIView):
    permission_classes = [AllowAny]
    @extend_schema(
        parameters=[
            OpenApiParameter(name='page', description='페이지', required=False, type=int, default=1),
            OpenApiParameter(name='size', description='리뷰 개수', required=False, type=int, default=5),
        ]
    )
    def get(self, request, product_code):
        try:
            page = int(request.query_params.get('page', 1))
            size = int(request.query_params.get('size', 5))
        except Exception as e:
            return Response({
                "status":500,
                "message":"리뷰 목록을 불러오는 중 서버 오류가 발생했습니다."
            },status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        result_data = ProductService.get_product_reviews(
            product_code=product_code,
            page=page,
            size=size
        )
        if result_data == None:
            return Response({
                    "status": 404,
                    "message": "해당 상품이 존재하지 않아 리뷰를 불러올 수 없습니다."
                }, status=status.HTTP_404_NOT_FOUND)

        # 3. 시리얼라이징 (데이터를 명세서 규격에 맞게 변환)
        serializer = ReviewListResponseSerializer(result_data)

        # 4. 최종 응답
        return Response({
            "status": 200,
            "data": serializer.data
        }, status=status.HTTP_200_OK)


@extend_schema(tags=['Products'])
class ProductAIReviewSummaryView(APIView):
    """
    AI 통합 리뷰 조회 API.

    GET /api/v1/products/{product_code}/reviews/summary
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="AI 통합 리뷰 조회",
        description="상품의 AI 분석 기반 리뷰 요약 정보를 조회합니다.",
        responses={
            200: OpenApiResponse(
                description="성공",
                response=ProductAIReviewSummarySerializer
            ),
            404: OpenApiResponse(description="해당 상품의 AI 분석 결과가 존재하지 않습니다."),
            500: OpenApiResponse(description="AI 분석 처리 중 오류가 발생했습니다."),
        }
    )
    def get(self, request, product_code: str):
        try:
            # 1. AI 리뷰 분석 결과 조회
            ai_review = product_service.get_ai_review_summary(product_code)

            # 2. 분석 결과가 없는 경우 빈 데이터 반환
            if not ai_review:
                return Response({
                    "status": "success",
                    "data": {
                        "product_code": product_code,
                        "total_review_count": 0,
                        "ai_summary": None,
                        "pros": [],
                        "cons": [],
                        "recommendation_score": None,
                        "score_reason": None,
                        "last_updated": None
                    }
                }, status=status.HTTP_200_OK)

            # 3. 시리얼라이징 및 응답
            serializer = ProductAIReviewSummarySerializer(ai_review)

            return Response({
                "status": "success",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": 500,
                "message": "AI 분석 처리 중 오류가 발생했습니다."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=['Products'])
class ProductAIReviewGenerateView(APIView):
    """
    AI 리뷰 분석 생성 API.

    POST /api/v1/products/{product_code}/reviews/summary/generate
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="AI 리뷰 분석 생성",
        description="Gemini를 사용하여 상품의 AI 리뷰 분석을 생성합니다.",
        responses={
            201: OpenApiResponse(
                description="AI 분석 생성 성공",
                response=ProductAIReviewSummarySerializer
            ),
            404: OpenApiResponse(description="상품을 찾을 수 없습니다."),
            500: OpenApiResponse(description="AI 분석 생성 중 오류가 발생했습니다."),
        }
    )
    def post(self, request, product_code: str):
        try:
            # 1. AI 리뷰 분석 생성
            ai_review = product_service.generate_ai_review_analysis(product_code)

            # 2. 생성 실패 시 404
            if not ai_review:
                return Response({
                    "status": 404,
                    "message": "상품을 찾을 수 없습니다."
                }, status=status.HTTP_404_NOT_FOUND)

            # 3. 시리얼라이징 및 응답
            serializer = ProductAIReviewSummarySerializer(ai_review)

            return Response({
                "status": "success",
                "message": "AI 분석이 성공적으로 생성되었습니다.",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                "status": 500,
                "message": f"AI 분석 생성 중 오류가 발생했습니다: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)