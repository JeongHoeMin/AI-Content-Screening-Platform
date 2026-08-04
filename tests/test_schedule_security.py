from __future__ import annotations

import pytest

from app.config.errors import ConfigurationError
from app.config.schedule_security import load_schedule_settings_password


def test_schedule_settings_password_is_required_when_schedule_api_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SCHEDULE_SETTINGS_PASSWORD", raising=False)

    with pytest.raises(ConfigurationError, match="SCHEDULE_SETTINGS_PASSWORD"):
        load_schedule_settings_password()


def test_schedule_settings_password_rejects_short_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCHEDULE_SETTINGS_PASSWORD", "short")

    with pytest.raises(ConfigurationError, match="at least 32"):
        load_schedule_settings_password()
