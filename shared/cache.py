"""
Shared Redis cache utilities.
"""
import json
from typing import Any, Optional

from django.core.cache import cache


class CacheService:
    """Redis cache wrapper with prefix support."""

    def __init__(self, prefix: str = ""):
        self.prefix = prefix

    def _key(self, key: str) -> str:
        """Build cache key with prefix."""
        return f"{self.prefix}:{key}" if self.prefix else key

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        value = cache.get(self._key(key))
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        return value

    def set(self, key: str, value: Any, timeout: int = 300) -> None:
        """Set value in cache with timeout (default 5 minutes)."""
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        cache.set(self._key(key), value, timeout)

    def delete(self, key: str) -> None:
        """Delete key from cache."""
        cache.delete(self._key(key))

    def get_or_set(self, key: str, default_func, timeout: int = 300) -> Any:
        """Get value from cache or set it using default function."""
        value = self.get(key)
        if value is None:
            value = default_func()
            self.set(key, value, timeout)
        return value

    def increment(self, key: str, delta: int = 1) -> int:
        """Increment a value in cache."""
        try:
            return cache.incr(self._key(key), delta)
        except ValueError:
            self.set(key, delta)
            return delta

    def decrement(self, key: str, delta: int = 1) -> int:
        """Decrement a value in cache."""
        try:
            return cache.decr(self._key(key), delta)
        except ValueError:
            self.set(key, -delta)
            return -delta

    def clear_pattern(self, pattern: str) -> None:
        """Clear all keys matching pattern (requires redis backend)."""
        # Note: This requires direct redis access
        try:
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            full_pattern = self._key(pattern)
            keys = redis_conn.keys(full_pattern)
            if keys:
                redis_conn.delete(*keys)
        except Exception:
            pass


# Pre-configured cache instances
user_cache = CacheService(prefix="user")
product_cache = CacheService(prefix="product")
order_cache = CacheService(prefix="order")
