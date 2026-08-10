"""Harness orchestration for immutable recommendation entry price observations."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol, Tuple, Union

import structlog

from app.market_prices.contracts import PriceLookupObservation
from app.models.candidate_selection import CandidateEvaluation
from app.market_prices.performance import (
    RecommendationPerformanceItem,
    RecommendationPerformancePolicy,
    RecommendationPerformanceResponse,
    RecommendationRunHistoryItem,
    RecommendationRunHistoryResponse,
)
from app.models.market_price import (
    PriceErrorKind,
    RecommendationPerformance,
    RecommendationPriceSnapshot,
)
from app.models.recommendation import RecommendationAction, RecommendationDecision
from app.models.resolved_news_event import ResolvedCompany, ResolvedTicker
from app.persistence.price_repository import RecommendationPriceEntry, SnapshotKind

logger = structlog.get_logger(__name__)


class RecommendationPriceCapture(Protocol):
    """One bounded market-price observation source used by the Harness."""

    async def capture(
        self,
        ticker: str,
        observed_at: datetime,
    ) -> PriceLookupObservation:
        """Capture one safe price observation without persistence side effects."""


class RecommendationPricePersistence(Protocol):
    """Harness boundary for immutable recommendation entry price storage."""

    async def store_entries(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> None:
        """Store entry snapshots, preserving existing snapshot identities."""


class RecommendationPerformancePersistence(Protocol):
    """Harness boundary for refreshing and reading recommendation performance."""

    async def upsert_latest(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> None:
        """Store replacement latest observations under the LATEST identity."""

    async def list_snapshots(self) -> Tuple[RecommendationPriceEntry, ...]:
        """Load safe snapshot records without exposing database implementation."""


class RecommendationPriceRecorder:
    """Record one independent entry-price observation for every priceable decision."""

    def __init__(
        self,
        price_capture: RecommendationPriceCapture,
        persistence: RecommendationPricePersistence,
    ) -> None:
        self._price_capture: RecommendationPriceCapture = price_capture
        self._persistence: RecommendationPricePersistence = persistence

    async def record_entries(
        self,
        run_id: str,
        recommendations: Tuple[Union[RecommendationDecision, CandidateEvaluation], ...],
        observed_at: datetime,
    ) -> None:
        """Capture each resolved direction independently and persist all outcomes."""
        entries: list[RecommendationPriceEntry] = []
        ordinal_index: int
        recommendation: Union[RecommendationDecision, CandidateEvaluation]
        for ordinal_index, recommendation in enumerate(recommendations):
            recommendation_index: int = (
                recommendation.input_index
                if isinstance(recommendation, CandidateEvaluation)
                else ordinal_index
            )
            decision: RecommendationDecision = (
                recommendation.decision
                if isinstance(recommendation, CandidateEvaluation)
                else recommendation
            )
            action: RecommendationAction | None = self._price_action(decision.action)
            company: ResolvedCompany = decision.company_score.company
            ticker: ResolvedTicker | None = company.ticker
            if action is None or ticker is None:
                continue
            try:
                observation: PriceLookupObservation = await self._price_capture.capture(
                    ticker.ticker,
                    observed_at,
                )
            except Exception as error:
                logger.warning(
                    "recommendation_price_capture_failed",
                    run_id=run_id,
                    recommendation_index=recommendation_index,
                    error_type=type(error).__name__,
                )
                observation = PriceLookupObservation.unavailable(
                    observed_at,
                    PriceErrorKind.TRANSPORT,
                )
            snapshot: RecommendationPriceSnapshot = RecommendationPriceSnapshot(
                run_id=run_id,
                recommendation_index=recommendation_index,
                ticker=ticker.ticker,
                action=action,
                status=observation.status,
                price=observation.price,
                basis=observation.basis,
                provider=observation.provider,
                observed_at=observation.observed_at,
                trading_date=observation.trading_date,
                error_kind=observation.error_kind,
            )
            entries.append(
                RecommendationPriceEntry(
                    snapshot=snapshot,
                    snapshot_kind=SnapshotKind.ENTRY,
                    company_id=company.company_id or ticker.ticker,
                    company_name=company.name,
                )
            )
        await self._persistence.store_entries(tuple(entries))

    @staticmethod
    def _price_action(action: RecommendationAction) -> RecommendationAction | None:
        """Normalize recommendation strength to the BUY/SELL snapshot contract."""
        if action in {RecommendationAction.STRONG_BUY, RecommendationAction.BUY}:
            return RecommendationAction.BUY
        if action in {RecommendationAction.STRONG_SELL, RecommendationAction.SELL}:
            return RecommendationAction.SELL
        return None


class RecommendationPerformanceService:
    """Harness-owned latest-price refresh and safe performance projection."""

    def __init__(
        self,
        price_capture: RecommendationPriceCapture,
        persistence: RecommendationPerformancePersistence,
        policy: RecommendationPerformancePolicy | None = None,
    ) -> None:
        self._price_capture: RecommendationPriceCapture = price_capture
        self._persistence: RecommendationPerformancePersistence = persistence
        self._policy: RecommendationPerformancePolicy = policy or RecommendationPerformancePolicy()

    async def refresh_and_query(
        self,
        run_id: str | None = None,
    ) -> RecommendationPerformanceResponse:
        """Refresh and summarize either all entries or only one requested dashboard run."""
        evaluated_at: datetime = datetime.now(timezone.utc)
        entries, items, performances = await self._collect(run_id, evaluated_at)
        return RecommendationPerformanceResponse(
            items=items,
            summary=self._policy.summarize(performances),
            evaluated_at=evaluated_at,
        )

    async def list_run_histories(self) -> RecommendationRunHistoryResponse:
        """Group every stored run's recommendations with their price performance."""
        evaluated_at: datetime = datetime.now(timezone.utc)
        entries, items, performances = await self._collect(None, evaluated_at)
        run_ids_in_order: list[str] = []
        performances_by_run: dict[str, list[RecommendationPerformance]] = {}
        items_by_run: dict[str, list[RecommendationPerformanceItem]] = {}
        observed_at_by_run: dict[str, datetime] = {}
        for entry, item, performance in zip(entries, items, performances):
            run_id: str = entry.snapshot.run_id
            if run_id not in items_by_run:
                run_ids_in_order.append(run_id)
                items_by_run[run_id] = []
                performances_by_run[run_id] = []
                observed_at_by_run[run_id] = entry.snapshot.observed_at
            else:
                observed_at_by_run[run_id] = min(
                    observed_at_by_run[run_id], entry.snapshot.observed_at
                )
            items_by_run[run_id].append(item)
            performances_by_run[run_id].append(performance)
        runs: Tuple[RecommendationRunHistoryItem, ...] = tuple(
            RecommendationRunHistoryItem(
                run_id=run_id,
                observed_at=observed_at_by_run[run_id],
                items=tuple(items_by_run[run_id]),
                summary=self._policy.summarize(tuple(performances_by_run[run_id])),
            )
            for run_id in sorted(
                run_ids_in_order,
                key=lambda candidate: observed_at_by_run[candidate],
                reverse=True,
            )
        )
        return RecommendationRunHistoryResponse(runs=runs, evaluated_at=evaluated_at)

    async def _collect(
        self,
        run_id: str | None,
        evaluated_at: datetime,
    ) -> Tuple[
        Tuple[RecommendationPriceEntry, ...],
        Tuple[RecommendationPerformanceItem, ...],
        Tuple[RecommendationPerformance, ...],
    ]:
        """Refresh latest prices and project entries into items/performances once."""
        stored: Tuple[RecommendationPriceEntry, ...] = await self._persistence.list_snapshots()
        entries: Tuple[RecommendationPriceEntry, ...] = tuple(
            item
            for item in stored
            if item.snapshot_kind is SnapshotKind.ENTRY
            and (run_id is None or item.snapshot.run_id == run_id)
        )
        latest_entries: list[RecommendationPriceEntry] = []
        entry: RecommendationPriceEntry
        for entry in entries:
            latest_entries.append(await self._refresh_latest(entry, evaluated_at))
        if latest_entries:
            await self._persistence.upsert_latest(tuple(latest_entries))
        latest_by_identity: dict[tuple[str, int], RecommendationPriceEntry] = {
            (item.snapshot.run_id, item.snapshot.recommendation_index): item
            for item in latest_entries
        }
        performances = tuple(
            self._policy.evaluate(
                entry.snapshot,
                self._latest_for_entry(entry, latest_by_identity, stored),
            )
            for entry in entries
        )
        items: Tuple[RecommendationPerformanceItem, ...] = tuple(
            self._item(entry, performance.latest, performance.return_percent)
            for entry, performance in zip(entries, performances)
        )
        return entries, items, performances

    async def _refresh_latest(
        self,
        entry: RecommendationPriceEntry,
        observed_at: datetime,
    ) -> RecommendationPriceEntry:
        """Capture one latest observation without allowing one provider failure to abort peers."""
        try:
            observation: PriceLookupObservation = await self._price_capture.capture(
                entry.snapshot.ticker,
                observed_at,
            )
        except Exception as error:
            logger.warning(
                "recommendation_latest_price_capture_failed",
                run_id=entry.snapshot.run_id,
                recommendation_index=entry.snapshot.recommendation_index,
                error_type=type(error).__name__,
            )
            observation = PriceLookupObservation.unavailable(
                observed_at,
                PriceErrorKind.TRANSPORT,
            )
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
            snapshot_kind=SnapshotKind.LATEST,
            company_id=entry.company_id,
            company_name=entry.company_name,
        )

    @staticmethod
    def _latest_for_entry(
        entry: RecommendationPriceEntry,
        refreshed: dict[tuple[str, int], RecommendationPriceEntry],
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> RecommendationPriceSnapshot | None:
        """Prefer this query's refresh and otherwise retain a separately persisted latest."""
        identity: tuple[str, int] = (
            entry.snapshot.run_id,
            entry.snapshot.recommendation_index,
        )
        refreshed_latest: RecommendationPriceEntry | None = refreshed.get(identity)
        if refreshed_latest is not None:
            return refreshed_latest.snapshot
        for item in snapshots:
            if (
                item.snapshot_kind is SnapshotKind.LATEST
                and item.snapshot.run_id == entry.snapshot.run_id
                and item.snapshot.recommendation_index
                == entry.snapshot.recommendation_index
            ):
                return item.snapshot
        return None

    @staticmethod
    def _item(
        entry: RecommendationPriceEntry,
        latest: RecommendationPriceSnapshot | None,
        return_percent: Decimal | None,
    ) -> RecommendationPerformanceItem:
        """Project validated snapshots without status error detail or provider payloads."""
        return RecommendationPerformanceItem(
            run_id=entry.snapshot.run_id,
            recommendation_index=entry.snapshot.recommendation_index,
            company_name=entry.company_name,
            ticker=entry.snapshot.ticker,
            action=entry.snapshot.action,
            entry_price=(float(entry.snapshot.price) if entry.snapshot.price is not None else None),
            entry_provider=entry.snapshot.provider,
            entry_basis=entry.snapshot.basis,
            entry_observed_at=entry.snapshot.observed_at,
            entry_error_kind=entry.snapshot.error_kind,
            latest_price=(float(latest.price) if latest is not None and latest.price is not None else None),
            latest_observed_at=latest.observed_at if latest is not None else None,
            latest_error_kind=latest.error_kind if latest is not None else None,
            return_percent=(float(return_percent) if return_percent is not None else None),
        )
