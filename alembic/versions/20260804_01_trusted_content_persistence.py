"""Create trusted-content persistence tables.

Revision ID: 20260804_01
Revises:
Create Date: 2026-08-04
"""

from __future__ import annotations

from alembic import op

from app.persistence.schema import metadata

revision = "20260804_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create source_documents, document_paragraphs, extracted_events, event_evidence,
    deduplication_comparisons, and canonical_event_memberships."""
    metadata.create_all(op.get_bind())


def downgrade() -> None:
    """Remove the complete trusted-content persistence schema."""
    metadata.drop_all(op.get_bind())
