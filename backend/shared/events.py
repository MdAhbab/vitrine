"""
EventBus — the async event spine.

Two backends, chosen by settings.EVENT_BUS:
  * 'memory' (default): in-process asyncio pub/sub.
  * 'redis': Redis Streams + consumer groups (at-least-once, multi-process).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from .settings import settings

_log = logging.getLogger("vitrine.eventbus")

Handler = Callable[[dict], Awaitable[None]]
STREAM = "vitrine:events"
GROUP = "vitrine-workers"
# Failed events land here for inspection/replay instead of vanishing.
DEAD_LETTER_STREAM = "vitrine:events:dead"
# Redeliveries tolerated before an event is dead-lettered (AGENTS.md §7).
MAX_DELIVERIES = 3


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
        # Hold strong refs to in-flight handler tasks. Without this, Python may
        # garbage-collect a running task mid-execution (see asyncio docs), which
        # would silently drop pipeline events (listing.created -> intake, ...).
        self._tasks: set[asyncio.Task] = set()

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subs[topic].append(handler)

    async def publish(self, type_: str, payload: dict, **kw) -> None:
        event = make_event(type_, payload, **kw)
        handlers: list[Handler] = list(self._subs.get(type_, []))
        prefix = type_.split(".", 1)[0] + ".*"
        handlers += self._subs.get(prefix, [])
        for h in handlers:
            task = asyncio.create_task(_safe(h, event))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)


class _RedisBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)
        self._redis = None
        self._consumer_task: asyncio.Task | None = None
        self._seen: set[str] = set()
        self._deliveries: dict[str, int] = {}

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

    async def _dead_letter(self, r, msg_id: str, payload: str, reason: str) -> None:
        """Park a message that will never succeed, then ack it so the consumer
        group can move on. Without this a poison event is retried forever."""
        try:
            await r.xadd(DEAD_LETTER_STREAM, {
                "data": payload,
                "reason": reason[:500],
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "original_id": msg_id,
            })
        except Exception:
            _log.exception("[eventbus] could not write dead letter for %s", msg_id)
        await r.xack(STREAM, GROUP, msg_id)

    async def _handle(self, r, msg_id: str, fields: dict) -> None:
        payload = fields.get("data", "")
        try:
            event = json.loads(payload)
        except Exception as exc:
            # Unparseable: retrying cannot help.
            await self._dead_letter(r, msg_id, payload, f"malformed envelope: {exc}")
            return

        idem = event.get("idempotency_key", msg_id)
        if idem in self._seen:
            await r.xack(STREAM, GROUP, msg_id)
            return

        # Run every handler, collecting failures. `_safe` swallows exceptions so
        # one failing handler cannot prevent the others from running.
        failures = [exc for exc in
                    [await _safe(h, event) for h in self._handlers_for(event["type"])]
                    if exc is not None]

        if not failures:
            # Only mark as seen once it actually succeeded — marking on receipt
            # meant a redelivery after a crash was skipped as a duplicate.
            self._seen.add(idem)
            if len(self._seen) > 10_000:
                self._seen.clear()
            await r.xack(STREAM, GROUP, msg_id)
            return

        # Leave unacked so the group redelivers it. Previously the ack happened
        # unconditionally, so a handler crash silently dropped the event and the
        # listing stayed wedged mid-pipeline with no retry and no trace.
        reason = "; ".join(str(e) for e in failures)
        deliveries = self._deliveries.get(msg_id, 0) + 1
        self._deliveries[msg_id] = deliveries
        if deliveries >= MAX_DELIVERIES:
            _log.error("[eventbus] dead-lettering %s after %d attempts: %s",
                       msg_id, deliveries, reason)
            self._deliveries.pop(msg_id, None)
            await self._dead_letter(r, msg_id, payload, reason)
        else:
            _log.warning("[eventbus] handler failure on %s (attempt %d/%d): %s",
                         event.get("type"), deliveries, MAX_DELIVERIES, reason)

    async def _consume_loop(self) -> None:
        r = await self._client()
        consumer = f"worker-{uuid.uuid4().hex[:8]}"
        while True:
            try:
                # ">" delivers new messages; "0" reclaims this consumer's own
                # unacked backlog so retries actually happen after a failure.
                for start_id in (">", "0"):
                    rows = await r.xreadgroup(GROUP, consumer, {STREAM: start_id},
                                              count=10, block=2000 if start_id == ">" else 0)
                    for _stream, messages in rows or []:
                        for msg_id, fields in messages:
                            try:
                                await self._handle(r, msg_id, fields)
                            except Exception:
                                _log.exception("[eventbus] consumer error on %s", msg_id)
            except asyncio.CancelledError:
                break
            except Exception:
                _log.exception("[eventbus] redis loop error")
                await asyncio.sleep(1)


async def _safe(handler: Handler, event: dict) -> Exception | None:
    """Run a handler, returning the exception instead of raising it.

    Returning it (rather than only logging) is what lets the Redis consumer
    decide whether to ack, retry, or dead-letter — it previously had no way to
    tell a successful handler from a failed one.
    """
    try:
        await handler(event)
        return None
    except Exception as exc:
        # Full traceback, not just the message — a swallowed handler error here
        # is otherwise invisible (dropped pipeline event with no trace).
        _log.exception("[eventbus] handler error on %s", event.get("type"))
        return exc


def get_bus() -> _MemoryBus | _RedisBus:
    if settings.EVENT_BUS == "redis":
        return _RedisBus()
    return _MemoryBus()


bus = get_bus()
