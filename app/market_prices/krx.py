"""KRX daily-closing-price transport adapter with bounded date lookback."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from app.config.market_data import KrxConfig
from app.market_prices.contracts import PriceLookupObservation
from app.market_prices.parser import MarketPriceParser, PricePayloadError
from app.models.market_price import (
    PriceBasis,
    PriceErrorKind,
    PriceProvider,
    PriceSnapshotStatus,
)
from app.providers.http import ExternalServiceError, JsonHttpClient, StdlibJsonHttpClient

_KRX_ENDPOINTS: tuple[str, str, str] = (
    "https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd",
    "https://data-dbg.krx.co.kr/svc/apis/sto/ksq_bydd_trd",
    "https://data-dbg.krx.co.kr/svc/apis/sto/knx_bydd_trd",
)
_MAX_LOOKBACK_DAYS: int = 7
_TICKER_PATTERN: re.Pattern[str] = re.compile(r"^\d{6}$")
_HTTP_STATUS_PATTERN: re.Pattern[str] = re.compile(r"HTTP status (\d{3})")


class KrxClosingPriceClient:
    """Fetch the nearest KRX closing price across KOSPI, KOSDAQ, and KONEX."""

    def __init__(
        self,
        config: KrxConfig,
        http_client: Optional[JsonHttpClient] = None,
    ) -> None:
        self._config: KrxConfig = config
        self._http_client: JsonHttpClient = http_client or StdlibJsonHttpClient()

    async def fetch(
        self,
        ticker: str,
        observed_at: datetime,
    ) -> PriceLookupObservation:
        """Return the nearest available KRX close within the seven-day lookback."""
        if _TICKER_PATTERN.fullmatch(ticker) is None:
            return PriceLookupObservation.unavailable(
                observed_at,
                PriceErrorKind.INVALID_TICKER,
            )
        observed_date: date = observed_at.date()
        had_valid_payload: bool = False
        had_invalid_payload: bool = False
        last_external_error: Optional[PriceErrorKind] = None
        days_ago: int
        for days_ago in range(_MAX_LOOKBACK_DAYS):
            trading_date: date = observed_date - timedelta(days=days_ago)
            endpoint: str
            for endpoint in _KRX_ENDPOINTS:
                try:
                    payload: Mapping[str, Any] = await self._http_client.post(
                        url=endpoint,
                        headers={"AUTH_KEY": self._config.api_key.get_secret_value()},
                        body={"basDd": trading_date.strftime("%Y%m%d")},
                        timeout_seconds=self._config.timeout_seconds,
                    )
                    price: Optional[Decimal] = MarketPriceParser.parse_krx_closing_price(
                        payload,
                        ticker,
                    )
                except ExternalServiceError as error:
                    last_external_error = self._classify_external_error(error)
                    continue
                except PricePayloadError:
                    had_invalid_payload = True
                    continue
                had_valid_payload = True
                if price is None:
                    continue
                return PriceLookupObservation(
                    status=PriceSnapshotStatus.AVAILABLE,
                    price=price,
                    basis=PriceBasis.CLOSE,
                    provider=PriceProvider.KRX,
                    observed_at=observed_at,
                    trading_date=trading_date,
                )
        if had_valid_payload:
            return PriceLookupObservation.unavailable(
                observed_at,
                PriceErrorKind.NOT_FOUND,
            )
        if had_invalid_payload:
            return PriceLookupObservation.unavailable(
                observed_at,
                PriceErrorKind.INVALID_PAYLOAD,
            )
        return PriceLookupObservation.unavailable(
            observed_at,
            last_external_error or PriceErrorKind.TRANSPORT,
        )

    @staticmethod
    def _classify_external_error(error: ExternalServiceError) -> PriceErrorKind:
        message: str = str(error)
        match: Optional[re.Match[str]] = _HTTP_STATUS_PATTERN.search(message)
        if match is None:
            return PriceErrorKind.TRANSPORT
        status_code: int = int(match.group(1))
        if status_code in {401, 403}:
            return PriceErrorKind.AUTHENTICATION
        if status_code == 400:
            return PriceErrorKind.INVALID_TICKER
        if status_code == 404:
            return PriceErrorKind.NOT_FOUND
        if status_code == 429:
            return PriceErrorKind.RATE_LIMIT
        if status_code >= 500:
            return PriceErrorKind.SERVER
        return PriceErrorKind.TRANSPORT
