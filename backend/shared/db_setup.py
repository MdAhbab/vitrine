"""
DB bootstrap helper (invoked by run.py locally and the container entrypoint on the VM).

    python -m backend.shared.db_setup --ensure        # create tables if missing
    python -m backend.shared.db_setup --drop-create    # wipe + recreate

SQLite: this IS the schema setup (create_all). Postgres: prefer Alembic
migrations for real changes; --ensure is still handy for a fresh dev DB.
"""
from __future__ import annotations

import argparse
import asyncio

from .db import create_all, drop_all
from .settings import settings


async def _run(drop: bool) -> None:
    if drop:
        print("[db_setup] dropping all tables...")
        await drop_all()
    print(f"[db_setup] creating tables on {settings.DATABASE_URL.split('://')[0]}...")
    await create_all()
    print("[db_setup] done.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ensure", action="store_true")
    ap.add_argument("--drop-create", action="store_true")
    args = ap.parse_args()
    asyncio.run(_run(drop=args.drop_create))


if __name__ == "__main__":
    main()
