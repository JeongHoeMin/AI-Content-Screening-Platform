from __future__ import annotations

import os
from pathlib import Path

import pytest

import app.config.openai as openai_config
from app.config import ConfigurationError, load_openai_config

_OPENAI_ENVIRONMENT_NAMES: tuple[str, ...] = (
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_TIMEOUT_SECONDS",
    "OPENAI_MAX_RETRIES",
)


@pytest.fixture(autouse=True)
def isolate_openai_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Keep tests independent from both shell values and the repository dotenv file."""
    for name in _OPENAI_ENVIRONMENT_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(openai_config, "_OPENAI_DOTENV_PATH", tmp_path / ".env")


def test_load_openai_config_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("OPENAI_MAX_RETRIES", raising=False)

    config = load_openai_config()

    assert config.model == "gpt-4o-mini"
    assert config.timeout_seconds == 60.0
    assert config.max_retries == 2


def test_openai_config_repr_redacts_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sensitive-api-key")

    config = load_openai_config()

    assert "sensitive-api-key" not in repr(config)
    assert "[redacted]" in repr(config)


def test_dotenv_path_is_repository_root_and_ignores_current_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    expected_path: Path = Path(openai_config.__file__).resolve().parents[2] / ".env"
    calls: list[tuple[Path, bool]] = []

    def fake_load_dotenv(*, dotenv_path: Path, override: bool) -> bool:
        calls.append((dotenv_path, override))
        return True

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(openai_config, "_OPENAI_DOTENV_PATH", expected_path)
    monkeypatch.setattr(Path, "is_file", lambda path: path == expected_path)
    monkeypatch.setattr(openai_config, "load_dotenv", fake_load_dotenv)
    monkeypatch.setenv("OPENAI_API_KEY", "shell-key")

    config = load_openai_config()

    assert config.api_key == "shell-key"
    assert calls == [(expected_path, False)]


def test_existing_dotenv_provides_openai_key_without_overriding_shell_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dotenv_path: Path = tmp_path / ".env"
    dotenv_path.touch()
    calls: list[tuple[Path, bool]] = []

    def fake_load_dotenv(*, dotenv_path: Path, override: bool) -> bool:
        calls.append((dotenv_path, override))
        monkeypatch.setenv("OPENAI_API_KEY", "dotenv-key")
        return True

    monkeypatch.setattr(openai_config, "load_dotenv", fake_load_dotenv)

    config = load_openai_config()

    assert config.api_key == "dotenv-key"
    assert calls == [(dotenv_path, False)]


def test_shell_environment_wins_over_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dotenv_path: Path = tmp_path / ".env"
    dotenv_path.touch()
    monkeypatch.setenv("OPENAI_API_KEY", "shell-key")

    def fake_load_dotenv(*, dotenv_path: Path, override: bool) -> bool:
        assert override is False
        os.environ.setdefault("OPENAI_API_KEY", "dotenv-key")
        return True

    monkeypatch.setattr(openai_config, "load_dotenv", fake_load_dotenv)

    config = load_openai_config()

    assert config.api_key == "shell-key"


def test_missing_dotenv_is_not_an_error_or_loader_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []
    monkeypatch.setenv("OPENAI_API_KEY", "shell-key")
    monkeypatch.setattr(openai_config, "load_dotenv", lambda **kwargs: calls.append(True))

    config = load_openai_config()

    assert config.api_key == "shell-key"
    assert calls == []


def test_dotenv_loader_os_error_becomes_safe_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dotenv_path: Path = tmp_path / ".env"
    dotenv_path.touch()

    def fake_load_dotenv(*, dotenv_path: Path, override: bool) -> bool:
        raise OSError("unreadable dotenv contents")

    monkeypatch.setattr(openai_config, "load_dotenv", fake_load_dotenv)

    with pytest.raises(ConfigurationError, match="Unable to load OpenAI dotenv configuration") as error_info:
        load_openai_config()

    assert "unreadable dotenv contents" not in str(error_info.value)


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
