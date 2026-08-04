from __future__ import annotations

import pytest

from app.config.errors import ConfigurationError
from app.config.telegram import load_optional_telegram_config


def test_telegram_config_is_optional_when_both_values_are_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    assert load_optional_telegram_config() is None


def test_telegram_config_rejects_half_configured_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(ConfigurationError, match="together"):
        load_optional_telegram_config()
