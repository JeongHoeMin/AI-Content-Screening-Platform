"""Persist deterministic dashboard collection filter conditions.

Revision ID: 20260805_01
Revises: 20260804_01
Create Date: 2026-08-05
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

from app.persistence.schema import collection_filter_snapshots

revision = "20260805_01"
down_revision = "20260804_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create filter snapshots for databases migrated before this table existed."""
    inspector = inspect(op.get_bind())
    if "collection_filter_snapshots" not in inspector.get_table_names():
        collection_filter_snapshots.create(op.get_bind())


def downgrade() -> None:
    """Remove only the collection-filter snapshot table."""
    inspector = inspect(op.get_bind())
    if "collection_filter_snapshots" in inspector.get_table_names():
        collection_filter_snapshots.drop(op.get_bind())
