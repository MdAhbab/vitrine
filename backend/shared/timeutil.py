"""Timezone helpers.

SQLite hands back naive datetimes even for `DateTime(timezone=True)` columns, so
any Python-level comparison against `datetime.now(timezone.utc)` raises
`TypeError: can't compare offset-naive and offset-aware datetimes`. Every model
datetime read back from the DB should go through `as_utc()` before it is
compared or subtracted.

SQL-level comparisons (`select(...).where(Listing.expires_at > now)`) are fine —
SQLAlchemy adapts those itself.
"""
from __future__ import annotations

from datetime import datetime, timezone


def as_utc(dt: datetime | None) -> datetime | None:
    """Return `dt` as timezone-aware UTC, assuming naive values are already UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def is_past(dt: datetime | None) -> bool:
    """True when `dt` is set and lies in the past. Naive-safe."""
    aware = as_utc(dt)
    return aware is not None and aware < datetime.now(timezone.utc)


def is_future(dt: datetime | None) -> bool:
    """True when `dt` is set and lies in the future. Naive-safe."""
    aware = as_utc(dt)
    return aware is not None and aware > datetime.now(timezone.utc)
