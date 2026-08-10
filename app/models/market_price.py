from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator

from app.models.recommendation import RecommendationAction


class PriceBasis(str, Enum):
    """The market-price basis used for a successful observation."""

    REALTIME = "realtime"
    CLOSE = "close"


class PriceSnapshotStatus(str, Enum):
    """Availability state of one recommendation market-price observation."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class PriceProvider(str, Enum):
    """Approved providers for recommendation market-price observations."""

    KIS = "kis"
    KRX = "krx"


class PriceErrorKind(str, Enum):
    """Safe, bounded reasons that a market-price observation was unavailable."""

    NOT_CONFIGURED = "not_configured"
    TRANSPORT = "transport"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    SERVER = "server"
    INVALID_TICKER = "invalid_ticker"
    INVALID_PAYLOAD = "invalid_payload"
    NOT_FOUND = "not_found"


class RecommendationPriceSnapshot(BaseModel):
    """Immutable validated price observation for one BUY or SELL recommendation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: StrictStr = Field(min_length=1)
    recommendation_index: StrictInt = Field(ge=0)
    ticker: StrictStr = Field(pattern=r"^\d{6}$")
    action: RecommendationAction
    status: PriceSnapshotStatus
    price: Optional[Decimal] = None
    currency: StrictStr = "KRW"
    basis: Optional[PriceBasis] = None
    provider: Optional[PriceProvider] = None
    observed_at: datetime
    trading_date: Optional[date] = None
    error_kind: Optional[PriceErrorKind] = None

    @field_validator("run_id")
    @classmethod
    def _require_non_blank_run_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("run_id must not be blank")
        return value

    @field_validator("action")
    @classmethod
    def _require_buy_or_sell_action(
        cls,
        value: RecommendationAction,
    ) -> RecommendationAction:
        if value not in (RecommendationAction.BUY, RecommendationAction.SELL):
            raise ValueError("action must be BUY or SELL")
        return value

    @field_validator("currency")
    @classmethod
    def _require_krw_currency(cls, value: str) -> str:
        if value != "KRW":
            raise ValueError("currency must be KRW")
        return value

    @field_validator("observed_at")
    @classmethod
    def _require_utc_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("observed_at must be an aware UTC datetime")
        return value

    @model_validator(mode="after")
    def _require_consistent_availability_fields(self) -> "RecommendationPriceSnapshot":
        if self.status is PriceSnapshotStatus.AVAILABLE:
            if self.price is None or self.price <= Decimal("0"):
                raise ValueError("AVAILABLE requires a positive price")
            if self.basis is None or self.provider is None or self.trading_date is None:
                raise ValueError(
                    "AVAILABLE requires basis, provider, and trading_date"
                )
            if self.error_kind is not None:
                raise ValueError("AVAILABLE does not permit error_kind")
        elif (
            self.price is not None
            or self.basis is not None
            or self.provider is not None
            or self.trading_date is not None
        ):
            raise ValueError(
                "UNAVAILABLE requires price, basis, provider, and trading_date to be null"
            )
        elif self.error_kind is None:
            raise ValueError("UNAVAILABLE requires error_kind")
        return self


class RecommendationPerformance(BaseModel):
    """Immutable price-comparison result without investment advice or prediction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry: RecommendationPriceSnapshot
    latest: Optional[RecommendationPriceSnapshot]
    return_percent: Optional[Decimal] = None
