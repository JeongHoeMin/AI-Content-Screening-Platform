from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from fastapi.testclient import TestClient

from app.web.app import DashboardRunManager, create_web_app


class _HistoryService(Protocol):
    async def list_run_histories(self, refresh: bool = False) -> object:
        """Return the safe response projected by the dashboard history API."""


class _EmptyHistoryService:
    async def list_run_histories(self, refresh: bool = False) -> object:
        from app.market_prices.performance import RecommendationRunHistoryResponse

        return RecommendationRunHistoryResponse(
            evaluated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )


class _TwoRunHistoryService:
    async def list_run_histories(self, refresh: bool = False) -> object:
        from app.market_prices.performance import (
            RecommendationPerformanceItem,
            RecommendationPerformanceSummary,
            RecommendationRunHistoryItem,
            RecommendationRunHistoryResponse,
        )

        return RecommendationRunHistoryResponse(
            runs=(
                RecommendationRunHistoryItem(
                    run_id="run-newer",
                    observed_at=datetime(2026, 8, 6, tzinfo=timezone.utc),
                    items=(
                        RecommendationPerformanceItem(
                            run_id="run-newer",
                            recommendation_index=0,
                            company_name="삼성전자",
                            ticker="005930",
                            action="buy",
                            entry_price=100.0,
                            latest_price=110.0,
                            return_percent=10.0,
                        ),
                    ),
                    summary=RecommendationPerformanceSummary(confirmed_count=1, buy_count=1),
                ),
                RecommendationRunHistoryItem(
                    run_id="run-older",
                    observed_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
                ),
            ),
            evaluated_at=datetime(2026, 8, 6, tzinfo=timezone.utc),
        )


def test_history_api_returns_empty_runs_when_no_performance_service_is_configured() -> None:
    client = TestClient(create_web_app(DashboardRunManager()))

    response = client.get("/api/runs/history")

    assert response.status_code == 200
    payload: dict[str, object] = response.json()
    assert payload["runs"] == []


def test_history_api_returns_runs_grouped_most_recent_first() -> None:
    manager = DashboardRunManager(
        performance_service=_TwoRunHistoryService(),  # type: ignore[arg-type]
    )
    client = TestClient(create_web_app(manager))

    response = client.get("/api/runs/history")

    assert response.status_code == 200
    payload: dict[str, object] = response.json()
    assert [run["run_id"] for run in payload["runs"]] == ["run-newer", "run-older"]
    assert payload["runs"][0]["items"][0]["return_percent"] == 10.0
    assert "secret" not in response.text.lower()
    assert "payload" not in response.text.lower()
