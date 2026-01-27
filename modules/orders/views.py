"""
Orders module API views.
"""
import logging
from datetime import datetime
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .services import CartService, OrderService, OrderHistoryService, ReviewService
from .serializers import (
    CartSerializer,
    CartItemSerializer,
    CartItemCreateSerializer,
    CartItemUpdateSerializer,
    OrderSerializer,
    OrderHistorySerializer,
    ReviewSerializer,
    ReviewCreateSerializer,
    TokenRechargeSerializer,
    TokenPurchaseSerializer,
    CartPaymentSerializer,
)
from .exceptions import InvalidRechargeAmountError, InsufficientTokenBalanceError, OrderNotFoundError
from modules.products.exceptions import ProductNotFoundError
from modules.products.services import ProductService


logger = logging.getLogger(__name__)

cart_service = CartService()
order_service = OrderService()
order_history_service = OrderHistoryService()
review_service = ReviewService()


@extend_schema(tags=['Orders'])
class CartItemListCreateView(APIView):
    """Cart item list and create endpoint."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'cart_item_id': {'type': 'integer'},
                                'product_code': {'type': 'string'},
                                'product_name': {'type': 'string'},
                                'product_resentative_image_url': {'type': 'string'},
                                'quantity': {'type': 'integer'},
                                'price': {'type': 'integer'},
                                'total_price': {'type': 'integer'},
                            }
                        }
                    }
                }
            },
            401: {
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
                }
            }
        },
        summary="Get current user's cart items",
        description="장바구니 목록 조회",
    )
    def get(self, request):
        try:
            cart = cart_service.get_or_create_cart(request.user.id)
            items = cart_service.get_cart_items(cart.id)
            
            result = []
            for item in items:
                product = item.product
                if not product:
                    continue
                
                # Get representative image URL from mall_information
                representative_image_url = ''
                try:
                    mall_info = product.mall_information.filter(
                        deleted_at__isnull=True
                    ).first()
                    if mall_info and mall_info.representative_image_url:
                        representative_image_url = mall_info.representative_image_url
                except Exception:
                    pass
                
                # Use lowest_price as price
                price = product.lowest_price or 0
                total_price = price * item.quantity
                
                result.append({
                    'cart_item_id': item.id,
                    'product_code': product.danawa_product_id,
                    'product_name': product.name,
                    'product_resentative_image_url': representative_image_url,
                    'quantity': item.quantity,
                    'price': price,
                    'total_price': total_price,
                })
            
            return Response(
                {
                    'status': 200,
                    'message': '장바구니 목록 조회 성공',
                    'data': result,
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"장바구니 조회 중 서버 오류 발생: {str(e)}", exc_info=True)
            return Response(
                {
                    'status': 500,
                    'message': '서버 내부 오류가 발생했습니다.',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        request=CartItemCreateSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'cart_item_id': {'type': 'integer'},
                            'product_code': {'type': 'string'},
                            'quantity': {'type': 'integer'},
                            'added_at': {'type': 'string'},
                        }
                    }
                },
                'example': {
                    'status': 200,
                    'message': '장바구니에 상품을 담았습니다.',
                    'data': {
                        'cart_item_id': 1006,
                        'product_code': '1234567890',
                        'quantity': 2,
                        'added_at': '2026-01-17T13:54:06'
                    }
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                },
                'example': {
                    'status': 404,
                    'message': '해당 상품을 찾을 수 없습니다.'
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
        summary="Add item to cart",
        description="장바구니에 상품 추가",
    )
    def post(self, request):
        try:
            serializer = CartItemCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            data = serializer.validated_data
            product_code = data['product_code']
            quantity = data['quantity']

            # Check if product exists
            from modules.products.models import ProductModel
            try:
                product = ProductModel.objects.get(danawa_product_id=product_code, deleted_at__isnull=True)
            except ProductModel.DoesNotExist:
                return Response(
                    {
                        'status': 404,
                        'message': '해당 상품을 찾을 수 없습니다.',
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            cart = cart_service.get_or_create_cart(request.user.id)
            item = cart_service.add_item(
                cart_id=cart.id,
                danawa_product_id=product.danawa_product_id,
                quantity=quantity,
            )

            added_at = item.created_at.isoformat() if item.created_at else datetime.now().isoformat()

            return Response(
                {
                    'status': 200,
                    'message': '장바구니에 상품을 담았습니다.',
                    'data': {
                        'cart_item_id': item.id,
                        'product_code': product_code,
                        'quantity': item.quantity,
                        'added_at': added_at,
                    }
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"장바구니에 상품 추가 중 서버 오류 발생: {str(e)}", exc_info=True)
            return Response(
                {
                    'status': 500,
                    'message': '서버 내부 오류가 발생했습니다.',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(tags=['Orders'])
class CartItemDeleteView(APIView):
    """Cart item delete endpoint."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                },
                'example': {
                    'status': 200,
                    'message': '장바구니 항목이 삭제되었습니다.'
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
                    'message': '잘못된 요청이거나 본인의 장바구니 항목이 아닙니다.'
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
        }, # Removed 404 for product not found
        summary="Remove cart item",
        description="장바구니에서 특정 항목 삭제",
    )
    
    @extend_schema(
        summary="장바구니 항목 수정 및 삭제",
        description="quantity가 0보다 크면 수량을 수정하고, 0이면 항목을 삭제합니다.",
        request=CartItemUpdateSerializer,
    )
    def patch(self, request, cart_item_id: int):
        try:
            # 1. 수량 데이터 가져오기 (시리얼라이저 혹은 request.data)
            serializer = CartItemUpdateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            quantity = serializer.validated_data['quantity']

            cart = cart_service.get_or_create_cart(request.user.id)

            # 2. 서비스 호출
            updated_item = cart_service.update_item_quantity(
                cart_id=cart.id,
                cart_item_id=cart_item_id,
                quantity=quantity
            )

            # 3. [핵심] 결과가 없으면(False/None) 400 에러 처리
            if not updated_item:
                # 만약 수량이 0이라서 삭제된 경우라면 (서비스 로직상 None 반환)
                if quantity <= 0:
                    return Response({
                        "status": 200,
                        "message": "장바구니 항목이 삭제되었습니다." 
                    }, status=status.HTTP_200_OK)
                
                # 그 외에 항목을 못 찾았거나 본인 것이 아닌 경우
                return Response({
                    "status": 400,
                    "message": "잘못된 요청이거나 본인의 장바구니 항목이 아닙니다." 
                }, status=status.HTTP_400_BAD_REQUEST)

            # 4. 성공 시 응답
            return Response({
                "status": 200,
                "message": "장바구니 수량이 변경되었습니다."
            }, status=status.HTTP_200_OK)

        except Exception:
            return Response({
                "status": 500,
                "message": "서버 내부 오류가 발생했습니다." 
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=['Orders'])
class CartPaymentView(APIView):
    """Cart payment endpoint."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=CartPaymentSerializer,
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'order_id': {'type': 'string'},
                            'order_items': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'cart_item_id': {'type': 'integer'},
                                        'quantity': {'type': 'integer'},
                                    }
                                }
                            },
                            'total_price': {'type': 'integer'},
                            'current_tokens': {'type': 'integer'},
                            'order_status': {'type': 'string'},
                        }
                    }
                }
            },
            400: {
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
                }
            }
        },
        summary="Purchase cart items with tokens",
        description="장바구니 내 상품 결제",
    )
    def post(self, request):
        try:
            serializer = CartPaymentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            items = serializer.validated_data['items']
            total_price = serializer.validated_data['total_price']

            # Check if items list is empty
            if not items or len(items) == 0:
                return Response(
                    {
                        'status': 400,
                        'message': '결제할 상품이 선택되지 않았습니다.',
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Convert items to list of dicts
            cart_item_ids_with_quantities = [
                {'cart_item_id': item['cart_item_id'], 'quantity': item['quantity']}
                for item in items
            ]

            order, new_balance, cart_items = order_history_service.purchase_cart_items_with_tokens(
                user_id=request.user.id,
                cart_item_ids_with_quantities=cart_item_ids_with_quantities,
                total_price=total_price,
            )

            # Format order_id: ORD-YYYYMMDD-XXX
            order_date = order.created_at.strftime('%Y%m%d')
            order_id_formatted = f"ORD-{order_date}-{str(order.id).zfill(3)}"

            # Format order_items
            order_items = [
                {'cart_item_id': item['cart_item_id'], 'quantity': item['quantity']}
                for item in items
            ]

            return Response(
                {
                    'status': 201,
                    'message': '장바구니 상품 결제가 성공적으로 완료되었습니다.',
                    'data': {
                        'order_id': order_id_formatted,
                        'order_items': order_items,
                        'total_price': total_price,
                        'current_tokens': new_balance,
                        'order_status': 'success',
                    }
                },
                status=status.HTTP_201_CREATED
            )
        except InsufficientTokenBalanceError as e:
            return Response(
                {
                    'status': 402,
                    'message': '토큰 잔액이 부족합니다.',
                },
                status=402  # Payment Required
            )
        except OrderNotFoundError as e:
            return Response(
                {
                    'status': 400,
                    'message': '결제할 상품이 선택되지 않았습니다.',
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"장바구니 결제 중 서버 오류 발생: {str(e)}", exc_info=True)
            return Response(
                {
                    'status': 500,
                    'message': '서버 내부 오류로 결제에 실패했습니다.',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



@extend_schema(tags=['Orders'])
class TokenRechargeView(APIView):
    """Token recharge endpoint."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=TokenRechargeSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'current_tokens': {'type': 'integer'},
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
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
        summary="Recharge tokens",
        description="결제를 위한 토큰 충전",
    )
    def post(self, request):
        serializer = TokenRechargeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recharge_amount = serializer.validated_data['recharge_token']

        try:
            new_balance = order_history_service.recharge_token(
                user_id=request.user.id,
                recharge_amount=recharge_amount,
            )

            order_history_service.create_order_history(
                user_id=request.user.id,
                transaction_type='charge',
                token_change=recharge_amount,
                token_balance_after=new_balance,
                danawa_product_id='',
            )

            # Format the amount with commas for the message
            formatted_amount = f"{recharge_amount:,}"

            return Response(
                {
                    'status': 200,
                    'message': f"{formatted_amount} 토큰이 성공적으로 충전되었습니다.",
                    'data': {
                        'current_tokens': new_balance,
                    }
                },
                status=status.HTTP_200_OK
            )
        except InvalidRechargeAmountError as e:
            return Response(
                {
                    'status': 400,
                    'message': e.message,
                },
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema(tags=['Orders'])
class TokenBalanceView(APIView):
    """Token balance inquiry endpoint."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: {
                
                
                'status': {'type': 'integer'},
                'data': {
                    'type': 'object',
                    'properties': {
                    'current_tokens': {'type': 'integer'},
                    }
                    
                }
            },
            401: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                }
            }
        },
        summary="Get token balance",
        description="현재 사용자의 토큰 잔액 조회",
    )
    def get(self, request):
        from modules.users.models import UserModel
        
        # DB에서 최신 토큰 잔액 조회
        try:
            user = UserModel.objects.get(id=request.user.id, deleted_at__isnull=True)
            current_balance = user.token_balance or 0
        except UserModel.DoesNotExist:
            current_balance = 0

        return Response(
            {
                'status': 200,
                'data': {
                    'current_tokens': current_balance,
                }
            },
            status=status.HTTP_200_OK
        )


@extend_schema(tags=['Orders'])
class TokenPurchaseView(APIView):
    """Token purchase endpoint."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=TokenPurchaseSerializer,
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'order_id': {'type': 'string'},
                            'product_name': {'type': 'string'},
                            'total_price': {'type': 'integer'},
                            'current_tokens': {'type': 'integer'},
                            'order_status': {'type': 'string'},
                            'ordered_at': {'type': 'string'},
                        }
                    }
                }
            },
            401: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
                }
            },
            402: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer'},
                    'message': {'type': 'string'},
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
        summary="Purchase product with tokens",
        description="토큰을 사용하여 상품 구매",
    )
    def post(self, request):
        serializer = TokenPurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_code = serializer.validated_data['product_code']
        quantity = serializer.validated_data['quantity']
        total_price = serializer.validated_data['total_price']

        try:
            order, new_balance, product = order_history_service.purchase_with_tokens(
                user_id=request.user.id,
                product_code=product_code,
                quantity=quantity,
                total_price=total_price,
            )

            # Format order_id: ORD-YYYYMMDD-XXX (XXX는 order.id를 3자리로 포맷)
            order_date = order.created_at.strftime('%Y%m%d')
            order_id_formatted = f"ORD-{order_date}-{str(order.id).zfill(3)}"
            ordered_at = order.created_at.isoformat()

            return Response(
                {
                    'status': 201,
                    'message': '결제가 완료되었습니다.',
                    'data': {
                        'order_id': order_id_formatted,
                        'product_name': product.name,
                        'total_price': total_price,
                        'current_tokens': new_balance,
                        'order_status': 'success',
                        'ordered_at': ordered_at,
                    }
                },
                status=status.HTTP_201_CREATED
            )
        except InsufficientTokenBalanceError as e:
            return Response(
                {
                    'status': 402,
                    'message': '토큰 잔액이 부족합니다.',
                },
                status=402  # Payment Required
            )
        except OrderNotFoundError as e:
            # Check if it's a product not found error
            if 'Product' in str(e):
                return Response(
                    {
                        'status': 404,
                        'message': '상품 정보를 찾을 수 없습니다.',
                    },
                    status=status.HTTP_404_NOT_FOUND
                )