"""Deterministic recommendation price-performance policy and safe DTOs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from statistics import median
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.models.market_price import (
    PriceBasis,
    PriceErrorKind,
    PriceProvider,
    PriceSnapshotStatus,
    RecommendationPerformance,
    RecommendationPriceSnapshot,
)
from app.models.recommendation import RecommendationAction

_PERCENT_QUANTUM: Decimal = Decimal("0.1")


class RecommendationPerformanceSummary(BaseModel):
    """Aggregate only price-comparison observations that can be evaluated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    confirmed_count: int = Field(default=0, ge=0)
    unavailable_count: int = Field(default=0, ge=0)
    buy_count: int = Field(default=0, ge=0)
    sell_count: int = Field(default=0, ge=0)
    positive_win_rate: Optional[float] = Field(default=None, ge=0, le=100)
    mean_return_percent: Optional[float] = None
    median_return_percent: Optional[float] = None
    latest_observed_at: Optional[datetime] = None


class RecommendationPerformanceItem(BaseModel):
    """One browser-safe entry/latest projection without provider payloads."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1)
    recommendation_index: int = Field(ge=0)
    company_name: str = Field(min_length=1)
    ticker: str = Field(pattern=r"^\d{6}$")
    action: RecommendationAction
    entry_price: Optional[float] = None
    entry_provider: Optional[PriceProvider] = None
    entry_basis: Optional[PriceBasis] = None
    entry_observed_at: Optional[datetime] = None
    entry_error_kind: Optional[PriceErrorKind] = None
    latest_price: Optional[float] = None
    latest_observed_at: Optional[datetime] = None
    latest_error_kind: Optional[PriceErrorKind] = None
    return_percent: Optional[float] = None


class RecommendationPerformanceResponse(BaseModel):
    """The complete, bounded response of the recommendation performance API."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: Tuple[RecommendationPerformanceItem, ...] = ()
    summary: RecommendationPerformanceSummary = RecommendationPerformanceSummary()
    evaluated_at: datetime


class RecommendationRunHistoryItem(BaseModel):
    """One past run's recommendations and price-performance summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1)
    observed_at: datetime
    items: Tuple[RecommendationPerformanceItem, ...] = ()
    summary: RecommendationPerformanceSummary = RecommendationPerformanceSummary()


class RecommendationRunHistoryResponse(BaseModel):
    """Every priced run, most recent first, for the history page."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runs: Tuple[RecommendationRunHistoryItem, ...] = ()
    evaluated_at: datetime


class RecommendationPerformancePolicy:
    """Evaluate simple directional price changes without making investment decisions."""

    def evaluate(
        self,
        entry: RecommendationPriceSnapshot,
        latest: Optional[RecommendationPriceSnapshot],
    ) -> RecommendationPerformance:
        """Return a one-decimal simple return only when both snapshots agree."""
        return_percent: Optional[Decimal] = None
        if self._is_comparable(entry, latest):
            assert latest is not None
            assert entry.price is not None
            assert latest.price is not None
            difference: Decimal = (
                latest.price - entry.price
                if entry.action is RecommendationAction.BUY
                else entry.price - latest.price
            )
            return_percent = (difference / entry.price * Decimal("100")).quantize(
                _PERCENT_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
        return RecommendationPerformance(
            entry=entry,
            latest=latest,
            return_percent=return_percent,
        )

    def summarize(
        self,
        performances: Tuple[RecommendationPerformance, ...],
    ) -> RecommendationPerformanceSummary:
        """Summarize known returns while retaining unavailable observations separately."""
        returns: tuple[Decimal, ...] = tuple(
            performance.return_percent
            for performance in performances
            if performance.return_percent is not None
        )
        confirmed_count: int = len(returns)
        latest_times: tuple[datetime, ...] = tuple(
            performance.latest.observed_at
            for performance in performances
            if performance.latest is not None
        )
        buy_count: int = sum(
            performance.entry.action is RecommendationAction.BUY
            for performance in performances
        )
        sell_count: int = sum(
            performance.entry.action is RecommendationAction.SELL
            for performance in performances
        )
        if not returns:
            return RecommendationPerformanceSummary(
                confirmed_count=0,
                unavailable_count=len(performances),
                buy_count=buy_count,
                sell_count=sell_count,
                latest_observed_at=max(latest_times) if latest_times else None,
            )
        positive_count: int = sum(value > Decimal("0") for value in returns)
        win_rate: Decimal = (
            Decimal(positive_count) / Decimal(confirmed_count) * Decimal("100")
        ).quantize(_PERCENT_QUANTUM, rounding=ROUND_HALF_UP)
        mean_value: Decimal = (sum(returns) / Decimal(confirmed_count)).quantize(
            _PERCENT_QUANTUM,
            rounding=ROUND_HALF_UP,
        )
        median_value: Decimal = Decimal(str(median(returns))).quantize(
            _PERCENT_QUANTUM,
            rounding=ROUND_HALF_UP,
        )
        return RecommendationPerformanceSummary(
            confirmed_count=confirmed_count,
            unavailable_count=len(performances) - confirmed_count,
            buy_count=buy_count,
            sell_count=sell_count,
            positive_win_rate=float(win_rate),
            mean_return_percent=float(mean_value),
            median_return_percent=float(median_value),
            latest_observed_at=max(latest_times) if latest_times else None,
        )

    @staticmethod
    def _is_comparable(
        entry: RecommendationPriceSnapshot,
        latest: Optional[RecommendationPriceSnapshot],
    ) -> bool:
        """Reject unavailable, non-positive, or incompatible observations."""
        if latest is None:
            return False
        if (
            entry.status is not PriceSnapshotStatus.AVAILABLE
            or latest.status is not PriceSnapshotStatus.AVAILABLE
            or entry.price is None
            or latest.price is None
        ):
            return False
        if entry.price <= Decimal("0") or latest.price <= Decimal("0"):
            return False
        return entry.ticker == latest.ticker and entry.currency == latest.currency
