"""KRX daily-closing-price transport adapter with bounded date lookback."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from zoneinfo import ZoneInfo

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
_RETRY_DELAYS_SECONDS: tuple[float, float] = (1.0, 2.0)
_TICKER_PATTERN: re.Pattern[str] = re.compile(r"^\d{6}$")
_HTTP_STATUS_PATTERN: re.Pattern[str] = re.compile(r"HTTP status (\d{3})")
_KST: ZoneInfo = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class _KrxEndpointLookupResult:
    """Validated result from one KRX exchange endpoint for one trading date."""

    price: Optional[Decimal]
    error_kind: Optional[PriceErrorKind]


class KrxClosingPriceClient:
    """Fetch the nearest KRX closing price across KOSPI, KOSDAQ, and KONEX."""

    def __init__(
        self,
        config: KrxConfig,
        http_client: Optional[JsonHttpClient] = None,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._config: KrxConfig = config
        self._http_client: JsonHttpClient = http_client or StdlibJsonHttpClient()
        self._sleep: Callable[[float], Awaitable[None]] = sleep

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
        observed_date: date = observed_at.astimezone(_KST).date()
        days_ago: int
        for days_ago in range(_MAX_LOOKBACK_DAYS):
            trading_date: date = observed_date - timedelta(days=days_ago)
            day_error: Optional[PriceErrorKind] = None
            endpoint: str
            for endpoint in _KRX_ENDPOINTS:
                endpoint_result: _KrxEndpointLookupResult = await self._fetch_endpoint(
                    endpoint,
                    ticker,
                    trading_date,
                )
                if endpoint_result.price is None:
                    if endpoint_result.error_kind is not None and day_error is None:
                        day_error = endpoint_result.error_kind
                    continue
                return PriceLookupObservation(
                    status=PriceSnapshotStatus.AVAILABLE,
                    price=endpoint_result.price,
                    basis=PriceBasis.CLOSE,
                    provider=PriceProvider.KRX,
                    observed_at=observed_at,
                    trading_date=trading_date,
                )
            if day_error is not None:
                return PriceLookupObservation.unavailable(observed_at, day_error)
        return PriceLookupObservation.unavailable(
            observed_at,
            PriceErrorKind.NOT_FOUND,
        )

    async def _fetch_endpoint(
        self,
        endpoint: str,
        ticker: str,
        trading_date: date,
    ) -> _KrxEndpointLookupResult:
        """Fetch one endpoint, retrying only its bounded transient failures."""
        retry_index: int
        for retry_index in range(len(_RETRY_DELAYS_SECONDS) + 1):
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
                error_kind: PriceErrorKind = self._classify_external_error(error)
                if (
                    error_kind
                    not in {
                        PriceErrorKind.TRANSPORT,
                        PriceErrorKind.RATE_LIMIT,
                        PriceErrorKind.SERVER,
                    }
                    or retry_index == len(_RETRY_DELAYS_SECONDS)
                ):
                    return _KrxEndpointLookupResult(None, error_kind)
                delay_seconds: float = _RETRY_DELAYS_SECONDS[retry_index]
                await self._sleep(delay_seconds)
                continue
            except PricePayloadError:
                return _KrxEndpointLookupResult(None, PriceErrorKind.INVALID_PAYLOAD)
            return _KrxEndpointLookupResult(price, None)
        raise RuntimeError("KRX retry loop did not return")

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
