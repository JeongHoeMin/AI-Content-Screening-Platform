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
from app.deduplicators.event_deduplicator import EventDeduplicator
from app.llms.budget import ProviderRequestBudget
from app.models.article import Article, ArticleEvaluationResult
from app.models.candidate_selection import CandidateSelectionResult
from app.models.cross_validation import CrossValidationResult, CrossValidationStatus
from app.models.evidence import EvidenceAggregation
from app.models.impact_analysis import ImpactAnalysis
from app.models.llm_inference import LLMInferenceResult
from app.models.recommendation import RecommendationResult
from app.models.resolved_news_event import ResolvedDecisionType, ResolvedNewsEvent
from app.models.scoring import ScoringResult
from app.models.screening import ScreeningDecision, ScreeningDecisionType
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
    WorkflowEvidenceQuote,
    WorkflowEventEvidenceProgress,
    WorkflowProgressEvent,
    WorkflowScorecardProgress,
    WorkflowScreeningAnalysisProgress,
    WorkflowStageCounts,
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
        event_deduplicator: Optional[EventDeduplicator] = None,
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
            event_deduplicator=event_deduplicator,
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
                    previous_state: dict[str, object] = dict(state)
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
                    stage_counts: Optional[WorkflowStageCounts] = self._stage_counts(
                        node,
                        previous_state,
                        node_update,
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
                    next_node: Optional[str] = self._next_node(node, state)
                    await progress_callback(
                        WorkflowProgressEvent(
                            node=node,
                            completed_node_count=completed_node_count,
                            output_keys=tuple(sorted(str(key) for key in node_update)),
                            next_node=next_node,
                            article_analyses=article_analyses,
                            screening_analyses=screening_analyses,
                            validation_analyses=validation_analyses,
                            stage_counts=stage_counts,
                        )
                    )
        except Exception as error:
            self._raise_retry_exhausted(error)
            raise
        return self._result_from_final_state(state)

    @staticmethod
    def _next_node(node: str, state: Mapping[str, object]) -> Optional[str]:
        """Expose the graph's actual safe next edge without leaking workflow state."""
        if node == "evaluate":
            evaluations = cast(
                Tuple[ArticleEvaluationResult, ...],
                state.get("evaluations", ()),
            )
            return "extract" if any(item.accepted for item in evaluations) else "aggregate"
        node_order: tuple[str, ...] = (
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
        try:
            index: int = node_order.index(node)
        except ValueError:
            return None
        return node_order[index + 1] if index + 1 < len(node_order) else None

    @staticmethod
    def _raise_retry_exhausted(error: Exception) -> None:
        if not _retry_llm_stage(error):
            return
        if isinstance(error, AllExtractionBatchesFailedError):
            stage: str = "extract"
        elif isinstance(error, NoValidScreeningDecisionsError):
            stage = "screen"
        elif isinstance(error, StructuredOutputCallError):
            stage = str(getattr(error, "workflow_stage", "cross_validate"))
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
                        event_evidence=tuple(
                            WorkflowEventEvidenceProgress(
                                event_title=event.title,
                                source_url=str(item.article.url),
                                quotes=tuple(
                                    WorkflowEvidenceQuote(
                                        paragraph_index=evidence.paragraph_index,
                                        quote=evidence.quote,
                                    )
                                    for evidence in event.evidence[:2]
                                ),
                            )
                            for event in item.events
                        ),
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
                        scorecard=(WorkflowScorecardProgress(
                            theme_directness=item.scorecard.relevance.theme_directness,
                            topic_match=item.scorecard.relevance.topic_match,
                            market_transmission_path=item.scorecard.relevance.market_transmission_path,
                            relevance_reason=item.scorecard.relevance.reason,
                            impact_magnitude=item.scorecard.importance.impact_magnitude,
                            scope_and_spillover=item.scorecard.importance.scope_and_spillover,
                            time_sensitivity=item.scorecard.importance.time_sensitivity,
                            importance_reason=item.scorecard.importance.reason,
                            source_authority=item.scorecard.credibility.source_authority,
                            evidence_specificity=item.scorecard.credibility.evidence_specificity,
                            corroboration_and_uncertainty=item.scorecard.credibility.corroboration_and_uncertainty,
                            credibility_reason=item.scorecard.credibility.reason,
                        ) if item.scorecard is not None else None),
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

    @staticmethod
    def _stage_counts(
        node: str,
        previous_state: Mapping[str, object],
        node_update: Mapping[str, object],
    ) -> Optional[WorkflowStageCounts]:
        """Project safe input/accepted/rejected counts from one node's own output."""
        if node == "evaluate":
            evaluations = cast(
                Tuple[ArticleEvaluationResult, ...],
                node_update.get("evaluations", ()),
            )
            accepted: int = sum(1 for item in evaluations if item.accepted)
            return WorkflowStageCounts(
                input_count=len(cast(tuple, previous_state.get("articles", ()))),
                accepted_count=accepted,
                rejected_count=len(evaluations) - accepted,
            )
        if node == "extract":
            prior_evaluations = cast(
                Tuple[ArticleEvaluationResult, ...],
                previous_state.get("evaluations", ()),
            )
            events = cast(tuple, node_update.get("events", ()))
            extraction_errors = cast(tuple, node_update.get("extraction_errors", ()))
            return WorkflowStageCounts(
                input_count=sum(1 for item in prior_evaluations if item.accepted),
                accepted_count=len(events),
                rejected_count=len(extraction_errors),
            )
        if node == "deduplicate":
            if "events" not in node_update:
                passthrough: int = len(cast(tuple, previous_state.get("events", ())))
                return WorkflowStageCounts(
                    input_count=passthrough,
                    accepted_count=passthrough,
                    rejected_count=0,
                )
            prior_inferences = cast(
                Tuple[LLMInferenceResult, ...],
                previous_state.get("inferences", ()),
            )
            pre_dedup_count: int = sum(len(item.events) for item in prior_inferences)
            canonical_count: int = len(cast(tuple, node_update.get("events", ())))
            return WorkflowStageCounts(
                input_count=pre_dedup_count,
                accepted_count=canonical_count,
                rejected_count=max(pre_dedup_count - canonical_count, 0),
            )
        if node == "screen":
            decisions = cast(
                Tuple[ScreeningDecision, ...],
                node_update.get("decisions", ()),
            )
            passed: int = sum(
                1
                for item in decisions
                if item.decision is not ScreeningDecisionType.REJECT
            )
            return WorkflowStageCounts(
                input_count=len(decisions),
                accepted_count=passed,
                rejected_count=len(decisions) - passed,
            )
        if node == "cross_validate":
            prior_decisions = cast(
                Tuple[ScreeningDecision, ...],
                previous_state.get("decisions", ()),
            )
            input_count: int = sum(
                1
                for item in prior_decisions
                if item.decision is ScreeningDecisionType.REVIEW
            )
            results = cast(
                Tuple[CrossValidationResult, ...],
                node_update.get("cross_validation_results", ()),
            )
            verified: int = sum(
                1
                for item in results
                if item.status
                in (
                    CrossValidationStatus.VERIFIED,
                    CrossValidationStatus.PARTIALLY_VERIFIED,
                )
            )
            return WorkflowStageCounts(
                input_count=input_count,
                accepted_count=verified,
                rejected_count=len(results) - verified,
            )
        if node == "resolve":
            prior_decisions = cast(
                Tuple[ScreeningDecision, ...],
                previous_state.get("decisions", ()),
            )
            resolved_events = cast(
                Tuple[ResolvedNewsEvent, ...],
                node_update.get("resolved_events", ()),
            )
            resolved_accepted: int = sum(
                1
                for item in resolved_events
                if item.decision is not ResolvedDecisionType.REJECT
            )
            return WorkflowStageCounts(
                input_count=len(prior_decisions),
                accepted_count=resolved_accepted,
                rejected_count=len(resolved_events) - resolved_accepted,
            )
        if node == "analyze":
            prior_resolved_events = cast(
                Tuple[ResolvedNewsEvent, ...],
                previous_state.get("resolved_events", ()),
            )
            analyses = cast(Tuple[ImpactAnalysis, ...], node_update.get("analyses", ()))
            return WorkflowStageCounts(
                input_count=len(prior_resolved_events),
                accepted_count=len(analyses),
                rejected_count=max(len(prior_resolved_events) - len(analyses), 0),
            )
        if node == "aggregate":
            prior_analyses = cast(
                Tuple[ImpactAnalysis, ...],
                previous_state.get("analyses", ()),
            )
            impact_evaluations = tuple(
                evaluation
                for analysis in prior_analyses
                for evaluation in analysis.evaluations
            )
            eligible: int = sum(1 for item in impact_evaluations if item.eligible)
            return WorkflowStageCounts(
                input_count=len(impact_evaluations),
                accepted_count=eligible,
                rejected_count=len(impact_evaluations) - eligible,
            )
        if node == "score":
            prior_evidence = cast(
                Optional[EvidenceAggregation],
                previous_state.get("evidence"),
            )
            input_companies: int = (
                len(prior_evidence.companies) if prior_evidence is not None else 0
            )
            scoring = cast(Optional[ScoringResult], node_update.get("scoring"))
            scored_companies: int = len(scoring.companies) if scoring is not None else 0
            return WorkflowStageCounts(
                input_count=input_companies,
                accepted_count=scored_companies,
                rejected_count=max(input_companies - scored_companies, 0),
            )
        if node == "recommend":
            prior_scoring = cast(Optional[ScoringResult], previous_state.get("scoring"))
            input_companies = (
                len(prior_scoring.companies) if prior_scoring is not None else 0
            )
            recommendation = cast(
                Optional[RecommendationResult],
                node_update.get("recommendation"),
            )
            decided: int = (
                len(recommendation.decisions) if recommendation is not None else 0
            )
            return WorkflowStageCounts(
                input_count=input_companies,
                accepted_count=decided,
                rejected_count=max(input_companies - decided, 0),
            )
        if node == "select_candidates":
            candidate_selection = cast(
                Optional[CandidateSelectionResult],
                node_update.get("candidate_selection"),
            )
            if candidate_selection is None:
                return None
            return WorkflowStageCounts(
                input_count=len(candidate_selection.evaluations),
                accepted_count=len(candidate_selection.candidates),
                rejected_count=len(candidate_selection.excluded),
            )
        return None

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
