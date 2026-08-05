from __future__ import annotations

import pytest

from app.config import ConfigurationError, KisConfig, load_optional_kis_config


_KIS_ENVIRONMENT_NAMES: tuple[str, ...] = (
    "KIS_APP_KEY",
    "KIS_APP_SECRET",
    "KIS_ACCOUNT_PRODUCT_CODE",
    "KIS_BASE_URL",
    "KIS_TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def isolate_kis_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _KIS_ENVIRONMENT_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_load_optional_kis_config_returns_none_without_credentials() -> None:
    assert load_optional_kis_config() is None


def test_load_optional_kis_config_rejects_partial_credentials_without_leaking_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KIS_APP_KEY", "sensitive-kis-key")

    with pytest.raises(ConfigurationError) as error_info:
        load_optional_kis_config()

    assert "KIS_APP_KEY and KIS_APP_SECRET must both be set" in str(error_info.value)
    assert "sensitive-kis-key" not in str(error_info.value)


def test_load_optional_kis_config_reads_validated_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KIS_APP_KEY", "app-key")
    monkeypatch.setenv("KIS_APP_SECRET", "app-secret")

    config: KisConfig | None = load_optional_kis_config()

    assert config is not None
    assert config.app_key.get_secret_value() == "app-key"
    assert config.app_secret.get_secret_value() == "app-secret"
    assert config.account_product_code == "01"
    assert config.base_url == "https://openapi.koreainvestment.com:9443"
    assert config.timeout_seconds == 10.0
