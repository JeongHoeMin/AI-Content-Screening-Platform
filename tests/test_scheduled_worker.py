from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from app.config import ConfigurationError, DatabaseConfig, KrxConfig
from app.harness.scheduled_recommendations import (
    ScheduledRecommendationOutcome,
    ScheduledRecommendationRunner,
    ScheduledRecommendationWorker,
)
from app.harness.telegram import TelegramRecommendationSummary
from app.models.scheduled_recommendation import ScheduledRecommendationJob
from app.persistence.schedule_repository import ClaimedScheduledRecommendationJob


class _SchedulePersistence:
    def __init__(self, claim: ClaimedScheduledRecommendationJob) -> None:
        self._claim: Optional[ClaimedScheduledRecommendationJob] = claim

    async def claim_due(
        self,
        now_utc: datetime,
        lease_owner: str,
        lease_until: datetime,
    ) -> Optional[ClaimedScheduledRecommendationJob]:
        claim: Optional[ClaimedScheduledRecommendationJob] = self._claim
        self._claim = None
        return claim

    async def complete_execution(
        self,
        execution_id: str,
        job_id: str,
        lease_owner: str,
        status: str,
        error_type: Optional[str],
        finished_at: datetime,
    ) -> bool:
        return True

    async def renew_lease(
        self,
        job_id: str,
        execution_id: str,
        lease_owner: str,
        lease_until: datetime,
    ) -> bool:
        return True


class _Runner:
    async def run(
        self, job: ScheduledRecommendationJob, scheduled_for: datetime
    ) -> ScheduledRecommendationOutcome:
        return ScheduledRecommendationOutcome(
            execution_id="execution-1",
            recommendation_count=1,
            recommendations=("AI · 분석 후보",),
        )


class _Reporter:
    def __init__(self) -> None:
        self.summary: Optional[TelegramRecommendationSummary] = None

    async def deliver(self, summary: TelegramRecommendationSummary) -> Optional[str]:
        self.summary = summary
        return None


def test_worker_claims_due_job_and_sends_telegram_only_when_enabled() -> None:
    now: datetime = datetime(2026, 8, 5, 23, 0, tzinfo=timezone.utc)
    job = ScheduledRecommendationJob(
        id="default", cron_expression="0 8 * * *", telegram_enabled=True
    )
    claim = ClaimedScheduledRecommendationJob(
        job=job,
        scheduled_for=now,
        lease_owner="worker-1",
        lease_until=now + timedelta(minutes=30),
        execution_id="scheduled-default-1",
    )
    reporter = _Reporter()
    worker = ScheduledRecommendationWorker(
        _SchedulePersistence(claim), _Runner(), reporter, "worker-1"
    )

    assert asyncio.run(worker.run_due(now)) == 1
    assert reporter.summary is not None
    assert reporter.summary.recommendation_count == 1


def test_worker_protocol_remains_runner_compatible() -> None:
    assert isinstance(_Runner(), ScheduledRecommendationRunner)


def test_schedule_worker_partial_kis_configuration_keeps_a_price_recorder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.scheduled_worker as scheduled_worker

    class KisClient:
        def __init__(self, config: object) -> None:
            self.config: object = config

    class KrxClient:
        def __init__(self, config: KrxConfig) -> None:
            self.config: KrxConfig = config

    class PricePersistence:
        async def store_entries(self, snapshots: tuple[object, ...]) -> None:
            return None

    database_config = DatabaseConfig(
        url="postgresql+asyncpg://screening:secret@db:5432/screening"
    )
    krx_config = KrxConfig(api_key="krx-key")

    def partial_kis_config() -> None:
        raise ConfigurationError("KIS configuration is incomplete")

    monkeypatch.setattr(scheduled_worker, "load_optional_kis_config", partial_kis_config)
    monkeypatch.setattr(scheduled_worker, "load_krx_config", lambda: krx_config)
    monkeypatch.setattr(scheduled_worker, "KisRealtimePriceClient", KisClient)
    monkeypatch.setattr(scheduled_worker, "KrxClosingPriceClient", KrxClient)
    monkeypatch.setattr(
        scheduled_worker,
        "create_recommendation_price_persistence",
        lambda config: PricePersistence(),
    )

    recorder = scheduled_worker._create_optional_price_recorder(database_config)

    assert recorder is not None
    assert recorder._price_capture._kis_client.config is None
