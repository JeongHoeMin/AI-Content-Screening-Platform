"""Harness recovery of recommendation entry prices that never resolved."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Protocol, Tuple
from zoneinfo import ZoneInfo

import structlog

from app.market_prices.contracts import PriceLookupClient, PriceLookupObservation
from app.models.market_price import (
    PriceSnapshotStatus,
    RecommendationPriceSnapshot,
)
from app.persistence.price_repository import RecommendationPriceEntry, SnapshotKind

logger = structlog.get_logger(__name__)

_KST: ZoneInfo = ZoneInfo("Asia/Seoul")


class EntryPriceBackfillPersistence(Protocol):
    """Harness boundary for reading and recovering unpriced entry snapshots."""

    async def list_snapshots(self) -> Tuple[RecommendationPriceEntry, ...]:
        """Load safe snapshot records without exposing database implementation."""

    async def backfill_entries(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> int:
        """Recover entry observations that never obtained a price."""


class HistoricalClosingPriceCapture:
    """Observe the close of a past trading day, never a live quote.

    An entry price answers "what did this cost when it was recommended", so a
    recovery lookup must go to the daily-close source with the original
    observation time. The realtime client would answer today's question instead.
    """

    def __init__(self, closing_price_client: PriceLookupClient) -> None:
        self._closing_price_client: PriceLookupClient = closing_price_client

    async def capture(
        self,
        ticker: str,
        observed_at: datetime,
    ) -> PriceLookupObservation:
        """Return the nearest close on or before the original recommendation time."""
        return await self._closing_price_client.fetch(ticker, observed_at)


class RecommendationEntryPriceBackfill:
    """Re-observe unpriced entry snapshots at their own recommendation time."""

    def __init__(
        self,
        historical_capture: HistoricalClosingPriceCapture,
        persistence: EntryPriceBackfillPersistence,
    ) -> None:
        self._historical_capture: HistoricalClosingPriceCapture = historical_capture
        self._persistence: EntryPriceBackfillPersistence = persistence

    async def backfill(
        self,
        run_id: Optional[str] = None,
        recommendation_index: Optional[int] = None,
    ) -> int:
        """Recover every selected unpriced entry and return how many now have a price."""
        pending: Tuple[RecommendationPriceEntry, ...] = await self._pending_entries(
            run_id,
            recommendation_index,
        )
        recovered: list[RecommendationPriceEntry] = []
        entry: RecommendationPriceEntry
        for entry in pending:
            observation: Optional[PriceLookupObservation] = await self._observe(entry)
            if observation is None:
                continue
            recovered.append(self._recovered_entry(entry, observation))
        if not recovered:
            return 0
        return await self._persistence.backfill_entries(tuple(recovered))

    async def _pending_entries(
        self,
        run_id: Optional[str],
        recommendation_index: Optional[int],
    ) -> Tuple[RecommendationPriceEntry, ...]:
        """Select stored entry snapshots that are still without a price."""
        stored: Tuple[RecommendationPriceEntry, ...] = (
            await self._persistence.list_snapshots()
        )
        return tuple(
            entry
            for entry in stored
            if entry.snapshot_kind is SnapshotKind.ENTRY
            and entry.snapshot.status is PriceSnapshotStatus.UNAVAILABLE
            and (run_id is None or entry.snapshot.run_id == run_id)
            and (
                recommendation_index is None
                or entry.snapshot.recommendation_index == recommendation_index
            )
        )

    async def _observe(
        self,
        entry: RecommendationPriceEntry,
    ) -> Optional[PriceLookupObservation]:
        """Capture one recovery observation without letting a failure abort its peers."""
        try:
            observation: PriceLookupObservation = await self._historical_capture.capture(
                entry.snapshot.ticker,
                entry.snapshot.observed_at,
            )
        except Exception as error:
            logger.warning(
                "recommendation_entry_price_backfill_failed",
                run_id=entry.snapshot.run_id,
                recommendation_index=entry.snapshot.recommendation_index,
                error_type=type(error).__name__,
            )
            return None
        if observation.status is not PriceSnapshotStatus.AVAILABLE:
            return None
        return observation

    @staticmethod
    def _recovered_entry(
        entry: RecommendationPriceEntry,
        observation: PriceLookupObservation,
    ) -> RecommendationPriceEntry:
        """Rebuild the entry identity around its recovered price observation."""
        return RecommendationPriceEntry(
            snapshot=RecommendationPriceSnapshot(
                run_id=entry.snapshot.run_id,
                recommendation_index=entry.snapshot.recommendation_index,
                ticker=entry.snapshot.ticker,
                action=entry.snapshot.action,
                status=observation.status,
                price=observation.price,
                basis=observation.basis,
                provider=observation.provider,
                observed_at=observation.observed_at,
                trading_date=observation.trading_date,
                error_kind=observation.error_kind,
            ),
            snapshot_kind=SnapshotKind.ENTRY,
            company_id=entry.company_id,
            company_name=entry.company_name,
        )


class DailyEntryPriceBackfill:
    """Run the entry-price recovery at most once per KST calendar day."""

    def __init__(self, backfill: RecommendationEntryPriceBackfill) -> None:
        self._backfill: RecommendationEntryPriceBackfill = backfill
        self._last_run_date: Optional[date] = None

    async def run_if_due(self, now_utc: datetime) -> Optional[int]:
        """Recover unpriced entries once a day, returning None when already done today."""
        today_kst: date = now_utc.astimezone(_KST).date()
        if self._last_run_date == today_kst:
            return None
        # Claimed before the work starts so a failing run does not retry on every
        # poll of the worker loop; the next calendar day is the next attempt.
        self._last_run_date = today_kst
        try:
            recovered_count: int = await self._backfill.backfill()
        except Exception as error:
            logger.warning(
                "recommendation_entry_price_daily_backfill_failed",
                error_type=type(error).__name__,
            )
            return 0
        logger.info(
            "recommendation_entry_price_daily_backfill_completed",
            recovered_count=recovered_count,
        )
        return recovered_count
