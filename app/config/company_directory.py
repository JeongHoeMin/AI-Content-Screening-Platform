from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from app.config.errors import ConfigurationError
from app.resolvers.directory import CompanyDirectory, LocalCsvCompanyDirectory, StaticCompanyDirectory


class CompanyDirectoryMode(str, Enum):
    """Runtime directory modes independent from the LLM execution mode."""

    EMPTY = "empty"
    LOCAL_CSV = "local_csv"


class CompanyDirectoryConfig(BaseModel):
    """Validated configuration for the immutable Company Directory snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: CompanyDirectoryMode
    csv_path: Optional[Path] = None

    @model_validator(mode="after")
    def _validate_path(self) -> "CompanyDirectoryConfig":
        if self.mode is CompanyDirectoryMode.LOCAL_CSV and self.csv_path is None:
            raise ValueError("COMPANY_DIRECTORY_CSV_PATH is required for local_csv")
        if self.mode is CompanyDirectoryMode.EMPTY and self.csv_path is not None:
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
    if config.csv_path is None:
        raise ConfigurationError("COMPANY_DIRECTORY_CSV_PATH is required for local_csv")
    return LocalCsvCompanyDirectory.from_csv(config.csv_path)
