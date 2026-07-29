from __future__ import annotations

from pathlib import Path

import pytest

from app.config import (
    CompanyDirectoryConfig,
    CompanyDirectoryMode,
    ConfigurationError,
    create_company_directory,
    load_company_directory_config,
)


def test_empty_directory_is_the_default_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COMPANY_DIRECTORY_MODE", raising=False)
    monkeypatch.delenv("COMPANY_DIRECTORY_CSV_PATH", raising=False)

    config = load_company_directory_config()
    directory = create_company_directory(config)

    assert config.mode is CompanyDirectoryMode.EMPTY
    assert directory.version == "empty"
    assert directory.find_candidates("Samsung Electronics") == ()


def test_local_csv_mode_requires_a_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPANY_DIRECTORY_MODE", "local_csv")
    monkeypatch.delenv("COMPANY_DIRECTORY_CSV_PATH", raising=False)

    with pytest.raises(ConfigurationError):
        load_company_directory_config()


def test_empty_mode_rejects_csv_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPANY_DIRECTORY_MODE", "empty")
    monkeypatch.setenv("COMPANY_DIRECTORY_CSV_PATH", "companies.csv")

    with pytest.raises(ConfigurationError):
        load_company_directory_config()


def test_local_csv_mode_loads_a_directory(tmp_path: Path) -> None:
    path: Path = tmp_path / "companies.csv"
    path.write_text(
        "company_id,canonical_name,ticker,exchange,aliases,directory_version\n"
        'KRX-COMPANY-000001,Samsung Electronics,005930,KOSPI,"[""Samsung""]",2026-07-30\n',
        encoding="utf-8",
    )
    config = CompanyDirectoryConfig(
        mode=CompanyDirectoryMode.LOCAL_CSV,
        csv_path=path,
    )

    directory = create_company_directory(config)

    assert directory.version == "2026-07-30"
    assert directory.find_candidates("Samsung")[0].company_id == "KRX-COMPANY-000001"
