"""
Redis client — async connection pool and caching subsystem via redis-py.
Provides robust cache read/write/invalidation helpers with graceful
fallback when Redis is unavailable.
"""

import json
import hashlib
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import re
import ssl
import time
import fnmatch
import asyncio
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger("cache.redis")

_redis_client: Optional[aioredis.Redis] = None
_redis_down_until: float = 0.0
_redis_down_logged: bool = False


def mask_redis_url(url: Optional[str]) -> str:
    """Mask password credentials in Redis URL for safe logging/diagnostics."""
    if not url:
        return "not-configured"
    return re.sub(r"//([^:]+):([^@]+)@", r"//\1:***@", url)


async def get_redis_client() -> Optional[aioredis.Redis]:
    """Return the shared async Redis client (singleton) or None if unavailable/unconfigured."""
    global _redis_client
    if _redis_client is None:
        url = (settings.REDIS_URL or "").strip()
        if not url or not any(url.startswith(scheme) for scheme in ("redis://", "rediss://", "unix://")):
            logger.info("[Redis Cache] REDIS_URL not configured or invalid scheme. Running with in-memory L1 cache only.")
            return None

        # Build connection options for optimal cloud performance & reliability
        connection_kwargs: dict[str, Any] = {
            "encoding": "utf-8",
            "decode_responses": True,
            "max_connections": 20,
            "socket_timeout": 3.0,
            "socket_connect_timeout": 3.0,
            "retry_on_timeout": True,
            "health_check_interval": 30,
        }

        try:
            _redis_client = aioredis.from_url(url, **connection_kwargs)
        except Exception as e:
            logger.error(f"[Redis Cache] Failed to create Redis client for {mask_redis_url(url)}: {e}")
            _redis_client = None

    return _redis_client


async def check_redis_health() -> dict[str, Any]:
    """
    Test live connectivity to Redis and return diagnostic report.
    Useful for health-check endpoints and debugging deployment setup.
    """
    url = (settings.REDIS_URL or "").strip()
    if not url or not any(url.startswith(s) for s in ("redis://", "rediss://", "unix://")):
        return {
            "status": "unconfigured",
            "message": "REDIS_URL environment variable is not set. Cache runs in in-memory mode.",
        }

    masked = mask_redis_url(url)
    client = await get_redis_client()
    if not client:
        return {
            "status": "error",
            "url": masked,
            "message": "Failed to initialize Redis client.",
        }

    t0 = time.time()
    try:
        await asyncio.wait_for(client.ping(), timeout=2.5)
        latency = round((time.time() - t0) * 1000, 2)
        return {
            "status": "connected",
            "url": masked,
            "latency_ms": latency,
        }
    except Exception as e:
        return {
            "status": "unreachable",
            "url": masked,
            "error": f"{type(e).__name__}: {str(e)}",
            "help": "Ensure your cloud host (e.g. Railway, Render) has REDIS_URL configured with a valid, reachable Redis connection string.",
        }


async def get_redis() -> Optional[aioredis.Redis]:
    """FastAPI dependency for Redis access."""
    return await get_redis_client()


def _json_serial(obj: Any) -> Any:
    """JSON serializer helper for UUIDs, Decimals, dates/times, and Pydantic models."""
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "dict"):
        return obj.dict()
    raise TypeError(f"Type {type(obj)} is not JSON serializable")


# L1 In-Memory High-Speed Cache (Fast RAM lookup: <0.1ms, zero network latency)
_memory_cache: dict[str, tuple[float, Any]] = {}


async def cache_get(key: str) -> Optional[Any]:
    """
    Retrieve from L1 memory cache first; fall back to L2 Redis cache.
    Returns None on cache miss.
    """
    global _redis_down_until, _redis_down_logged
    now = time.time()

    # 1. Fast L1 RAM check
    if key in _memory_cache:
        expire_at, val = _memory_cache[key]
        if now < expire_at:
            return val
        _memory_cache.pop(key, None)

    # 2. Check circuit breaker cooldown
    if now < _redis_down_until:
        return None

    # 3. L2 Redis check
    try:
        client = await get_redis_client()
        if not client:
            return None
        raw = await client.get(key)
        if raw is not None:
            val = json.loads(raw)
            # Promote to L1 memory cache for 60 seconds
            _memory_cache[key] = (now + 60, val)
            _redis_down_logged = False
            return val
    except Exception as e:
        _redis_down_until = now + 20.0
        if not _redis_down_logged:
            logger.warning(
                f"[Redis Cache] L2 Redis unreachable ({type(e).__name__}: {e}). "
                f"Falling back to L1 in-memory cache for 20s. Check REDIS_URL in cloud deployment."
            )
            _redis_down_logged = True
    return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    """
    Store in L1 memory cache and L2 Redis cache with TTL.
    """
    global _redis_down_until, _redis_down_logged
    now = time.time()

    # 1. Store in L1 memory cache
    try:
        _memory_cache[key] = (now + ttl, value)
        if len(_memory_cache) > 2000:
            expired = [k for k, (exp, _) in _memory_cache.items() if now >= exp]
            for k in expired:
                _memory_cache.pop(k, None)
    except Exception:
        pass

    # 2. Skip L2 if in circuit-breaker cooldown
    if now < _redis_down_until:
        return True

    # 3. Store in L2 Redis
    try:
        client = await get_redis_client()
        if not client:
            return True
        payload = json.dumps(value, default=_json_serial)
        await client.set(key, payload, ex=ttl)
        _redis_down_logged = False
        return True
    except Exception as e:
        _redis_down_until = now + 20.0
        if not _redis_down_logged:
            logger.warning(
                f"[Redis Cache] L2 cache_set failed ({type(e).__name__}: {e}). Entering 20s fallback mode."
            )
            _redis_down_logged = True
        return True


async def cache_delete(key: str) -> bool:
    """
    Invalidate key from both L1 memory cache and L2 Redis.
    """
    global _redis_down_until
    _memory_cache.pop(key, None)
    if time.time() < _redis_down_until:
        return True

    try:
        client = await get_redis_client()
        if client:
            await client.delete(key)
        return True
    except Exception as e:
        logger.warning(f"[Redis Cache] cache_delete('{key}') failed: {e}")
        return True


async def cache_delete_pattern(pattern: str) -> bool:
    """
    Invalidate all keys matching glob pattern in both L1 memory and L2 Redis.
    """
    global _redis_down_until
    now = time.time()
    to_delete = [k for k in _memory_cache.keys() if fnmatch.fnmatch(k, pattern)]
    for k in to_delete:
        _memory_cache.pop(k, None)

    if now < _redis_down_until:
        return True

    try:
        client = await get_redis_client()
        if client:
            keys = await client.keys(pattern)
            if keys:
                await client.delete(*keys)
        return True
    except Exception as e:
        logger.warning(f"[Redis Cache] cache_delete_pattern('{pattern}') failed: {e}")
        return True


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


from contextlib import asynccontextmanager
import uuid

@asynccontextmanager
async def distributed_lock(lock_key: str, ttl_seconds: int = 600, wait_timeout: float = 30.0):
    """
    Acquire a cross-process distributed lock backed by Redis SET NX EX (F-35).
    Releases atomically using Lua script verifying token ownership.
    Falls back gracefully if Redis is unavailable.
    """
    client = await get_redis_client()
    token = str(uuid.uuid4())
    full_key = f"lock:{lock_key}"
    acquired = False

    if client:
        start_time = time.monotonic()
        while time.monotonic() - start_time < wait_timeout:
            try:
                res = await client.set(full_key, token, ex=ttl_seconds, nx=True)
                if res:
                    acquired = True
                    break
            except Exception as e_lock:
                logger.warning(f"Redis distributed lock acquire error: {e_lock}")
                break
            await asyncio.sleep(0.1)

    try:
        yield acquired
    finally:
        if acquired and client:
            release_lua = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            try:
                await client.eval(release_lua, 1, full_key, token)
            except Exception as e_rel:
                logger.warning(f"Redis distributed lock release error: {e_rel}")

