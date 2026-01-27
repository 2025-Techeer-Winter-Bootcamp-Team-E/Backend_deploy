"""
Timers API views.
"""
import logging
from datetime import timedelta

from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter
from django.utils import timezone

from .services import TimerService, PriceHistoryService

logger = logging.getLogger(__name__)
from .serializers import (
    TimerSerializer,
    TimerListSerializer,
    TimerCreateSerializer,
    TimerUpdateSerializer,
    TimerRetrieveSerializer,
    TimerListItemSerializer,
    PriceHistorySerializer,
    PriceHistoryCreateSerializer,
    PriceTrendSerializer,
)


timer_service = TimerService()
history_service = PriceHistoryService()


@extend_schema(tags=['Timers'])
class TimerListCreateView(APIView):
    """List and create timers."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='적정 구매 타이머 조회',
        description='product_code로 단일 조회 또는 user_id로 전체 목록 조회',
        request=None,
        parameters=[
            OpenApiParameter(
                name='product_code',
                type=str,
                required=False,
                description='상품 코드 (단일 조회 시 사용)'
            ),
            OpenApiParameter(
                name='user_id',
                type=int,
                required=False,
                description='조회를 원하는 사용자의 고유 ID (전체 목록 조회 시 사용)'
            ),
            OpenApiParameter(
                name='page',
                type=int,
                required=False,
                description='요청 페이지 번호 (기본값: 1, user_id 있을 때만 사용)',
                default=1
            ),
            OpenApiParameter(
                name='size',
                type=int,
                required=False,
                description='페이지 크기 (기본값: 10, user_id 있을 때만 사용)',
                default=10
            ),
        ],
        responses={
            200: {
                'description': '단일 조회 또는 전체 목록 조회 응답'
            },
            404: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                },
                'example': {
                    'status': 404,
                    'message': '해당 예측 데이터를 찾을 수 없습니다.'
                }
            },
            500: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                },
                'example': {
                    'status': 500,
                    'message': '서버 내부 오류가 발생했습니다.'
                }
            }
        },
    )
    def get(self, request):
        """적정 구매 타이머 조회"""
        try:
            product_code = request.query_params.get('product_code')
            user_id_param = request.query_params.get('user_id')
            
            # product_code가 있으면 단일 조회
            if product_code:
                from modules.products.models import ProductModel
                from .models import TimerModel
                
                # 상품 존재 확인
                try:
                    product = ProductModel.objects.select_related().prefetch_related('mall_information').get(
                        danawa_product_id=product_code,
                        deleted_at__isnull=True
                    )
                except ProductModel.DoesNotExist:
                    return Response(
                        {
                            'status': 404,
                            'message': '해당 상품을 찾을 수 없습니다.'
                        },
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # 사용자의 해당 상품 타이머 조회 (가장 최근 것)
                timer = TimerModel.objects.filter(
                    user_id=request.user.id,
                    danawa_product_id=product_code,
                    deleted_at__isnull=True
                ).order_by('-created_at').first()
                
                if not timer:
                    return Response(
                        {
                            'status': 404,
                            'message': '해당 예측 데이터를 찾을 수 없습니다.'
                        },
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # 대표 이미지 URL 가져오기
                thumbnail_url = ''
                try:
                    mall_info = product.mall_information.filter(
                        deleted_at__isnull=True
                    ).first()
                    if mall_info and mall_info.representative_image_url:
                        thumbnail_url = mall_info.representative_image_url
                except Exception:
                    pass
                
                # confidence_score를 퍼센트로 변환 (0.925 -> 92.5)
                confidence_percent = (timer.confidence_score * 100) if timer.confidence_score else 0
                
                data = {
                    'product_code': timer.danawa_product_id,
                    'product_name': product.name,
                    'target_price': timer.target_price,
                    'predicted_price': timer.predicted_price or 0,
                    'confidence_score': round(confidence_percent, 1),
                    'recommendation_score': timer.purchase_suitability_score or 0,
                    'thumbnail_url': thumbnail_url,
                    'reason_message': timer.purchase_guide_message or '',
                    'predicted_at': timer.prediction_date or timer.created_at,
                }
                
                serializer = TimerRetrieveSerializer(data)
                return Response(
                    {
                        'status': 200,
                        'data': serializer.data
                    },
                    status=status.HTTP_200_OK
                )
            # user_id가 있으면 전체 목록 조회
            elif user_id_param:
                return self._get_timer_list(request, user_id_param)
            else:
                # 둘 다 없으면 에러
                return Response(
                    {
                        'status': 400,
                        'message': 'product_code 또는 user_id 중 하나는 필수입니다.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.error(f"타이머 조회 중 서버 오류 발생: {str(e)}", exc_info=True)
            return Response(
                {
                    'status': 500,
                    'message': '서버 내부 오류가 발생했습니다.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    
    def _get_timer_list(self, request, user_id_param):
        """전체 타이머 목록 조회 - 사용자가 설정한 타이머 전체 조회"""
        try:
            user_id = int(user_id_param)
        except (ValueError, TypeError):
            return Response(
                {
                    'status': 400,
                    'message': '유효하지 않은 user_id입니다.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 쿼리 파라미터 파싱
        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('size', 10))
        
        # 페이지 번호 검증
        if page < 1:
            page = 1
        if size < 1 or size > 100:
            size = 10
        
        # offset 계산 (페이지는 1부터 시작하지만 내부적으로는 0부터)
        offset = (page - 1) * size
        
        # 사용자의 타이머 조회
        timers = timer_service.get_user_timers(
            user_id=user_id,
            offset=offset,
            limit=size
        )
        
        # 전체 개수 조회
        from .models import TimerModel
        total_count = TimerModel.objects.filter(
            user_id=user_id,
            deleted_at__isnull=True
        ).count()
        
        total_pages = (total_count + size - 1) // size if total_count > 0 else 0
        is_last = page >= total_pages
        
        # 상품 정보와 함께 데이터 구성
        timer_items = []
        from modules.products.models import ProductModel
        
        for timer in timers:
            try:
                product = ProductModel.objects.select_related().prefetch_related('mall_information').get(
                    danawa_product_id=timer.danawa_product_id,
                    deleted_at__isnull=True
                )
                
                # 대표 이미지 URL 가져오기
                thumbnail_url = ''
                try:
                    mall_info = product.mall_information.filter(
                        deleted_at__isnull=True
                    ).first()
                    if mall_info and mall_info.representative_image_url:
                        thumbnail_url = mall_info.representative_image_url
                except Exception:
                    pass
                
                # confidence_score를 퍼센트로 변환 (0.925 -> 92.5)
                confidence_percent = (timer.confidence_score * 100) if timer.confidence_score else 0
                
                item_data = {
                    'timer_id': timer.id,
                    'product_code': timer.danawa_product_id,
                    'product_name': product.name,
                    'target_price': timer.target_price,
                    'predicted_price': timer.predicted_price or 0,
                    'confidence_score': round(confidence_percent, 1),
                    'recommendation_score': timer.purchase_suitability_score or 0,
                    'thumbnail_url': thumbnail_url,
                    'reason_message': timer.purchase_guide_message or '',
                    'predicted_at': timer.prediction_date or timer.created_at,
                }
                
                serializer = TimerListItemSerializer(item_data)
                timer_items.append(serializer.data)
            except ProductModel.DoesNotExist:
                # 상품이 없으면 스킵
                continue
        
        return Response(
            {
                'status': 200,
                'message': '사용자별 타이머 목록 조회가 완료되었습니다.',
                'data': {
                    'user_id': user_id,
                    'page_info': {
                        'current_page': page - 1,  # 명세서에서 0부터 시작
                        'page_size': size,
                        'total_elements': total_count,
                        'total_pages': total_pages,
                        'is_last': is_last
                    },
                    'timers': timer_items
                }
            },
            status=status.HTTP_200_OK
        )

    @extend_schema(
        summary='적정 구매 타이머 등록',
        description='상품 상세에서 적정 구매 타이머 설정',
        request=TimerCreateSerializer,
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'timer_id': {'type': 'integer'},
                        }
                    }
                },
                'example': {
                    'status': 201,
                    'message': '타이머가 성공적으로 등록되었습니다.',
                    'data': {'timer_id': 1}
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                },
                'example': {
                    'status': 400,
                    'message': '잘못된 상품 번호이거나 필수 값이 누락되었습니다.'
                }
            },
            401: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                },
                'example': {
                    'status': 401,
                    'message': '로그인이 필요합니다.'
                }
            }
        },
    )
    def post(self, request):
        """
        적정 구매 타이머 등록

        Request Body:
          - product_code: ProductModel.danawa_product_id (string/varchar(15))
          - target_price: int
        """
        serializer = TimerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_code = str(serializer.validated_data["product_code"])
        target_price = serializer.validated_data["target_price"]
        
        # 명세서에 없지만 예측에 필요한 값이므로 내부적으로 기본값 사용
        prediction_days = 7  # 기본값: 7일 후 예측
        prediction_date = timezone.now() + timedelta(days=prediction_days)
        timer = timer_service.create_timer(
            danawa_product_id=product_code,
            user_id=request.user.id,
            target_price=target_price,
            prediction_date=prediction_date,
        )

        return Response(
            {
                "status": 201,
                "message": "타이머가 성공적으로 등록되었습니다.",
                "data": {"timer_id": timer.id},
            },
            status=status.HTTP_201_CREATED,
            )

@extend_schema(tags=['Timers'])
class TimerByProductView(APIView):
    """상품 코드로 타이머 조회."""
    permission_classes = [AllowAny]

    @extend_schema(
        summary='상품별 타이머 조회',
        description='상품 코드로 해당 상품의 타이머 정보를 조회합니다. 로그인하지 않은 경우 빈 데이터를 반환합니다.',
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'data': {'type': 'object'}
                }
            }
        },
    )
    def get(self, request, product_code: str):
        """상품 코드로 타이머 조회"""
        try:
            from modules.products.models import ProductModel
            from .models import TimerModel

            # 상품 존재 확인
            try:
                product = ProductModel.objects.select_related().prefetch_related('mall_information').get(
                    danawa_product_id=product_code,
                    deleted_at__isnull=True
                )
            except ProductModel.DoesNotExist:
                return Response({
                    'status': 200,
                    'data': None
                }, status=status.HTTP_200_OK)

            # 로그인하지 않은 경우 빈 데이터 반환
            if not request.user.is_authenticated:
                return Response({
                    'status': 200,
                    'data': None
                }, status=status.HTTP_200_OK)

            # 사용자의 해당 상품 타이머 조회 (가장 최근 것)
            timer = TimerModel.objects.filter(
                user_id=request.user.id,
                danawa_product_id=product_code,
                deleted_at__isnull=True
            ).order_by('-created_at').first()

            if not timer:
                return Response({
                    'status': 200,
                    'data': None
                }, status=status.HTTP_200_OK)

            # 대표 이미지 URL 가져오기
            thumbnail_url = ''
            try:
                mall_info = product.mall_information.filter(deleted_at__isnull=True).first()
                if mall_info and mall_info.representative_image_url:
                    thumbnail_url = mall_info.representative_image_url
            except Exception:
                pass

            # confidence_score를 퍼센트로 변환
            confidence_percent = (timer.confidence_score * 100) if timer.confidence_score else 0

            data = {
                'timer_id': timer.id,
                'product_code': timer.danawa_product_id,
                'product_name': product.name,
                'target_price': timer.target_price,
                'predicted_price': timer.predicted_price or 0,
                'confidence_score': round(confidence_percent, 1),
                'recommendation_score': timer.purchase_suitability_score or 0,
                'thumbnail_url': thumbnail_url,
                'reason_message': timer.purchase_guide_message or '',
                'predicted_at': timer.prediction_date or timer.created_at,
            }

            return Response({
                'status': 200,
                'data': data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"타이머 조회 중 서버 오류 발생: {str(e)}", exc_info=True)
            return Response({
                'status': 200,
                'data': None
            }, status=status.HTTP_200_OK)


@extend_schema(tags=['Timers'])
class TimerDetailView(APIView):
    """Timer detail endpoint."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='타이머 수정',
        description='타이머 목표 가격 수정',
        request=TimerUpdateSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                },
                'example': {
                    'status': 200,
                    'message': '수정이 완료되었습니다.'
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                },
                'example': {
                    'status': 400,
                    'message': '유효하지 않은 가격 형식입니다.'
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                },
                'example': {
                    'status': 403,
                    'message': '본인의 타이머만 수정할 수 있습니다.'
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                }
            }
        },
    )
    def patch(self, request, timer_id: int):
        """Update timer target price."""
        timer = timer_service.get_timer_by_id(timer_id)
        if not timer:
            return Response(
                {
                    'status': 404,
                    'message': '타이머를 찾을 수 없습니다.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # Check ownership
        if timer.user_id != request.user.id and not request.user.is_staff:
            return Response(
                {
                    'status': 403,
                    'message': '본인의 타이머만 수정할 수 있습니다.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = TimerUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_price = serializer.validated_data['target_price']
        timer_service.update_timer(timer_id, target_price=target_price)

        return Response(
            {
                'status': 200,
                'message': '수정이 완료되었습니다.'
            },
            status=status.HTTP_200_OK
        )

    @extend_schema(
        summary='Delete timer',
        responses={
            204: {
                'description': '타이머가 성공적으로 삭제되었습니다.',
            },
            404: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                }
            },
            500: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                },
                'example': {
                    'status': 500,
                    'message': '데이터베이스 처리 중 오류가 발생했습니다.'
                }
            }
        },
    )
    def delete(self, request, timer_id: int):
        """Delete a timer."""
        try:
            timer = timer_service.get_timer_by_id(timer_id)
            if not timer:
                return Response(
                    {'message': '삭제할 대상을 찾을 수 없습니다.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check ownership
            if timer.user_id != request.user.id and not request.user.is_staff:
                return Response(
                    {'message': '본인 계정에서만 삭제할 수 있습니다.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            timer_service.delete_timer(timer_id)
            return Response(
            {
                'status': 200,
                'message': '성공적으로 삭제(추적 중단)되었습니다.'
            },
            status=status.HTTP_200_OK
        )

        except Exception as e:
            logger.error(f"타이머 삭제 중 서버 오류 발생: {str(e)}", exc_info=True)
            return Response(
                {
                    'status': 500,
                    'message': '데이터베이스 처리 중 오류가 발생했습니다.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(tags=['Timers'])
class PriceTrendView(APIView):
    """Get price trend analysis."""
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Get price trend',
        parameters=[
            OpenApiParameter(
                name='danawa_product_id',
                type=str,
                required=True,
                description='Danawa Product ID'
            ),
            OpenApiParameter(
                name='days',
                type=int,
                required=False,
                description='Analysis period in days (default: 30)'
            ),
        ],
        responses={200: PriceTrendSerializer},
    )
    def get(self, request):
        """Analyze price trend for a product."""
        danawa_product_id = request.query_params.get('danawa_product_id')
        days = int(request.query_params.get('days', 30))

        if not danawa_product_id:
            return Response(
                {'error': 'danawa_product_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        trend = timer_service.get_price_trend(
            danawa_product_id=danawa_product_id,
            days=days
        )
        serializer = PriceTrendSerializer(trend)
        return Response(serializer.data)


@extend_schema(tags=['Price History'])
class PriceHistoryListCreateView(APIView):
    """List and create price history."""

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    @extend_schema(
        summary='Get price history',
        parameters=[
            OpenApiParameter(
                name='danawa_product_id',
                type=str,
                required=True,
                description='Danawa Product ID'
            ),
            OpenApiParameter(
                name='days',
                type=int,
                required=False,
                description='Number of days (default: 30)'
            ),
        ],
        responses={200: PriceHistorySerializer(many=True)},
    )
    def get(self, request):
        """Get price history for a product."""
        danawa_product_id = request.query_params.get('danawa_product_id')
        days = int(request.query_params.get('days', 30))

        if not danawa_product_id:
            return Response(
                {'error': 'danawa_product_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        history = history_service.get_history_by_product(
            danawa_product_id=danawa_product_id,
            days=days
        )
        serializer = PriceHistorySerializer(history, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary='Create price history record',
        request=PriceHistoryCreateSerializer,
        responses={201: PriceHistorySerializer},
    )
    def post(self, request):
        """Create a new price history record."""
        serializer = PriceHistoryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        history = history_service.create_history(
            danawa_product_id=serializer.validated_data['danawa_product_id'],
            lowest_price=serializer.validated_data['lowest_price'],
        )

        result_serializer = PriceHistorySerializer(history)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)
