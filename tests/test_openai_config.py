from __future__ import annotations

import pytest

from app.config import ConfigurationError, load_openai_config


def test_load_openai_config_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("OPENAI_MAX_RETRIES", raising=False)

    config = load_openai_config()

    assert config.model == "gpt-4o-mini"
    assert config.timeout_seconds == 60.0
    assert config.max_retries == 2


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("OPENAI_TIMEOUT_SECONDS", "zero"),
        ("OPENAI_TIMEOUT_SECONDS", "0"),
        ("OPENAI_TIMEOUT_SECONDS", "-1"),
        ("OPENAI_TIMEOUT_SECONDS", "nan"),
        ("OPENAI_TIMEOUT_SECONDS", "inf"),
        ("OPENAI_MAX_RETRIES", "-1"),
        ("OPENAI_MAX_RETRIES", "1.5"),
        ("OPENAI_MAX_RETRIES", "invalid"),
    ),
)
def test_load_openai_config_rejects_invalid_numeric_values(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv(name, value)

    with pytest.raises(ConfigurationError):
        load_openai_config()


def test_load_openai_config_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY is required"):
        load_openai_config()


@pytest.mark.parametrize("model", ("", "   "))
def test_load_openai_config_rejects_empty_model(
    monkeypatch: pytest.MonkeyPatch,
    model: str,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", model)

    with pytest.raises(ConfigurationError, match="OPENAI_MODEL must not be empty"):
        load_openai_config()
