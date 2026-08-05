"""KIS real-time-price transport adapter with bounded retries."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, ValidationError

from app.config.market_data import KisConfig
from app.market_prices.contracts import PriceLookupObservation
from app.market_prices.parser import MarketPriceParser, PricePayloadError
from app.models.market_price import (
    PriceBasis,
    PriceErrorKind,
    PriceProvider,
    PriceSnapshotStatus,
)
from app.providers.http import ExternalServiceError, JsonHttpClient, StdlibJsonHttpClient

_TOKEN_PATH: str = "/oauth2/tokenP"
_PRICE_PATH: str = "/uapi/domestic-stock/v1/quotations/inquire-price"
_RETRY_DELAYS_SECONDS: tuple[float, float] = (1.0, 2.0)
_TICKER_PATTERN: re.Pattern[str] = re.compile(r"^\d{6}$")
_HTTP_STATUS_PATTERN: re.Pattern[str] = re.compile(r"HTTP status (\d{3})")


class _KisTokenPayload(BaseModel):
    """Minimal KIS token shape; its secret value never leaves this adapter."""

    model_config = ConfigDict(extra="ignore")

    access_token: str


class KisRealtimePriceClient:
    """Fetch KIS domestic-stock current prices through an injected JSON client."""

    def __init__(
        self,
        config: Optional[KisConfig],
        http_client: Optional[JsonHttpClient] = None,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._config: Optional[KisConfig] = config
        self._http_client: JsonHttpClient = http_client or StdlibJsonHttpClient()
        self._sleep: Callable[[float], Awaitable[None]] = sleep
        self._access_token: Optional[str] = None

    async def fetch(
        self,
        ticker: str,
        observed_at: datetime,
    ) -> PriceLookupObservation:
        """Fetch a KIS real-time price, retrying only safe transient failures."""
        if self._config is None:
            return PriceLookupObservation.unavailable(
                observed_at,
                PriceErrorKind.NOT_CONFIGURED,
            )
        if _TICKER_PATTERN.fullmatch(ticker) is None:
            return PriceLookupObservation.unavailable(
                observed_at,
                PriceErrorKind.INVALID_TICKER,
            )
        retry_index: int
        for retry_index in range(len(_RETRY_DELAYS_SECONDS) + 1):
            observation: PriceLookupObservation = await self._fetch_once(ticker, observed_at)
            if (
                observation.status is PriceSnapshotStatus.AVAILABLE
                or observation.error_kind
                not in {
                    PriceErrorKind.TRANSPORT,
                    PriceErrorKind.RATE_LIMIT,
                    PriceErrorKind.SERVER,
                }
                or retry_index == len(_RETRY_DELAYS_SECONDS)
            ):
                return observation
            delay_seconds: float = _RETRY_DELAYS_SECONDS[retry_index]
            await self._sleep(delay_seconds)
        raise RuntimeError("KIS retry loop did not return")

    async def _fetch_once(
        self,
        ticker: str,
        observed_at: datetime,
    ) -> PriceLookupObservation:
        try:
            access_token: str = await self._get_access_token()
            config: KisConfig = self._require_config()
            payload: Mapping[str, Any] = await self._http_client.get(
                url=f"{config.base_url.rstrip('/')}{_PRICE_PATH}",
                headers={
                    "authorization": f"Bearer {access_token}",
                    "appkey": config.app_key.get_secret_value(),
                    "appsecret": config.app_secret.get_secret_value(),
                    "tr_id": "FHKST01010100",
                },
                query={
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": ticker,
                },
                timeout_seconds=config.timeout_seconds,
            )
            price: Decimal = MarketPriceParser.parse_kis_realtime(payload)
        except ExternalServiceError as error:
            return PriceLookupObservation.unavailable(
                observed_at,
                self._classify_external_error(error),
            )
        except (PricePayloadError, ValidationError, ValueError):
            return PriceLookupObservation.unavailable(
                observed_at,
                PriceErrorKind.INVALID_PAYLOAD,
            )
        return PriceLookupObservation(
            status=PriceSnapshotStatus.AVAILABLE,
            price=price,
            basis=PriceBasis.REALTIME,
            provider=PriceProvider.KIS,
            observed_at=observed_at,
            trading_date=observed_at.date(),
        )

    async def _get_access_token(self) -> str:
        if self._access_token is not None:
            return self._access_token
        config: KisConfig = self._require_config()
        payload: Mapping[str, Any] = await self._http_client.post(
            url=f"{config.base_url.rstrip('/')}{_TOKEN_PATH}",
            headers={},
            body={
                "grant_type": "client_credentials",
                "appkey": config.app_key.get_secret_value(),
                "appsecret": config.app_secret.get_secret_value(),
            },
            timeout_seconds=config.timeout_seconds,
        )
        try:
            token_payload: _KisTokenPayload = _KisTokenPayload.model_validate(payload)
        except ValidationError as error:
            raise PricePayloadError("KIS token payload is invalid") from error
        token: str = token_payload.access_token.strip()
        if not token:
            raise PricePayloadError("KIS token payload is invalid")
        self._access_token = token
        return token

    def _require_config(self) -> KisConfig:
        if self._config is None:
            raise ValueError("KIS configuration is required")
        return self._config

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
