from __future__ import annotations

from pathlib import Path


def test_compose_defines_healthy_postgres_with_persistent_volume() -> None:
    compose: str = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "postgres:" in compose
    assert "postgres_data:" in compose
    assert "pg_isready" in compose
    assert "DATABASE_URL:" in compose
    assert "condition: service_healthy" in compose
