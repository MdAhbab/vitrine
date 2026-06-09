"""Tiny id/slug helpers shared across services."""
from __future__ import annotations

import re
import secrets
import uuid


def new_id() -> str:
    return uuid.uuid4().hex


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or new_id()[:8]


def license_key() -> str:
    raw = secrets.token_hex(10).upper()
    return "-".join(raw[i:i + 5] for i in range(0, 20, 5))
