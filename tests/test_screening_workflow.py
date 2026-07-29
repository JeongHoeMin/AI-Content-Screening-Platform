from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Mapping, Optional, Tuple

import pytest

from app.aggregators import EvidenceAggregator
from app.analyzers import ImpactAnalyzer
from app.evaluators import ArticleEvaluator
from app.extractors import NewsEventExtractor
from app.models import (
    Article,
    ArticleEvaluationResult,
    CompanyRelation,
    EvidenceAggregation,
    ExtractedCompany,
    ImpactAnalysis,
    LLMExtractionResult,
    LLMInferenceResult,
    NewsEvent,
    RecommendationResult,
    ResolvedNewsEvent,
    ScoringResult,
)
from app.recommenders import RecommendationEngine
from app.resolvers import TickerResolver
from app.scorers import ScoringEngine
from app.workflows import ScreeningWorkflow, WorkflowContext


class FakeArticleEvaluator(ArticleEvaluator):
    def __init__(self, accepted_ids: Tuple[str, ...]) -> None:
        self.accepted_ids: Tuple[str, ...] = accepted_ids
        self.calls: List[Tuple[Article, ...]] = []

    def evaluate(
        self,
        articles: Tuple[Article, ...],
    ) -> Tuple[ArticleEvaluationResult, ...]:
        self.calls.append(articles)
        return tuple(
            ArticleEvaluationResult(
                article=article,
                accepted=article.id in self.accepted_ids,
                rejection_reason=None
                if article.id in self.accepted_ids
                else "body_too_short",
            )
            for article in articles
        )


class FakeExtractor(NewsEventExtractor):
    def __init__(self, error: Optional[Exception] = None) -> None:
        self.error: Optional[Exception] = error
        self.calls: List[Tuple[Article, ...]] = []
        self.events: List[NewsEvent] = []

    async def extract(
        self,
        articles: Tuple[Article, ...],
    ) -> LLMExtractionResult:
        self.calls.append(articles)
        if self.error is not None:
            raise self.error
        inferences: List[LLMInferenceResult] = []
        for article in articles:
            event: NewsEvent = NewsEvent(
                title=f"Event {article.id}",
                summary="Event summary",
                companies=[
                    ExtractedCompany(
                        name="Samsung Electronics",
                        relation=CompanyRelation.DIRECT,
                    )
                ],
                industries=["Semiconductors"],
                keywords=["HBM"],
                reasons=["Explicit source fact"],
            )
            self.events.append(event)
            inferences.append(
                LLMInferenceResult(
                    article=article,
                    events=(event,),
                    summary="Article summary",
                    reasoning="The event is explicitly stated.",
                    confidence=0.9,
                )
            )
        return LLMExtractionResult(
            inferences=tuple(inferences),
            llm_requests=1 if articles else 0,
        )


class FakeResolver(TickerResolver):
    def __init__(self) -> None:
        self.calls: List[List[NewsEvent]] = []

    def resolve(self, events: List[NewsEvent]) -> List[ResolvedNewsEvent]:
        self.calls.append(events)
        return [ResolvedNewsEvent(event=event, companies=()) for event in events]


class FakeAnalyzer(ImpactAnalyzer):
    def __init__(self) -> None:
        self.calls: List[List[ResolvedNewsEvent]] = []

    def analyze(self, events: List[ResolvedNewsEvent]) -> List[ImpactAnalysis]:
        self.calls.append(events)
        return []


class FakeAggregator(EvidenceAggregator):
    def __init__(self) -> None:
        self.calls: List[List[ImpactAnalysis]] = []

    def aggregate(self, analyses: List[ImpactAnalysis]) -> EvidenceAggregation:
        self.calls.append(analyses)
        return EvidenceAggregation(companies=())


class FakeScoringEngine(ScoringEngine):
    def __init__(self) -> None:
        self.calls: List[EvidenceAggregation] = []

    def score(self, aggregation: EvidenceAggregation) -> ScoringResult:
        self.calls.append(aggregation)
        return ScoringResult(companies=())


class FakeRecommendationEngine(RecommendationEngine):
    def __init__(self) -> None:
        self.calls: List[ScoringResult] = []
        self.result: RecommendationResult = RecommendationResult(companies=())

    def recommend(self, scoring: ScoringResult) -> RecommendationResult:
        self.calls.append(scoring)
        return self.result


class CapturingGraph:
    def __init__(
        self,
        recommendation: RecommendationResult,
        statistics: object,
    ) -> None:
        self.recommendation: RecommendationResult = recommendation
        self.statistics: object = statistics
        self.states: List[Mapping[str, object]] = []

    async def ainvoke(self, state: Mapping[str, object]) -> Mapping[str, object]:
        self.states.append(state)
        return {
            "recommendation": self.recommendation,
            "statistics": self.statistics,
        }


def build_article(index: int) -> Article:
    return Article(
        id=f"article-{index}",
        title=f"Title {index}",
        content="content " * 50,
        source="Example News",
        published_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        url=f"https://example.com/articles/{index}",
    )


def build_workflow(
    accepted_ids: Tuple[str, ...],
    extractor_error: Optional[Exception] = None,
) -> tuple[
    ScreeningWorkflow,
    FakeArticleEvaluator,
    FakeExtractor,
    FakeResolver,
    FakeAnalyzer,
    FakeAggregator,
    FakeScoringEngine,
    FakeRecommendationEngine,
]:
    evaluator: FakeArticleEvaluator = FakeArticleEvaluator(accepted_ids)
    extractor: FakeExtractor = FakeExtractor(extractor_error)
    resolver: FakeResolver = FakeResolver()
    analyzer: FakeAnalyzer = FakeAnalyzer()
    aggregator: FakeAggregator = FakeAggregator()
    scorer: FakeScoringEngine = FakeScoringEngine()
    recommender: FakeRecommendationEngine = FakeRecommendationEngine()
    workflow: ScreeningWorkflow = ScreeningWorkflow(
        evaluator=evaluator,
        extractor=extractor,
        resolver=resolver,
        impact_analyzer=analyzer,
        evidence_aggregator=aggregator,
        scoring_engine=scorer,
        recommendation_engine=recommender,
    )
    return (
        workflow,
        evaluator,
        extractor,
        resolver,
        analyzer,
        aggregator,
        scorer,
        recommender,
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_workflow_runs_in_order_and_preserves_event_identity() -> None:
    articles: Tuple[Article, ...] = (build_article(1), build_article(2))
    workflow, evaluator, extractor, resolver, analyzer, aggregator, scorer, recommender = (
        build_workflow(("article-1", "article-2"))
    )

    result = await workflow.run(articles, context=WorkflowContext())

    assert evaluator.calls == [articles]
    assert extractor.calls == [articles]
    assert resolver.calls[0] == extractor.events
    assert resolver.calls[0][0] is extractor.events[0]
    assert analyzer.calls[0][0].event is extractor.events[0]
    assert len(aggregator.calls) == len(scorer.calls) == len(recommender.calls) == 1
    assert result.recommendation is recommender.result
    assert result.statistics.total_articles == 2
    assert result.statistics.accepted_articles == 2
    assert result.statistics.rejected_articles == 0
    assert result.statistics.extracted_events == 2
    assert result.statistics.llm_requests == 1


@pytest.mark.anyio
async def test_workflow_skips_llm_for_empty_or_all_rejected_input() -> None:
    article: Article = build_article(1)
    workflow, _, extractor, resolver, analyzer, aggregator, scorer, recommender = (
        build_workflow(())
    )

    result = await workflow.run((article,))

    assert extractor.calls == []
    assert resolver.calls == []
    assert analyzer.calls == []
    assert aggregator.calls == [[]]
    assert len(scorer.calls) == len(recommender.calls) == 1
    assert result.recommendation.companies == ()
    assert result.statistics.rejected_articles == 1
    assert result.statistics.extracted_events == 0
    assert result.statistics.llm_requests == 0


@pytest.mark.anyio
async def test_workflow_handles_empty_input_as_a_normal_empty_result() -> None:
    workflow, _, extractor, _, _, aggregator, _, _ = build_workflow(())

    result = await workflow.run(())

    assert extractor.calls == []
    assert aggregator.calls == [[]]
    assert result.recommendation.companies == ()
    assert result.statistics.total_articles == 0
    assert result.statistics.llm_requests == 0


@pytest.mark.anyio
async def test_workflow_accepts_none_or_an_immutable_context() -> None:
    workflow, _, _, _, _, _, _, recommender = build_workflow(())
    context: WorkflowContext = WorkflowContext()
    statistics = await workflow.run((), context=None)
    graph: CapturingGraph = CapturingGraph(
        recommendation=recommender.result,
        statistics=statistics.statistics,
    )
    workflow._graph = graph  # type: ignore[assignment]

    none_result = await workflow.run((), context=None)
    supplied_result = await workflow.run((), context=context)

    assert none_result.recommendation.companies == ()
    assert supplied_result.recommendation.companies == ()
    assert graph.states[0]["context"] is not None
    assert graph.states[1]["context"] is context
    assert context == WorkflowContext()


@pytest.mark.anyio
async def test_workflow_propagates_extractor_error_without_wrapping() -> None:
    expected_error: RuntimeError = RuntimeError("LLM failed")
    workflow, _, extractor, _, _, _, _, _ = build_workflow(
        ("article-1",),
        extractor_error=expected_error,
    )

    with pytest.raises(RuntimeError) as error_info:
        await workflow.run((build_article(1),))

    assert error_info.value is expected_error
    assert len(extractor.calls) == 1
