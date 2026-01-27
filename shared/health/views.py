"""
Health check views.
"""
from django.db import connection
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


@extend_schema(exclude=True)
class HealthCheckView(APIView):
    """Basic health check endpoint."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'status': 'healthy'})


@extend_schema(exclude=True)
class ReadinessCheckView(APIView):
    """Readiness check - verifies all dependencies are available."""
    permission_classes = [AllowAny]

    def get(self, request):
        checks = {
            'database': self._check_database(),
            'cache': self._check_cache(),
        }

        all_healthy = all(check['healthy'] for check in checks.values())

        return Response(
            {
                'status': 'ready' if all_healthy else 'not_ready',
                'checks': checks,
            },
            status=status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    def _check_database(self) -> dict:
        """Check database connectivity."""
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            return {'healthy': True}
        except Exception as e:
            return {'healthy': False, 'error': str(e)}

    def _check_cache(self) -> dict:
        """Check cache (Redis) connectivity."""
        try:
            cache.set('health_check', 'ok', 10)
            value = cache.get('health_check')
            if value == 'ok':
                return {'healthy': True}
            return {'healthy': False, 'error': 'Cache read/write failed'}
        except Exception as e:
            return {'healthy': False, 'error': str(e)}


@extend_schema(exclude=True)
class LivenessCheckView(APIView):
    """Liveness check - basic app responsiveness."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'status': 'alive'})
