"""
Orders module Celery tasks.
"""
from celery import shared_task


@shared_task(name='modules.orders.tasks.process_order')
def process_order(order_id: str):
    """Process a new order (payment, notifications, etc.)."""
    from .models import OrderModel

    try:
        order = OrderModel.objects.get(id=order_id)
    except OrderModel.DoesNotExist:
        return False

    # TODO: Implement payment processing
    # TODO: Send order confirmation email
    # TODO: Notify admin

    print(f"Processing order {order.order_number}")
    return True


@shared_task(name='modules.orders.tasks.send_order_confirmation')
def send_order_confirmation(order_id: str, email: str):
    """Send order confirmation email."""
    # TODO: Implement email sending
    print(f"Sending order confirmation to {email} for order {order_id}")
    return True


@shared_task(name='modules.orders.tasks.send_shipping_notification')
def send_shipping_notification(order_id: str, email: str, tracking_number: str = None):
    """Send shipping notification email."""
    # TODO: Implement email sending
    print(f"Sending shipping notification to {email} for order {order_id}")
    return True


@shared_task(name='modules.orders.tasks.cleanup_abandoned_carts')
def cleanup_abandoned_carts(days: int = 30):
    """Clean up carts that haven't been updated in X days."""
    from datetime import timedelta
    from django.utils import timezone
    from .models import CartModel

    cutoff_date = timezone.now() - timedelta(days=days)
    deleted_count, _ = CartModel.objects.filter(updated_at__lt=cutoff_date).delete()

    print(f"Deleted {deleted_count} abandoned carts")
    return deleted_count
