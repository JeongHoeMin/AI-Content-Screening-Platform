from __future__ import annotations

from typing import Dict, Mapping, Protocol, Tuple, TypeVar

import structlog
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.aggregators.base import EvidenceAggregator
from app.candidates.candidate_selection_engine import CandidateSelectionEngine
from app.analyzers.base import ImpactAnalyzer
from app.evaluators.article_evaluator import ArticleEvaluator
from app.extractors.base import NewsEventExtractor
from app.models.article import Article, ArticleEvaluationResult
from app.models.candidate_selection import CandidateSelectionResult
from app.models.evidence import EvidenceAggregation
from app.models.impact_analysis import (
    ImpactAnalysis,
    ImpactEvaluation,
    ImpactExclusionReason,
)
from app.models.llm_inference import (
    ExtractionError,
    ExtractionErrorKind,
    LLMExtractionResult,
    LLMInferenceResult,
)
from app.models.news_event import NewsEvent
from app.models.recommendation import RecommendationResult
from app.models.resolved_news_event import (
    ResolvedDecisionType,
    ResolvedNewsEvent,
    TickerResolvedEvent,
)
from app.models.scoring import ScoringResult
from app.models.screening import ScreeningDecision, ScreeningDecisionType
from app.recommenders.recommendation_engine import RecommendationEngine
from app.resolvers.base import TickerResolver
from app.resolvers.policy import ResolvePolicy
from app.scorers.base import ScoringEngine
from app.screeners.base import EventScreener
from app.cross_validators.base import CrossValidator
from app.models.cross_validation import CrossValidationCandidate, CrossValidationResult, CrossValidationStatus
from app.workflows.screening.result import (
    WorkflowImpactDiagnostics,
    WorkflowStatistics,
)
from app.workflows.screening.state import ScreeningState

logger = structlog.get_logger(__name__)


class HasNewsEvent(Protocol):
    """Typed contract for values indexed by NewsEvent object identity."""

    event: NewsEvent


TEventItem = TypeVar("TEventItem", bound=HasNewsEvent)


class _ScreeningNodes:
    """Private node adapters that delegate to one injected Domain service each."""

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
    ) -> None:
        self._evaluator: ArticleEvaluator = evaluator
        self._extractor: NewsEventExtractor = extractor
        self._screener: EventScreener = screener
        self._cross_validator: CrossValidator = cross_validator
        self._resolver: TickerResolver = resolver
        self._resolve_policy: ResolvePolicy = resolve_policy
        self._impact_analyzer: ImpactAnalyzer = impact_analyzer
        self._evidence_aggregator: EvidenceAggregator = evidence_aggregator
        self._scoring_engine: ScoringEngine = scoring_engine
        self._recommendation_engine: RecommendationEngine = recommendation_engine
        self._candidate_selection_engine: CandidateSelectionEngine = candidate_selection_engine

    def evaluate(self, state: ScreeningState) -> Mapping[str, object]:
        evaluations: Tuple[ArticleEvaluationResult, ...] = self._evaluator.evaluate(
            state["articles"]
        )
        return {"evaluations": evaluations}

    async def extract(self, state: ScreeningState) -> Mapping[str, object]:
        accepted_articles: Tuple[Article, ...] = tuple(
            evaluation.article
            for evaluation in state["evaluations"]
            if evaluation.accepted
        )
        extraction: LLMExtractionResult = await self._extractor.extract(
            accepted_articles
        )
        inferences: Tuple[LLMInferenceResult, ...] = extraction.inferences
        events: Tuple[NewsEvent, ...] = tuple(
            event for inference in inferences for event in inference.events
        )
        logger.info(
            "workflow_extraction_completed",
            accepted_article_count=len(accepted_articles),
            inference_count=len(inferences),
            extracted_event_count=len(events),
            successful_batch_count=extraction.successful_batches,
            extraction_error_count=len(extraction.errors),
            extraction_error_kinds=tuple(error.kind.value for error in extraction.errors),
        )
        return {
            "inferences": inferences,
            "events": events,
            "successful_batches": extraction.successful_batches,
            "extraction_errors": extraction.errors,
        }

    async def screen(self, state: ScreeningState) -> Mapping[str, object]:
        decisions: Tuple[ScreeningDecision, ...] = await self._screener.screen(
            state["inferences"]
        )
        return {"decisions": decisions}

    async def cross_validate(self, state: ScreeningState) -> Mapping[str, object]:
        source_by_event_id: dict[int, Article] = {
            id(event): inference.article
            for inference in state.get("inferences", ())
            for event in inference.events
        }
        candidates_list: list[CrossValidationCandidate] = []
        for index, decision in enumerate(state.get("decisions", ())):
            if decision.decision is not ScreeningDecisionType.REVIEW:
                continue
            source_article: Article | None = source_by_event_id.get(id(decision.event))
            if source_article is None:
                raise ValueError(
                    "Screening decision event cannot be traced to an extraction inference"
                )
            candidates_list.append(
                CrossValidationCandidate(
                    candidate_id=f"{source_article.id}:{index}",
                    decision=decision,
                    source_article=source_article,
                    related_articles=tuple(
                        article for article in state["articles"]
                        if article.id != source_article.id
                    ),
                )
            )
        candidates: Tuple[CrossValidationCandidate, ...] = tuple(candidates_list)
        if not candidates:
            return {"cross_validation_results": ()}
        results: Tuple[CrossValidationResult, ...] = await self._cross_validator.validate(candidates)
        return {"cross_validation_results": results}

    def resolve(self, state: ScreeningState) -> Mapping[str, object]:
        decisions: Tuple[ScreeningDecision, ...] = state.get("decisions", ())
        validations_by_event_id: Dict[int, CrossValidationResult] = (
            self._index_by_event_identity(
                state.get("cross_validation_results", ()),
                item_name="cross-validation result",
            )
        )
        decision_ids: set[int] = {id(decision.event) for decision in decisions}
        if not set(validations_by_event_id).issubset(decision_ids):
            raise ValueError(
                "A cross-validation result references an Event object "
                "that does not match any ScreeningDecision."
            )
        ticker_results: Tuple[TickerResolvedEvent, ...] = tuple(
            self._resolver.resolve([decision.event for decision in decisions])
        )
        tickers_by_event_id: Dict[int, TickerResolvedEvent] = (
            self._index_by_event_identity(
                ticker_results,
                item_name="ticker snapshot",
            )
        )
        if not set(tickers_by_event_id).issubset(decision_ids):
            raise ValueError(
                "A ticker snapshot references an Event object "
                "that does not match any ScreeningDecision."
            )
        if not decision_ids.issubset(tickers_by_event_id):
            raise ValueError(
                "No ticker snapshot was found for a ScreeningDecision Event."
            )
        resolved_events: Tuple[ResolvedNewsEvent, ...] = tuple(
            self._resolve_event(
                decision,
                validations_by_event_id.get(id(decision.event)),
                tickers_by_event_id[id(decision.event)],
            )
            for decision in decisions
        )
        return {"resolved_events": resolved_events}

    def _resolve_event(self, decision: ScreeningDecision, validation: CrossValidationResult | None, ticker_result: TickerResolvedEvent) -> ResolvedNewsEvent:
        if ticker_result.event is not decision.event:
            raise ValueError(
                "Ticker snapshot Event identity does not match "
                "the ScreeningDecision Event identity."
            )
        policy_decision = self._resolve_policy.resolve(decision, validation)
        return ResolvedNewsEvent(event=decision.event, companies=ticker_result.companies, screening_decision=decision.decision, cross_validation_status=validation.status if validation is not None else None, decision=policy_decision.decision, reasons=policy_decision.reasons)

    @staticmethod
    def _index_by_event_identity(
        items: Tuple[TEventItem, ...],
        *,
        item_name: str,
    ) -> Dict[int, TEventItem]:
        indexed: Dict[int, TEventItem] = {}
        for item in items:
            event_id: int = id(item.event)
            if event_id in indexed:
                raise ValueError(
                    f"Multiple {item_name}s were found "
                    "for the same Event object identity."
                )
            indexed[event_id] = item
        return indexed

    def analyze(self, state: ScreeningState) -> Mapping[str, object]:
        analyses: Tuple[ImpactAnalysis, ...] = tuple(
            self._impact_analyzer.analyze(list(state["resolved_events"]))
        )
        return {"analyses": analyses}

    def aggregate(self, state: ScreeningState) -> Mapping[str, object]:
        analyses: Tuple[ImpactAnalysis, ...] = state.get("analyses", ())
        evidence: EvidenceAggregation = self._evidence_aggregator.aggregate(
            list(analyses)
        )
        return {"evidence": evidence}

    def score(self, state: ScreeningState) -> Mapping[str, object]:
        scoring: ScoringResult = self._scoring_engine.score(state["evidence"])
        return {"scoring": scoring}

    def recommend(self, state: ScreeningState) -> Mapping[str, object]:
        recommendation: RecommendationResult = self._recommendation_engine.recommend(
            state["scoring"]
        )
        evaluations: Tuple[ArticleEvaluationResult, ...] = state["evaluations"]
        impact_analyses: Tuple[ImpactAnalysis, ...] = state.get("analyses", ())
        extraction_errors: Tuple[ExtractionError, ...] = state.get(
            "extraction_errors",
            (),
        )
        impact_evaluations: Tuple[ImpactEvaluation, ...] = tuple(
            evaluation
            for analysis in impact_analyses
            for evaluation in analysis.evaluations
        )
        impact_diagnostics: WorkflowImpactDiagnostics = WorkflowImpactDiagnostics(
            events_without_impact_observations=sum(
                not analysis.evaluations for analysis in impact_analyses
            ),
            failed_extraction_batches=sum(
                error.kind
                in {
                    ExtractionErrorKind.API_CALL,
                    ExtractionErrorKind.RESPONSE_PROCESSING,
                }
                for error in extraction_errors
            ),
            malformed_extraction_items=sum(
                error.kind
                in {
                    ExtractionErrorKind.EVENT_VALIDATION,
                    ExtractionErrorKind.FACT_VALIDATION,
                }
                for error in extraction_errors
            ),
            total_impact_observations=len(impact_evaluations),
            eligible_impact_observations=sum(
                evaluation.eligible for evaluation in impact_evaluations
            ),
            event_rejected_exclusions=self._impact_exclusion_count(
                impact_evaluations,
                ImpactExclusionReason.EVENT_REJECTED,
            ),
            review_not_verified_exclusions=self._impact_exclusion_count(
                impact_evaluations,
                ImpactExclusionReason.EVENT_REVIEW_NOT_VERIFIED,
            ),
            unresolved_company_exclusions=self._impact_exclusion_count(
                impact_evaluations,
                ImpactExclusionReason.COMPANY_NOT_RESOLVED,
            ),
            missing_company_identity_exclusions=self._impact_exclusion_count(
                impact_evaluations,
                ImpactExclusionReason.COMPANY_IDENTITY_MISSING,
            ),
            unsupported_scope_exclusions=self._impact_exclusion_count(
                impact_evaluations,
                ImpactExclusionReason.UNSUPPORTED_SCOPE,
            ),
            unknown_direction_exclusions=self._impact_exclusion_count(
                impact_evaluations,
                ImpactExclusionReason.UNKNOWN_DIRECTION,
            ),
            scored_company_count=len(state["scoring"].companies),
        )
        accepted_articles: int = sum(
            evaluation.accepted for evaluation in evaluations
        )
        statistics: WorkflowStatistics = WorkflowStatistics(
            total_articles=len(state["articles"]),
            accepted_articles=accepted_articles,
            rejected_articles=len(evaluations) - accepted_articles,
            extracted_events=len(state.get("events", ())),
            successful_batches=state.get("successful_batches", 0),
            accepted_events=sum(
                decision.decision is ScreeningDecisionType.ACCEPT
                for decision in state.get("decisions", ())
            ),
            review_events=sum(
                decision.decision is ScreeningDecisionType.REVIEW
                for decision in state.get("decisions", ())
            ),
            rejected_events=sum(
                decision.decision is ScreeningDecisionType.REJECT
                for decision in state.get("decisions", ())
            ),
            verified_events=sum(result.status is CrossValidationStatus.VERIFIED for result in state.get("cross_validation_results", ())),
            partially_verified_events=sum(result.status is CrossValidationStatus.PARTIALLY_VERIFIED for result in state.get("cross_validation_results", ())),
            conflicted_events=sum(result.status is CrossValidationStatus.CONFLICTED for result in state.get("cross_validation_results", ())),
            insufficient_evidence_events=sum(result.status is CrossValidationStatus.INSUFFICIENT_EVIDENCE for result in state.get("cross_validation_results", ())),
            resolved_accept_count=sum(event.decision is ResolvedDecisionType.ACCEPT for event in state.get("resolved_events", ())),
            resolved_review_count=sum(event.decision is ResolvedDecisionType.REVIEW for event in state.get("resolved_events", ())),
            resolved_reject_count=sum(event.decision is ResolvedDecisionType.REJECT for event in state.get("resolved_events", ())),
            impact_diagnostics=impact_diagnostics,
        )
        logger.info(
            "workflow_recommendation_decided",
            recommendation_count=len(recommendation.decisions),
            scored_company_count=impact_diagnostics.scored_company_count,
            eligible_impact_observation_count=(
                impact_diagnostics.eligible_impact_observations
            ),
            events_without_impact_observation_count=(
                impact_diagnostics.events_without_impact_observations
            ),
            review_not_verified_exclusion_count=(
                impact_diagnostics.review_not_verified_exclusions
            ),
            unresolved_company_exclusion_count=(
                impact_diagnostics.unresolved_company_exclusions
            ),
            failed_extraction_batch_count=(
                impact_diagnostics.failed_extraction_batches
            ),
        )
        return {"recommendation": recommendation, "statistics": statistics}

    @staticmethod
    def _impact_exclusion_count(
        evaluations: Tuple[ImpactEvaluation, ...],
        reason: ImpactExclusionReason,
    ) -> int:
        """Count one safe policy exclusion without retaining raw event content."""
        return sum(
            evaluation.exclusion_reason is reason
            for evaluation in evaluations
        )

    def select_candidates(self, state: ScreeningState) -> Mapping[str, object]:
        candidate_selection: CandidateSelectionResult = self._candidate_selection_engine.select(
            state["recommendation"]
        )
        logger.info(
            "workflow_candidates_selected",
            selected_candidate_count=len(candidate_selection.candidates),
            excluded_candidate_count=len(candidate_selection.excluded),
        )
        return {"candidate_selection": candidate_selection}

    @staticmethod
    def has_accepted_articles(state: ScreeningState) -> str:
        if any(evaluation.accepted for evaluation in state["evaluations"]):
            return "extract"
        return "aggregate"


def _build_screening_graph(
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
) -> CompiledStateGraph:
    """Build the private LangGraph implementation used by ScreeningWorkflow."""
    nodes: _ScreeningNodes = _ScreeningNodes(
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
    builder: StateGraph = StateGraph(ScreeningState)
    builder.add_node("evaluate", nodes.evaluate)
    builder.add_node("extract", nodes.extract)
    builder.add_node("screen", nodes.screen)
    builder.add_node("cross_validate", nodes.cross_validate)
    builder.add_node("resolve", nodes.resolve)
    builder.add_node("analyze", nodes.analyze)
    builder.add_node("aggregate", nodes.aggregate)
    builder.add_node("score", nodes.score)
    builder.add_node("recommend", nodes.recommend)
    builder.add_node("select_candidates", nodes.select_candidates)
    builder.add_edge(START, "evaluate")
    builder.add_conditional_edges(
        "evaluate",
        nodes.has_accepted_articles,
        {"extract": "extract", "aggregate": "aggregate"},
    )
    builder.add_edge("extract", "screen")
    builder.add_edge("screen", "cross_validate")
    builder.add_edge("cross_validate", "resolve")
    builder.add_edge("resolve", "analyze")
    builder.add_edge("analyze", "aggregate")
    builder.add_edge("aggregate", "score")
    builder.add_edge("score", "recommend")
    builder.add_edge("recommend", "select_candidates")
    builder.add_edge("select_candidates", END)
    return builder.compile()
