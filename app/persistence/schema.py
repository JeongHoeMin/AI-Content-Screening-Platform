from __future__ import annotations

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata: MetaData = MetaData()

source_documents: Table = Table(
    "source_documents",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("source", String(32), nullable=False),
    Column("external_id", String(255), nullable=False),
    Column("canonical_url", Text, nullable=False),
    Column("content_sha256", String(64), nullable=True),
    Column("title", Text, nullable=False),
    Column("content", Text, nullable=True),
    Column("published_at", DateTime(timezone=True), nullable=False),
    Column("analysis_eligible", Integer, nullable=False),
    Column("quality_status", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("source", "external_id"),
    UniqueConstraint("canonical_url"),
)

document_paragraphs: Table = Table(
    "document_paragraphs",
    metadata,
    Column("document_id", String(36), ForeignKey("source_documents.id"), primary_key=True),
    Column("paragraph_index", Integer, primary_key=True),
    Column("content", Text, nullable=False),
)

extracted_events: Table = Table(
    "extracted_events",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("document_id", String(36), ForeignKey("source_documents.id"), nullable=False),
    Column("event_index", Integer, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("document_id", "event_index"),
)

event_evidence: Table = Table(
    "event_evidence",
    metadata,
    Column("event_id", String(36), ForeignKey("extracted_events.id"), primary_key=True),
    Column("evidence_index", Integer, primary_key=True),
    Column("document_id", String(36), ForeignKey("source_documents.id"), nullable=False),
    Column("paragraph_index", Integer, nullable=False),
    Column("quote", String(280), nullable=False),
)

deduplication_comparisons: Table = Table(
    "deduplication_comparisons",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("left_event_id", String(36), ForeignKey("extracted_events.id"), nullable=False),
    Column("right_event_id", String(36), ForeignKey("extracted_events.id"), nullable=False),
    Column("relation", String(16), nullable=False),
    Column("confidence", Integer, nullable=False),
    Column("reasons", JSON, nullable=False),
    CheckConstraint("confidence >= 0 AND confidence <= 100"),
    UniqueConstraint("left_event_id", "right_event_id"),
)

canonical_event_memberships: Table = Table(
    "canonical_event_memberships",
    metadata,
    Column("event_id", String(36), ForeignKey("extracted_events.id"), primary_key=True),
    Column("canonical_event_id", String(36), ForeignKey("extracted_events.id"), nullable=False),
    Column("reason", String(64), nullable=False),
)
