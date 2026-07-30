from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.bootstrap import ExecutionMode
from app.harness import Harness
from app.harness.execution_audit import ScreeningExecutionHarness
from app.market_data import (
    create_market_collect_posts_skill,
    create_market_screening_workflow,
    posts_to_articles,
)
from app.models.collect_posts import CollectPostsRequest
from app.models.community import CommunityType
from app.models.post import Post
from app.workflows import ScreeningResult, WorkflowProgressEvent


class RecommendationRunRequest(BaseModel):
    """Validated public input for one dashboard recommendation execution."""

    model_config = ConfigDict(frozen=True)

    category: str = Field(default="국내 증시", min_length=1, max_length=100)
    limit: int = Field(default=50, ge=1, le=100)
    period_hours: int = Field(default=24, ge=1, le=168)


class DashboardEvent(BaseModel):
    """Safe server-sent event payload used by the browser timeline."""

    model_config = ConfigDict(frozen=True)

    type: str = Field(min_length=1)
    message: str = Field(min_length=1)
    node: Optional[str] = None
    completed_node_count: Optional[int] = Field(default=None, ge=1)
    error_type: Optional[str] = None


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


class DashboardRunResult(BaseModel):
    """Terminal dashboard result without raw provider responses or prompts."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    news_cards: List[NewsCard]
    recommendations: List[RecommendationCard]
    statistics: Dict[str, int]


@dataclass
class _RunState:
    queue: asyncio.Queue[DashboardEvent] = field(default_factory=asyncio.Queue)
    result: Optional[DashboardRunResult] = None
    error_type: Optional[str] = None
    completed: bool = False


class DashboardRunManager:
    """Harness-owned in-memory state for bounded live dashboard executions."""

    def __init__(self) -> None:
        self._runs: Dict[str, _RunState] = {}

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
        try:
            await self._emit(state, "collecting", "오늘의 뉴스와 공시를 수집하고 있습니다.")
            collect_result = await Harness().run(
                create_market_collect_posts_skill(),
                CollectPostsRequest(
                    sources=[CommunityType.NAVER_NEWS, CommunityType.DART],
                    limit=request.limit,
                    period=timedelta(hours=request.period_hours),
                    category=request.category,
                ),
            )
            posts: List[Post] = collect_result.data.posts
            articles = posts_to_articles(posts)
            await self._emit(
                state,
                "collected",
                f"{len(posts)}건을 수집하고 {len(articles)}건을 분석 대상으로 선택했습니다.",
            )
            await self._emit(state, "directory", "KRX 종목 스냅샷을 준비하고 있습니다.")
            workflow = await create_market_screening_workflow(ExecutionMode.OPENAI)

            async def on_progress(event: WorkflowProgressEvent) -> None:
                await self._emit(
                    state,
                    "workflow",
                    f"LangGraph 단계 완료: {event.node}",
                    node=event.node,
                    completed_node_count=event.completed_node_count,
                )

            result: ScreeningResult = await ScreeningExecutionHarness().run_with_progress(
                workflow,
                articles,
                ExecutionMode.OPENAI.value,
                on_progress,
            )
            state.result = self._build_result(run_id, posts, result)
            state.completed = True
            await self._emit(state, "completed", "추천 분석이 완료되었습니다.")
        except Exception as error:
            state.error_type = type(error).__name__
            state.completed = True
            await self._emit(
                state,
                "failed",
                "추천 실행에 실패했습니다. 실행 환경 설정을 확인하세요.",
                error_type=state.error_type,
            )

    def _build_result(
        self,
        run_id: str,
        posts: List[Post],
        result: ScreeningResult,
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
        statistics: Dict[str, int] = result.statistics.model_dump()
        return DashboardRunResult(
            run_id=run_id,
            news_cards=news_cards,
            recommendations=recommendations,
            statistics=statistics,
        )

    async def _emit(
        self,
        state: _RunState,
        event_type: str,
        message: str,
        node: Optional[str] = None,
        completed_node_count: Optional[int] = None,
        error_type: Optional[str] = None,
    ) -> None:
        await state.queue.put(
            DashboardEvent(
                type=event_type,
                message=message,
                node=node,
                completed_node_count=completed_node_count,
                error_type=error_type,
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
        return _DASHBOARD_HTML

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


_DASHBOARD_HTML: str = """<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>오늘의 투자 인사이트</title><style>body{font-family:system-ui;margin:0;background:#07111e;color:#edf3ff}main{max-width:1100px;margin:auto;padding:32px}button{background:#4f8cff;color:white;border:0;border-radius:8px;padding:12px 18px;font-weight:700}.panel{background:#101d2d;border:1px solid #253852;border-radius:12px;padding:20px;margin:18px 0}.timeline li{margin:8px 0}.cards{display:flex;gap:14px;overflow-x:auto}.card{min-width:260px;background:#17263a;border-radius:10px;padding:16px}.buy{color:#7ae5a1}.sell{color:#ff8c9b}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #29415f;text-align:left}</style></head><body><main><h1>오늘의 투자 인사이트</h1><p>실제 뉴스·공시를 수집하고 LangGraph 분석을 거쳐 Policy 기반 종목 후보를 생성합니다.</p><button id='run'>오늘의 뉴스를 기준으로 추천받기</button><section class='panel'><h2>실시간 작업</h2><ol id='timeline' class='timeline'></ol></section><section class='panel'><h2>선택된 뉴스</h2><div id='cards' class='cards'></div></section><section class='panel'><h2>매수 · 판매 추천</h2><table><thead><tr><th>종목</th><th>코드</th><th>점수</th><th>추천</th><th>근거</th></tr></thead><tbody id='recommendations'></tbody></table></section><script>const t=document.querySelector('#timeline'),c=document.querySelector('#cards'),r=document.querySelector('#recommendations');document.querySelector('#run').onclick=async()=>{t.innerHTML='';c.innerHTML='';r.innerHTML='';const x=await fetch('/api/runs',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({})});const {run_id}=await x.json();const es=new EventSource(`/api/runs/${run_id}/events`);es.onmessage=()=>{};for(const n of ['collecting','collected','directory','workflow','completed','failed'])es.addEventListener(n,e=>{const d=JSON.parse(e.data);t.insertAdjacentHTML('beforeend',`<li>${d.message}</li>`);if(d.type==='completed'){es.close();load(run_id)}})};async function load(id){const d=await (await fetch(`/api/runs/${id}`)).json();c.innerHTML=d.news_cards.map(n=>`<article class='card'><small>${n.source}</small><h3>${n.title}</h3><p>${n.excerpt}</p><a href='${n.url}' target='_blank'>원문 보기</a></article>`).join('');r.innerHTML=d.recommendations.map(x=>`<tr><td>${x.company_name}</td><td>${x.ticker||'-'}</td><td>${x.score}</td><td class='${x.action.includes('buy')?'buy':x.action.includes('sell')?'sell':''}'>${x.action}</td><td>${x.reason_code}</td></tr>`).join('')}</script></main></body></html>"""
