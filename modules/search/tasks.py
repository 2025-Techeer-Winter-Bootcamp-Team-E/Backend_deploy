"""
Search Celery tasks.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def cleanup_old_search_history(days: int = 90):
    """
    Clean up old search history records.

    Args:
        days: Delete records older than this many days
    """
    from datetime import timedelta
    from django.utils import timezone
    from .models import SearchHistoryModel

    cutoff_date = timezone.now() - timedelta(days=days)

    deleted_count, _ = SearchHistoryModel.objects.filter(
        created_at__lt=cutoff_date
    ).delete()

    logger.info(f"Deleted {deleted_count} old search history records")
    return deleted_count


@shared_task
def update_popular_searches_ranking():
    """
    Recalculate popular searches based on recent activity.

    This task should be scheduled to run periodically.
    """
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Count
    from .models import SearchHistoryModel, PopularSearchModel

    # Get searches from last 7 days
    start_date = timezone.now() - timedelta(days=7)

    recent_searches = (
        SearchHistoryModel.objects
        .filter(created_at__gte=start_date)
        .values('query')
        .annotate(count=Count('id'))
        .order_by('-count')[:100]
    )

    for search in recent_searches:
        PopularSearchModel.objects.update_or_create(
            query=search['query'].lower(),
            defaults={'search_count': search['count']}
        )

    logger.info(f"Updated {len(recent_searches)} popular search rankings")


@shared_task
def generate_search_report(days: int = 30):
    """
    Generate search analytics report.

    Args:
        days: Report period in days
    """
    from .services import SearchAnalyticsService

    analytics_service = SearchAnalyticsService()
    stats = analytics_service.get_search_stats(days=days)

    logger.info(f"Search Report ({days} days):")
    logger.info(f"  Total searches: {stats['total_searches']}")
    logger.info(f"  By type: {stats['searches_by_type']}")
    logger.info(f"  Avg results: {stats['avg_results_per_search']}")

    return stats
