from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import ceil
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.bootstrap import ExecutionMode
from app.harness import Harness
from app.harness.execution_audit import ScreeningExecutionHarness
from app.harness.execution_audit import JsonLinesWorkflowExecutionAuditSink
from app.market_data import (
    create_market_collect_posts_skill,
    create_market_screening_workflow,
    posts_to_articles,
)
from app.models.collect_posts import CollectPostsRequest
from app.models.community import CommunityType
from app.models.post import Post
from app.workflows import ScreeningResult, WorkflowProgressEvent
from app.web.dashboard_html import DASHBOARD_HTML
from app.observability import configure_application_logging

import structlog

configure_application_logging()
logger = structlog.get_logger(__name__)

_RETRIED_ERROR_TYPES: frozenset[str] = frozenset(
    {"APITimeoutError", "APIConnectionError", "AuthenticationError", "PermissionDeniedError"}
)


class RecommendationRunRequest(BaseModel):
    """Validated public input for one dashboard recommendation execution."""

    model_config = ConfigDict(frozen=True)

    category: str = Field(default="국내 증시", min_length=1, max_length=100)
    limit: Literal[10, 25, 50, 100] = 10
    period_hours: int = Field(default=24, ge=1, le=168)


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

    def __init__(self) -> None:
        self._runs: Dict[str, _RunState] = {}

    _WORKFLOW_NODES: tuple[str, ...] = (
        "evaluate",
        "extract",
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
            collection_sources: tuple[CommunityType, ...] = (
                CommunityType.NAVER_NEWS,
                CommunityType.DART,
            )
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
            initial_analyses: List[NewsAnalysisCard] = self._initial_analyses(posts)
            state.analyses = {analysis.id: analysis for analysis in initial_analyses}
            await self._emit(
                state,
                "collected",
                f"{len(posts)}건을 수집하고 {len(articles)}건을 분석 대상으로 선택했습니다.",
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
                    active_stage=self._next_workflow_stage(event.node),
                    completed_stage_count=event.completed_node_count + 2,
                    analyses=changed_analyses,
                )

            result: ScreeningResult = await ScreeningExecutionHarness(
                audit_sink=self._audit_sink(),
            ).run_with_progress(
                workflow,
                articles,
                ExecutionMode.OPENAI.value,
                on_progress,
            )
            state.result = self._build_result(run_id, posts, result, state.analyses)
            state.completed = True
            await self._emit(
                state,
                "completed",
                "추천 분석이 완료되었습니다.",
                completed_stage_count=self._TOTAL_STAGE_COUNT,
            )
        except Exception as error:
            state.error_type = type(error).__name__
            state.failure_stage = getattr(error, "stage", state.active_stage)
            error_type: str = getattr(error, "error_type", state.error_type)
            state.failure_attempts = getattr(
                error,
                "attempts",
                3 if error_type in _RETRIED_ERROR_TYPES else 1,
            )
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
        for decision in result.recommendation.decisions:
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
                )
            )
        statistics: Dict[str, Any] = result.statistics.model_dump()
        return DashboardRunResult(
            run_id=run_id,
            news_cards=news_cards,
            analyses=list(analyses.values()),
            recommendations=recommendations,
            statistics=statistics,
        )

    @staticmethod
    def _initial_analyses(posts: List[Post]) -> List[NewsAnalysisCard]:
        """Project all collected posts before workflow analysis begins."""
        return [
            NewsAnalysisCard(
                id=f"{post.source.value}:{post.id}",
                title=post.title,
                source=post.source.value,
                status="수집 완료 · 분석 대기",
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


def create_web_app(manager: Optional[DashboardRunManager] = None) -> FastAPI:
    """Create the dashboard API and its static single-page client."""
    run_manager: DashboardRunManager = manager or DashboardRunManager()
    app = FastAPI(title="AI Content Screening Dashboard")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return DASHBOARD_HTML

    @app.get("/api/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

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
