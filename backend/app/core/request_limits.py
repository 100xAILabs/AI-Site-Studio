"""Small shared rate limit helpers for expensive authenticated operations."""

import time
import hashlib
from collections import defaultdict, deque

from fastapi import HTTPException, status

from app.core.redis import get_redis

_local_windows: dict[str, deque[float]] = defaultdict(deque)


async def enforce_key_limit(subject: str, operation: str, limit: int = 10, window_seconds: int = 900) -> None:
    """Limit a public operation by a caller supplied stable subject (IP/email)."""
    digest = hashlib.sha256(subject.encode("utf-8", errors="replace")).hexdigest()
    key = f"ratelimit:{operation}:{digest}"
    redis = await get_redis()
    if redis:
        try:
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, window_seconds)
            if count > limit:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests. Please try again later.")
            return
        except HTTPException:
            raise
        except Exception:
            # Preserve a local per-process limit when Redis is configured but unavailable.
            pass

    now = time.monotonic()
    bucket = _local_windows[key]
    while bucket and now - bucket[0] >= window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests. Please try again later.")
    bucket.append(now)
    if len(_local_windows) > 10000:
        _local_windows.clear()


async def enforce_user_limit(user_id: str, operation: str, limit: int = 20, window_seconds: int = 900) -> None:
    """Limit repeated cost-bearing operations, using shared Redis when configured."""
    await enforce_key_limit(user_id, operation, limit, window_seconds)
