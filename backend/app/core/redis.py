"""
Redis client — async connection pool and caching subsystem via redis-py.
Provides robust cache read/write/invalidation helpers with graceful
fallback when Redis is unavailable.
"""

import json
import hashlib
import logging
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger("cache.redis")

_redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> aioredis.Redis:
    """Return the shared async Redis client (singleton)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


async def get_redis() -> aioredis.Redis:
    """FastAPI dependency for Redis access."""
    return await get_redis_client()


def _json_serial(obj: Any) -> Any:
    """JSON serializer helper for UUIDs, Decimals, and Pydantic models."""
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "dict"):
        return obj.dict()
    raise TypeError(f"Type {type(obj)} is not JSON serializable")


async def cache_get(key: str) -> Optional[Any]:
    """
    Retrieve and deserialize a JSON-cached object from Redis.
    Returns None on cache miss or when Redis is unreachable.
    """
    try:
        client = await get_redis_client()
        raw = await client.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception as e:
        logger.debug(f"[Redis Cache] cache_get('{key}') missed/failed: {e}")
    return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    """
    Serialize and store an object as JSON in Redis with a TTL in seconds.
    Returns True on success, False on error.
    """
    try:
        client = await get_redis_client()
        payload = json.dumps(value, default=_json_serial)
        await client.set(key, payload, ex=ttl)
        return True
    except Exception as e:
        logger.debug(f"[Redis Cache] cache_set('{key}') failed: {e}")
        return False


async def cache_delete(key: str) -> bool:
    """
    Invalidate a specific cache key.
    """
    try:
        client = await get_redis_client()
        await client.delete(key)
        return True
    except Exception as e:
        logger.debug(f"[Redis Cache] cache_delete('{key}') failed: {e}")
        return False


async def cache_delete_pattern(pattern: str) -> bool:
    """
    Invalidate all keys matching a glob pattern (e.g. 'templates:*').
    """
    try:
        client = await get_redis_client()
        keys = await client.keys(pattern)
        if keys:
            await client.delete(*keys)
        return True
    except Exception as e:
        logger.debug(f"[Redis Cache] cache_delete_pattern('{pattern}') failed: {e}")
        return False


class CacheKeys:
    """Centralized, deterministic cache key builder."""

    @staticmethod
    def template(slug: str) -> str:
        return f"template:{slug}"

    @staticmethod
    def template_list(page: int, filters: str) -> str:
        return f"templates:list:{page}:{filters}"

    @staticmethod
    def featured(limit: int = 8) -> str:
        return f"templates:featured:{limit}"

    @staticmethod
    def categories() -> str:
        return "categories:all"

    @staticmethod
    def user_favorites(user_id: str) -> str:
        return f"user:{user_id}:favorites"

    @staticmethod
    def user_wishlist(user_id: str) -> str:
        return f"user:{user_id}:wishlist"

    @staticmethod
    def search(query: str, filters: str = "") -> str:
        # Deterministic MD5 hash independent of python process seed
        digest = hashlib.md5(f"{query.lower().strip()}:{filters}".encode("utf-8")).hexdigest()[:16]
        return f"search:{digest}"

    CACHE_TTL_SHORT = 60       # 1 minute
    CACHE_TTL_MEDIUM = 300     # 5 minutes
    CACHE_TTL_LONG = 3600      # 1 hour
    CACHE_TTL_DAY = 86400      # 24 hours
