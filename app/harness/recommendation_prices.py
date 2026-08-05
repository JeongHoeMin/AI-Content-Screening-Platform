"""Harness orchestration for immutable recommendation entry price observations."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, Tuple, Union

import structlog

from app.market_prices.contracts import PriceLookupObservation
from app.models.candidate_selection import CandidateEvaluation
from app.models.market_price import PriceErrorKind, RecommendationPriceSnapshot
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
