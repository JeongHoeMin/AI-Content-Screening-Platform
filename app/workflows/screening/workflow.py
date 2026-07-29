from __future__ import annotations

from typing import Mapping, Optional, Tuple, cast

from langgraph.graph.state import CompiledStateGraph

from app.aggregators.base import EvidenceAggregator
from app.analyzers.base import ImpactAnalyzer
from app.evaluators.article_evaluator import ArticleEvaluator
from app.extractors.base import NewsEventExtractor
from app.models.article import Article
from app.models.recommendation import RecommendationResult
from app.models.screening import ScreeningDecision
from app.recommenders.recommendation_engine import RecommendationEngine
from app.resolvers.base import TickerResolver
from app.scorers.base import ScoringEngine
from app.screeners.base import EventScreener
from app.workflows.screening.graph import _build_screening_graph
from app.workflows.screening.result import (
    ScreeningResult,
    WorkflowContext,
    WorkflowStatistics,
)
from app.workflows.screening.state import ScreeningState


class ScreeningWorkflow:
    """Public workflow entrypoint that encapsulates the LangGraph implementation."""

    def __init__(
        self,
        evaluator: ArticleEvaluator,
        extractor: NewsEventExtractor,
        screener: EventScreener,
        resolver: TickerResolver,
        impact_analyzer: ImpactAnalyzer,
        evidence_aggregator: EvidenceAggregator,
        scoring_engine: ScoringEngine,
        recommendation_engine: RecommendationEngine,
    ) -> None:
        self._graph: CompiledStateGraph = _build_screening_graph(
            evaluator=evaluator,
            extractor=extractor,
            screener=screener,
            resolver=resolver,
            impact_analyzer=impact_analyzer,
            evidence_aggregator=evidence_aggregator,
            scoring_engine=scoring_engine,
            recommendation_engine=recommendation_engine,
        )

    async def run(
        self,
        articles: Tuple[Article, ...],
        context: Optional[WorkflowContext] = None,
    ) -> ScreeningResult:
        """Run one screening execution without exposing graph internals."""
        if context is None:
            context = WorkflowContext()
        initial_state: ScreeningState = {"articles": articles, "context": context}
        final_state: Mapping[str, object] = await self._graph.ainvoke(initial_state)
        recommendation: RecommendationResult = cast(
            RecommendationResult,
            final_state["recommendation"],
        )
        statistics: WorkflowStatistics = cast(
            WorkflowStatistics,
            final_state["statistics"],
        )
        decisions: Tuple[ScreeningDecision, ...] = cast(
            Tuple[ScreeningDecision, ...],
            final_state.get("decisions", ()),
        )
        return ScreeningResult(
            recommendation=recommendation,
            decisions=decisions,
            statistics=statistics,
        )
