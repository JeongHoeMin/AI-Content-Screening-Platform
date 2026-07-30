from __future__ import annotations

import os
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.config.errors import ConfigurationError


class NaverNewsConfig(BaseModel):
    """Validated Naver News API configuration loaded from the environment."""

    model_config = ConfigDict(frozen=True)

    client_id: SecretStr
    client_secret: SecretStr
    timeout_seconds: float = Field(default=10.0, gt=0.0, le=60.0)


class DartConfig(BaseModel):
    """Validated OpenDART API configuration loaded from the environment."""

    model_config = ConfigDict(frozen=True)

    api_key: SecretStr
    timeout_seconds: float = Field(default=10.0, gt=0.0, le=60.0)


class KrxConfig(BaseModel):
    """Validated KRX OpenAPI configuration loaded from the environment."""

    model_config = ConfigDict(frozen=True)

    api_key: SecretStr
    directory_date: date = Field(default_factory=date.today)
    timeout_seconds: float = Field(default=15.0, gt=0.0, le=60.0)


def load_naver_news_config() -> NaverNewsConfig:
    """Load Naver credentials without exposing their values in errors."""
    client_id: Optional[str] = os.getenv("NAVER_CLIENT_ID")
    client_secret: Optional[str] = os.getenv("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ConfigurationError("NAVER_CLIENT_ID and NAVER_CLIENT_SECRET are required")
    return NaverNewsConfig(client_id=client_id, client_secret=client_secret)


def load_dart_config() -> DartConfig:
    """Load the OpenDART credential without exposing its value in errors."""
    api_key: Optional[str] = os.getenv("DART_API_KEY")
    if not api_key:
        raise ConfigurationError("DART_API_KEY is required")
    return DartConfig(api_key=api_key)


def load_krx_config() -> KrxConfig:
    """Load KRX credentials and the optional immutable snapshot date."""
    api_key: Optional[str] = os.getenv("KRX_API_KEY")
    raw_date: Optional[str] = os.getenv("KRX_DIRECTORY_DATE")
    if not api_key:
        raise ConfigurationError("KRX_API_KEY is required")
    try:
        return KrxConfig(api_key=api_key, directory_date=raw_date or date.today())
    except ValueError as error:
        raise ConfigurationError("KRX_DIRECTORY_DATE must use YYYY-MM-DD") from error
