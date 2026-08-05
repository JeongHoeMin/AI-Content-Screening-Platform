from __future__ import annotations

from datetime import datetime, timezone
import asyncio

from app.harness.telegram import TelegramBotReporter, TelegramRecommendationSummary
from app.models.recommendation import RecommendationAction


def test_telegram_summary_includes_at_most_ten_safe_price_candidates() -> None:
    candidates: tuple[str, ...] = tuple(
        f"회사-{index} · buy · {72000 + index} KRW · close"
        for index in range(11)
    )
    summary = TelegramRecommendationSummary(
        execution_id="execution-1",
        scheduled_for=datetime(2026, 8, 5, 23, 0, tzinfo=timezone.utc),
        recommendation_count=11,
        recommendations=candidates,
    )

    text: str = TelegramBotReporter._format_summary(summary)

    assert "회사-9 · buy · 72009 KRW · close" in text
    assert "회사-10" not in text
    assert "secret" not in text.lower()
    assert "payload" not in text.lower()


def test_scheduled_runner_projects_entry_price_and_basis_for_telegram() -> None:
    from app.market_prices.performance import (
        RecommendationPerformanceItem,
        RecommendationPerformanceResponse,
        RecommendationPerformanceSummary,
    )
    from app.models.scheduled_recommendation import ScheduledRecommendationJob
    from app.scheduled_worker import DashboardScheduledRecommendationRunner
    from app.web.app import CollectionFilterSummary, DashboardRunResult, RecommendationCard

    class _Manager:
        async def run_scheduled(self, request: object) -> DashboardRunResult:
            return DashboardRunResult(
                run_id="run-1",
                news_cards=[],
                analyses=[],
                recommendations=[
                    RecommendationCard(
                        company_name="삼성전자",
                        ticker="005930",
                        exchange="kospi",
                        score=2.0,
                        action="buy",
                        reason_code="score_at_or_above_buy_threshold",
                    )
                ],
                statistics={},
                collection_filter=CollectionFilterSummary(
                    catalog_version="v1",
                    accepted_count=0,
                    excluded_count=0,
                    rejection_counts={},
                ),
            )

        async def recommendation_performance(self) -> RecommendationPerformanceResponse:
            return RecommendationPerformanceResponse(
                items=(
                    RecommendationPerformanceItem(
                        run_id="run-1",
                        recommendation_index=0,
                        company_name="삼성전자",
                        ticker="005930",
                        action=RecommendationAction.BUY,
                        entry_price=72000.0,
                        entry_provider="kis",
                        entry_basis="realtime",
                        entry_observed_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
                    ),
                ),
                summary=RecommendationPerformanceSummary(),
                evaluated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            )

    outcome = asyncio.run(
        DashboardScheduledRecommendationRunner(_Manager()).run(  # type: ignore[arg-type]
            ScheduledRecommendationJob(id="default", cron_expression="0 8 * * *"),
            datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
    )

    assert outcome.recommendations == ("삼성전자 · buy · 72000 KRW · realtime",)
