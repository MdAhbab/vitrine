"""
Async SQLAlchemy engine/session, dialect-agnostic.

Works on SQLite (now) and Postgres (later) unchanged — models use only
portable column types (String, Integer, Boolean, DateTime, JSON, Text).
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .settings import settings


class Base(DeclarativeBase):
    """Declarative base for all models (see shared/models.py)."""


# SQLite needs check_same_thread off for async; `timeout` is the busy-wait
# (seconds) so concurrent writers (background event handlers + requests) wait
# instead of erroring with "database is locked". Postgres ignores these.
_connect_args = {"check_same_thread": False, "timeout": 30} if settings.is_sqlite else {}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args=_connect_args,
)

if settings.is_sqlite:
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")      # concurrent readers + 1 writer
        cur.execute("PRAGMA busy_timeout=30000")     # 30s wait on lock
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a request-scoped session."""
    async with SessionLocal() as session:
        yield session


async def create_all() -> None:
    """Dev bootstrap (SQLite): create every table from the models metadata.

    Production uses Alembic migrations instead (see backend.md step-by-step).
    """
    from . import models  # noqa: F401  (register mappers)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    if settings.is_sqlite:
        await _sqlite_additive_columns()


async def _sqlite_additive_columns() -> None:
    """Add columns introduced after initial deploy without full re-seed."""
    from sqlalchemy import text

    alters = [
        "ALTER TABLE users ADD COLUMN banned_until DATETIME",
        "ALTER TABLE chat_messages ADD COLUMN attachments JSON DEFAULT '[]'",
        "ALTER TABLE listings ADD COLUMN expires_at DATETIME",
        "ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN location VARCHAR(120) DEFAULT ''",
        "ALTER TABLE users ADD COLUMN theme_default VARCHAR(16) DEFAULT 'dark'",
        "ALTER TABLE users ADD COLUMN minimal_profile BOOLEAN DEFAULT 0",
        "ALTER TABLE users ADD COLUMN ai_points INTEGER DEFAULT 100",
    ]
    async with engine.begin() as conn:
        for stmt in alters:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass  # column already exists


async def drop_all() -> None:
    from . import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
