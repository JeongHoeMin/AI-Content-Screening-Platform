from __future__ import annotations

from pathlib import Path


def test_initial_persistence_migration_creates_all_schema_tables() -> None:
    migration: str = Path(
        "alembic/versions/20260804_01_trusted_content_persistence.py"
    ).read_text(encoding="utf-8")

    for table_name in (
        "source_documents",
        "document_paragraphs",
        "extracted_events",
        "event_evidence",
        "deduplication_comparisons",
        "canonical_event_memberships",
    ):
        assert table_name in migration
