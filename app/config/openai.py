from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """Raised when the OpenAI runtime configuration is invalid."""


@dataclass(frozen=True)
class OpenAIConfig:
    """Immutable settings used to create the OpenAI Responses client."""

    api_key: str
    model: str
    timeout_seconds: float
    max_retries: int


def load_openai_config() -> OpenAIConfig:
    """Load OpenAI settings from environment variables without loading dotenv files."""
    api_key: str = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ConfigurationError("OPENAI_API_KEY is required for openai mode.")
    model: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()
    if not model:
        raise ConfigurationError("OPENAI_MODEL must not be empty.")
    return OpenAIConfig(
        api_key=api_key,
        model=model,
        timeout_seconds=_load_positive_float("OPENAI_TIMEOUT_SECONDS", 60.0),
        max_retries=_load_non_negative_int("OPENAI_MAX_RETRIES", 2),
    )


def _load_positive_float(name: str, default: float) -> float:
    raw_value: str = os.environ.get(name, "").strip()
    if not raw_value:
        return default
    try:
        value: float = float(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a positive number.") from error
    if value <= 0:
        raise ConfigurationError(f"{name} must be a positive number.")
    return value


def _load_non_negative_int(name: str, default: int) -> int:
    raw_value: str = os.environ.get(name, "").strip()
    if not raw_value:
        return default
    try:
        value: int = int(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a non-negative integer.") from error
    if value < 0:
        raise ConfigurationError(f"{name} must be a non-negative integer.")
    return value
