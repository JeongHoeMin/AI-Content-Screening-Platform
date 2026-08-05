from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import pytest

from app.config import KrxConfig
from app.models import PriceBasis, PriceErrorKind, PriceProvider, PriceSnapshotStatus
from app.providers.http import JsonHttpClient


class KrxHttpClientDouble(JsonHttpClient):
    def __init__(self) -> None:
        self.requested_dates: list[str] = []

    async def get(
        self,
        url: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        raise AssertionError("KRX price lookup uses POST")

    async def post(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        requested_date: str = str(body["basDd"])
        self.requested_dates.append(requested_date)
        if requested_date == "20260804" and url.endswith("/stk_bydd_trd"):
            return {"OutBlock_1": [{"ISU_SRT_CD": "005930", "TDD_CLSPRC": "72000"}]}
        return {"OutBlock_1": []}


@pytest.mark.anyio
async def test_fetch_looks_back_from_holiday_to_most_recent_krx_close() -> None:
    from app.market_prices.krx import KrxClosingPriceClient

    client: KrxHttpClientDouble = KrxHttpClientDouble()
    price_client: KrxClosingPriceClient = KrxClosingPriceClient(
        KrxConfig(api_key="krx-key"),
        client,
    )
    observed_at: datetime = datetime(2026, 8, 5, 0, 15, tzinfo=timezone.utc)

    observation = await price_client.fetch("005930", observed_at)

    assert observation.status is PriceSnapshotStatus.AVAILABLE
    assert observation.price == 72000
    assert observation.basis is PriceBasis.CLOSE
    assert observation.provider is PriceProvider.KRX
    assert observation.trading_date.isoformat() == "2026-08-04"
    assert "20260805" in client.requested_dates
    assert "20260804" in client.requested_dates


@pytest.mark.anyio
async def test_fetch_returns_invalid_payload_when_krx_row_price_is_not_positive() -> None:
    from app.market_prices.krx import KrxClosingPriceClient

    class InvalidPriceKrxHttpClient(KrxHttpClientDouble):
        async def post(
            self,
            url: str,
            headers: Mapping[str, str],
            body: Mapping[str, Any],
            timeout_seconds: float,
        ) -> Mapping[str, Any]:
            return {"OutBlock_1": [{"ISU_SRT_CD": "005930", "TDD_CLSPRC": "0"}]}

    price_client: KrxClosingPriceClient = KrxClosingPriceClient(
        KrxConfig(api_key="krx-key"),
        InvalidPriceKrxHttpClient(),
    )
    observation = await price_client.fetch(
        "005930",
        datetime(2026, 8, 5, 0, 15, tzinfo=timezone.utc),
    )

    assert observation.status is PriceSnapshotStatus.UNAVAILABLE
    assert observation.error_kind is PriceErrorKind.INVALID_PAYLOAD
