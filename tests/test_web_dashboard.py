from __future__ import annotations

from fastapi.testclient import TestClient

from datetime import datetime, timezone
from typing import Optional

import pytest
from app.filters import ArticleFilter, DefaultThemeCatalog
from app.market_data import posts_to_articles
from app.models import CollectionFilter, CommunityType, InvestmentTheme, NewsTopic, Post
from app.models.scheduled_recommendation import ScheduledRecommendationJob
from app.web.app import (
    DEFAULT_ANALYSIS_SOURCES,
    DashboardEvent,
    DashboardRunManager,
    RecommendationRunRequest,
    create_web_app,
)
from app.workflows.screening.errors import WorkflowStageRetriesExhaustedError


class RecordingExecutionAuditPersistence:
    async def persist(self, audit: object) -> None:
        return None


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
    assert "JSON.stringify({limit:selectedSize,themes:selectedThemes,topics:selectedTopics})" in response.text
    assert "추천 실행 후 선택된 뉴스를 표시합니다." in response.text
    assert "문단 ${escapeHtml(quote.paragraph_index)}" in response.text
    assert "event_evidence" in response.text


def test_dashboard_page_exposes_actual_workflow_graph_and_retry_path() -> None:
    response = TestClient(create_web_app()).get("/")

    assert 'id="workflow-graph"' in response.text
    assert 'id="graph-deduplicate"' in response.text
    assert 'id="retry-path"' in response.text
    assert "renderWorkflowGraph" in response.text
    assert "failure_attempts" in response.text


def test_dashboard_exposes_theme_and_news_topic_filters() -> None:
    client: TestClient = TestClient(create_web_app())

    response = client.get("/")

    assert "투자 테마" in response.text
    assert "반도체" in response.text
    assert "뉴스 주제" in response.text
    assert "themes:selectedThemes" in response.text
    assert "topics:selectedTopics" in response.text


def test_dashboard_uses_low_default_collection_limit() -> None:
    request: RecommendationRunRequest = RecommendationRunRequest()

    assert request.limit == 10


def test_dashboard_defaults_to_rss_only_analysis_source() -> None:
    assert DEFAULT_ANALYSIS_SOURCES == (CommunityType.IR_RSS,)


def test_dashboard_manager_accepts_harness_owned_execution_audit_persistence() -> None:
    persistence = RecordingExecutionAuditPersistence()
    manager = DashboardRunManager(execution_audit_persistence=persistence)

    assert manager._execution_audit_persistence is persistence


def test_dashboard_request_accepts_theme_and_news_topic_filters() -> None:
    request: RecommendationRunRequest = RecommendationRunRequest(
        themes=(InvestmentTheme.SEMICONDUCTOR,),
        topics=(NewsTopic.SUPPLY_CHAIN,),
    )

    assert request.themes == (InvestmentTheme.SEMICONDUCTOR,)
    assert request.topics == (NewsTopic.SUPPLY_CHAIN,)


def test_dashboard_filter_snapshot_counts_analysis_articles_not_empty_posts() -> None:
    posts = [
        Post(
            id="with-content",
            source=CommunityType.DART,
            title="반도체 공급 계약",
            content="HBM 메모리 공급 계약을 체결했다.",
            created_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            url="https://example.com/with-content",
        ),
        Post(
            id="without-content",
            source=CommunityType.DART,
            title="본문 없는 공시",
            content=None,
            created_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            url="https://example.com/without-content",
        ),
    ]
    articles = posts_to_articles(posts)
    filter_result = ArticleFilter(DefaultThemeCatalog()).filter(
        articles,
        CollectionFilter(themes=(InvestmentTheme.SEMICONDUCTOR,)),
    )

    snapshot = DashboardRunManager._build_filter_snapshot(
        run_id="run-1",
        request=RecommendationRunRequest(
            themes=(InvestmentTheme.SEMICONDUCTOR,),
        ),
        articles=articles,
        filter_result=filter_result,
    )

    assert snapshot.collected_count == 1
    assert snapshot.accepted_count == 1
    assert snapshot.excluded_count == 0


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


def test_dashboard_event_exposes_safe_terminal_failure_detail() -> None:
    event = DashboardEvent(
        type="failed",
        message="cross_validate 단계에서 APITimeoutError 오류로 작업이 중단되었습니다.",
        error_type="APITimeoutError",
        failure_stage="cross_validate",
        failure_attempts=3,
    )

    assert event.failure_stage == "cross_validate"
    assert event.failure_attempts == 3


def test_dashboard_maps_completed_workflow_node_to_next_active_stage() -> None:
    assert DashboardRunManager._next_workflow_stage("screen") == "cross_validate"
    assert DashboardRunManager._next_workflow_stage("select_candidates") is None


def test_dashboard_workflow_order_includes_deduplicate_before_screen() -> None:
    assert DashboardRunManager._next_workflow_stage("extract") == "deduplicate"
    assert DashboardRunManager._next_workflow_stage("deduplicate") == "screen"


class _UnretriedConnectionError(Exception):
    error_type = "APIConnectionError"


class _UntrustedError(Exception):
    error_type = "provider message with raw request data"


def test_dashboard_failure_uses_one_attempt_without_retry_exhaustion() -> None:
    error_type, attempts = DashboardRunManager._safe_failure_details(
        _UnretriedConnectionError(),
    )

    assert error_type == "APIConnectionError"
    assert attempts == 1


def test_dashboard_failure_replaces_untrusted_error_type() -> None:
    error_type, attempts = DashboardRunManager._safe_failure_details(_UntrustedError())

    assert error_type == "unexpected_error"
    assert attempts == 1


def test_dashboard_uses_retry_attempts_only_for_retry_exhaustion() -> None:
    error_type, attempts = DashboardRunManager._safe_failure_details(
        WorkflowStageRetriesExhaustedError("screen", "APITimeoutError"),
    )

    assert error_type == "APITimeoutError"
    assert attempts == 3


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


class SchedulePersistence:
    def __init__(self) -> None:
        self.job: Optional[ScheduledRecommendationJob] = None

    async def get(self, job_id: str) -> Optional[ScheduledRecommendationJob]:
        return self.job

    async def save(
        self,
        job: ScheduledRecommendationJob,
        next_run_at: datetime,
        expected_version: Optional[int],
    ) -> None:
        self.job = job


def test_schedule_settings_can_be_saved_and_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEDULE_SETTINGS_PASSWORD", "x" * 32)
    monkeypatch.setenv("SCHEDULE_COOKIE_SECURE", "false")
    persistence = SchedulePersistence()
    manager = DashboardRunManager(schedule_persistence=persistence)
    client = TestClient(create_web_app(manager))

    unauthenticated = client.put(
        "/api/settings/schedule",
        json={"cron_expression": "0 8 * * *"},
    )
    assert unauthenticated.status_code == 401

    login = client.post(
        "/api/settings/login",
        json={"password": "x" * 32},
    )
    assert login.status_code == 204

    saved = client.put(
        "/api/settings/schedule",
        json={
            "active": True,
            "cron_expression": "0 8 * * *",
            "themes": ["semiconductor"],
            "limit": 25,
            "telegram_enabled": False,
        },
    )

    assert saved.status_code == 200
    assert saved.json()["next_run_at"].endswith("Z")
    loaded = client.get("/api/settings/schedule")
    assert loaded.status_code == 200
    assert loaded.json()["timezone"] == "Asia/Seoul"

    stale = client.put(
        "/api/settings/schedule",
        json={"cron_expression": "0 9 * * *", "version": 99},
    )

    assert stale.status_code == 409


def test_schedule_page_requires_password_before_schedule_api_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCHEDULE_SETTINGS_PASSWORD", "x" * 32)
    monkeypatch.setenv("SCHEDULE_COOKIE_SECURE", "false")
    client = TestClient(create_web_app(DashboardRunManager(schedule_persistence=SchedulePersistence())))

    page = client.get("/settings")
    response = client.get("/api/settings/schedule")

    assert page.status_code == 200
    assert "정기 실행 설정" in page.text
    assert response.status_code == 401
