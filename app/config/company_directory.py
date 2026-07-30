from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from app.config.errors import ConfigurationError
from app.config.market_data import KrxConfig, load_krx_config
from app.resolvers.directory import (
    CompanyDirectory,
    KrxMasterCsvCompanyDirectory,
    LocalCsvCompanyDirectory,
    StaticCompanyDirectory,
)


class CompanyDirectoryMode(str, Enum):
    """Runtime directory modes independent from the LLM execution mode."""

    EMPTY = "empty"
    LOCAL_CSV = "local_csv"
    KRX_API = "krx_api"
    KRX_MASTER_CSV = "krx_master_csv"


class CompanyDirectoryConfig(BaseModel):
    """Validated configuration for the immutable Company Directory snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: CompanyDirectoryMode
    csv_path: Optional[Path] = None

    @model_validator(mode="after")
    def _validate_path(self) -> "CompanyDirectoryConfig":
        if self.mode in {CompanyDirectoryMode.LOCAL_CSV, CompanyDirectoryMode.KRX_MASTER_CSV} and self.csv_path is None:
            raise ValueError("COMPANY_DIRECTORY_CSV_PATH is required for CSV directory modes")
        if self.mode in {CompanyDirectoryMode.EMPTY, CompanyDirectoryMode.KRX_API} and self.csv_path is not None:
            raise ValueError("COMPANY_DIRECTORY_CSV_PATH is not allowed for empty")
        return self


def load_company_directory_config() -> CompanyDirectoryConfig:
    """Load directory mode without coupling it to Mock or OpenAI execution."""
    raw_mode: str = os.environ.get("COMPANY_DIRECTORY_MODE", "empty").strip()
    raw_path: str = os.environ.get("COMPANY_DIRECTORY_CSV_PATH", "").strip()
    try:
        mode: CompanyDirectoryMode = CompanyDirectoryMode(raw_mode)
    except ValueError as error:
        raise ConfigurationError("COMPANY_DIRECTORY_MODE is invalid") from error
    try:
        return CompanyDirectoryConfig(
            mode=mode,
            csv_path=Path(raw_path) if raw_path else None,
        )
    except ValueError as error:
        raise ConfigurationError("Company directory configuration is invalid") from error


def create_company_directory(config: CompanyDirectoryConfig) -> CompanyDirectory:
    """Create one immutable directory snapshot from validated runtime config."""
    if config.mode is CompanyDirectoryMode.EMPTY:
        return StaticCompanyDirectory()
    if config.mode is CompanyDirectoryMode.KRX_API:
        raise ConfigurationError("KRX API directory must be created asynchronously")
    if config.mode is CompanyDirectoryMode.KRX_MASTER_CSV:
        if config.csv_path is None:
            raise ConfigurationError("COMPANY_DIRECTORY_CSV_PATH is required for krx_master_csv")
        return KrxMasterCsvCompanyDirectory.from_csv(config.csv_path)
    if config.csv_path is None:
        raise ConfigurationError("COMPANY_DIRECTORY_CSV_PATH is required for local_csv")
    return LocalCsvCompanyDirectory.from_csv(config.csv_path)


async def create_company_directory_async(config: CompanyDirectoryConfig) -> CompanyDirectory:
    """Create a directory snapshot, querying KRX only when explicitly configured."""
    if config.mode is not CompanyDirectoryMode.KRX_API:
        return create_company_directory(config)
    from app.resolvers.krx_directory import KrxCompanyDirectoryLoader

    krx_config: KrxConfig = load_krx_config()
    return await KrxCompanyDirectoryLoader(krx_config).load()
