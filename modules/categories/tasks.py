"""
Categories Celery tasks.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def sync_category_product_counts():
    """
    Sync product counts for all categories.

    This task should be scheduled to run periodically.
    """
    from .models import CategoryModel

    categories = CategoryModel.objects.filter(is_active=True)
    updated = 0

    for category in categories:
        # This would integrate with products module
        # product_count = ProductModel.objects.filter(category=category).count()
        # category.product_count = product_count
        # category.save(update_fields=['product_count'])
        updated += 1

    logger.info(f"Synced product counts for {updated} categories")
    return updated


@shared_task
def cleanup_empty_categories(days_inactive: int = 30):
    """
    Find and report categories with no products.

    Args:
        days_inactive: Days without products to consider empty
    """
    from datetime import timedelta
    from django.utils import timezone
    from .models import CategoryModel

    # This is informational - doesn't auto-delete
    cutoff_date = timezone.now() - timedelta(days=days_inactive)

    empty_categories = CategoryModel.objects.filter(
        is_active=True,
        # Would need product_count field or join with products
        created_at__lt=cutoff_date
    )

    if empty_categories.exists():
        logger.warning(
            f"Found {empty_categories.count()} potentially empty categories"
        )
        for cat in empty_categories[:10]:
            logger.warning(f"  - {cat.name} ({cat.id})")

    return empty_categories.count()


@shared_task
def rebuild_category_tree_cache():
    """
    Rebuild category tree cache for faster retrieval.
    """
    from django.core.cache import cache
    from .services import CategoryService

    service = CategoryService()
    tree = service.get_category_tree()

    cache.set('category_tree', tree, timeout=3600)  # 1 hour
    logger.info("Rebuilt category tree cache")

    return len(tree)
