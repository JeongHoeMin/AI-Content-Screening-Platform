from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import pytest

from app.config import KrxConfig
from app.models import PriceBasis, PriceErrorKind, PriceProvider, PriceSnapshotStatus
from app.providers.http import ExternalServiceError, JsonHttpClient


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


@pytest.mark.anyio
async def test_fetch_retries_transient_krx_transport_with_injected_backoff() -> None:
    from app.market_prices.krx import KrxClosingPriceClient

    class TransientKrxHttpClient(KrxHttpClientDouble):
        def __init__(self) -> None:
            super().__init__()
            self.kospi_attempts: int = 0

        async def post(
            self,
            url: str,
            headers: Mapping[str, str],
            body: Mapping[str, Any],
            timeout_seconds: float,
        ) -> Mapping[str, Any]:
            self.requested_dates.append(str(body["basDd"]))
            if not url.endswith("/stk_bydd_trd"):
                return {"OutBlock_1": []}
            self.kospi_attempts += 1
            if self.kospi_attempts < 3:
                raise ExternalServiceError("Network request failed")
            return {"OutBlock_1": [{"ISU_SRT_CD": "005930", "TDD_CLSPRC": "72000"}]}

    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    client: TransientKrxHttpClient = TransientKrxHttpClient()
    price_client: KrxClosingPriceClient = KrxClosingPriceClient(
        KrxConfig(api_key="krx-key"),
        client,
        sleep=record_sleep,
    )

    observation = await price_client.fetch(
        "005930",
        datetime(2026, 8, 5, 0, 15, tzinfo=timezone.utc),
    )

    assert observation.status is PriceSnapshotStatus.AVAILABLE
    assert client.kospi_attempts == 3
    assert sleeps == [1.0, 2.0]


@pytest.mark.anyio
async def test_fetch_does_not_retry_authentication_schema_or_invalid_ticker_failures() -> None:
    from app.market_prices.krx import KrxClosingPriceClient

    class FixedResponseKrxHttpClient(KrxHttpClientDouble):
        def __init__(self, response: Mapping[str, Any] | Exception) -> None:
            super().__init__()
            self.response: Mapping[str, Any] | Exception = response
            self.calls: int = 0

        async def post(
            self,
            url: str,
            headers: Mapping[str, str],
            body: Mapping[str, Any],
            timeout_seconds: float,
        ) -> Mapping[str, Any]:
            self.calls += 1
            if isinstance(self.response, Exception):
                raise self.response
            return self.response

    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    auth_client: FixedResponseKrxHttpClient = FixedResponseKrxHttpClient(
        ExternalServiceError("HTTP status 401")
    )
    auth_price_client: KrxClosingPriceClient = KrxClosingPriceClient(
        KrxConfig(api_key="krx-key"),
        auth_client,
        sleep=record_sleep,
    )
    auth_observation = await auth_price_client.fetch(
        "005930",
        datetime(2026, 8, 5, 0, 15, tzinfo=timezone.utc),
    )

    schema_client: FixedResponseKrxHttpClient = FixedResponseKrxHttpClient({"invalid": []})
    schema_price_client: KrxClosingPriceClient = KrxClosingPriceClient(
        KrxConfig(api_key="krx-key"),
        schema_client,
        sleep=record_sleep,
    )
    schema_observation = await schema_price_client.fetch(
        "005930",
        datetime(2026, 8, 5, 0, 15, tzinfo=timezone.utc),
    )

    invalid_ticker_client: FixedResponseKrxHttpClient = FixedResponseKrxHttpClient(
        {"OutBlock_1": []}
    )
    invalid_ticker_price_client: KrxClosingPriceClient = KrxClosingPriceClient(
        KrxConfig(api_key="krx-key"),
        invalid_ticker_client,
        sleep=record_sleep,
    )
    invalid_ticker_observation = await invalid_ticker_price_client.fetch(
        "5930",
        datetime(2026, 8, 5, 0, 15, tzinfo=timezone.utc),
    )

    assert auth_observation.error_kind is PriceErrorKind.AUTHENTICATION
    assert auth_client.calls == 3
    assert schema_observation.error_kind is PriceErrorKind.INVALID_PAYLOAD
    assert schema_client.calls == 3
    assert invalid_ticker_observation.error_kind is PriceErrorKind.INVALID_TICKER
    assert invalid_ticker_client.calls == 0
    assert sleeps == []


@pytest.mark.anyio
async def test_fetch_stops_lookback_when_an_exchange_cannot_confirm_ticker_absence() -> None:
    from app.market_prices.krx import KrxClosingPriceClient

    class PartialFailureKrxHttpClient(KrxHttpClientDouble):
        async def post(
            self,
            url: str,
            headers: Mapping[str, str],
            body: Mapping[str, Any],
            timeout_seconds: float,
        ) -> Mapping[str, Any]:
            requested_date: str = str(body["basDd"])
            self.requested_dates.append(requested_date)
            if requested_date == "20260805" and url.endswith("/stk_bydd_trd"):
                raise ExternalServiceError("HTTP status 503")
            if requested_date == "20260804" and url.endswith("/stk_bydd_trd"):
                return {"OutBlock_1": [{"ISU_SRT_CD": "005930", "TDD_CLSPRC": "70000"}]}
            return {"OutBlock_1": []}

    async def no_delay(seconds: float) -> None:
        assert seconds in {1.0, 2.0}

    client: PartialFailureKrxHttpClient = PartialFailureKrxHttpClient()
    price_client: KrxClosingPriceClient = KrxClosingPriceClient(
        KrxConfig(api_key="krx-key"),
        client,
        sleep=no_delay,
    )

    observation = await price_client.fetch(
        "005930",
        datetime(2026, 8, 5, 0, 15, tzinfo=timezone.utc),
    )

    assert observation.status is PriceSnapshotStatus.UNAVAILABLE
    assert observation.error_kind is PriceErrorKind.SERVER
    assert "20260804" not in client.requested_dates


@pytest.mark.anyio
async def test_fetch_uses_kst_date_at_the_utc_midnight_boundary() -> None:
    from app.market_prices.krx import KrxClosingPriceClient

    class KstBoundaryKrxHttpClient(KrxHttpClientDouble):
        async def post(
            self,
            url: str,
            headers: Mapping[str, str],
            body: Mapping[str, Any],
            timeout_seconds: float,
        ) -> Mapping[str, Any]:
            requested_date: str = str(body["basDd"])
            self.requested_dates.append(requested_date)
            if requested_date == "20260805" and url.endswith("/stk_bydd_trd"):
                return {"OutBlock_1": [{"ISU_SRT_CD": "005930", "TDD_CLSPRC": "72000"}]}
            return {"OutBlock_1": []}

    client: KstBoundaryKrxHttpClient = KstBoundaryKrxHttpClient()
    price_client: KrxClosingPriceClient = KrxClosingPriceClient(
        KrxConfig(api_key="krx-key"),
        client,
    )
    observed_at: datetime = datetime(2026, 8, 4, 15, 30, tzinfo=timezone.utc)

    observation = await price_client.fetch("005930", observed_at)

    assert observation.status is PriceSnapshotStatus.AVAILABLE
    assert observation.observed_at is observed_at
    assert observation.trading_date.isoformat() == "2026-08-05"
    assert client.requested_dates == ["20260805"]
