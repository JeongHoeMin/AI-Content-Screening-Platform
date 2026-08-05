from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from fastapi.testclient import TestClient

from app.web.app import DashboardRunManager, create_web_app


class _PerformanceService(Protocol):
    async def refresh_and_query(self) -> object:
        """Return the safe response projected by the dashboard API."""


class _UnavailablePerformanceService:
    async def refresh_and_query(self) -> object:
        from app.market_prices.performance import (
            RecommendationPerformanceItem,
            RecommendationPerformanceResponse,
            RecommendationPerformanceSummary,
        )

        return RecommendationPerformanceResponse(
            items=(
                RecommendationPerformanceItem(
                    run_id="run-1",
                    recommendation_index=0,
                    company_name="삼성전자",
                    ticker="005930",
                    action="buy",
                    entry_price=None,
                    entry_provider=None,
                    entry_basis=None,
                    entry_observed_at=None,
                    latest_price=None,
                    latest_observed_at=None,
                    return_percent=None,
                ),
            ),
            summary=RecommendationPerformanceSummary(),
            evaluated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )


def test_performance_api_returns_null_return_for_an_unavailable_item() -> None:
    manager = DashboardRunManager(
        performance_service=_UnavailablePerformanceService(),  # type: ignore[arg-type]
    )
    client = TestClient(create_web_app(manager))

    response = client.get("/api/recommendations/performance")

    assert response.status_code == 200
    payload: dict[str, object] = response.json()
    assert set(payload) == {"items", "summary", "evaluated_at"}
    item: dict[str, object] = payload["items"][0]  # type: ignore[index]
    assert item["return_percent"] is None
    assert "secret" not in response.text.lower()
    assert "payload" not in response.text.lower()
