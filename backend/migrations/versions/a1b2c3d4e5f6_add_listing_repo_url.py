"""Add listings.repo_url

The Repo-Intake agent has always taken a repository URL as its primary input,
but the listing row had nowhere to keep it — so the URL lived only inside the
event payload and was lost the moment the run finished. Sellers reopening the
editor saw an empty field and re-runs had nothing to work from.

Revision ID: a1b2c3d4e5f6
Revises: c70ecd2438af
Create Date: 2026-08-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'c70ecd2438af'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('repo_url', sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column('listings', 'repo_url')
