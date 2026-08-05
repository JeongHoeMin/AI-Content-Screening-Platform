"""Transport payload validation for KIS and KRX market-price adapters."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional

from pydantic import BaseModel, ConfigDict, ValidationError


class PricePayloadError(ValueError):
    """Raised when a provider response cannot produce a positive price."""


class _KisPricePayload(BaseModel):
    """Minimal KIS transport shape required by this adapter."""

    model_config = ConfigDict(extra="ignore")

    output: Mapping[str, Any]


class _KrxPricePayload(BaseModel):
    """Minimal KRX transport shape required by this adapter."""

    model_config = ConfigDict(extra="ignore")

    OutBlock_1: list[Mapping[str, Any]]


class MarketPriceParser:
    """Convert minimal provider payload values into validated decimal prices."""

    @staticmethod
    def parse_kis_realtime(payload: Mapping[str, Any]) -> Decimal:
        """Extract only KIS ``output.stck_prpr`` as a positive decimal."""
        try:
            transport: _KisPricePayload = _KisPricePayload.model_validate(payload)
            raw_price: Any = transport.output.get("stck_prpr")
        except ValidationError as error:
            raise PricePayloadError("KIS price payload is invalid") from error
        return MarketPriceParser._parse_positive_decimal(raw_price)

    @staticmethod
    def parse_krx_closing_price(
        payload: Mapping[str, Any],
        ticker: str,
    ) -> Optional[Decimal]:
        """Extract a matching KRX row's ``TDD_CLSPRC``, if the ticker exists."""
        try:
            transport: _KrxPricePayload = _KrxPricePayload.model_validate(payload)
        except ValidationError as error:
            raise PricePayloadError("KRX price payload is invalid") from error
        row: Mapping[str, Any]
        for row in transport.OutBlock_1:
            raw_ticker: Any = row.get("ISU_SRT_CD")
            if raw_ticker != ticker:
                continue
            return MarketPriceParser._parse_positive_decimal(row.get("TDD_CLSPRC"))
        return None

    @staticmethod
    def _parse_positive_decimal(value: Any) -> Decimal:
        if isinstance(value, bool) or value is None:
            raise PricePayloadError("market price is invalid")
        raw_value: str = str(value).strip().replace(",", "")
        if not raw_value:
            raise PricePayloadError("market price is invalid")
        try:
            price: Decimal = Decimal(raw_value)
        except (InvalidOperation, ValueError) as error:
            raise PricePayloadError("market price is invalid") from error
        if not price.is_finite() or price <= Decimal("0"):
            raise PricePayloadError("market price is invalid")
        return price
