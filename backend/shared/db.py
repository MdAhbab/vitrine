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


# SQLite needs check_same_thread off for async; Postgres ignores it.
_connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args=_connect_args,
)

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


async def drop_all() -> None:
    from . import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
