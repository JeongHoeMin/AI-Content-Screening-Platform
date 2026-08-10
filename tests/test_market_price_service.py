from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models import PriceBasis, PriceErrorKind, PriceProvider, PriceSnapshotStatus


class PriceClientDouble:
    def __init__(self, observation: object) -> None:
        self.observation: object = observation
        self.calls: int = 0

    async def fetch(self, ticker: str, observed_at: datetime) -> object:
        self.calls += 1
        return self.observation


def available_krx_observation(observed_at: datetime) -> object:
    from app.market_prices.contracts import PriceLookupObservation

    return PriceLookupObservation(
        status=PriceSnapshotStatus.AVAILABLE,
        price=Decimal("72000"),
        basis=PriceBasis.CLOSE,
        provider=PriceProvider.KRX,
        observed_at=observed_at,
        trading_date=date(2026, 8, 4),
    )


def unavailable_observation(observed_at: datetime, error_kind: PriceErrorKind) -> object:
    from app.market_prices.contracts import PriceLookupObservation

    return PriceLookupObservation(
        status=PriceSnapshotStatus.UNAVAILABLE,
        observed_at=observed_at,
        error_kind=error_kind,
    )


@pytest.mark.anyio
async def test_capture_falls_back_to_krx_after_kis_transport_failure() -> None:
    from app.market_prices.service import MarketPriceService

    observed_at: datetime = datetime(2026, 8, 5, 0, 15, tzinfo=timezone.utc)
    kis_client: PriceClientDouble = PriceClientDouble(
        unavailable_observation(observed_at, PriceErrorKind.TRANSPORT)
    )
    krx_client: PriceClientDouble = PriceClientDouble(available_krx_observation(observed_at))
    service: MarketPriceService = MarketPriceService(kis_client, krx_client)

    observation = await service.capture("005930", observed_at)

    assert observation.status is PriceSnapshotStatus.AVAILABLE
    assert observation.price == Decimal("72000")
    assert observation.basis is PriceBasis.CLOSE
    assert observation.provider is PriceProvider.KRX
    assert observation.trading_date == date(2026, 8, 4)
    assert kis_client.calls == 1
    assert krx_client.calls == 1


@pytest.mark.anyio
async def test_capture_returns_kis_realtime_price_without_calling_krx() -> None:
    from app.market_prices.contracts import PriceLookupObservation
    from app.market_prices.service import MarketPriceService

    observed_at: datetime = datetime(2026, 8, 5, 0, 15, tzinfo=timezone.utc)
    kis_observation: PriceLookupObservation = PriceLookupObservation(
        status=PriceSnapshotStatus.AVAILABLE,
        price=Decimal("72100"),
        basis=PriceBasis.REALTIME,
        provider=PriceProvider.KIS,
        observed_at=observed_at,
        trading_date=date(2026, 8, 5),
    )
    kis_client: PriceClientDouble = PriceClientDouble(kis_observation)
    krx_client: PriceClientDouble = PriceClientDouble(available_krx_observation(observed_at))
    service: MarketPriceService = MarketPriceService(kis_client, krx_client)

    observation = await service.capture("005930", observed_at)

    assert observation is kis_observation
    assert krx_client.calls == 0


@pytest.mark.anyio
async def test_capture_keeps_one_bounded_krx_failure_after_kis_is_not_configured() -> None:
    from app.market_prices.service import MarketPriceService

    observed_at: datetime = datetime(2026, 8, 5, 0, 15, tzinfo=timezone.utc)
    kis_client: PriceClientDouble = PriceClientDouble(
        unavailable_observation(observed_at, PriceErrorKind.NOT_CONFIGURED)
    )
    krx_client: PriceClientDouble = PriceClientDouble(
        unavailable_observation(observed_at, PriceErrorKind.NOT_FOUND)
    )
    service: MarketPriceService = MarketPriceService(kis_client, krx_client)

    observation = await service.capture("005930", observed_at)

    assert observation.status is PriceSnapshotStatus.UNAVAILABLE
    assert observation.error_kind is PriceErrorKind.NOT_FOUND
    assert observation.price is None
    assert observation.provider is None
    assert kis_client.calls == 1
    assert krx_client.calls == 1
