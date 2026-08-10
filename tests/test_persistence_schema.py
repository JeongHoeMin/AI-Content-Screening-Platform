from __future__ import annotations

from app.persistence.schema import metadata


def test_persistence_schema_defines_required_audit_tables() -> None:
    assert set(metadata.tables) == {
        "source_documents",
        "document_paragraphs",
        "extracted_events",
        "event_evidence",
        "deduplication_comparisons",
        "canonical_event_memberships",
        "collection_filter_snapshots",
        "workflow_execution_audits",
        "scheduled_recommendation_jobs",
        "scheduled_recommendation_executions",
        "recommendation_price_snapshots",
    }


def test_source_document_schema_prevents_reprocessing_by_source_or_url() -> None:
    table = metadata.tables["source_documents"]
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert ("source", "external_id") in unique_columns
    assert ("canonical_url",) in unique_columns


def test_workflow_execution_audit_schema_contains_only_safe_terminal_fields() -> None:
    table = metadata.tables["workflow_execution_audits"]

    assert set(table.columns.keys()) == {
        "execution_id",
        "execution_mode",
        "status",
        "started_at",
        "finished_at",
        "duration_seconds",
        "input_article_count",
        "statistics",
        "error_type",
    }
