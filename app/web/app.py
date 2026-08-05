from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.bootstrap import ExecutionMode
from app.config import (
    DatabaseConfig,
    KisConfig,
    load_krx_config,
    load_optional_database_config,
    load_optional_kis_config,
    load_schedule_settings_password,
)
from app.config.errors import ConfigurationError
from app.config.schedule_security import (
    SCHEDULE_SESSION_COOKIE,
    has_valid_schedule_session,
    issue_schedule_session,
    passwords_match,
    schedule_cookie_uses_secure_transport,
)
from app.persistence import (
    CollectionFilterPersistence,
    ScheduledRecommendationPersistence,
    WorkflowExecutionAuditPersistence,
    create_collection_filter_persistence,
    create_recommendation_price_persistence,
    create_scheduled_recommendation_persistence,
    create_workflow_execution_audit_persistence,
)
from app.harness.recommendation_prices import RecommendationPriceRecorder
from app.harness.recommendation_prices import RecommendationPerformanceService
from app.persistence.schedule_repository import ScheduleVersionConflictError
from app.harness import Harness
from app.harness.execution_audit import ScreeningExecutionHarness
from app.harness.execution_audit import JsonLinesWorkflowExecutionAuditSink
from app.filters import ArticleFilter, DefaultThemeCatalog
from app.market_data import (
    create_market_collect_posts_skill,
    create_market_screening_workflow,
    posts_to_articles,
)
from app.market_prices import (
    KisRealtimePriceClient,
    KrxClosingPriceClient,
    MarketPriceService,
    RecommendationPerformanceResponse,
)
from app.models.collect_posts import CollectPostsRequest
from app.models.article import Article
from app.models.collection_filter import CollectionFilter, FilterRejectionReason, InvestmentTheme, NewsTopic
from app.models.scheduled_recommendation import ScheduledRecommendationJob
from app.models.collection_filter_result import (
    CollectionFilterResult,
    CollectionFilterSnapshot,
)
from app.models.candidate_selection import CandidateEvaluation, CandidateSelectionResult
from app.models.community import CommunityType
from app.models.post import Post
from app.workflows import ScreeningResult, WorkflowProgressEvent
from app.workflows.screening.errors import WorkflowStageRetriesExhaustedError
from app.web.dashboard_html import DASHBOARD_HTML
from app.web.settings_html import SCHEDULE_SETTINGS_HTML
from app.observability import configure_application_logging

import structlog

configure_application_logging()
logger = structlog.get_logger(__name__)

DEFAULT_ANALYSIS_SOURCES: tuple[CommunityType, ...] = (CommunityType.IR_RSS,)

_RETRIED_ERROR_TYPES: frozenset[str] = frozenset(
    {"APITimeoutError", "APIConnectionError", "AuthenticationError", "PermissionDeniedError"}
)
_SAFE_DASHBOARD_ERROR_TYPES: frozenset[str] = _RETRIED_ERROR_TYPES | frozenset(
    {
        "ConfigurationError",
        "WorkflowStageRetriesExhaustedError",
        "AllExtractionBatchesFailedError",
        "NoValidScreeningDecisionsError",
        "unexpected_error",
    }
)


class RecommendationRunRequest(BaseModel):
    """Validated public input for one dashboard recommendation execution."""

    model_config = ConfigDict(frozen=True)

    category: str = Field(default="국내 증시", min_length=1, max_length=100)
    limit: Literal[10, 25, 50, 100] = 10
    period_hours: int = Field(default=24, ge=1, le=168)
    themes: tuple[InvestmentTheme, ...] = ()
    topics: tuple[NewsTopic, ...] = ()


class ScheduleSettingsRequest(BaseModel):
    """KST schedule input; delivery credentials are server environment only."""

    model_config = ConfigDict(frozen=True)

    active: bool = True
    cron_expression: str = Field(min_length=9, max_length=128)
    themes: tuple[InvestmentTheme, ...] = ()
    topics: tuple[NewsTopic, ...] = ()
    limit: Literal[25, 50, 100] = 25
    telegram_enabled: bool = False
    version: Optional[int] = Field(default=None, ge=1)


class ScheduleLoginRequest(BaseModel):
    """Bounded password input used only to issue an HttpOnly settings session."""

    model_config = ConfigDict(frozen=True)

    password: str = Field(min_length=1, max_length=512)


class ScheduleSettingsResponse(BaseModel):
    """Persisted schedule projection without delivery secrets."""

    model_config = ConfigDict(frozen=True)

    active: bool
    cron_expression: str
    timezone: Literal["Asia/Seoul"]
    themes: tuple[InvestmentTheme, ...]
    topics: tuple[NewsTopic, ...]
    limit: Literal[25, 50, 100]
    telegram_enabled: bool
    version: int
    next_run_at: datetime


class DashboardEvent(BaseModel):
    """Safe server-sent event payload used by the browser timeline."""

    model_config = ConfigDict(frozen=True)

    type: str = Field(min_length=1)
    message: str = Field(min_length=1)
    node: Optional[str] = None
    completed_node_count: Optional[int] = Field(default=None, ge=1)
    active_stage: Optional[str] = None
    completed_stage_count: int = Field(default=0, ge=0)
    total_stage_count: int = Field(default=12, ge=1)
    error_type: Optional[str] = None
    failure_stage: Optional[str] = None
    failure_attempts: Optional[int] = Field(default=None, ge=1, le=3)
    analyses: List["NewsAnalysisCard"] = Field(default_factory=list)


class NewsCard(BaseModel):
    """Small, display-safe projection of a normalized selected news item."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    source: str
    published_at: datetime
    url: str
    excerpt: str


class RecommendationCard(BaseModel):
    """Display projection of a deterministic policy decision."""

    model_config = ConfigDict(frozen=True)

    company_name: str
    ticker: Optional[str]
    exchange: Optional[str]
    score: float
    action: str
    reason_code: str
    recommendation_index: int = Field(default=0, ge=0)


class NewsAnalysisCard(BaseModel):
    """Display-safe live analysis projection for one collected news item."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    source: str
    status: str
    summary: Optional[str] = None
    reasoning: Optional[str] = None
    event_titles: List[str] = Field(default_factory=list)
    event_evidence: List["EventEvidenceCard"] = Field(default_factory=list)
    decision: Optional[str] = None
    relevance: Optional[int] = Field(default=None, ge=0, le=100)
    importance: Optional[int] = Field(default=None, ge=0, le=100)
    credibility: Optional[int] = Field(default=None, ge=0, le=100)
    reasons: List[str] = Field(default_factory=list)
    validation_status: Optional[str] = None
    theme_filter_excluded: bool = False
    filter_rejection_reason: Optional[str] = None


class CollectionFilterSummary(BaseModel):
    """Display-safe aggregate of deterministic collection filtering."""

    model_config = ConfigDict(frozen=True)

    catalog_version: str
    accepted_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    rejection_counts: Dict[str, int]


class EvidenceQuoteCard(BaseModel):
    """Display-safe quote projection for an extracted event."""

    model_config = ConfigDict(frozen=True)

    paragraph_index: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=280)


class EventEvidenceCard(BaseModel):
    """Display-safe source evidence projection for an extracted event."""

    model_config = ConfigDict(frozen=True)

    event_title: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    quotes: List[EvidenceQuoteCard] = Field(default_factory=list, max_length=2)


class DashboardRunResult(BaseModel):
    """Terminal dashboard result without raw provider responses or prompts."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    news_cards: List[NewsCard]
    analyses: List[NewsAnalysisCard]
    recommendations: List[RecommendationCard]
    statistics: Dict[str, Any]
    collection_filter: CollectionFilterSummary


@dataclass
class _RunState:
    queue: asyncio.Queue[DashboardEvent] = field(default_factory=asyncio.Queue)
    result: Optional[DashboardRunResult] = None
    error_type: Optional[str] = None
    failure_stage: Optional[str] = None
    failure_attempts: Optional[int] = None
    completed: bool = False
    analyses: Dict[str, NewsAnalysisCard] = field(default_factory=dict)
    active_stage: str = "collect"
    completed_stage_count: int = 0


class DashboardRunManager:
    """Harness-owned in-memory state for bounded live dashboard executions."""

    def __init__(
        self,
        filter_persistence: Optional[CollectionFilterPersistence] = None,
        execution_audit_persistence: Optional[WorkflowExecutionAuditPersistence] = None,
        schedule_persistence: Optional[ScheduledRecommendationPersistence] = None,
        price_recorder: Optional[RecommendationPriceRecorder] = None,
        performance_service: Optional[RecommendationPerformanceService] = None,
    ) -> None:
        self._runs: Dict[str, _RunState] = {}
        self._filter_persistence: Optional[CollectionFilterPersistence] = filter_persistence
        self._execution_audit_persistence: Optional[WorkflowExecutionAuditPersistence] = (
            execution_audit_persistence
        )
        self._schedule_persistence: Optional[ScheduledRecommendationPersistence] = (
            schedule_persistence
        )
        self._price_recorder: Optional[RecommendationPriceRecorder] = price_recorder
        self._performance_service: Optional[RecommendationPerformanceService] = (
            performance_service
        )

    _WORKFLOW_NODES: tuple[str, ...] = (
        "evaluate",
        "extract",
        "deduplicate",
        "screen",
        "cross_validate",
        "resolve",
        "analyze",
        "aggregate",
        "score",
        "recommend",
        "select_candidates",
    )
    _TOTAL_STAGE_COUNT: int = 12

    async def start(self, request: RecommendationRunRequest) -> str:
        run_id: str = uuid4().hex
        state: _RunState = _RunState()
        self._runs[run_id] = state
        asyncio.create_task(self._execute(run_id, state, request))
        return run_id

    async def run_scheduled(
        self,
        request: RecommendationRunRequest,
    ) -> DashboardRunResult:
        """Run one background schedule with the same Harness-owned pipeline as the UI."""
        run_id: str = uuid4().hex
        state: _RunState = _RunState()
        self._runs[run_id] = state
        try:
            await self._execute(run_id, state, request)
            if state.error_type is not None:
                raise RuntimeError(state.error_type)
            if state.result is None:
                raise RuntimeError("Scheduled recommendation produced no result")
            return state.result
        finally:
            self._runs.pop(run_id, None)

    async def get_schedule(self) -> Optional[ScheduleSettingsResponse]:
        """Read the single durable schedule without disclosing any secret."""
        if self._schedule_persistence is None:
            return None
        job: Optional[ScheduledRecommendationJob] = await self._schedule_persistence.get(
            "default"
        )
        if job is None:
            return None
        return self._schedule_response(job, job.next_run_at(datetime.now(timezone.utc)))

    async def save_schedule(
        self,
        request: ScheduleSettingsRequest,
    ) -> ScheduleSettingsResponse:
        """Persist the validated KST cron configuration through the Harness boundary."""
        if self._schedule_persistence is None:
            raise RuntimeError("Scheduled recommendations require DATABASE_URL")
        previous: Optional[ScheduledRecommendationJob] = await self._schedule_persistence.get(
            "default"
        )
        if previous is not None and request.version != previous.version:
            raise ScheduleVersionConflictError("Schedule version is stale")
        if previous is None and request.version is not None:
            raise ScheduleVersionConflictError("Schedule does not exist yet")
        version: int = 1 if previous is None else previous.version + 1
        job = ScheduledRecommendationJob(
            id="default",
            active=request.active,
            cron_expression=request.cron_expression,
            themes=request.themes,
            topics=request.topics,
            limit=request.limit,
            telegram_enabled=request.telegram_enabled,
            version=version,
        )
        next_run_at: datetime = job.next_run_at(datetime.now(timezone.utc))
        await self._schedule_persistence.save(job, next_run_at, request.version)
        return self._schedule_response(job, next_run_at)

    @staticmethod
    def _schedule_response(
        job: ScheduledRecommendationJob,
        next_run_at: datetime,
    ) -> ScheduleSettingsResponse:
        return ScheduleSettingsResponse(
            active=job.active,
            cron_expression=job.cron_expression,
            timezone=job.timezone,
            themes=job.themes,
            topics=job.topics,
            limit=job.limit,
            telegram_enabled=job.telegram_enabled,
            version=job.version,
            next_run_at=next_run_at,
        )

    async def events(self, run_id: str) -> AsyncIterator[DashboardEvent]:
        state: _RunState = self._get_state(run_id)
        while True:
            event: DashboardEvent = await state.queue.get()
            yield event
            if event.type in {"completed", "failed"}:
                return

    def ensure_exists(self, run_id: str) -> None:
        """Fail before an SSE response starts for an unknown execution id."""
        self._get_state(run_id)

    def result(self, run_id: str) -> DashboardRunResult:
        state: _RunState = self._get_state(run_id)
        if not state.completed:
            raise HTTPException(status_code=409, detail="Recommendation is still running")
        if state.error_type is not None:
            raise HTTPException(status_code=500, detail=state.error_type)
        if state.result is None:
            raise HTTPException(status_code=500, detail="Missing recommendation result")
        return state.result

    async def recommendation_performance(self) -> RecommendationPerformanceResponse:
        """Refresh and project price performance only through the Harness service."""
        if self._performance_service is None:
            return RecommendationPerformanceResponse(evaluated_at=datetime.now(timezone.utc))
        return await self._performance_service.refresh_and_query()

    async def _execute(
        self,
        run_id: str,
        state: _RunState,
        request: RecommendationRunRequest,
    ) -> None:
        heartbeat_task: asyncio.Task[None] = asyncio.create_task(
            self._emit_heartbeats(state)
        )
        try:
            await self._emit(
                state,
                "collecting",
                "오늘의 뉴스와 공시를 수집하고 있습니다.",
                active_stage="collect",
            )
            collection_sources: tuple[CommunityType, ...] = DEFAULT_ANALYSIS_SOURCES
            per_source_limit: int = self._per_source_collection_limit(
                request.limit,
                len(collection_sources),
            )
            collect_result = await Harness().run(
                create_market_collect_posts_skill(collection_sources),
                CollectPostsRequest(
                    sources=list(collection_sources),
                    limit=per_source_limit,
                    period=timedelta(hours=request.period_hours),
                    category=request.category,
                ),
            )
            posts: List[Post] = collect_result.data.posts[: request.limit]
            articles = posts_to_articles(posts)
            filter_result: CollectionFilterResult = ArticleFilter(
                DefaultThemeCatalog()
            ).filter(
                articles,
                CollectionFilter(themes=request.themes, topics=request.topics),
            )
            await self._persist_filter_snapshot(
                run_id,
                request,
                articles,
                filter_result,
            )
            initial_analyses: List[NewsAnalysisCard] = self._initial_analyses(
                posts,
                filter_result.rejected_article_reasons,
            )
            state.analyses = {analysis.id: analysis for analysis in initial_analyses}
            await self._emit(
                state,
                "collected",
                f"{len(posts)}건을 수집하고 {len(filter_result.accepted_articles)}건을 분석 대상으로 선택했습니다. "
                f"테마·주제 필터로 {len(filter_result.rejected_article_ids)}건을 제외했습니다.",
                completed_stage_count=1,
                analyses=initial_analyses,
            )
            await self._emit(
                state,
                "directory",
                "KRX 종목 스냅샷을 준비하고 있습니다.",
                active_stage="directory",
                completed_stage_count=1,
            )
            workflow = await create_market_screening_workflow(ExecutionMode.OPENAI)
            await self._emit(
                state,
                "workflow_started",
                "분석 워크플로우를 시작했습니다.",
                active_stage="evaluate",
                completed_stage_count=2,
            )

            async def on_progress(event: WorkflowProgressEvent) -> None:
                changed_analyses: List[NewsAnalysisCard] = self._apply_progress_analyses(
                    state,
                    event,
                )
                await self._emit(
                    state,
                    "workflow",
                    f"{event.node} 단계를 완료했습니다.",
                    node=event.node,
                    completed_node_count=event.completed_node_count,
                    active_stage=event.next_node,
                    completed_stage_count=event.completed_node_count + 2,
                    analyses=changed_analyses,
                )

            result: ScreeningResult = await ScreeningExecutionHarness(
                audit_sink=self._audit_sink(),
                execution_audit_persistence=self._execution_audit_persistence,
            ).run_with_progress(
                workflow,
                filter_result.accepted_articles,
                ExecutionMode.OPENAI.value,
                on_progress,
            )
            state.result = self._build_result(
                run_id,
                posts,
                result,
                state.analyses,
                filter_result,
            )
            await self._record_price_entries(
                run_id,
                self._selected_price_recommendations(result.candidate_selection),
                datetime.now(timezone.utc),
            )
            state.completed = True
            await self._emit(
                state,
                "completed",
                "추천 분석이 완료되었습니다.",
                completed_stage_count=self._TOTAL_STAGE_COUNT,
            )
        except Exception as error:
            state.error_type = type(error).__name__
            state.failure_stage = self._safe_failure_stage(
                getattr(error, "stage", state.active_stage)
            )
            error_type, state.failure_attempts = self._safe_failure_details(error)
            state.completed = True
            logger.error(
                "dashboard_workflow_failed",
                run_id=run_id,
                stage=state.failure_stage,
                error_type=error_type,
                attempts=state.failure_attempts,
            )
            await self._emit(
                state,
                "failed",
                f"{state.failure_stage} 단계에서 {error_type} 오류로 작업이 중단되었습니다. "
                f"시도 횟수: {state.failure_attempts}/3.",
                completed_stage_count=state.completed_stage_count,
                error_type=error_type,
                failure_stage=state.failure_stage,
                failure_attempts=state.failure_attempts,
            )
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    @classmethod
    def _next_workflow_stage(cls, node: str) -> Optional[str]:
        """Return the next graph stage after a completed node."""
        try:
            node_index: int = cls._WORKFLOW_NODES.index(node)
        except ValueError:
            return None
        next_index: int = node_index + 1
        if next_index >= len(cls._WORKFLOW_NODES):
            return None
        return cls._WORKFLOW_NODES[next_index]

    @staticmethod
    def _safe_failure_details(error: Exception) -> tuple[str, int]:
        """Return a bounded error category and the actual observed attempt count."""
        raw_error_type: object = getattr(error, "error_type", type(error).__name__)
        error_type: str = (
            raw_error_type
            if isinstance(raw_error_type, str)
            and raw_error_type in _SAFE_DASHBOARD_ERROR_TYPES
            else "unexpected_error"
        )
        raw_attempts: object = (
            getattr(error, "attempts", 1)
            if isinstance(error, WorkflowStageRetriesExhaustedError)
            else 1
        )
        attempts: int = (
            raw_attempts
            if isinstance(raw_attempts, int) and not isinstance(raw_attempts, bool)
            and 1 <= raw_attempts <= 3
            else 1
        )
        return error_type, attempts

    @classmethod
    def _safe_failure_stage(cls, value: object) -> str:
        """Keep terminal SSE stage names inside the known dashboard workflow."""
        known_stages: frozenset[str] = frozenset(
            {"collect", "directory", *cls._WORKFLOW_NODES}
        )
        if isinstance(value, str) and value in known_stages:
            return value
        return "unknown_stage"

    @staticmethod
    def _per_source_collection_limit(total_limit: int, source_count: int) -> int:
        """Request enough from each source to fill the public total limit."""
        if source_count <= 0:
            raise ValueError("Collection source count must be positive")
        return ceil(total_limit / source_count)

    @staticmethod
    def _audit_sink() -> Optional[JsonLinesWorkflowExecutionAuditSink]:
        raw_path: str = os.getenv("WORKFLOW_AUDIT_LOG_PATH", "").strip()
        if not raw_path:
            return None
        from pathlib import Path
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return JsonLinesWorkflowExecutionAuditSink(path)

    async def _emit_heartbeats(self, state: _RunState) -> None:
        """Confirm long-running work without exposing provider or LLM internals."""
        while True:
            await asyncio.sleep(5)
            if state.completed:
                return
            await self._emit(
                state,
                "heartbeat",
                "현재 단계를 계속 처리하고 있습니다.",
                completed_stage_count=state.completed_stage_count,
            )

    def _build_result(
        self,
        run_id: str,
        posts: List[Post],
        result: ScreeningResult,
        analyses: Dict[str, NewsAnalysisCard],
        filter_result: CollectionFilterResult,
    ) -> DashboardRunResult:
        news_cards: List[NewsCard] = [
            NewsCard(
                id=post.id,
                title=post.title,
                source=post.source.value,
                published_at=post.created_at,
                url=str(post.url),
                excerpt=(post.content or "")[:240],
            )
            for post in posts
        ]
        recommendations: List[RecommendationCard] = []
        recommendation_index: int
        for recommendation_index, decision in enumerate(result.recommendation.decisions):
            company = decision.company_score.company
            ticker = company.ticker
            recommendations.append(
                RecommendationCard(
                    company_name=company.name,
                    ticker=ticker.ticker if ticker is not None else None,
                    exchange=ticker.exchange.value if ticker is not None else None,
                    score=decision.score,
                    action=decision.action.value,
                    reason_code=decision.reason_code.value,
                    recommendation_index=recommendation_index,
                )
            )
        statistics: Dict[str, Any] = result.statistics.model_dump()
        filter_summary = CollectionFilterSummary(
            catalog_version=filter_result.catalog_version,
            accepted_count=len(filter_result.accepted_articles),
            excluded_count=len(filter_result.rejected_article_ids),
            rejection_counts={
                reason.value: count
                for reason, count in filter_result.rejection_counts.items()
            },
        )
        return DashboardRunResult(
            run_id=run_id,
            news_cards=news_cards,
            analyses=list(analyses.values()),
            recommendations=recommendations,
            statistics=statistics,
            collection_filter=filter_summary,
        )

    @staticmethod
    def _initial_analyses(
        posts: List[Post],
        rejected_article_reasons: Optional[Dict[str, FilterRejectionReason]] = None,
    ) -> List[NewsAnalysisCard]:
        """Project all collected posts before workflow analysis begins."""
        reasons: Dict[str, FilterRejectionReason] = rejected_article_reasons or {}
        return [
            NewsAnalysisCard(
                id=f"{post.source.value}:{post.id}",
                title=post.title,
                source=post.source.value,
                status=(
                    "테마·주제 필터 제외"
                    if f"{post.source.value}:{post.id}" in reasons
                    else "수집 완료 · 분석 대기"
                ),
                theme_filter_excluded=f"{post.source.value}:{post.id}" in reasons,
                filter_rejection_reason=(
                    reasons[f"{post.source.value}:{post.id}"].value
                    if f"{post.source.value}:{post.id}" in reasons
                    else None
                ),
            )
            for post in posts
        ]

    @staticmethod
    def _apply_progress_analyses(
        state: _RunState,
        event: WorkflowProgressEvent,
    ) -> List[NewsAnalysisCard]:
        """Merge safe node observations into the harness-owned card state."""
        changed: List[NewsAnalysisCard] = []
        for analysis in event.article_analyses:
            current: Optional[NewsAnalysisCard] = state.analyses.get(analysis.article_id)
            if current is None:
                continue
            updated: NewsAnalysisCard = current.model_copy(
                update={
                    "status": "이벤트 추출 완료" if analysis.event_titles else "투자 이벤트 미추출",
                    "summary": analysis.summary,
                    "reasoning": analysis.reasoning,
                    "event_titles": list(analysis.event_titles),
                    "event_evidence": [
                        EventEvidenceCard(
                            event_title=evidence.event_title,
                            source_url=evidence.source_url,
                            quotes=[
                                EvidenceQuoteCard(
                                    paragraph_index=quote.paragraph_index,
                                    quote=quote.quote,
                                )
                                for quote in evidence.quotes
                            ],
                        )
                        for evidence in analysis.event_evidence
                    ],
                }
            )
            state.analyses[updated.id] = updated
            changed.append(updated)
        for analysis in event.screening_analyses:
            current = state.analyses.get(analysis.article_id)
            if current is None:
                continue
            updated = current.model_copy(
                update={
                    "status": f"스크리닝 완료 · {analysis.decision}",
                    "decision": analysis.decision,
                    "relevance": analysis.relevance,
                    "importance": analysis.importance,
                    "credibility": analysis.credibility,
                    "reasons": list(analysis.reasons),
                }
            )
            state.analyses[updated.id] = updated
            changed.append(updated)
        for analysis in event.validation_analyses:
            current = state.analyses.get(analysis.article_id)
            if current is None:
                continue
            updated = current.model_copy(
                update={
                    "status": f"교차검증 완료 · {analysis.status}",
                    "validation_status": analysis.status,
                }
            )
            state.analyses[updated.id] = updated
            changed.append(updated)
        return changed

    async def _emit(
        self,
        state: _RunState,
        event_type: str,
        message: str,
        node: Optional[str] = None,
        completed_node_count: Optional[int] = None,
        error_type: Optional[str] = None,
        failure_stage: Optional[str] = None,
        failure_attempts: Optional[int] = None,
        analyses: Optional[List[NewsAnalysisCard]] = None,
        active_stage: Optional[str] = None,
        completed_stage_count: Optional[int] = None,
    ) -> None:
        if active_stage is not None:
            state.active_stage = active_stage
        if completed_stage_count is not None:
            state.completed_stage_count = completed_stage_count
        await state.queue.put(
            DashboardEvent(
                type=event_type,
                message=message,
                node=node,
                completed_node_count=completed_node_count,
                active_stage=state.active_stage,
                completed_stage_count=state.completed_stage_count,
                total_stage_count=self._TOTAL_STAGE_COUNT,
                error_type=error_type,
                failure_stage=failure_stage,
                failure_attempts=failure_attempts,
                analyses=analyses or [],
            )
        )

    def _get_state(self, run_id: str) -> _RunState:
        state: Optional[_RunState] = self._runs.get(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Recommendation run was not found")
        return state

    async def _persist_filter_snapshot(
        self,
        run_id: str,
        request: RecommendationRunRequest,
        articles: tuple[Article, ...],
        filter_result: CollectionFilterResult,
    ) -> None:
        """Persist reproducible safe filter conditions through the harness boundary."""
        if self._filter_persistence is None:
            return
        snapshot: CollectionFilterSnapshot = self._build_filter_snapshot(
            run_id=run_id,
            request=request,
            articles=articles,
            filter_result=filter_result,
        )
        await self._filter_persistence.persist(snapshot)

    async def _record_price_entries(
        self,
        run_id: str,
        recommendations: tuple[CandidateEvaluation, ...],
        observed_at: datetime,
    ) -> None:
        """Record price observations without changing a completed recommendation result."""
        if self._price_recorder is None:
            return
        try:
            await self._price_recorder.record_entries(
                run_id,
                recommendations,
                observed_at,
            )
        except Exception as error:
            logger.warning(
                "dashboard_recommendation_price_recording_failed",
                run_id=run_id,
                error_type=type(error).__name__,
            )

    @staticmethod
    def _selected_price_recommendations(
        candidate_selection: CandidateSelectionResult,
    ) -> tuple[CandidateEvaluation, ...]:
        """Return only selected candidates in stable rank order for entry pricing."""
        return candidate_selection.candidates

    @staticmethod
    def _build_filter_snapshot(
        run_id: str,
        request: RecommendationRunRequest,
        articles: tuple[Article, ...],
        filter_result: CollectionFilterResult,
    ) -> CollectionFilterSnapshot:
        """Build a snapshot whose count basis is exactly the filter input articles."""
        return CollectionFilterSnapshot(
            run_id=run_id,
            themes=request.themes,
            topics=request.topics,
            catalog_version=filter_result.catalog_version,
            collected_count=len(articles),
            accepted_count=len(filter_result.accepted_articles),
            excluded_count=len(filter_result.rejected_article_ids),
            rejection_counts={
                reason.value: count
                for reason, count in filter_result.rejection_counts.items()
            },
            created_at=datetime.now(timezone.utc),
        )


def _create_optional_filter_persistence() -> Optional[CollectionFilterPersistence]:
    """Configure dashboard filter persistence only when PostgreSQL is configured."""
    database_config: Optional[DatabaseConfig] = load_optional_database_config()
    if database_config is None:
        return None
    return create_collection_filter_persistence(database_config)


def _create_optional_execution_audit_persistence() -> Optional[WorkflowExecutionAuditPersistence]:
    """Configure durable dashboard execution audits only when PostgreSQL is configured."""
    database_config = load_optional_database_config()
    if database_config is None:
        return None
    return create_workflow_execution_audit_persistence(database_config)


def _create_optional_schedule_persistence() -> Optional[ScheduledRecommendationPersistence]:
    """Configure KST schedule persistence only when PostgreSQL is configured."""
    database_config = load_optional_database_config()
    if database_config is None:
        return None
    return create_scheduled_recommendation_persistence(database_config)


def _create_optional_price_recorder() -> Optional[RecommendationPriceRecorder]:
    """Assemble entry-price recording only when every safe dependency is configured."""
    database_config: Optional[DatabaseConfig] = load_optional_database_config()
    if database_config is None:
        return None
    try:
        try:
            kis_config: Optional[KisConfig] = load_optional_kis_config()
        except ConfigurationError:
            logger.warning(
                "dashboard_recommendation_price_kis_unavailable",
                reason="partial_configuration",
            )
            kis_config = None
        price_service: MarketPriceService = MarketPriceService(
            KisRealtimePriceClient(kis_config),
            KrxClosingPriceClient(load_krx_config()),
        )
        return RecommendationPriceRecorder(
            price_service,
            create_recommendation_price_persistence(database_config),
        )
    except Exception as error:
        logger.warning(
            "dashboard_recommendation_price_recorder_unavailable",
            error_type=type(error).__name__,
        )
        return None


def _create_optional_performance_service() -> Optional[RecommendationPerformanceService]:
    """Assemble on-demand latest-price refresh only when DB and price adapters exist."""
    database_config: Optional[DatabaseConfig] = load_optional_database_config()
    if database_config is None:
        return None
    try:
        try:
            kis_config: Optional[KisConfig] = load_optional_kis_config()
        except ConfigurationError:
            logger.warning(
                "dashboard_recommendation_performance_kis_unavailable",
                reason="partial_configuration",
            )
            kis_config = None
        price_service: MarketPriceService = MarketPriceService(
            KisRealtimePriceClient(kis_config),
            KrxClosingPriceClient(load_krx_config()),
        )
        return RecommendationPerformanceService(
            price_service,
            create_recommendation_price_persistence(database_config),
        )
    except Exception as error:
        logger.warning(
            "dashboard_recommendation_performance_unavailable",
            error_type=type(error).__name__,
        )
        return None


def create_web_app(manager: Optional[DashboardRunManager] = None) -> FastAPI:
    """Create the dashboard API and its static single-page client."""
    run_manager: DashboardRunManager = manager or DashboardRunManager(
        filter_persistence=_create_optional_filter_persistence(),
        execution_audit_persistence=_create_optional_execution_audit_persistence(),
        schedule_persistence=_create_optional_schedule_persistence(),
        price_recorder=_create_optional_price_recorder(),
        performance_service=_create_optional_performance_service(),
    )
    app = FastAPI(title="AI Content Screening Dashboard")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return DASHBOARD_HTML

    @app.get("/api/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/recommendations/performance")
    async def get_recommendation_performance() -> RecommendationPerformanceResponse:
        return await run_manager.recommendation_performance()

    @app.get("/settings", response_class=HTMLResponse)
    async def schedule_settings_page() -> str:
        return SCHEDULE_SETTINGS_HTML

    @app.post("/api/settings/login", status_code=204)
    async def login_schedule_settings(
        request: ScheduleLoginRequest,
        response: Response,
    ) -> None:
        expected: str = load_schedule_settings_password()
        if not passwords_match(request.password, expected):
            raise HTTPException(status_code=401, detail="Schedule authentication failed")
        response.set_cookie(
            key=SCHEDULE_SESSION_COOKIE,
            value=issue_schedule_session(expected),
            max_age=60 * 60 * 8,
            httponly=True,
            secure=schedule_cookie_uses_secure_transport(),
            samesite="strict",
            path="/api/settings",
        )

    def require_schedule_session(
        session: Optional[str] = Cookie(default=None, alias=SCHEDULE_SESSION_COOKIE),
    ) -> None:
        expected: str = load_schedule_settings_password()
        if not has_valid_schedule_session(session, expected):
            raise HTTPException(status_code=401, detail="Schedule authentication failed")

    @app.get("/api/settings/schedule")
    async def get_schedule(
        _: None = Depends(require_schedule_session),
    ) -> ScheduleSettingsResponse:
        schedule: Optional[ScheduleSettingsResponse] = await run_manager.get_schedule()
        if schedule is None:
            raise HTTPException(status_code=404, detail="Schedule is not configured")
        return schedule

    @app.put("/api/settings/schedule")
    async def save_schedule(
        request: ScheduleSettingsRequest,
        _: None = Depends(require_schedule_session),
    ) -> ScheduleSettingsResponse:
        try:
            return await run_manager.save_schedule(request)
        except ScheduleVersionConflictError as error:
            raise HTTPException(status_code=409, detail="Schedule was changed elsewhere") from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post("/api/runs")
    async def start_run(request: RecommendationRunRequest) -> Dict[str, str]:
        return {"run_id": await run_manager.start(request)}

    @app.get("/api/runs/{run_id}/events")
    async def stream_events(run_id: str) -> StreamingResponse:
        run_manager.ensure_exists(run_id)

        async def stream() -> AsyncIterator[str]:
            async for event in run_manager.events(run_id):
                payload: str = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
                yield f"event: {event.type}\ndata: {payload}\n\n"
        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/runs/{run_id}")
    async def get_result(run_id: str) -> DashboardRunResult:
        return run_manager.result(run_id)

    return app


app: FastAPI = create_web_app()


_DASHBOARD_HTML: str = """<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>오늘의 투자 인사이트</title><style>body{font-family:system-ui;margin:0;background:#07111e;color:#edf3ff}main{max-width:1100px;margin:auto;padding:32px}button{background:#4f8cff;color:white;border:0;border-radius:8px;padding:12px 18px;font-weight:700}button:disabled{background:#5a6d86}.panel{background:#101d2d;border:1px solid #253852;border-radius:12px;padding:20px;margin:18px 0}.timeline li{margin:8px 0}.cards{display:flex;gap:14px;overflow-x:auto}.card{min-width:260px;background:#17263a;border-radius:10px;padding:16px}.empty{color:#aec0d8}.buy{color:#7ae5a1}.sell{color:#ff8c9b}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #29415f;text-align:left}</style></head><body><main><h1>오늘의 투자 인사이트</h1><p>실제 뉴스·공시를 수집하고 LangGraph 분석을 거쳐 Policy 기반 종목 후보를 생성합니다.</p><button id='run'>오늘의 뉴스를 기준으로 추천받기</button><section class='panel'><h2>실시간 작업</h2><ol id='timeline' class='timeline'></ol></section><section class='panel'><h2>선택된 뉴스</h2><div id='cards' class='cards'><p class='empty'>추천 실행 후 선택된 뉴스를 표시합니다.</p></div></section><section class='panel'><h2>매수 · 판매 추천</h2><table><thead><tr><th>종목</th><th>코드</th><th>점수</th><th>추천</th><th>근거</th></tr></thead><tbody id='recommendations'><tr><td colspan='5' class='empty'>추천 실행 후 결과를 표시합니다.</td></tr></tbody></table></section><script>const t=document.querySelector('#timeline'),c=document.querySelector('#cards'),r=document.querySelector('#recommendations'),b=document.querySelector('#run');const e=v=>String(v).replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));const empty=(m)=>`<p class='empty'>${e(m)}</p>`;const emptyRow=m=>`<tr><td colspan='5' class='empty'>${e(m)}</td></tr>`;const reset=()=>{b.disabled=false;b.textContent='오늘의 뉴스를 기준으로 추천받기'};b.onclick=async()=>{t.innerHTML='';c.innerHTML=empty('뉴스를 수집하고 있습니다.');r.innerHTML=emptyRow('추천 분석을 진행하고 있습니다.');b.disabled=true;b.textContent='추천 분석 중…';try{const x=await fetch('/api/runs',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({limit:3})});if(!x.ok)throw new Error('run_start_failed');const {run_id}=await x.json();let terminal=false;const es=new EventSource(`/api/runs/${run_id}/events`);for(const n of ['collecting','collected','directory','workflow','completed','failed'])es.addEventListener(n,async q=>{const d=JSON.parse(q.data);t.insertAdjacentHTML('beforeend',`<li>${e(d.message)}</li>`);if(d.type==='completed'){terminal=true;es.close();try{await load(run_id)}catch(_){c.innerHTML=empty('결과를 불러오지 못했습니다.');r.innerHTML=emptyRow('결과를 다시 실행해 주세요.')}reset()}if(d.type==='failed'){terminal=true;es.close();c.innerHTML=empty('뉴스 분석이 완료되지 않았습니다.');r.innerHTML=emptyRow('실행 환경을 확인한 뒤 다시 시도해 주세요.');reset()}});es.onerror=()=>{if(!terminal){es.close();c.innerHTML=empty('실시간 연결이 끊겼습니다.');r.innerHTML=emptyRow('다시 실행해 주세요.');reset()}}}catch(_){c.innerHTML=empty('추천 실행을 시작하지 못했습니다.');r.innerHTML=emptyRow('잠시 후 다시 시도해 주세요.');reset()}};async function load(id){const response=await fetch(`/api/runs/${id}`);if(!response.ok)throw new Error('result_load_failed');const d=await response.json();c.innerHTML=d.news_cards.length?d.news_cards.map(n=>`<article class='card'><small>${e(n.source)}</small><h3>${e(n.title)}</h3><p>${e(n.excerpt)}</p><a href='${e(n.url)}' target='_blank' rel='noreferrer'>원문 보기</a></article>`).join(''):empty('선택된 뉴스가 없습니다.');r.innerHTML=d.recommendations.length?d.recommendations.map(x=>`<tr><td>${e(x.company_name)}</td><td>${e(x.ticker||'-')}</td><td>${e(x.score)}</td><td class='${x.action.includes('buy')?'buy':x.action.includes('sell')?'sell':''}'>${e(x.action)}</td><td>${e(x.reason_code)}</td></tr>`).join(''):emptyRow('현재 정책 기준을 통과한 추천 종목이 없습니다.')}</script></main></body></html>"""
