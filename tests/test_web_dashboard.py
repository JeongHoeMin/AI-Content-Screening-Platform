from __future__ import annotations

from fastapi.testclient import TestClient

from datetime import datetime, timezone

import pytest
from app.models import CommunityType, Post
from app.web.app import (
    DashboardEvent,
    DashboardRunManager,
    RecommendationRunRequest,
    create_web_app,
)


def test_dashboard_page_exposes_recommendation_controls() -> None:
    client: TestClient = TestClient(create_web_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "오늘의 뉴스를 기준으로 추천받기" in response.text
    assert "실시간 작업" in response.text
    assert "전체 진행 상황" in response.text
    assert "AI Screening" in response.text
    assert "교차검증 필요 시 REVIEW" in response.text
    assert "선택된 뉴스" in response.text
    assert "매수 · 판매 추천" in response.text
    assert "전체 수집 뉴스 분석" in response.text
    assert "analysisById" in response.text
    assert "적게 · 10건" in response.text
    assert "중간 · 25건" in response.text
    assert "많이 · 50건" in response.text
    assert "최대 · 100건" in response.text
    assert "JSON.stringify({limit:selectedSize})" in response.text
    assert "추천 실행 후 선택된 뉴스를 표시합니다." in response.text


def test_dashboard_uses_low_default_collection_limit() -> None:
    request: RecommendationRunRequest = RecommendationRunRequest()

    assert request.limit == 10


@pytest.mark.parametrize(
    ("total_limit", "expected_per_source_limit"),
    [(10, 5), (25, 13), (50, 25), (100, 50)],
)
def test_dashboard_collection_size_is_a_total_limit(
    total_limit: int,
    expected_per_source_limit: int,
) -> None:
    assert (
        DashboardRunManager._per_source_collection_limit(total_limit, 2)
        == expected_per_source_limit
    )


def test_dashboard_rejects_unsupported_collection_size() -> None:
    with pytest.raises(ValueError):
        RecommendationRunRequest(limit=11)


def test_dashboard_event_exposes_full_progress_state() -> None:
    event: DashboardEvent = DashboardEvent(
        type="heartbeat",
        message="현재 단계를 계속 처리하고 있습니다.",
        active_stage="screen",
        completed_stage_count=4,
    )

    assert event.active_stage == "screen"
    assert event.completed_stage_count == 4
    assert event.total_stage_count == 12


def test_dashboard_maps_completed_workflow_node_to_next_active_stage() -> None:
    assert DashboardRunManager._next_workflow_stage("screen") == "cross_validate"
    assert DashboardRunManager._next_workflow_stage("select_candidates") is None


def test_dashboard_analysis_cards_use_workflow_article_identity() -> None:
    post: Post = Post(
        id="post-1",
        source=CommunityType.NAVER_NEWS,
        title="News title",
        content="News content",
        created_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
        url="https://example.com/news",
    )

    analysis = DashboardRunManager._initial_analyses([post])[0]

    assert analysis.id == "naver_news:post-1"


def test_dashboard_rejects_unknown_run() -> None:
    client: TestClient = TestClient(create_web_app())

    response = client.get("/api/runs/not-found")

    assert response.status_code == 404


def test_dashboard_rejects_unknown_event_stream_before_response_starts() -> None:
    client: TestClient = TestClient(create_web_app())

    response = client.get("/api/runs/not-found/events")

    assert response.status_code == 404


def test_dashboard_health_endpoint_is_ready_without_credentials() -> None:
    client: TestClient = TestClient(create_web_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
