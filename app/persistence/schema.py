from __future__ import annotations

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
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

collection_filter_snapshots: Table = Table(
    "collection_filter_snapshots",
    metadata,
    Column("run_id", String(64), primary_key=True),
    Column("themes", JSON, nullable=False),
    Column("topics", JSON, nullable=False),
    Column("catalog_version", String(64), nullable=False),
    Column("collected_count", Integer, nullable=False),
    Column("accepted_count", Integer, nullable=False),
    Column("excluded_count", Integer, nullable=False),
    Column("rejection_counts", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("collected_count = accepted_count + excluded_count"),
)

workflow_execution_audits: Table = Table(
    "workflow_execution_audits",
    metadata,
    Column("execution_id", String(64), primary_key=True),
    Column("execution_mode", String(32), nullable=False),
    Column("status", String(16), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=False),
    Column("duration_seconds", Float, nullable=False),
    Column("input_article_count", Integer, nullable=False),
    Column("statistics", JSON, nullable=True),
    Column("error_type", String(128), nullable=True),
    CheckConstraint("duration_seconds >= 0"),
    CheckConstraint("input_article_count >= 0"),
)

scheduled_recommendation_jobs: Table = Table(
    "scheduled_recommendation_jobs",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("active", Integer, nullable=False),
    Column("cron_expression", String(128), nullable=False),
    Column("timezone", String(64), nullable=False),
    Column("themes", JSON, nullable=False),
    Column("topics", JSON, nullable=False),
    Column("limit", Integer, nullable=False),
    Column("telegram_enabled", Integer, nullable=False),
    Column("version", Integer, nullable=False),
    Column("next_run_at", DateTime(timezone=True), nullable=False),
    Column("last_run_at", DateTime(timezone=True), nullable=True),
    Column("lease_owner", String(64), nullable=True),
    Column("lease_until", DateTime(timezone=True), nullable=True),
    CheckConstraint("version >= 1"),
)

scheduled_recommendation_executions: Table = Table(
    "scheduled_recommendation_executions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("job_id", String(64), ForeignKey("scheduled_recommendation_jobs.id"), nullable=False),
    Column("scheduled_for", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("status", String(32), nullable=False),
    Column("error_type", String(128), nullable=True),
    UniqueConstraint("job_id", "scheduled_for"),
)

recommendation_price_snapshots: Table = Table(
    "recommendation_price_snapshots",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("run_id", String(64), nullable=False),
    Column("recommendation_index", Integer, nullable=False),
    Column("snapshot_kind", String(16), nullable=False),
    Column("company_id", String(128), nullable=False),
    Column("company_name", Text, nullable=False),
    Column("ticker", String(6), nullable=False),
    Column("action", String(16), nullable=False),
    Column("status", String(16), nullable=False),
    Column("price", Numeric(20, 4), nullable=True),
    Column("currency", String(3), nullable=False),
    Column("basis", String(16), nullable=True),
    Column("provider", String(16), nullable=True),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("trading_date", Date, nullable=True),
    Column("error_kind", String(32), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("run_id", "recommendation_index", "snapshot_kind"),
)
