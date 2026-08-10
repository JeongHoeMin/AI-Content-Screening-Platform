from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import pytest

from app.config import ConfigurationError, DatabaseConfig, KrxConfig
from app.market_prices.contracts import PriceLookupObservation
from app.models.company_resolution import KRXExchange
from app.models.market_price import (
    PriceBasis,
    PriceErrorKind,
    PriceProvider,
    PriceSnapshotStatus,
)
from app.models.news_event import CompanyRelation
from app.models.recommendation import RecommendationAction, RecommendationDecision
from app.models.resolved_news_event import ResolvedCompany, ResolvedTicker
from app.models.scoring import CompanyScore
from app.web.app import DashboardRunManager, DashboardRunResult, RecommendationRunRequest


class _Recorder:
    def __init__(self, fail: bool = False) -> None:
        self.fail: bool = fail
        self.calls: list[tuple[str, tuple[object, ...], datetime]] = []

    async def record_entries(
        self,
        run_id: str,
        recommendations: tuple[object, ...],
        observed_at: datetime,
    ) -> None:
        self.calls.append((run_id, recommendations, observed_at))
        if self.fail:
            raise RuntimeError("price persistence failed")


class _PricePersistence:
    def __init__(self) -> None:
        self.snapshots: tuple[object, ...] = ()

    async def store_entries(self, snapshots: tuple[object, ...]) -> None:
        self.snapshots = snapshots


class _KisUnavailableClient:
    def __init__(self, config: object) -> None:
        self.config: object = config

    async def fetch(self, ticker: str, observed_at: datetime) -> PriceLookupObservation:
        return PriceLookupObservation.unavailable(
            observed_at,
            PriceErrorKind.NOT_CONFIGURED,
        )


class _KrxAvailableClient:
    def __init__(self, config: KrxConfig) -> None:
        self.config: KrxConfig = config

    async def fetch(self, ticker: str, observed_at: datetime) -> PriceLookupObservation:
        return PriceLookupObservation(
            status=PriceSnapshotStatus.AVAILABLE,
            price=Decimal("72000"),
            basis=PriceBasis.CLOSE,
            provider=PriceProvider.KRX,
            observed_at=observed_at,
            trading_date=observed_at.date(),
        )


def _buy_decision(ticker: str = "005930") -> RecommendationDecision:
    from app.models.recommendation import (
        DEFAULT_RECOMMENDATION_THRESHOLD_SNAPSHOT,
        RecommendationReasonCode,
    )

    return RecommendationDecision.model_construct(
        company_score=CompanyScore.model_construct(
            company=ResolvedCompany(
                name=f"회사-{ticker}",
                relation=CompanyRelation.DIRECT,
                ticker=ResolvedTicker(ticker=ticker, exchange=KRXExchange.KOSPI),
                company_id=f"company-{ticker}",
                resolution_status="resolved",
                directory_version="2026-08-05",
            ),
            score=2.0,
        ),
        action=RecommendationAction.BUY,
        reason_code=RecommendationReasonCode.SCORE_AT_OR_ABOVE_BUY_THRESHOLD,
        threshold_snapshot=DEFAULT_RECOMMENDATION_THRESHOLD_SNAPSHOT,
    )


def test_dashboard_price_recording_is_optional_and_best_effort() -> None:
    manager = DashboardRunManager()

    asyncio.run(manager._record_price_entries("run-1", (), datetime(2026, 8, 5, tzinfo=timezone.utc)))

    assert manager._price_recorder is None


def test_dashboard_price_recording_does_not_raise_when_recorder_fails() -> None:
    recorder = _Recorder(fail=True)
    manager = DashboardRunManager(price_recorder=recorder)  # type: ignore[arg-type]

    asyncio.run(manager._record_price_entries("run-1", (), datetime(2026, 8, 5, tzinfo=timezone.utc)))

    assert len(recorder.calls) == 1


def test_dashboard_partial_kis_configuration_keeps_krx_entry_price_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.web.app as dashboard_app

    persistence = _PricePersistence()
    database_config = DatabaseConfig(
        url="postgresql+asyncpg://screening:secret@db:5432/screening"
    )
    krx_config = KrxConfig(api_key="krx-key")

    def _partial_kis_config() -> None:
        raise ConfigurationError("KIS configuration is incomplete")

    monkeypatch.setattr(
        dashboard_app,
        "load_optional_database_config",
        lambda: database_config,
    )
    monkeypatch.setattr(dashboard_app, "load_optional_kis_config", _partial_kis_config)
    monkeypatch.setattr(dashboard_app, "load_krx_config", lambda: krx_config)
    monkeypatch.setattr(dashboard_app, "KisRealtimePriceClient", _KisUnavailableClient)
    monkeypatch.setattr(dashboard_app, "KrxClosingPriceClient", _KrxAvailableClient)
    monkeypatch.setattr(
        dashboard_app,
        "create_recommendation_price_persistence",
        lambda config: persistence,
    )

    recorder = dashboard_app._create_optional_price_recorder()

    assert recorder is not None
    asyncio.run(
        recorder.record_entries(
            "run-1",
            (_buy_decision(),),
            datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
    )
    assert len(persistence.snapshots) == 1
    assert persistence.snapshots[0].snapshot.status is PriceSnapshotStatus.AVAILABLE  # type: ignore[union-attr]
    assert persistence.snapshots[0].snapshot.provider is PriceProvider.KRX  # type: ignore[union-attr]


def test_dashboard_selected_price_recommendations_exclude_unselected_buy() -> None:
    from app.harness.recommendation_prices import RecommendationPriceRecorder
    from app.models.candidate_selection import (
        CandidateEvaluation,
        CandidateSelectionResult,
        CandidateStatus,
    )

    selected_decision = _buy_decision("005930")
    excluded_buy_decision = _buy_decision("000660")
    selected = CandidateEvaluation.model_construct(
        status=CandidateStatus.SELECTED,
        decision=selected_decision,
        rank=1,
        input_index=0,
    )
    excluded_buy = CandidateEvaluation.model_construct(
        status=CandidateStatus.OUTSIDE_LIMIT,
        decision=excluded_buy_decision,
        rank=None,
        input_index=1,
    )
    candidate_selection = CandidateSelectionResult.model_construct(
        policy_version="v1",
        evaluations=(selected, excluded_buy),
    )

    recommendations = DashboardRunManager._selected_price_recommendations(
        candidate_selection
    )

    assert recommendations == (selected,)
    assert tuple(item.decision for item in recommendations) == (selected_decision,)
    assert excluded_buy_decision not in tuple(
        item.decision for item in recommendations
    )
    persistence = _PricePersistence()
    recorder = RecommendationPriceRecorder(
        _KrxAvailableClient(KrxConfig(api_key="krx-key")),
        persistence,  # type: ignore[arg-type]
    )

    asyncio.run(
        recorder.record_entries(
            "run-1",
            recommendations,
            datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
    )

    assert len(persistence.snapshots) == 1


def test_manual_and_scheduled_runs_share_the_price_recording_execution_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _Recorder()
    manager = DashboardRunManager(price_recorder=recorder)  # type: ignore[arg-type]
    executed_run_ids: list[str] = []

    async def execute(
        run_id: str,
        state: object,
        request: RecommendationRunRequest,
        notify: bool = False,
    ) -> None:
        executed_run_ids.append(run_id)
        await manager._record_price_entries(
            run_id,
            (),
            datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
        setattr(state, "result", DashboardRunResult.model_construct(run_id=run_id))
        setattr(state, "completed", True)

    monkeypatch.setattr(manager, "_execute", execute)

    async def run_both_paths() -> DashboardRunResult:
        await manager.start(RecommendationRunRequest())
        await asyncio.sleep(0)
        return await manager.run_scheduled(RecommendationRunRequest())

    scheduled_result = asyncio.run(run_both_paths())

    assert len(executed_run_ids) == 2
    assert len(recorder.calls) == 2
    assert scheduled_result.run_id == executed_run_ids[1]
