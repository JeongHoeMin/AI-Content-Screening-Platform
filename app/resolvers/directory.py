from __future__ import annotations

import csv
import json
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Iterable, Mapping, Protocol, Sequence, Tuple

from app.config.errors import ConfigurationError
from app.models.company_resolution import (
    CanonicalCompany,
    CompanyDirectoryEntry,
)

_CSV_COLUMNS: Tuple[str, ...] = (
    "company_id",
    "canonical_name",
    "ticker",
    "exchange",
    "aliases",
    "directory_version",
)


class CompanyDirectory(Protocol):
    """Provides normalized name candidates without making resolution decisions."""

    @property
    def version(self) -> str:
        """Return the immutable directory snapshot identifier."""
        ...

    def find_candidates(self, company_name: str) -> Tuple[CanonicalCompany, ...]:
        """Return canonical candidates for one extracted company name."""
        ...


def normalize_company_name(company_name: str) -> str:
    """Apply the v1 deterministic name-index normalization policy."""
    return " ".join(company_name.casefold().split())


class StaticCompanyDirectory(CompanyDirectory):
    """Immutable in-memory directory for empty mode and deterministic tests."""

    def __init__(
        self,
        entries: Sequence[CompanyDirectoryEntry] = (),
        *,
        version: str = "empty",
    ) -> None:
        if not version:
            raise ValueError("Directory version must not be empty")
        if version == "empty" and entries:
            raise ValueError("Empty directory must not contain company entries")
        for entry in entries:
            if entry.company.directory_version != version:
                raise ValueError("Directory entry version does not match directory")
        self._version: str = version
        self._index: Mapping[str, Tuple[CanonicalCompany, ...]] = (
            self._build_index(entries)
        )

    @property
    def version(self) -> str:
        return self._version

    def find_candidates(self, company_name: str) -> Tuple[CanonicalCompany, ...]:
        return self._index.get(normalize_company_name(company_name), ())

    @staticmethod
    def _build_index(
        entries: Sequence[CompanyDirectoryEntry],
    ) -> Mapping[str, Tuple[CanonicalCompany, ...]]:
        seen_company_ids: set[str] = set()
        index: Dict[str, Dict[str, CanonicalCompany]] = {}
        for entry in entries:
            company: CanonicalCompany = entry.company
            if company.company_id in seen_company_ids:
                raise ValueError("Duplicate company_id in company directory")
            seen_company_ids.add(company.company_id)
            names: Iterable[str] = (company.canonical_name, *entry.aliases)
            for name in names:
                normalized_name: str = normalize_company_name(name)
                if not normalized_name:
                    raise ValueError("Directory names must not normalize to empty")
                candidates: Dict[str, CanonicalCompany] = index.setdefault(
                    normalized_name,
                    {},
                )
                candidates[company.company_id] = company
        immutable_index: Dict[str, Tuple[CanonicalCompany, ...]] = {
            name: tuple(
                candidates[company_id]
                for company_id in sorted(candidates)
            )
            for name, candidates in index.items()
        }
        return MappingProxyType(immutable_index)


class LocalCsvCompanyDirectory(StaticCompanyDirectory):
    """KRX directory loaded once from a validated versioned UTF-8 CSV file."""

    @classmethod
    def from_csv(cls, path: Path) -> "LocalCsvCompanyDirectory":
        try:
            with path.open("r", encoding="utf-8", newline="") as source:
                reader: csv.DictReader = csv.DictReader(source)
                if reader.fieldnames is None or not set(_CSV_COLUMNS).issubset(
                    reader.fieldnames
                ):
                    raise ConfigurationError(
                        "Company directory CSV is missing required columns"
                    )
                rows: list[dict[str, str | None]] = list(reader)
        except OSError as error:
            raise ConfigurationError("Unable to read company directory CSV") from error
        if not rows:
            raise ConfigurationError("Company directory CSV must contain at least one row")

        entries: list[CompanyDirectoryEntry] = []
        versions: set[str] = set()
        for row in rows:
            entry: CompanyDirectoryEntry = cls._parse_row(row)
            entries.append(entry)
            versions.add(entry.company.directory_version)
        if len(versions) != 1:
            raise ConfigurationError("Company directory CSV must use one version")
        version: str = next(iter(versions))
        try:
            return cls(entries, version=version)
        except ValueError as error:
            raise ConfigurationError("Company directory CSV contains invalid rows") from error

    @staticmethod
    def _parse_row(row: Mapping[str, str | None]) -> CompanyDirectoryEntry:
        try:
            aliases_payload: object = json.loads(row.get("aliases") or "")
        except json.JSONDecodeError as error:
            raise ConfigurationError("Company directory aliases must be valid JSON") from error
        if not isinstance(aliases_payload, list) or any(
            type(alias) is not str for alias in aliases_payload
        ):
            raise ConfigurationError(
                "Company directory aliases must be a JSON string array"
            )
        aliases: Tuple[str, ...] = tuple(aliases_payload)
        try:
            company: CanonicalCompany = CanonicalCompany(
                company_id=row.get("company_id"),
                canonical_name=row.get("canonical_name"),
                ticker=row.get("ticker"),
                exchange=row.get("exchange"),
                directory_version=row.get("directory_version"),
            )
            return CompanyDirectoryEntry(company=company, aliases=aliases)
        except ValueError as error:
            raise ConfigurationError("Company directory row is invalid") from error
