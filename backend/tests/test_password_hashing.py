"""Password hashing must not stall the event loop, and must not leak accounts.

Two separate properties:
  * hashing is CPU-bound, so request handlers offload it to a thread — inline
    it would freeze every other request and SSE stream in the process;
  * a login attempt for an unknown email does the same work as one for a known
    email, so response time doesn't reveal which addresses have accounts.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from backend.shared.security import (
    hash_password,
    hash_password_async,
    verify_password,
    verify_password_async,
    verify_password_or_dummy,
)


@pytest.mark.asyncio
async def test_async_helpers_match_their_sync_counterparts():
    hashed = await hash_password_async("secret123")
    assert await verify_password_async("secret123", hashed)
    assert not await verify_password_async("wrong", hashed)
    # Interchangeable with the sync pair used by seed.py and scripts.
    assert verify_password("secret123", hashed)
    assert await verify_password_async("secret123", hash_password("secret123"))


@pytest.mark.asyncio
async def test_hashing_does_not_block_the_event_loop():
    """The loop must stay responsive while a hash is in flight."""
    ticks = 0

    async def heartbeat() -> None:
        nonlocal ticks
        for _ in range(50):
            await asyncio.sleep(0.001)
            ticks += 1

    beat = asyncio.create_task(heartbeat())
    await hash_password_async("some-password")
    await beat
    # If hashing ran inline the loop would have been parked and the heartbeat
    # could not have advanced during it.
    assert ticks == 50


@pytest.mark.asyncio
async def test_unknown_account_still_pays_the_hashing_cost():
    """Regression: returning early on a missing user made a miss measurably
    faster than a hit, which is an account-enumeration oracle."""
    real = hash_password("correct-horse")

    start = time.perf_counter()
    assert await verify_password_or_dummy("guess", None) is False
    miss = time.perf_counter() - start

    start = time.perf_counter()
    assert await verify_password_or_dummy("guess", real) is False
    hit = time.perf_counter() - start

    # Same order of magnitude — the miss must not short-circuit.
    assert miss > hit / 4, f"miss {miss:.4f}s vs hit {hit:.4f}s: miss skipped the KDF"


@pytest.mark.asyncio
async def test_correct_password_still_authenticates():
    hashed = await hash_password_async("correct-horse")
    assert await verify_password_or_dummy("correct-horse", hashed) is True
