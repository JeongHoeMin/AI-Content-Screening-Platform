"""Fallback orchestration for one recommendation market-price lookup."""

from __future__ import annotations

from datetime import datetime

from app.market_prices.contracts import PriceLookupClient, PriceLookupObservation
from app.models.market_price import PriceSnapshotStatus


class MarketPriceService:
    """Prefer KIS real-time prices, then fall back to KRX closing prices."""

    def __init__(
        self,
        kis_client: PriceLookupClient,
        krx_client: PriceLookupClient,
    ) -> None:
        self._kis_client: PriceLookupClient = kis_client
        self._krx_client: PriceLookupClient = krx_client

    async def capture(
        self,
        ticker: str,
        observed_at: datetime,
    ) -> PriceLookupObservation:
        """Capture one price without allowing an unavailable KIS result to abort it."""
        kis_observation: PriceLookupObservation = await self._kis_client.fetch(
            ticker,
            observed_at,
        )
        if kis_observation.status is PriceSnapshotStatus.AVAILABLE:
            return kis_observation
        return await self._krx_client.fetch(ticker, observed_at)
