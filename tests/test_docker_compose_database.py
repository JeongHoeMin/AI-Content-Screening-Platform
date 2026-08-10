from __future__ import annotations

from pathlib import Path


def test_compose_defines_healthy_postgres_with_persistent_volume() -> None:
    compose: str = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "postgres:" in compose
    assert "postgres_data:" in compose
    assert "pg_isready" in compose
    assert "DATABASE_URL:" in compose
    assert "condition: service_healthy" in compose
    assert "env_file:" not in compose
    assert "OPENAI_API_KEY:" in compose
    assert "KRX_API_KEY:" in compose
    assert "IR_RSS_FEEDS:" in compose
    assert "schedule-worker:" in compose
    assert "app.scheduled_worker" in compose
    assert "SCHEDULE_SETTINGS_PASSWORD:" in compose
    assert "db-migrate:" in compose
    assert "service_completed_successfully" in compose


def test_compose_serves_the_next_frontend_against_the_dashboard_api() -> None:
    compose: str = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "frontend:" in compose
    assert "context: ./frontend" in compose
    assert "API_BASE_URL: http://dashboard:8000" in compose
    assert '"3000:3000"' in compose


def test_frontend_image_runs_the_standalone_server_as_a_non_root_user() -> None:
    dockerfile: str = Path("frontend/Dockerfile").read_text(encoding="utf-8")

    assert "ARG API_BASE_URL" in dockerfile
    assert "USER nextjs" in dockerfile
    assert 'CMD ["node", "server.js"]' in dockerfile


def test_compose_forwards_optional_kis_configuration_to_runtime_services() -> None:
    compose: str = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert compose.count("KIS_APP_KEY: ${KIS_APP_KEY:-}") == 2
    assert compose.count("KIS_APP_SECRET: ${KIS_APP_SECRET:-}") == 2
    assert compose.count("KIS_ACCOUNT_PRODUCT_CODE: ${KIS_ACCOUNT_PRODUCT_CODE:-01}") == 2
    assert compose.count(
        "KIS_BASE_URL: ${KIS_BASE_URL:-https://openapi.koreainvestment.com:9443}"
    ) == 2
    assert compose.count("KIS_TIMEOUT_SECONDS: ${KIS_TIMEOUT_SECONDS:-10}") == 2
