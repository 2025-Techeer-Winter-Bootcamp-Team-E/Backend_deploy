"""
Shared exceptions and custom exception handler.
Consolidates all domain exceptions for the application.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


# === Base Exceptions ===

class AppException(Exception):
    """Base exception for application."""

    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code or self.__class__.__name__
        super().__init__(self.message)


class NotFoundError(AppException):
    """Entity not found."""

    def __init__(self, entity_name: str, entity_id: str):
        super().__init__(
            message=f"{entity_name} with id '{entity_id}' not found",
            code="ENTITY_NOT_FOUND"
        )
        self.entity_name = entity_name
        self.entity_id = entity_id


class ValidationError(AppException):
    """Validation failed."""

    def __init__(self, message: str, field: str = None):
        super().__init__(message=message, code="VALIDATION_ERROR")
        self.field = field


class BusinessRuleError(AppException):
    """Business rule violated."""

    def __init__(self, message: str, rule: str = None):
        super().__init__(message=message, code="BUSINESS_RULE_VIOLATION")
        self.rule = rule


class InsufficientStockError(AppException):
    """Stock insufficient."""

    def __init__(self, product_id: str, requested: int, available: int):
        super().__init__(
            message=f"Insufficient stock for product '{product_id}': requested {requested}, available {available}",
            code="INSUFFICIENT_STOCK"
        )
        self.product_id = product_id
        self.requested = requested
        self.available = available


class InvalidOperationError(AppException):
    """Raised when an operation is invalid for the current state."""

    def __init__(self, message: str, operation: str = None, state: str = None):
        super().__init__(message=message, code="INVALID_OPERATION")
        self.operation = operation
        self.state = state


# === Exception Handler ===

def custom_exception_handler(exc, context):
    """Handle custom application exceptions."""
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # Handle authentication errors (401)
    from rest_framework.exceptions import NotAuthenticated, AuthenticationFailed
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        return Response(
            {
                'status': 401,
                'message': '로그인이 필요합니다.'
            },
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Handle permission denied (403)
    from rest_framework.exceptions import PermissionDenied
    if isinstance(exc, PermissionDenied):
        return Response(
            {
                'status': 403,
                'message': '접근 권한이 없습니다.'
            },
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Handle DRF ValidationError (from serializer.is_valid(raise_exception=True))
    from rest_framework.exceptions import ValidationError as DRFValidationError
    if isinstance(exc, DRFValidationError):
        # DRF ValidationError는 response.data에 필드별 에러 정보를 담고 있음
        if response is not None and response.data:
            # 필드별 에러가 있는 경우 ({"field": ["error message"]})
            if isinstance(response.data, dict) and not 'detail' in response.data:
                # 첫 번째 에러 메시지를 기본 메시지로 사용
                first_error = list(response.data.values())[0] if response.data else []
                error_message = first_error[0] if isinstance(first_error, list) and first_error else "잘못된 상품 번호이거나 필수 값이 누락되었습니다."
                return Response(
                    {
                        'status': response.status_code,
                        'message': error_message,
                        'errors': response.data
                    },
                    status=response.status_code
                )
            # detail 키가 있는 경우
            elif 'detail' in response.data:
                error_message = response.data['detail']
                return Response(
                    {
                        'status': response.status_code,
                        'message': error_message
                    },
                    status=response.status_code
                )
    
    # Convert DRF's default error format to our format if response exists
    if response is not None and response.data:
        # Check if it's DRF's default error format (has 'detail' key)
        if 'detail' in response.data:
            error_message = response.data['detail']
            return Response(
                {
                    'status': response.status_code,
                    'message': error_message
                },
                status=response.status_code
            )

    # Handle NotFoundError
    if isinstance(exc, NotFoundError):
        return Response(
            {
                'error': exc.message,
                'code': exc.code,
                'entity': exc.entity_name,
                'entity_id': exc.entity_id,
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Handle ValidationError
    if isinstance(exc, ValidationError):
        return Response(
            {
                'error': exc.message,
                'code': exc.code,
                'field': exc.field,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Handle InsufficientStockError
    if isinstance(exc, InsufficientStockError):
        return Response(
            {
                'error': exc.message,
                'code': exc.code,
                'product_id': exc.product_id,
                'requested': exc.requested,
                'available': exc.available,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Handle BusinessRuleError
    if isinstance(exc, BusinessRuleError):
        return Response(
            {
                'error': exc.message,
                'code': exc.code,
                'rule': exc.rule,
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # Handle InvalidOperationError
    if isinstance(exc, InvalidOperationError):
        return Response(
            {
                'error': exc.message,
                'code': exc.code,
                'operation': exc.operation,
                'state': exc.state,
            },
            status=status.HTTP_409_CONFLICT,
        )

    # Handle generic AppException
    if isinstance(exc, AppException):
        return Response(
            {
                'error': exc.message,
                'code': exc.code,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    return response
