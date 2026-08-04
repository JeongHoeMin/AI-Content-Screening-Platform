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


def test_alembic_environment_uses_asyncpg_migration_connection() -> None:
    """The runtime database URL uses asyncpg, including during migration."""
    environment: str = Path("alembic/env.py").read_text(encoding="utf-8")

    assert "async_engine_from_config" in environment
    assert "connection.run_sync" in environment


def test_collection_filter_snapshot_migration_extends_the_initial_schema() -> None:
    migration: str = Path(
        "alembic/versions/20260805_01_collection_filter_snapshots.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision = "20260804_01"' in migration
    assert "collection_filter_snapshots" in migration
