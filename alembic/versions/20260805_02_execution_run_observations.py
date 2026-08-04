"""Persist safe terminal workflow execution observations.

Revision ID: 20260805_02
Revises: 20260805_01
Create Date: 2026-08-05
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

from app.persistence.schema import workflow_execution_audits

revision = "20260805_02"
down_revision = "20260805_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create durable, content-free workflow audit storage."""
    inspector = inspect(op.get_bind())
    if "workflow_execution_audits" not in inspector.get_table_names():
        workflow_execution_audits.create(op.get_bind())


def downgrade() -> None:
    """Remove only workflow audit observations."""
    inspector = inspect(op.get_bind())
    if "workflow_execution_audits" in inspector.get_table_names():
        workflow_execution_audits.drop(op.get_bind())
