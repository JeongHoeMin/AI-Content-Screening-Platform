from __future__ import annotations

from pathlib import Path


PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]


def test_dashboard_image_includes_alembic_migration_artifacts() -> None:
    dockerfile: str = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY alembic ./alembic" in dockerfile
    assert "COPY alembic.ini ./alembic.ini" in dockerfile


def test_alembic_prefers_the_runtime_database_url() -> None:
    environment: str = (PROJECT_ROOT / "alembic" / "env.py").read_text(
        encoding="utf-8"
    )

    assert 'os.environ.get("DATABASE_URL", "").strip()' in environment
    assert 'config.set_main_option("sqlalchemy.url", database_url)' in environment
