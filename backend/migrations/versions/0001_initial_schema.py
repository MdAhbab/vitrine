"""Initial schema — all Vitrine tables.

Revision ID: 0001
Revises:
Create Date: 2026-06-09
"""
from __future__ import annotations

from alembic import op

from backend.shared.db import Base
from backend.shared import models  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
