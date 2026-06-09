"""
EventBus — the async event spine.

Two backends, chosen by settings.EVENT_BUS:
  * 'memory' (default): in-process asyncio pub/sub. Zero dependencies — perfect
    for SQLite-only local dev where all services run in ONE process (the
    gateway monolith). Events do NOT cross process boundaries.
  * 'redis': Redis Streams + consumer groups (at-least-once, multi-process).
    Use this once services run as separate processes / on the VM.

Envelope mirrors backend.md §3. Handlers are `async def handler(event: dict)`.

NOTE (scaffold): the memory bus is functional; the redis bus is a thin stub
to be completed in Phase 2 (see backend.md step-by-step).
"""
from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from .settings import settings

Handler = Callable[[dict], Awaitable[None]]


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
        # match exact topic and wildcard prefix subscribers (e.g. 'listing.*')
        handlers: list[Handler] = list(self._subs.get(type_, []))
        prefix = type_.split(".", 1)[0] + ".*"
        handlers += self._subs.get(prefix, [])
        for h in handlers:
            asyncio.create_task(_safe(h, event))


async def _safe(handler: Handler, event: dict) -> None:
    try:
        await handler(event)
    except Exception as exc:  # noqa: BLE001 — never let one handler kill the bus
        print(f"[eventbus] handler error on {event['type']}: {exc}")


class _RedisBus:
    """TODO(Phase 2): Redis Streams implementation.

    publish -> XADD stream <type>. subscribe -> XREADGROUP consumer loop with
    acks, idempotency dedupe on idempotency_key, and a dead-letter after
    MAX_DELIVERIES. See backend.md §3.
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "Redis EventBus not implemented yet — set EVENT_BUS=memory for now."
        )


def get_bus() -> _MemoryBus:
    if settings.EVENT_BUS == "redis":
        return _RedisBus()  # type: ignore[return-value]
    return _MemoryBus()


bus = get_bus()
