"""Persist immutable recommendation entry price snapshots.

Revision ID: 20260805_04
Revises: 20260805_03
Create Date: 2026-08-05
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

from app.persistence.schema import recommendation_price_snapshots

revision = "20260805_04"
down_revision = "20260805_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add price snapshot storage without changing existing operational data."""
    inspector = inspect(op.get_bind())
    if "recommendation_price_snapshots" not in inspector.get_table_names():
        recommendation_price_snapshots.create(op.get_bind())


def downgrade() -> None:
    """Remove only recommendation price observations."""
    inspector = inspect(op.get_bind())
    if "recommendation_price_snapshots" in inspector.get_table_names():
        recommendation_price_snapshots.drop(op.get_bind())
