"""Persist KST scheduled recommendation jobs and terminal execution references.

Revision ID: 20260805_03
Revises: 20260805_02
Create Date: 2026-08-05
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

from app.persistence.schema import (
    scheduled_recommendation_executions,
    scheduled_recommendation_jobs,
)

revision = "20260805_03"
down_revision = "20260805_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create schedule storage without changing existing source or audit data."""
    inspector = inspect(op.get_bind())
    if "scheduled_recommendation_jobs" not in inspector.get_table_names():
        scheduled_recommendation_jobs.create(op.get_bind())
    if "scheduled_recommendation_executions" not in inspector.get_table_names():
        scheduled_recommendation_executions.create(op.get_bind())


def downgrade() -> None:
    """Remove only scheduled recommendation operational data."""
    inspector = inspect(op.get_bind())
    if "scheduled_recommendation_executions" in inspector.get_table_names():
        scheduled_recommendation_executions.drop(op.get_bind())
    if "scheduled_recommendation_jobs" in inspector.get_table_names():
        scheduled_recommendation_jobs.drop(op.get_bind())
