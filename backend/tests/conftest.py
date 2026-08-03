"""Pytest fixtures — in-memory SQLite for isolated tests."""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.shared.db import Base
from backend.shared import models  # noqa: F401


@pytest.fixture(autouse=True)
def _no_live_llm_calls(monkeypatch):
    """Tests must never reach a real model provider.

    `.env` carries working OPENAI/GEMINI keys for local development, and the
    client builds its env-key clients lazily, so any test touching an agent path
    would otherwise bill a real request (and block on it).
    """
    async def _none():
        return []

    from backend.ai.client import client
    monkeypatch.setattr(client, "_resolved_clients", _none)
    monkeypatch.setattr(client, "_get_configured_clients", _none)


@pytest_asyncio.fixture(autouse=True)
async def _drain_background_tasks():
    """Settle fire-and-forget agent replies before the test loop closes.

    Endpoints like /chats/negotiate/start spawn a background reply task that
    uses the *global* SessionLocal, not the per-test engine — so without this
    its aiosqlite worker thread calls back into a closed loop during teardown.
    """
    yield
    from backend.services.chats.app import drain_agent_replies
    await drain_agent_replies(timeout=5.0)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    # Dispose while the loop is still running, otherwise aiosqlite's worker
    # thread calls back into a closed loop during GC.
    await engine.dispose()
