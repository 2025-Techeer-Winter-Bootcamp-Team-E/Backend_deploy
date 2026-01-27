"""
Price Prediction module exceptions.
"""
from shared.exceptions import AppException


class PricePredictionError(AppException):
    """Base exception for price prediction module."""
    pass


class PredictionNotFoundError(PricePredictionError):
    """Raised when prediction is not found."""

    def __init__(self, product_id=None, prediction_id=None):
        self.product_id = product_id
        self.prediction_id = prediction_id
        if prediction_id:
            message = f"Prediction not found: {prediction_id}"
        else:
            message = f"No prediction found for product: {product_id}"
        super().__init__(message, code='PREDICTION_NOT_FOUND')


class InsufficientHistoryDataError(PricePredictionError):
    """Raised when there's not enough historical data for prediction."""

    def __init__(self, product_id, required: int, available: int):
        self.product_id = product_id
        self.required = required
        self.available = available
        message = (
            f"Insufficient price history for product {product_id}. "
            f"Required: {required}, Available: {available}"
        )
        super().__init__(message, code='INSUFFICIENT_HISTORY_DATA')


class PredictionServiceError(PricePredictionError):
    """Raised when prediction service fails."""

    def __init__(self, message: str, original_error=None):
        self.original_error = original_error
        super().__init__(message, code='PREDICTION_SERVICE_ERROR')
