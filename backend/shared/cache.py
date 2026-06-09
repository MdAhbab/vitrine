"""
Cache + AI result cache (content-hash keyed).

'memory' (default): in-process dict with TTL. 'redis': Redis GET/SETEX.
Used by the AI orchestrator to make identical agent runs cost $0 (see AGENTS.md
principle #4) and for general short-TTL caching.
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
    """TODO(Phase 2): Redis-backed cache (redis.asyncio)."""

    def __init__(self) -> None:
        raise NotImplementedError("Redis cache not implemented — set CACHE=memory.")


def get_cache() -> _MemoryCache:
    if settings.CACHE == "redis":
        return _RedisCache()  # type: ignore[return-value]
    return _MemoryCache()


cache = get_cache()
