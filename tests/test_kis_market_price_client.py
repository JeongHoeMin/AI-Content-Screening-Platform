from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import pytest

from app.config import KisConfig
from app.models import PriceBasis, PriceErrorKind, PriceProvider, PriceSnapshotStatus
from app.providers.http import ExternalServiceError, JsonHttpClient


class KisHttpClientDouble(JsonHttpClient):
    def __init__(self, quote_responses: list[Mapping[str, Any] | Exception]) -> None:
        self.quote_responses: list[Mapping[str, Any] | Exception] = quote_responses
        self.token_requests: int = 0
        self.quote_requests: int = 0

    async def get(
        self,
        url: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        self.quote_requests += 1
        assert url.endswith("/uapi/domestic-stock/v1/quotations/inquire-price")
        assert query == {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930"}
        response: Mapping[str, Any] | Exception = self.quote_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def post(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        self.token_requests += 1
        assert url.endswith("/oauth2/tokenP")
        assert body["grant_type"] == "client_credentials"
        return {"access_token": "test-access-token"}


@pytest.fixture
def observed_at() -> datetime:
    return datetime(2026, 8, 5, 0, 15, tzinfo=timezone.utc)


@pytest.fixture
def config() -> KisConfig:
    return KisConfig(app_key="app-key", app_secret="app-secret")


@pytest.mark.anyio
async def test_fetch_returns_validated_realtime_kis_observation(
    config: KisConfig,
    observed_at: datetime,
) -> None:
    from app.market_prices.kis import KisRealtimePriceClient

    client: KisHttpClientDouble = KisHttpClientDouble([{"output": {"stck_prpr": "72000"}}])
    price_client: KisRealtimePriceClient = KisRealtimePriceClient(config, client)

    observation = await price_client.fetch("005930", observed_at)

    assert observation.status is PriceSnapshotStatus.AVAILABLE
    assert observation.price == 72000
    assert observation.basis is PriceBasis.REALTIME
    assert observation.provider is PriceProvider.KIS
    assert observation.trading_date == observed_at.date()


@pytest.mark.anyio
async def test_fetch_caches_a_successful_access_token(
    config: KisConfig,
    observed_at: datetime,
) -> None:
    from app.market_prices.kis import KisRealtimePriceClient

    client: KisHttpClientDouble = KisHttpClientDouble(
        [
            {"output": {"stck_prpr": "72000"}},
            {"output": {"stck_prpr": "72100"}},
        ]
    )
    price_client: KisRealtimePriceClient = KisRealtimePriceClient(config, client)

    await price_client.fetch("005930", observed_at)
    second_observation = await price_client.fetch("005930", observed_at)

    assert second_observation.price == 72100
    assert client.token_requests == 1


@pytest.mark.anyio
async def test_invalid_ticker_returns_without_retries_or_requests(
    config: KisConfig,
    observed_at: datetime,
) -> None:
    from app.market_prices.kis import KisRealtimePriceClient

    client: KisHttpClientDouble = KisHttpClientDouble([])
    price_client: KisRealtimePriceClient = KisRealtimePriceClient(config, client)

    observation = await price_client.fetch("5930", observed_at)

    assert observation.status is PriceSnapshotStatus.UNAVAILABLE
    assert observation.error_kind is PriceErrorKind.INVALID_TICKER
    assert client.token_requests == 0
    assert client.quote_requests == 0


@pytest.mark.anyio
async def test_transport_failure_retries_with_injected_backoff(
    config: KisConfig,
    observed_at: datetime,
) -> None:
    from app.market_prices.kis import KisRealtimePriceClient

    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    client: KisHttpClientDouble = KisHttpClientDouble(
        [
            ExternalServiceError("Network request failed"),
            ExternalServiceError("Network request failed"),
            {"output": {"stck_prpr": "72000"}},
        ]
    )
    price_client: KisRealtimePriceClient = KisRealtimePriceClient(
        config,
        client,
        sleep=record_sleep,
    )

    observation = await price_client.fetch("005930", observed_at)

    assert observation.status is PriceSnapshotStatus.AVAILABLE
    assert observation.price == 72000
    assert sleeps == [1.0, 2.0]
    assert client.quote_requests == 3


@pytest.mark.anyio
async def test_rate_limit_retries_but_authentication_failure_does_not(
    config: KisConfig,
    observed_at: datetime,
) -> None:
    from app.market_prices.kis import KisRealtimePriceClient

    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    rate_limited_client: KisHttpClientDouble = KisHttpClientDouble(
        [ExternalServiceError("HTTP status 429"), {"output": {"stck_prpr": "72000"}}]
    )
    rate_limited_price_client: KisRealtimePriceClient = KisRealtimePriceClient(
        config,
        rate_limited_client,
        sleep=record_sleep,
    )
    rate_limited_observation = await rate_limited_price_client.fetch("005930", observed_at)

    auth_client: KisHttpClientDouble = KisHttpClientDouble([ExternalServiceError("HTTP status 401")])
    auth_price_client: KisRealtimePriceClient = KisRealtimePriceClient(
        config,
        auth_client,
        sleep=record_sleep,
    )
    auth_observation = await auth_price_client.fetch("005930", observed_at)

    assert rate_limited_observation.status is PriceSnapshotStatus.AVAILABLE
    assert rate_limited_client.quote_requests == 2
    assert auth_observation.error_kind is PriceErrorKind.AUTHENTICATION
    assert auth_client.quote_requests == 1
    assert sleeps == [1.0]
