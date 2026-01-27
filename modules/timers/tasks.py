"""
Price Prediction Celery tasks.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_daily_predictions(self):
    """
    Generate daily price predictions for all active products.

    This task should be scheduled to run daily via Celery Beat.
    """
    from datetime import date, timedelta
    from modules.products.services import ProductService
    from .services import PricePredictionService

    try:
        product_service = ProductService()
        prediction_service = PricePredictionService()

        # Get all active products
        products = product_service.get_all_active_products()

        for product in products:
            try:
                prediction_service.create_prediction(
                    product_id=product.id,
                    current_price=product.price,
                    prediction_date=date.today() + timedelta(days=1)
                )
                logger.info(f"Created prediction for product {product.id}")
            except Exception as e:
                logger.warning(
                    f"Failed to create prediction for product {product.id}: {e}"
                )

        logger.info(f"Completed daily predictions for {len(products)} products")

    except Exception as e:
        logger.error(f"Daily prediction task failed: {e}")
        raise self.retry(exc=e, countdown=60 * 5)


@shared_task(bind=True, max_retries=3)
def record_product_prices(self):
    """
    Record current prices for all products (for historical tracking).

    This task should be scheduled to run periodically via Celery Beat.
    """
    from modules.products.services import ProductService
    from .services import PricePredictionService

    try:
        product_service = ProductService()
        prediction_service = PricePredictionService()

        products = product_service.get_all_active_products()

        for product in products:
            prediction_service.record_price_history(
                product_id=product.id,
                price=product.price,
                source='scheduled_task'
            )

        logger.info(f"Recorded prices for {len(products)} products")

    except Exception as e:
        logger.error(f"Price recording task failed: {e}")
        raise self.retry(exc=e, countdown=60 * 5)


@shared_task
def generate_prediction_for_product(product_id: str, days: int = 7):
    """Generate predictions for a specific product."""
    from datetime import date, timedelta
    from uuid import UUID
    from modules.products.services import ProductService
    from .services import PricePredictionService

    product_service = ProductService()
    prediction_service = PricePredictionService()

    product = product_service.get_product_by_id(UUID(product_id))
    if not product:
        logger.error(f"Product not found: {product_id}")
        return

    for i in range(1, days + 1):
        try:
            prediction_service.create_prediction(
                product_id=product.id,
                current_price=product.price,
                prediction_date=date.today() + timedelta(days=i)
            )
        except Exception as e:
            logger.warning(f"Failed to create prediction for day {i}: {e}")

    logger.info(f"Generated {days} predictions for product {product_id}")
