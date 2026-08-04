"""Runtime configuration models and loaders."""

from typing import Any

from app.config.errors import ConfigurationError
from app.config.openai import OpenAIConfig, load_openai_config
from app.config.persistence import DatabaseConfig, load_database_config
from app.config.trusted_sources import (
    IrRssFeedConfig,
    TrustedSourceConfig,
    load_trusted_source_config,
)
from app.config.market_data import (
    DartConfig,
    KrxConfig,
    NaverNewsConfig,
    load_dart_config,
    load_krx_config,
    load_naver_news_config,
)

__all__ = [
    "CompanyDirectoryConfig",
    "CompanyDirectoryMode",
    "ConfigurationError",
    "DartConfig",
    "NaverNewsConfig",
    "KrxConfig",
    "OpenAIConfig",
    "DatabaseConfig",
    "create_company_directory",
    "create_company_directory_async",
    "load_company_directory_config",
    "load_dart_config",
    "load_krx_config",
    "load_naver_news_config",
    "load_openai_config",
    "load_database_config",
    "IrRssFeedConfig",
    "TrustedSourceConfig",
    "load_trusted_source_config",
]


def __getattr__(name: str) -> Any:
    """Load directory configuration lazily to avoid the resolver import cycle."""
    if name in {
        "CompanyDirectoryConfig",
        "CompanyDirectoryMode",
        "create_company_directory",
        "create_company_directory_async",
        "load_company_directory_config",
    }:
        from app.config import company_directory

        return getattr(company_directory, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
