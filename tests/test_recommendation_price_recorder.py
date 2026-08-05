from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

from app.market_prices.contracts import PriceLookupObservation
from app.models.company_resolution import KRXExchange
from app.models.news_event import CompanyRelation
from app.models.market_price import (
    PriceBasis,
    PriceErrorKind,
    PriceProvider,
    PriceSnapshotStatus,
)
from app.models.recommendation import RecommendationAction, RecommendationDecision
from app.models.scoring import CompanyScore


class _PriceService:
    def __init__(self) -> None:
        self._calls: list[str] = []

    async def capture(self, ticker: str, observed_at: datetime) -> PriceLookupObservation:
        self._calls.append(ticker)
        if ticker == "000660":
            return PriceLookupObservation.unavailable(
                observed_at,
                PriceErrorKind.NOT_FOUND,
            )
        return PriceLookupObservation(
            status=PriceSnapshotStatus.AVAILABLE,
            price=Decimal("72000"),
            basis=PriceBasis.CLOSE,
            provider=PriceProvider.KRX,
            observed_at=observed_at,
            trading_date=date(2026, 8, 4),
        )


class _Persistence:
    def __init__(self) -> None:
        self.snapshots: tuple[object, ...] = ()

    async def store_entries(self, snapshots: tuple[object, ...]) -> None:
        self.snapshots = snapshots


class _PartiallyFailingPriceService(_PriceService):
    async def capture(self, ticker: str, observed_at: datetime) -> PriceLookupObservation:
        if ticker == "000660":
            raise RuntimeError("provider failure")
        return await super().capture(ticker, observed_at)


def _decision(ticker: str, action: RecommendationAction) -> RecommendationDecision:
    from app.models.recommendation import (
        DEFAULT_RECOMMENDATION_THRESHOLD_SNAPSHOT,
        RecommendationReasonCode,
    )
    from app.models.resolved_news_event import ResolvedCompany, ResolvedTicker

    reasons: dict[RecommendationAction, RecommendationReasonCode] = {
        RecommendationAction.STRONG_BUY: RecommendationReasonCode.SCORE_AT_OR_ABOVE_STRONG_BUY_THRESHOLD,
        RecommendationAction.BUY: RecommendationReasonCode.SCORE_AT_OR_ABOVE_BUY_THRESHOLD,
        RecommendationAction.SELL: RecommendationReasonCode.SCORE_AT_OR_BELOW_SELL_THRESHOLD,
        RecommendationAction.STRONG_SELL: RecommendationReasonCode.SCORE_AT_OR_BELOW_STRONG_SELL_THRESHOLD,
    }
    scores: dict[RecommendationAction, float] = {
        RecommendationAction.STRONG_BUY: 3.0,
        RecommendationAction.BUY: 2.0,
        RecommendationAction.SELL: -2.0,
        RecommendationAction.STRONG_SELL: -3.0,
    }
    return RecommendationDecision.model_construct(
        company_score=CompanyScore.model_construct(
            company=ResolvedCompany(
                name=f"회사-{ticker}",
                relation=CompanyRelation.DIRECT,
                ticker=ResolvedTicker(
                    ticker=ticker,
                    exchange=KRXExchange.KOSPI,
                ),
                company_id=f"company-{ticker}",
                resolution_status="resolved",
                directory_version="2026-08-05",
            ),
            score=scores[action],
        ),
        action=action,
        reason_code=reasons[action],
        threshold_snapshot=DEFAULT_RECOMMENDATION_THRESHOLD_SNAPSHOT,
    )


def test_recorder_stores_available_and_unavailable_buy_snapshots_independently() -> None:
    from app.harness.recommendation_prices import RecommendationPriceRecorder

    persistence = _Persistence()
    recorder = RecommendationPriceRecorder(_PriceService(), persistence)  # type: ignore[arg-type]

    asyncio.run(
        recorder.record_entries(
            "run-1",
            (_decision("005930", RecommendationAction.BUY), _decision("000660", RecommendationAction.BUY)),
            datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
    )

    assert len(persistence.snapshots) == 2
    assert persistence.snapshots[0].snapshot.status is PriceSnapshotStatus.AVAILABLE  # type: ignore[union-attr]
    assert persistence.snapshots[1].snapshot.status is PriceSnapshotStatus.UNAVAILABLE  # type: ignore[union-attr]


def test_recorder_normalizes_strong_buy_and_strong_sell_for_the_price_contract() -> None:
    from app.harness.recommendation_prices import RecommendationPriceRecorder

    persistence = _Persistence()
    recorder = RecommendationPriceRecorder(_PriceService(), persistence)  # type: ignore[arg-type]

    asyncio.run(
        recorder.record_entries(
            "run-1",
            (
                _decision("005930", RecommendationAction.STRONG_BUY),
                _decision("000660", RecommendationAction.STRONG_SELL),
            ),
            datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
    )

    assert persistence.snapshots[0].snapshot.action is RecommendationAction.BUY  # type: ignore[union-attr]
    assert persistence.snapshots[1].snapshot.action is RecommendationAction.SELL  # type: ignore[union-attr]


def test_recorder_preserves_sibling_entry_when_one_price_capture_raises() -> None:
    from app.harness.recommendation_prices import RecommendationPriceRecorder

    persistence = _Persistence()
    recorder = RecommendationPriceRecorder(_PartiallyFailingPriceService(), persistence)  # type: ignore[arg-type]

    asyncio.run(
        recorder.record_entries(
            "run-1",
            (_decision("005930", RecommendationAction.BUY), _decision("000660", RecommendationAction.BUY)),
            datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
    )

    assert len(persistence.snapshots) == 2
    assert persistence.snapshots[1].snapshot.error_kind is PriceErrorKind.TRANSPORT  # type: ignore[union-attr]


def test_recorder_keeps_all_25_priceable_recommendations_after_one_capture_failure() -> None:
    from app.harness.recommendation_prices import RecommendationPriceRecorder

    tickers: tuple[str, ...] = tuple(f"{index:06d}" for index in range(1, 25)) + ("000660",)
    recommendations: tuple[RecommendationDecision, ...] = tuple(
        _decision(ticker, RecommendationAction.BUY) for ticker in tickers
    )
    persistence = _Persistence()
    recorder = RecommendationPriceRecorder(_PartiallyFailingPriceService(), persistence)  # type: ignore[arg-type]

    asyncio.run(
        recorder.record_entries(
            "run-25",
            recommendations,
            datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
    )

    assert len(persistence.snapshots) == 25
    assert persistence.snapshots[-1].snapshot.status is PriceSnapshotStatus.UNAVAILABLE  # type: ignore[union-attr]
