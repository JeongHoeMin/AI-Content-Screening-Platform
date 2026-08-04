from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Mapping, Optional, Tuple, cast

import structlog
from langgraph.graph.state import CompiledStateGraph

from app.aggregators.base import EvidenceAggregator
from app.candidates.candidate_selection_engine import CandidateSelectionEngine
from app.analyzers.base import ImpactAnalyzer
from app.evaluators.article_evaluator import ArticleEvaluator
from app.extractors.base import NewsEventExtractor
from app.llms.budget import ProviderRequestBudget
from app.models.article import Article, ArticleEvaluationResult
from app.models.candidate_selection import CandidateSelectionResult
from app.models.cross_validation import CrossValidationResult
from app.models.llm_inference import LLMInferenceResult
from app.models.recommendation import RecommendationResult
from app.models.screening import ScreeningDecision
from app.recommenders.recommendation_engine import RecommendationEngine
from app.resolvers.base import TickerResolver
from app.resolvers.policy import ResolvePolicy
from app.scorers.base import ScoringEngine
from app.screeners.base import EventScreener
from app.cross_validators.base import CrossValidator
from app.workflows.screening.graph import _build_screening_graph
from app.workflows.screening.graph import _retry_llm_stage
from app.workflows.screening.errors import WorkflowStageRetriesExhaustedError
from app.extractors.errors import AllExtractionBatchesFailedError
from app.screeners.errors import NoValidScreeningDecisionsError
from app.llms.errors import StructuredOutputCallError
from app.workflows.screening.result import (
    ScreeningResult,
    WorkflowArticleAnalysisProgress,
    WorkflowContext,
    WorkflowProgressEvent,
    WorkflowScreeningAnalysisProgress,
    WorkflowStatistics,
    WorkflowValidationAnalysisProgress,
)
from app.workflows.screening.state import ScreeningState

logger = structlog.get_logger(__name__)


class ScreeningWorkflow:
    """Public workflow entrypoint that encapsulates the LangGraph implementation."""

    def __init__(
        self,
        evaluator: ArticleEvaluator,
        extractor: NewsEventExtractor,
        screener: EventScreener,
        cross_validator: CrossValidator,
        resolver: TickerResolver,
        resolve_policy: ResolvePolicy,
        impact_analyzer: ImpactAnalyzer,
        evidence_aggregator: EvidenceAggregator,
        scoring_engine: ScoringEngine,
        recommendation_engine: RecommendationEngine,
        candidate_selection_engine: CandidateSelectionEngine,
        request_budget: Optional[ProviderRequestBudget] = None,
    ) -> None:
        self._graph: CompiledStateGraph = _build_screening_graph(
            evaluator=evaluator,
            extractor=extractor,
            screener=screener,
            cross_validator=cross_validator,
            resolver=resolver,
            resolve_policy=resolve_policy,
            impact_analyzer=impact_analyzer,
            evidence_aggregator=evidence_aggregator,
            scoring_engine=scoring_engine,
            recommendation_engine=recommendation_engine,
            candidate_selection_engine=candidate_selection_engine,
        )
        self.request_budget: Optional[ProviderRequestBudget] = request_budget

    async def run(
        self,
        articles: Tuple[Article, ...],
        context: Optional[WorkflowContext] = None,
    ) -> ScreeningResult:
        """Run one screening execution without exposing graph internals."""
        if context is None:
            context = WorkflowContext()
        initial_state: ScreeningState = {"articles": articles, "context": context}
        try:
            final_state: Mapping[str, object] = await self._graph.ainvoke(initial_state)
        except Exception as error:
            self._raise_retry_exhausted(error)
            raise
        return self._result_from_final_state(final_state)

    async def run_with_progress(
        self,
        articles: Tuple[Article, ...],
        progress_callback: Callable[[WorkflowProgressEvent], Awaitable[None]],
        context: Optional[WorkflowContext] = None,
    ) -> ScreeningResult:
        """Run once and emit one safe event after each completed LangGraph node."""
        if context is None:
            context = WorkflowContext()
        state: dict[str, object] = {"articles": articles, "context": context}
        completed_node_count: int = 0
        article_id_by_event_id: dict[int, str] = {}
        try:
            async for update in self._graph.astream(state, stream_mode="updates"):
                for node, node_update in update.items():
                    if not isinstance(node_update, Mapping):
                        raise ValueError("LangGraph node update must be a mapping")
                    state.update(node_update)
                    completed_node_count += 1
                    (
                        article_analyses,
                        screening_analyses,
                        validation_analyses,
                    ) = self._analysis_progress(
                        node,
                        state,
                        article_id_by_event_id,
                    )
                    logger.info(
                        "workflow_node_completed",
                        node=node,
                        completed_node_count=completed_node_count,
                        output_keys=tuple(sorted(str(key) for key in node_update)),
                        article_analysis_count=len(article_analyses),
                        screening_analysis_count=len(screening_analyses),
                        validation_analysis_count=len(validation_analyses),
                    )
                    await progress_callback(
                        WorkflowProgressEvent(
                            node=node,
                            completed_node_count=completed_node_count,
                            output_keys=tuple(sorted(str(key) for key in node_update)),
                            article_analyses=article_analyses,
                            screening_analyses=screening_analyses,
                            validation_analyses=validation_analyses,
                        )
                    )
        except Exception as error:
            self._raise_retry_exhausted(error)
            raise
        return self._result_from_final_state(state)

    @staticmethod
    def _raise_retry_exhausted(error: Exception) -> None:
        if not _retry_llm_stage(error):
            return
        if isinstance(error, AllExtractionBatchesFailedError):
            stage: str = "extract"
        elif isinstance(error, NoValidScreeningDecisionsError):
            stage = "screen"
        elif isinstance(error, StructuredOutputCallError):
            stage = "cross_validate"
        else:
            return
        raise WorkflowStageRetriesExhaustedError(stage, error.error_type) from error

    @staticmethod
    def _analysis_progress(
        node: str,
        state: Mapping[str, object],
        article_id_by_event_id: dict[int, str],
    ) -> tuple[
        Tuple[WorkflowArticleAnalysisProgress, ...],
        Tuple[WorkflowScreeningAnalysisProgress, ...],
        Tuple[WorkflowValidationAnalysisProgress, ...],
    ]:
        """Project only safe, user-readable analysis observations from node outputs."""
        if node == "extract":
            inferences = cast(
                Tuple[LLMInferenceResult, ...],
                state.get("inferences", ()),
            )
            article_analyses: list[WorkflowArticleAnalysisProgress] = []
            inference_article_ids: set[str] = set()
            for item in inferences:
                inference_article_ids.add(item.article.id)
                for event in item.events:
                    article_id_by_event_id[id(event)] = item.article.id
                article_analyses.append(
                    WorkflowArticleAnalysisProgress(
                        article_id=item.article.id,
                        title=item.article.title,
                        source=item.article.source,
                        summary=item.summary,
                        reasoning=item.reasoning,
                        event_titles=tuple(event.title for event in item.events),
                    )
                )
            evaluations = cast(
                Tuple[ArticleEvaluationResult, ...],
                state.get("evaluations", ()),
            )
            for item in evaluations:
                if item.article.id in inference_article_ids:
                    continue
                status_reason: str = (
                    "The preflight evaluator rejected this article."
                    if not item.accepted
                    else "The extraction stage returned no valid inference for this article."
                )
                article_analyses.append(
                    WorkflowArticleAnalysisProgress(
                        article_id=item.article.id,
                        title=item.article.title,
                        source=item.article.source,
                        summary="No investment event was extracted from this article.",
                        reasoning=status_reason,
                    )
                )
            return tuple(article_analyses), (), ()
        if node == "screen":
            decisions = cast(
                Tuple[ScreeningDecision, ...],
                state.get("decisions", ()),
            )
            screening_analyses: list[WorkflowScreeningAnalysisProgress] = []
            for item in decisions:
                article_id: Optional[str] = article_id_by_event_id.get(id(item.event))
                if article_id is None:
                    continue
                screening_analyses.append(
                    WorkflowScreeningAnalysisProgress(
                        article_id=article_id,
                        event_title=item.event.title,
                        decision=item.decision.value,
                        relevance=item.relevance,
                        importance=item.importance,
                        credibility=item.credibility,
                        reasons=item.reasons,
                    )
                )
            return (), tuple(screening_analyses), ()
        if node == "cross_validate":
            validations = cast(
                Tuple[CrossValidationResult, ...],
                state.get("cross_validation_results", ()),
            )
            validation_analyses: list[WorkflowValidationAnalysisProgress] = []
            for item in validations:
                article_id = article_id_by_event_id.get(id(item.event))
                if article_id is None:
                    continue
                validation_analyses.append(
                    WorkflowValidationAnalysisProgress(
                        article_id=article_id,
                        event_title=item.event.title,
                        status=item.status.value,
                    )
                )
            return (), (), tuple(validation_analyses)
        return (), (), ()

    def _result_from_final_state(
        self,
        final_state: Mapping[str, object],
    ) -> ScreeningResult:
        recommendation: RecommendationResult = cast(
            RecommendationResult,
            final_state["recommendation"],
        )
        candidate_selection: CandidateSelectionResult = cast(
            CandidateSelectionResult,
            final_state["candidate_selection"],
        )
        statistics: WorkflowStatistics = cast(
            WorkflowStatistics,
            final_state["statistics"],
        )
        decisions: Tuple[ScreeningDecision, ...] = cast(
            Tuple[ScreeningDecision, ...],
            final_state.get("decisions", ()),
        )
        cross_validation_results = cast(
            tuple, final_state.get("cross_validation_results", ())
        )
        resolved_events = cast(tuple, final_state.get("resolved_events", ()))
        return ScreeningResult(
            recommendation=recommendation,
            candidate_selection=candidate_selection,
            decisions=decisions,
            cross_validation_results=cross_validation_results,
            resolved_events=resolved_events,
            statistics=statistics,
        )
