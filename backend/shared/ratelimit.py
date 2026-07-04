"""Token-bucket rate limiter — memory (dev) or Redis (production)."""
from __future__ import annotations

import time

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
    _PRUNE_EVERY = 512  # amortised cleanup cadence (checks between sweeps)

    def __init__(self) -> None:
        self._buckets: dict[str, tuple[float, int]] = {}
        self._checks_since_prune = 0

    def _prune(self, now: float) -> None:
        """Drop expired buckets so the map can't grow one entry per client IP
        forever (a slow but unbounded memory leak under real traffic)."""
        self._buckets = {k: v for k, v in self._buckets.items() if v[0] > now}

    async def check(self, key: str, limit: int, window: int) -> None:
        now = time.time()
        self._checks_since_prune += 1
        if self._checks_since_prune >= self._PRUNE_EVERY:
            self._checks_since_prune = 0
            self._prune(now)
        reset_at, count = self._buckets.get(key, (0.0, 0))
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
    ip = request.client.host if request.client else "unknown"
    # Only trust X-Forwarded-For behind a known reverse proxy (TRUST_PROXY_HEADERS).
    # Our nginx appends the real client as the LAST hop, so the rightmost entry is
    # authoritative — taking the leftmost (client-supplied) value lets anyone mint
    # a fresh bucket per request and bypass the limiter entirely.
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            if parts:
                ip = parts[-1]
    return f"{scope}:{ip}"


async def enforce_rate_limit(request: Request, *, scope: str, limit: int, window: int) -> None:
    await _limiter.check(client_key(request, scope), limit, window)
