from __future__ import annotations

from pathlib import Path

from app.config import CompanyDirectoryConfig, CompanyDirectoryMode, create_company_directory
from app.resolvers import KrxMasterCsvCompanyDirectory


def write_krx_master_csv(path: Path) -> Path:
    content: str = (
        "표준코드,단축코드,한글 종목명,한글 종목약명,영문 종목명,상장일,시장구분\n"
        '"KR7005930003","005930","삼성전자보통주","삼성전자","Samsung Electronics Co., Ltd.","1975/06/11","KOSPI"\n'
        '"KR7035420009","035420","NAVER보통주","NAVER","NAVER Corporation","2002/10/29","KOSPI"\n'
    )
    path.write_bytes(content.encode("cp949"))
    return path


def test_krx_master_csv_directory_preserves_ticker_aliases_and_version(
    tmp_path: Path,
) -> None:
    path: Path = write_krx_master_csv(tmp_path / "data_0551_20260730.csv")

    directory: KrxMasterCsvCompanyDirectory = KrxMasterCsvCompanyDirectory.from_csv(path)

    samsung = directory.find_candidates("삼성전자")[0]
    assert directory.version == "2026-07-30"
    assert samsung.company_id == "KR7005930003"
    assert samsung.ticker == "005930"
    assert directory.find_candidates("삼성전자보통주") == (samsung,)
    assert directory.find_candidates("samsung electronics co., ltd.") == (samsung,)


def test_krx_master_csv_mode_uses_the_user_source_without_conversion(
    tmp_path: Path,
) -> None:
    path: Path = write_krx_master_csv(tmp_path / "data_0551_20260730.csv")
    config: CompanyDirectoryConfig = CompanyDirectoryConfig(
        mode=CompanyDirectoryMode.KRX_MASTER_CSV,
        csv_path=path,
    )

    directory = create_company_directory(config)

    assert directory.find_candidates("NAVER")[0].ticker == "035420"
