from __future__ import annotations

import os

import pytest

from app.config.errors import ConfigurationError
from app.config.persistence import DatabaseConfig, load_database_config


def test_load_database_config_reads_valid_postgres_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://screening:screening@postgres:5432/screening",
    )

    config: DatabaseConfig = load_database_config()

    assert config.url == "postgresql+asyncpg://screening:screening@postgres:5432/screening"


@pytest.mark.parametrize("database_url", ["", "postgresql://localhost/screening", "sqlite:///screening.db"])
def test_load_database_config_rejects_non_asyncpg_postgres_url(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)

    with pytest.raises(ConfigurationError):
        load_database_config()


def test_database_config_redacts_password_in_repr() -> None:
    config: DatabaseConfig = DatabaseConfig(
        url="postgresql+asyncpg://screening:secret@postgres:5432/screening"
    )

    assert "secret" not in repr(config)


def teardown_module() -> None:
    os.environ.pop("DATABASE_URL", None)
