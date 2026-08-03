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


async def ensure_schema() -> None:
    """Bring the running database up to date on startup.

    Local SQLite builds the schema from scratch. The cloud deploy ships a
    pre-seeded vitrine.db and therefore never called create_all, which meant
    additive columns and newly-declared indexes silently never reached
    production. The additive step is idempotent (IF NOT EXISTS / tolerated
    failures), so it is safe to run on every boot.
    """
    if not settings.is_sqlite:
        return  # Postgres is managed by Alembic
    if settings.ENV == "local":
        await create_all()
    else:
        await _sqlite_additive_columns()


async def _sqlite_additive_columns() -> None:
    """Add columns and indexes introduced after initial deploy without re-seed.

    `create_all` only creates tables it does not already find, so an existing
    deployed vitrine.db never picks up newly-declared indexes. These mirror the
    `__table_args__` in models.py and are IF NOT EXISTS, so they are a no-op on
    a freshly created database.
    """
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
        # DB-level backstop for the one-review-per-buyer-per-listing invariant
        # (the endpoint's check-then-insert alone is racy under concurrency).
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_review_buyer_listing ON reviews (buyer_id, listing_id)",
        # Composite indexes covering filter+sort together (see models.py).
        "CREATE INDEX IF NOT EXISTS ix_listings_status_score ON listings (status, vitrine_score)",
        "CREATE INDEX IF NOT EXISTS ix_listings_status_category_score ON listings (status, category, vitrine_score)",
        "CREATE INDEX IF NOT EXISTS ix_orders_seller_status ON orders (seller_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_orders_listing_status ON orders (listing_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_orders_buyer_listing_status ON orders (buyer_id, listing_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_orders_provider_ref ON orders (provider_ref)",
        "CREATE INDEX IF NOT EXISTS ix_subscriptions_seller_active ON subscriptions (seller_id, active)",
        "CREATE INDEX IF NOT EXISTS ix_chat_messages_chat_created ON chat_messages (chat_id, created_at)",
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
