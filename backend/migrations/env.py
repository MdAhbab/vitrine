"""Alembic environment.

Reads the app's DATABASE_URL (converting the async driver to a sync one for
Alembic), targets the shared models metadata, and enables batch mode so SQLite
can run ALTERs. Generate migrations with:

    cd backend && alembic revision --autogenerate -m "message"
    cd backend && alembic upgrade head
"""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# make `backend` importable when alembic runs from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.shared.db import Base  # noqa: E402
from backend.shared import models  # noqa: E402,F401  (register tables)
from backend.shared.settings import settings  # noqa: E402

config = context.config

_sync_url = (settings.DATABASE_URL
             .replace("+aiosqlite", "")
             .replace("+asyncpg", "+psycopg2"))
config.set_main_option("sqlalchemy.url", _sync_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=_sync_url, target_metadata=target_metadata,
                      literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
