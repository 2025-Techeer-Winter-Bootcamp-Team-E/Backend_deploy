"""
Products module exceptions.
"""
from shared.exceptions import AppException, ValidationError


class ProductNotFoundError(AppException):
    """Raised when a product is not found."""

    def __init__(self, identifier: str):
        super().__init__(
            message=f"Product '{identifier}' not found",
            code="PRODUCT_NOT_FOUND"
        )
        self.identifier = identifier


class InsufficientStockError(AppException):
    """Raised when stock is insufficient."""

    def __init__(self, product_id: str, requested: int, available: int):
        super().__init__(
            message=f"Insufficient stock for product '{product_id}': requested {requested}, available {available}",
            code="INSUFFICIENT_STOCK"
        )
        self.product_id = product_id
        self.requested = requested
        self.available = available


class DuplicateSKUError(ValidationError):
    """Raised when SKU already exists."""

    def __init__(self, sku: str):
        super().__init__(
            message=f"Product with SKU '{sku}' already exists",
            field="sku"
        )
        self.sku = sku


class InvalidPriceError(ValidationError):
    """Raised when price is invalid."""

    def __init__(self, price):
        super().__init__(
            message=f"Invalid price: {price}. Price must be non-negative.",
            field="price"
        )
        self.price = price
