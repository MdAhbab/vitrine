"""
Cache + AI result cache (content-hash keyed).

'memory' (default): in-process dict with TTL. 'redis': Redis GET/SETEX.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from .settings import settings


def content_hash(*parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


class _MemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        expires, value = item
        if expires and expires < time.time():
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        self._store[key] = (time.time() + ttl if ttl else 0, value)


class _RedisCache:
    def __init__(self) -> None:
        self._redis = None

    async def _client(self):
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def get(self, key: str) -> Any | None:
        r = await self._client()
        raw = await r.get(f"cache:{key}")
        if not raw:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        r = await self._client()
        await r.setex(f"cache:{key}", ttl or 3600, json.dumps(value, default=str))


def get_cache() -> _MemoryCache | _RedisCache:
    if settings.CACHE == "redis":
        return _RedisCache()
    return _MemoryCache()


cache = get_cache()
