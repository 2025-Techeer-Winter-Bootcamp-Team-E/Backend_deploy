"""
Orders module exceptions.
"""
from shared.exceptions import AppException, BusinessRuleError


class OrderNotFoundError(AppException):
    """Raised when an order is not found."""

    def __init__(self, identifier: str):
        super().__init__(
            message=f"Order '{identifier}' not found",
            code="ORDER_NOT_FOUND"
        )
        self.identifier = identifier


class CartNotFoundError(AppException):
    """Raised when a cart is not found."""

    def __init__(self, user_id: str):
        super().__init__(
            message=f"Cart for user '{user_id}' not found",
            code="CART_NOT_FOUND"
        )
        self.user_id = user_id


class EmptyCartError(BusinessRuleError):
    """Raised when trying to checkout with an empty cart."""

    def __init__(self):
        super().__init__(
            message="Cannot create order from empty cart",
            rule="CART_NOT_EMPTY"
        )


class InvalidOrderStatusTransitionError(BusinessRuleError):
    """Raised when order status transition is invalid."""

    def __init__(self, current_status: str, new_status: str):
        super().__init__(
            message=f"Cannot change order status from '{current_status}' to '{new_status}'",
            rule="VALID_STATUS_TRANSITION"
        )
        self.current_status = current_status
        self.new_status = new_status


class OrderAlreadyCancelledError(BusinessRuleError):
    """Raised when trying to cancel an already cancelled order."""

    def __init__(self, order_id: str):
        super().__init__(
            message=f"Order '{order_id}' is already cancelled",
            rule="ORDER_NOT_CANCELLED"
        )
        self.order_id = order_id


class OrderCannotBeCancelledError(BusinessRuleError):
    """Raised when order cannot be cancelled due to its status."""

    def __init__(self, order_id: str, status: str):
        super().__init__(
            message=f"Order '{order_id}' with status '{status}' cannot be cancelled",
            rule="ORDER_CANCELLABLE"
        )
        self.order_id = order_id
        self.status = status


class InvalidRechargeAmountError(BusinessRuleError):
    """Raised when recharge amount is below minimum."""

    def __init__(self, minimum_amount: int):
        super().__init__(
            message=f"최소 충전 금액은 {minimum_amount:,}원입니다.",
            rule="MINIMUM_RECHARGE_AMOUNT"
        )
        self.minimum_amount = minimum_amount


class InsufficientTokenBalanceError(BusinessRuleError):
    """Raised when user doesn't have enough tokens for purchase."""

    def __init__(self, required: int, available: int):
        super().__init__(
            message=f"토큰 잔액이 부족합니다. 필요: {required:,}원, 보유: {available:,}원",
            rule="SUFFICIENT_TOKEN_BALANCE"
        )
        self.required = required
        self.available = available
