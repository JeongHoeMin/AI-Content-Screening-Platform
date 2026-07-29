from __future__ import annotations

from pathlib import Path

import pytest

from app.config import ConfigurationError
from app.models import CanonicalCompany, CompanyDirectoryEntry, KRXExchange
from app.resolvers import LocalCsvCompanyDirectory, StaticCompanyDirectory


def build_company(
    company_id: str = "KRX-COMPANY-000001",
    canonical_name: str = "Samsung Electronics",
    ticker: str = "005930",
    exchange: KRXExchange = KRXExchange.KOSPI,
) -> CanonicalCompany:
    return CanonicalCompany(
        company_id=company_id,
        canonical_name=canonical_name,
        ticker=ticker,
        exchange=exchange,
        directory_version="2026-07-30",
    )


def write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text(
        "company_id,canonical_name,ticker,exchange,aliases,directory_version\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )
    return path


def test_static_directory_indexes_canonical_name_and_aliases() -> None:
    company: CanonicalCompany = build_company()
    directory = StaticCompanyDirectory(
        [CompanyDirectoryEntry(company=company, aliases=("Samsung", "삼성전자"))],
        version="2026-07-30",
    )

    assert directory.find_candidates(" samsung electronics ") == (company,)
    assert directory.find_candidates("SAMSUNG") == (company,)
    assert directory.find_candidates("삼성전자") == (company,)


def test_empty_directory_rejects_company_entries() -> None:
    with pytest.raises(ValueError):
        StaticCompanyDirectory(
            [CompanyDirectoryEntry(company=build_company())],
            version="empty",
        )


def test_static_directory_preserves_cross_company_alias_collision() -> None:
    first: CanonicalCompany = build_company()
    second: CanonicalCompany = build_company(
        company_id="KRX-COMPANY-000002",
        canonical_name="Samsung SDI",
        ticker="006400",
    )
    directory = StaticCompanyDirectory(
        [
            CompanyDirectoryEntry(company=first, aliases=("Samsung",)),
            CompanyDirectoryEntry(company=second, aliases=("Samsung",)),
        ],
        version="2026-07-30",
    )

    assert directory.find_candidates("samsung") == (first, second)


def test_static_directory_deduplicates_same_company_alias_matches() -> None:
    company: CanonicalCompany = build_company(canonical_name="Samsung")
    directory = StaticCompanyDirectory(
        [CompanyDirectoryEntry(company=company, aliases=(" Samsung ", "SAMSUNG"))],
        version="2026-07-30",
    )

    assert directory.find_candidates("Samsung") == (company,)


@pytest.mark.parametrize(
    "row",
    (
        'KRX-COMPANY-000001,Samsung Electronics,5930,KOSPI,"[""Samsung""]",2026-07-30',
        'KRX-COMPANY-000001,Samsung Electronics,005930,KRX,"[""Samsung""]",2026-07-30',
        'KRX-COMPANY-000001,Samsung Electronics,005930,KOSPI,"[1]",2026-07-30',
        'KRX-COMPANY-000001,Samsung Electronics,005930,KOSPI,"[""  ""]",2026-07-30',
    ),
)
def test_csv_loader_rejects_invalid_ticker_exchange_or_alias(
    tmp_path: Path,
    row: str,
) -> None:
    path: Path = write_csv(tmp_path / "companies.csv", [row])

    with pytest.raises(ConfigurationError):
        LocalCsvCompanyDirectory.from_csv(path)


def test_csv_loader_preserves_leading_zero_ticker_and_version(tmp_path: Path) -> None:
    path: Path = write_csv(
        tmp_path / "companies.csv",
        [
            'KRX-COMPANY-000001,Samsung Electronics,005930,KOSPI,"[""Samsung"", ""삼성전자""]",2026-07-30'
        ],
    )

    directory = LocalCsvCompanyDirectory.from_csv(path)
    result = directory.find_candidates("삼성전자")

    assert directory.version == "2026-07-30"
    assert result[0].ticker == "005930"


def test_csv_loader_rejects_duplicate_company_rows_even_when_identical(
    tmp_path: Path,
) -> None:
    row: str = 'KRX-COMPANY-000001,Samsung Electronics,005930,KOSPI,"[""Samsung""]",2026-07-30'
    path: Path = write_csv(tmp_path / "companies.csv", [row, row])

    with pytest.raises(ConfigurationError):
        LocalCsvCompanyDirectory.from_csv(path)


def test_csv_loader_rejects_mixed_versions(tmp_path: Path) -> None:
    path: Path = write_csv(
        tmp_path / "companies.csv",
        [
            'KRX-COMPANY-000001,Samsung Electronics,005930,KOSPI,[],2026-07-30',
            'KRX-COMPANY-000002,Samsung SDI,006400,KOSPI,[],2026-07-31',
        ],
    )

    with pytest.raises(ConfigurationError):
        LocalCsvCompanyDirectory.from_csv(path)
