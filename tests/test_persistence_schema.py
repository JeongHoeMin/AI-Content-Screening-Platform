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
