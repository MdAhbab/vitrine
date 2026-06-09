"""Token-bucket rate limiter — memory (dev) or Redis (production)."""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from .settings import settings

_redis = None


async def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    if settings.CACHE != "redis":
        return None
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return _redis
    except Exception:
        return None


class _MemoryLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))

    async def check(self, key: str, limit: int, window: int) -> None:
        now = time.time()
        reset_at, count = self._buckets[key]
        if now >= reset_at:
            self._buckets[key] = (now + window, 1)
            return
        if count >= limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Rate limit exceeded — max {limit} requests per {window}s",
            )
        self._buckets[key] = (reset_at, count + 1)


class _RedisLimiter:
    async def check(self, key: str, limit: int, window: int) -> None:
        r = await _get_redis()
        if not r:
            await _memory.check(key, limit, window)
            return
        bucket = f"rl:{key}"
        count = await r.incr(bucket)
        if count == 1:
            await r.expire(bucket, window)
        if count > limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Rate limit exceeded — max {limit} requests per {window}s",
            )


_memory = _MemoryLimiter()
_limiter = _RedisLimiter() if settings.CACHE == "redis" else _memory


def client_key(request: Request, scope: str) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"{scope}:{ip}"


async def enforce_rate_limit(request: Request, *, scope: str, limit: int, window: int) -> None:
    await _limiter.check(client_key(request, scope), limit, window)
