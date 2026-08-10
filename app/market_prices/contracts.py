"""Immutable contracts shared by market-price transport adapters."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, Protocol

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.market_price import (
    PriceBasis,
    PriceErrorKind,
    PriceProvider,
    PriceSnapshotStatus,
)


class PriceLookupObservation(BaseModel):
    """One safe, immutable market-price lookup outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: PriceSnapshotStatus
    price: Optional[Decimal] = None
    basis: Optional[PriceBasis] = None
    provider: Optional[PriceProvider] = None
    observed_at: datetime
    trading_date: Optional[date] = None
    error_kind: Optional[PriceErrorKind] = None

    @field_validator("observed_at")
    @classmethod
    def _require_utc_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("observed_at must be an aware UTC datetime")
        return value

    @model_validator(mode="after")
    def _require_consistent_availability_fields(self) -> "PriceLookupObservation":
        if self.status is PriceSnapshotStatus.AVAILABLE:
            if self.price is None or self.price <= Decimal("0"):
                raise ValueError("AVAILABLE requires a positive price")
            if self.basis is None or self.provider is None or self.trading_date is None:
                raise ValueError("AVAILABLE requires basis, provider, and trading_date")
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

    @classmethod
    def unavailable(
        cls,
        observed_at: datetime,
        error_kind: PriceErrorKind,
    ) -> "PriceLookupObservation":
        """Build a bounded unavailable lookup outcome."""
        return cls(
            status=PriceSnapshotStatus.UNAVAILABLE,
            observed_at=observed_at,
            error_kind=error_kind,
        )


class PriceLookupClient(Protocol):
    """A source of one price observation without persistence side effects."""

    async def fetch(
        self,
        ticker: str,
        observed_at: datetime,
    ) -> PriceLookupObservation:
        """Return one bounded price lookup observation."""
