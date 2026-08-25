"""
Redis client — async connection pool via redis-py.
"""

from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

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


class CacheKeys:
    """Centralized cache key builder."""

    @staticmethod
    def template(slug: str) -> str:
        return f"template:{slug}"

    @staticmethod
    def template_list(page: int, filters: str) -> str:
        return f"templates:list:{page}:{filters}"

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
    def search(query: str, filters: str) -> str:
        return f"search:{hash(query + filters)}"

    CACHE_TTL_SHORT = 60       # 1 minute
    CACHE_TTL_MEDIUM = 300     # 5 minutes
    CACHE_TTL_LONG = 3600      # 1 hour
    CACHE_TTL_DAY = 86400      # 24 hours
