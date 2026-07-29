from __future__ import annotations

from typing import Mapping, Tuple

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.aggregators.base import EvidenceAggregator
from app.analyzers.base import ImpactAnalyzer
from app.evaluators.article_evaluator import ArticleEvaluator
from app.extractors.base import NewsEventExtractor
from app.models.article import Article, ArticleEvaluationResult
from app.models.evidence import EvidenceAggregation
from app.models.impact_analysis import ImpactAnalysis
from app.models.llm_inference import LLMExtractionResult, LLMInferenceResult
from app.models.news_event import NewsEvent
from app.models.recommendation import RecommendationResult
from app.models.resolved_news_event import ResolvedNewsEvent
from app.models.scoring import ScoringResult
from app.recommenders.recommendation_engine import RecommendationEngine
from app.resolvers.base import TickerResolver
from app.scorers.base import ScoringEngine
from app.workflows.screening.result import WorkflowStatistics
from app.workflows.screening.state import ScreeningState


class _ScreeningNodes:
    """Private node adapters that delegate to one injected Domain service each."""

    def __init__(
        self,
        evaluator: ArticleEvaluator,
        extractor: NewsEventExtractor,
        resolver: TickerResolver,
        impact_analyzer: ImpactAnalyzer,
        evidence_aggregator: EvidenceAggregator,
        scoring_engine: ScoringEngine,
        recommendation_engine: RecommendationEngine,
    ) -> None:
        self._evaluator: ArticleEvaluator = evaluator
        self._extractor: NewsEventExtractor = extractor
        self._resolver: TickerResolver = resolver
        self._impact_analyzer: ImpactAnalyzer = impact_analyzer
        self._evidence_aggregator: EvidenceAggregator = evidence_aggregator
        self._scoring_engine: ScoringEngine = scoring_engine
        self._recommendation_engine: RecommendationEngine = recommendation_engine

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
        return {
            "inferences": inferences,
            "events": events,
            "successful_batches": extraction.successful_batches,
        }

    def resolve(self, state: ScreeningState) -> Mapping[str, object]:
        resolved_events: Tuple[ResolvedNewsEvent, ...] = tuple(
            self._resolver.resolve(list(state["events"]))
        )
        return {"resolved_events": resolved_events}

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
        accepted_articles: int = sum(
            evaluation.accepted for evaluation in evaluations
        )
        statistics: WorkflowStatistics = WorkflowStatistics(
            total_articles=len(state["articles"]),
            accepted_articles=accepted_articles,
            rejected_articles=len(evaluations) - accepted_articles,
            extracted_events=len(state.get("events", ())),
            successful_batches=state.get("successful_batches", 0),
        )
        return {"recommendation": recommendation, "statistics": statistics}

    @staticmethod
    def has_accepted_articles(state: ScreeningState) -> str:
        if any(evaluation.accepted for evaluation in state["evaluations"]):
            return "extract"
        return "aggregate"


def _build_screening_graph(
    evaluator: ArticleEvaluator,
    extractor: NewsEventExtractor,
    resolver: TickerResolver,
    impact_analyzer: ImpactAnalyzer,
    evidence_aggregator: EvidenceAggregator,
    scoring_engine: ScoringEngine,
    recommendation_engine: RecommendationEngine,
) -> CompiledStateGraph:
    """Build the private LangGraph implementation used by ScreeningWorkflow."""
    nodes: _ScreeningNodes = _ScreeningNodes(
        evaluator=evaluator,
        extractor=extractor,
        resolver=resolver,
        impact_analyzer=impact_analyzer,
        evidence_aggregator=evidence_aggregator,
        scoring_engine=scoring_engine,
        recommendation_engine=recommendation_engine,
    )
    builder: StateGraph = StateGraph(ScreeningState)
    builder.add_node("evaluate", nodes.evaluate)
    builder.add_node("extract", nodes.extract)
    builder.add_node("resolve", nodes.resolve)
    builder.add_node("analyze", nodes.analyze)
    builder.add_node("aggregate", nodes.aggregate)
    builder.add_node("score", nodes.score)
    builder.add_node("recommend", nodes.recommend)
    builder.add_edge(START, "evaluate")
    builder.add_conditional_edges(
        "evaluate",
        nodes.has_accepted_articles,
        {"extract": "extract", "aggregate": "aggregate"},
    )
    builder.add_edge("extract", "resolve")
    builder.add_edge("resolve", "analyze")
    builder.add_edge("analyze", "aggregate")
    builder.add_edge("aggregate", "score")
    builder.add_edge("score", "recommend")
    builder.add_edge("recommend", END)
    return builder.compile()
