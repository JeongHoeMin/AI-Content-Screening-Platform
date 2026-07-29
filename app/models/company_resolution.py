from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator


class KRXExchange(str, Enum):
    """Supported KRX market taxonomies for Company Resolution v1."""

    KOSPI = "KOSPI"
    KOSDAQ = "KOSDAQ"
    KONEX = "KONEX"


class CompanyResolutionStatus(str, Enum):
    """Conservative outcome of mapping an extracted company to KRX identity."""

    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class CanonicalCompany(BaseModel):
    """Stable KRX company identity loaded from a versioned local directory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: StrictStr = Field(min_length=1)
    canonical_name: StrictStr = Field(min_length=1)
    ticker: StrictStr = Field(pattern=r"^\d{6}$")
    exchange: KRXExchange
    directory_version: StrictStr = Field(min_length=1)

    @field_validator("company_id", "canonical_name")
    @classmethod
    def _require_non_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("directory_version")
    @classmethod
    def _require_iso_date_version(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("directory_version must use YYYY-MM-DD") from error
        return value


class CompanyDirectoryEntry(BaseModel):
    """Canonical KRX company plus its directory-managed aliases."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    company: CanonicalCompany
    aliases: Tuple[StrictStr, ...] = ()

    @field_validator("aliases")
    @classmethod
    def _require_non_blank_aliases(cls, values: Tuple[str, ...]) -> Tuple[str, ...]:
        for value in values:
            if not value.strip():
                raise ValueError("aliases must not contain blank values")
        return values


class CompanyResolutionObservation(BaseModel):
    """Validated resolution outcome without exposing raw directory payloads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: CompanyResolutionStatus
    candidate_count: int = Field(ge=0)
    canonical_company: Optional[CanonicalCompany] = None
    directory_version: StrictStr = Field(min_length=1)

    @field_validator("directory_version")
    @classmethod
    def _validate_directory_version(cls, value: str) -> str:
        if value == "empty":
            return value
        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(
                "directory_version must be 'empty' or use YYYY-MM-DD"
            ) from error
        return value

    @model_validator(mode="after")
    def _validate_status_invariants(self) -> "CompanyResolutionObservation":
        if self.status is CompanyResolutionStatus.RESOLVED:
            if self.candidate_count != 1 or self.canonical_company is None:
                raise ValueError(
                    "RESOLVED requires one candidate and a canonical company"
                )
        elif self.status is CompanyResolutionStatus.AMBIGUOUS:
            if self.candidate_count < 2 or self.canonical_company is not None:
                raise ValueError(
                    "AMBIGUOUS requires at least two candidates and no canonical company"
                )
        elif self.candidate_count != 0 or self.canonical_company is not None:
            raise ValueError(
                "UNRESOLVED requires zero candidates and no canonical company"
            )
        return self
