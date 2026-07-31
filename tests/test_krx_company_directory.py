from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Mapping

import pytest

from app.config import ConfigurationError, KrxConfig, load_krx_config
from app.providers.http import ExternalServiceError, JsonHttpClient
from app.resolvers import KrxCompanyDirectoryLoader


class KrxHttpClientDouble(JsonHttpClient):
    def __init__(self, responses: Mapping[str, Mapping[str, Any]]) -> None:
        self.responses: Mapping[str, Mapping[str, Any]] = responses
        self.calls: list[tuple[str, Mapping[str, str], Mapping[str, Any]]] = []

    async def get(
        self,
        url: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        raise AssertionError("KRX directory must use JSON POST")

    async def post(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        self.calls.append((url, headers, body))
        response: Mapping[str, Any] = self.responses[url]
        if response == {"error": "network"}:
            raise ExternalServiceError("Network request failed")
        return response


class KrxDateAwareHttpClientDouble(JsonHttpClient):
    """Returns a configured KRX response for each requested snapshot date."""

    def __init__(self, responses: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
        self.responses: Mapping[str, Mapping[str, Mapping[str, Any]]] = responses
        self.calls: list[tuple[str, Mapping[str, str], Mapping[str, Any]]] = []

    async def get(
        self,
        url: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        raise AssertionError("KRX directory must use JSON POST")

    async def post(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        self.calls.append((url, headers, body))
        snapshot_date: str = str(body["basDd"])
        return self.responses[snapshot_date][url]


def test_krx_loader_builds_one_snapshot_from_all_markets() -> None:
    kospi_url: str = "https://data-dbg.krx.co.kr/svc/apis/sto/stk_isu_base_info"
    kosdaq_url: str = "https://data-dbg.krx.co.kr/svc/apis/sto/ksq_isu_base_info"
    konex_url: str = "https://data-dbg.krx.co.kr/svc/apis/sto/knx_isu_base_info"
    client: KrxHttpClientDouble = KrxHttpClientDouble(
        {
            kospi_url: {
                "OutBlock_1": [
                    {
                        "ISU_CD": "KR7005930003",
                        "ISU_SRT_CD": "005930",
                        "ISU_NM": "삼성전자",
                        "ISU_ABBRV": "삼성전자",
                        "ISU_ENG_NM": "Samsung Electronics",
                    }
                ]
            },
            kosdaq_url: {
                "OutBlock_1": [
                    {
                        "ISU_CD": "KR7035420009",
                        "ISU_SRT_CD": "035420",
                        "ISU_NM": "NAVER",
                        "ISU_ABBRV": "네이버",
                        "ISU_ENG_NM": "NAVER Corporation",
                    }
                ]
            },
            konex_url: {"OutBlock_1": []},
        }
    )
    loader: KrxCompanyDirectoryLoader = KrxCompanyDirectoryLoader(
        KrxConfig(api_key="krx-key", directory_date=date(2026, 7, 30)), client
    )

    directory = asyncio.run(loader.load())

    assert directory.version == "2026-07-30"
    assert directory.find_candidates("삼성전자")[0].ticker == "005930"
    assert directory.find_candidates("Samsung Electronics")[0].company_id == "KR7005930003"
    assert directory.find_candidates("네이버")[0].ticker == "035420"
    assert len(client.calls) == 3
    assert all(headers == {"AUTH_KEY": "krx-key"} for _, headers, _ in client.calls)
    assert all(body == {"basDd": "20260730"} for _, _, body in client.calls)


def test_krx_loader_keeps_successful_markets_after_one_market_failure() -> None:
    kospi_url: str = "https://data-dbg.krx.co.kr/svc/apis/sto/stk_isu_base_info"
    kosdaq_url: str = "https://data-dbg.krx.co.kr/svc/apis/sto/ksq_isu_base_info"
    konex_url: str = "https://data-dbg.krx.co.kr/svc/apis/sto/knx_isu_base_info"
    client: KrxHttpClientDouble = KrxHttpClientDouble(
        {
            kospi_url: {
                "OutBlock_1": [
                    {
                        "ISU_CD": "KR7005930003",
                        "ISU_SRT_CD": "005930",
                        "ISU_NM": "삼성전자",
                    }
                ]
            },
            kosdaq_url: {"error": "network"},
            konex_url: {"OutBlock_1": []},
        }
    )
    loader: KrxCompanyDirectoryLoader = KrxCompanyDirectoryLoader(
        KrxConfig(api_key="krx-key", directory_date=date(2026, 7, 30)), client
    )

    directory = asyncio.run(loader.load())

    assert directory.find_candidates("삼성전자")[0].exchange.value == "KOSPI"


def test_krx_loader_uses_latest_available_api_snapshot() -> None:
    kospi_url: str = "https://data-dbg.krx.co.kr/svc/apis/sto/stk_isu_base_info"
    kosdaq_url: str = "https://data-dbg.krx.co.kr/svc/apis/sto/ksq_isu_base_info"
    konex_url: str = "https://data-dbg.krx.co.kr/svc/apis/sto/knx_isu_base_info"
    empty_markets: Mapping[str, Mapping[str, Any]] = {
        url: {"OutBlock_1": []} for url in (kospi_url, kosdaq_url, konex_url)
    }
    available_markets: Mapping[str, Mapping[str, Any]] = {
        kospi_url: {
            "OutBlock_1": [
                {
                    "ISU_CD": "KR7005930003",
                    "ISU_SRT_CD": "005930",
                    "ISU_NM": "삼성전자",
                }
            ]
        },
        kosdaq_url: {"OutBlock_1": []},
        konex_url: {"OutBlock_1": []},
    }
    client: KrxDateAwareHttpClientDouble = KrxDateAwareHttpClientDouble(
        {"20260731": empty_markets, "20260730": available_markets}
    )
    loader: KrxCompanyDirectoryLoader = KrxCompanyDirectoryLoader(
        KrxConfig(api_key="krx-key", directory_date=date(2026, 7, 31)), client
    )

    directory = asyncio.run(loader.load())

    assert directory.version == "2026-07-30"
    assert directory.find_candidates("삼성전자")[0].ticker == "005930"
    assert [call[2]["basDd"] for call in client.calls] == [
        "20260731",
        "20260731",
        "20260731",
        "20260730",
        "20260730",
        "20260730",
    ]


def test_krx_loader_fails_when_no_market_can_supply_entries() -> None:
    urls: tuple[str, str, str] = (
        "https://data-dbg.krx.co.kr/svc/apis/sto/stk_isu_base_info",
        "https://data-dbg.krx.co.kr/svc/apis/sto/ksq_isu_base_info",
        "https://data-dbg.krx.co.kr/svc/apis/sto/knx_isu_base_info",
    )
    client: KrxHttpClientDouble = KrxHttpClientDouble(
        {url: {"error": "network"} for url in urls}
    )
    loader: KrxCompanyDirectoryLoader = KrxCompanyDirectoryLoader(
        KrxConfig(api_key="krx-key", directory_date=date(2026, 7, 30)), client
    )

    with pytest.raises(ConfigurationError, match="could not load"):
        asyncio.run(loader.load())


def test_krx_config_reads_secret_and_optional_snapshot_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KRX_API_KEY", "krx-key")
    monkeypatch.setenv("KRX_DIRECTORY_DATE", "2026-07-30")

    config: KrxConfig = load_krx_config()

    assert config.directory_date == date(2026, 7, 30)
    assert config.api_key.get_secret_value() == "krx-key"
    assert "krx-key" not in repr(config)


def test_krx_config_rejects_missing_or_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KRX_API_KEY", raising=False)
    with pytest.raises(ConfigurationError):
        load_krx_config()

    monkeypatch.setenv("KRX_API_KEY", "krx-key")
    monkeypatch.setenv("KRX_DIRECTORY_DATE", "30-07-2026")
    with pytest.raises(ConfigurationError):
        load_krx_config()
