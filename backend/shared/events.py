"""
EventBus — the async event spine.

Two backends, chosen by settings.EVENT_BUS:
  * 'memory' (default): in-process asyncio pub/sub.
  * 'redis': Redis Streams + consumer groups (at-least-once, multi-process).
"""
from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from .settings import settings

Handler = Callable[[dict], Awaitable[None]]
STREAM = "vitrine:events"
GROUP = "vitrine-workers"


def make_event(type_: str, payload: dict, *, actor: str = "system",
               idempotency_key: str | None = None) -> dict[str, Any]:
    return {
        "event_id": uuid.uuid4().hex,
        "type": type_,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "idempotency_key": idempotency_key or uuid.uuid4().hex,
        "payload": payload,
    }


class _MemoryBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subs[topic].append(handler)

    async def publish(self, type_: str, payload: dict, **kw) -> None:
        event = make_event(type_, payload, **kw)
        handlers: list[Handler] = list(self._subs.get(type_, []))
        prefix = type_.split(".", 1)[0] + ".*"
        handlers += self._subs.get(prefix, [])
        for h in handlers:
            asyncio.create_task(_safe(h, event))


class _RedisBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)
        self._redis = None
        self._consumer_task: asyncio.Task | None = None
        self._seen: set[str] = set()

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subs[topic].append(handler)

    async def _client(self):
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            try:
                await self._redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
            except Exception:
                pass
        return self._redis

    def _handlers_for(self, type_: str) -> list[Handler]:
        handlers = list(self._subs.get(type_, []))
        prefix = type_.split(".", 1)[0] + ".*"
        handlers += self._subs.get(prefix, [])
        return handlers

    async def publish(self, type_: str, payload: dict, **kw) -> None:
        # Only enqueue. The consumer loop (start_consumer) is the SINGLE place
        # that dispatches to handlers — dispatching here too would double-run
        # every handler in the publishing process.
        event = make_event(type_, payload, **kw)
        r = await self._client()
        await r.xadd(STREAM, {"data": json.dumps(event)})

    async def start_consumer(self) -> None:
        if self._consumer_task:
            return
        self._consumer_task = asyncio.create_task(self._consume_loop())

    async def _consume_loop(self) -> None:
        r = await self._client()
        consumer = f"worker-{uuid.uuid4().hex[:8]}"
        while True:
            try:
                rows = await r.xreadgroup(GROUP, consumer, {STREAM: ">"}, count=10, block=2000)
                if not rows:
                    continue
                for _stream, messages in rows:
                    for msg_id, fields in messages:
                        try:
                            event = json.loads(fields["data"])
                            idem = event.get("idempotency_key", msg_id)
                            if idem in self._seen:
                                await r.xack(STREAM, GROUP, msg_id)
                                continue
                            self._seen.add(idem)
                            if len(self._seen) > 10_000:
                                self._seen.clear()
                            for h in self._handlers_for(event["type"]):
                                await _safe(h, event)
                            await r.xack(STREAM, GROUP, msg_id)
                        except Exception as exc:
                            print(f"[eventbus] redis consumer error: {exc}")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                print(f"[eventbus] redis loop error: {exc}")
                await asyncio.sleep(1)


async def _safe(handler: Handler, event: dict) -> None:
    try:
        await handler(event)
    except Exception as exc:
        print(f"[eventbus] handler error on {event['type']}: {exc}")


def get_bus() -> _MemoryBus | _RedisBus:
    if settings.EVENT_BUS == "redis":
        return _RedisBus()
    return _MemoryBus()


bus = get_bus()
