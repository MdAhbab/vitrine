"""Redis event-bus delivery guarantees (AGENTS.md §7).

These exercise _RedisBus._handle against a fake Redis so the ack / retry /
dead-letter decisions are covered without needing a live server.
"""
from __future__ import annotations

import json

import pytest

from backend.shared.events import MAX_DELIVERIES, STREAM, GROUP, _RedisBus, make_event


class FakeRedis:
    def __init__(self):
        self.acked: list[str] = []
        self.dead: list[dict] = []

    async def xack(self, stream, group, msg_id):
        assert (stream, group) == (STREAM, GROUP)
        self.acked.append(msg_id)

    async def xadd(self, stream, fields):
        self.dead.append({"stream": stream, **fields})


def _fields(event: dict) -> dict:
    return {"data": json.dumps(event)}


@pytest.mark.asyncio
async def test_successful_handler_acks_once():
    bus, r = _RedisBus(), FakeRedis()
    seen = []
    bus.subscribe("listing.created", lambda e: _record(seen, e))
    await bus._handle(r, "1-0", _fields(make_event("listing.created", {"id": "a"})))
    assert len(seen) == 1
    assert r.acked == ["1-0"]
    assert r.dead == []


@pytest.mark.asyncio
async def test_failing_handler_is_not_acked_so_it_gets_redelivered():
    """Regression: the consumer used to ack unconditionally, so a handler crash
    silently dropped the event and left the listing wedged mid-pipeline."""
    bus, r = _RedisBus(), FakeRedis()

    async def boom(_event):
        raise RuntimeError("handler exploded")

    bus.subscribe("listing.created", boom)
    await bus._handle(r, "1-0", _fields(make_event("listing.created", {"id": "a"})))
    assert r.acked == [], "a failed event must stay pending for redelivery"
    assert r.dead == []


@pytest.mark.asyncio
async def test_repeated_failure_dead_letters_and_then_acks():
    bus, r = _RedisBus(), FakeRedis()

    async def boom(_event):
        raise RuntimeError("handler exploded")

    bus.subscribe("listing.created", boom)
    fields = _fields(make_event("listing.created", {"id": "a"}))
    for _ in range(MAX_DELIVERIES):
        await bus._handle(r, "1-0", fields)

    assert len(r.dead) == 1, "poison event must land on the dead-letter stream"
    assert "handler exploded" in r.dead[0]["reason"]
    assert r.acked == ["1-0"], "dead-lettered event is acked so the group moves on"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    "not json at all",
    '"a bare string"',
    "[1, 2, 3]",
    '{"no_type_key": true}',
])
async def test_structurally_invalid_events_dead_letter_immediately(payload):
    """Regression: valid JSON of the wrong shape raised past every ack path.
    Combined with self-reclaim of unacked messages, that retried forever."""
    bus, r = _RedisBus(), FakeRedis()
    await bus._handle(r, "1-0", {"data": payload})
    assert len(r.dead) == 1, "retrying cannot fix a malformed envelope"
    assert r.acked == ["1-0"]


@pytest.mark.asyncio
async def test_duplicate_delivery_is_skipped_after_success():
    bus, r = _RedisBus(), FakeRedis()
    seen = []
    bus.subscribe("listing.created", lambda e: _record(seen, e))
    event = make_event("listing.created", {"id": "a"}, idempotency_key="listing:a:v1")
    await bus._handle(r, "1-0", _fields(event))
    await bus._handle(r, "1-1", _fields(event))
    assert len(seen) == 1, "idempotency key must suppress the second delivery"
    assert r.acked == ["1-0", "1-1"]


@pytest.mark.asyncio
async def test_failed_event_is_not_marked_seen():
    """Dedupe is recorded only after success, so a crash mid-handler still gets
    a real retry instead of being skipped as a duplicate."""
    bus, r = _RedisBus(), FakeRedis()
    attempts = []

    async def flaky(event):
        attempts.append(event)
        if len(attempts) == 1:
            raise RuntimeError("transient")

    bus.subscribe("listing.created", flaky)
    event = make_event("listing.created", {"id": "a"}, idempotency_key="listing:a:v1")
    await bus._handle(r, "1-0", _fields(event))
    await bus._handle(r, "1-0", _fields(event))
    assert len(attempts) == 2
    assert r.acked == ["1-0"], "acked only once the retry succeeded"


async def _record(sink: list, event: dict) -> None:
    sink.append(event)
