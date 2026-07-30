from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

import pytest
from pydantic import ValidationError

from app.aggregators import EvidenceAggregator
from app.analyzers import ImpactAnalyzer
from app.evaluators import ArticleEvaluator
from app.extractors import NewsEventExtractor
from app.models import (
    DEFAULT_RECOMMENDATION_POLICY_CONFIG,
    Article,
    ArticleEvaluationResult,
    CompanyRelation,
    EventType,
    EvidenceAggregation,
    ExtractedCompany,
    ImpactAnalysis,
    LLMExtractionResult,
    LLMInferenceResult,
    NewsEvent,
    RecommendationResult,
    ResolvedNewsEvent,
    ResolvedDecisionType,
    TickerResolvedEvent,
    ScreeningDecision,
    ScreeningDecisionType,
    ScoringResult,
)
from app.recommenders import RecommendationEngine
from app.resolvers import DefaultResolvePolicy, TickerResolver
from app.scorers import ScoringEngine
from app.screeners import EventScreener
from app.cross_validators import CrossValidator
from app.models import CrossValidationCandidate, CrossValidationResult, CrossValidationStatus
from app.workflows import (
    ScreeningResult,
    ScreeningWorkflow,
    WorkflowContext,
    WorkflowStatistics,
)


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
                event_type=EventType.CORPORATE_EVENT,
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
            successful_batches=1 if articles else 0,
        )


class FakeResolver(TickerResolver):
    def __init__(self) -> None:
        self.calls: List[List[NewsEvent]] = []
        self.results: Optional[List[TickerResolvedEvent]] = None
        self.mode: Optional[str] = None

    def resolve(self, events: List[NewsEvent]) -> List[TickerResolvedEvent]:
        self.calls.append(events)
        if self.mode == "missing":
            return [TickerResolvedEvent(event=events[0], companies=())]
        if self.mode == "duplicate":
            return [
                TickerResolvedEvent(event=events[0], companies=()),
                TickerResolvedEvent(event=events[0], companies=()),
            ]
        if self.mode == "unknown":
            unknown: NewsEvent = NewsEvent.model_validate(events[0].model_dump())
            return [TickerResolvedEvent(event=unknown, companies=())]
        if self.results is not None:
            return self.results
        return [TickerResolvedEvent(event=event, companies=()) for event in events]


class FakeEventScreener(EventScreener):
    def __init__(
        self,
        decisions: Tuple[ScreeningDecisionType, ...] = (),
        returned_event_count: Optional[int] = None,
    ) -> None:
        self.decisions: Tuple[ScreeningDecisionType, ...] = decisions
        self.returned_event_count: Optional[int] = returned_event_count
        self.calls: List[Tuple[LLMInferenceResult, ...]] = []

    async def screen(
        self,
        inferences: Tuple[LLMInferenceResult, ...],
    ) -> Tuple[ScreeningDecision, ...]:
        self.calls.append(inferences)
        events: Tuple[NewsEvent, ...] = tuple(
            event for inference in inferences for event in inference.events
        )
        if self.returned_event_count is not None:
            events = events[: self.returned_event_count]
        return tuple(
            ScreeningDecision(
                event=event,
                decision=self.decisions[index]
                if index < len(self.decisions)
                else ScreeningDecisionType.ACCEPT,
                relevance=80,
                importance=80,
                credibility=80,
                requires_cross_validation=False,
                reasons=("Screened by fake policy",),
            )
            for index, event in enumerate(events)
        )


class FakeAnalyzer(ImpactAnalyzer):
    def __init__(self) -> None:
        self.calls: List[List[ResolvedNewsEvent]] = []

    def analyze(self, events: List[ResolvedNewsEvent]) -> List[ImpactAnalysis]:
        self.calls.append(events)
        return []


class FakeCrossValidator(CrossValidator):
    def __init__(self) -> None:
        self.calls: List[Tuple[CrossValidationCandidate, ...]] = []
        self.statuses: Tuple[CrossValidationStatus, ...] = ()
        self.mode: Optional[str] = None

    async def validate(
        self, candidates: Tuple[CrossValidationCandidate, ...]
    ) -> Tuple[CrossValidationResult, ...]:
        self.calls.append(candidates)
        if self.mode == "duplicate":
            event: NewsEvent = candidates[0].decision.event
            return (
                CrossValidationResult(event=event, status=CrossValidationStatus.VERIFIED, confidence=70, independent_source_count=2, evidence=(), reasons=("Verified.",)),
                CrossValidationResult(event=event, status=CrossValidationStatus.VERIFIED, confidence=70, independent_source_count=2, evidence=(), reasons=("Verified.",)),
            )
        if self.mode == "unknown":
            event = NewsEvent.model_validate(candidates[0].decision.event.model_dump())
            return (
                CrossValidationResult(event=event, status=CrossValidationStatus.VERIFIED, confidence=70, independent_source_count=2, evidence=(), reasons=("Verified.",)),
            )
        return tuple(
            CrossValidationResult(
                event=candidate.decision.event,
                status=self.statuses[index]
                if index < len(self.statuses)
                else CrossValidationStatus.INSUFFICIENT_EVIDENCE,
                confidence=0,
                independent_source_count=0,
                evidence=(),
                reasons=("No related articles are available.",),
            )
            for index, candidate in enumerate(candidates)
        )


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
        return ScoringResult(policy_version="test-v1", companies=())


class FakeRecommendationEngine(RecommendationEngine):
    def __init__(self) -> None:
        self.calls: List[ScoringResult] = []
        self.result: RecommendationResult = RecommendationResult(
            policy_version=DEFAULT_RECOMMENDATION_POLICY_CONFIG.policy_version,
            decisions=(),
        )

    def recommend(self, scoring: ScoringResult) -> RecommendationResult:
        self.calls.append(scoring)
        return self.result


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
    decisions: Tuple[ScreeningDecisionType, ...] = (),
    returned_event_count: Optional[int] = None,
) -> tuple[
    ScreeningWorkflow,
    FakeArticleEvaluator,
    FakeExtractor,
    FakeEventScreener,
    FakeCrossValidator,
    FakeResolver,
    FakeAnalyzer,
    FakeAggregator,
    FakeScoringEngine,
    FakeRecommendationEngine,
]:
    evaluator: FakeArticleEvaluator = FakeArticleEvaluator(accepted_ids)
    extractor: FakeExtractor = FakeExtractor(extractor_error)
    screener: FakeEventScreener = FakeEventScreener(decisions, returned_event_count)
    cross_validator: FakeCrossValidator = FakeCrossValidator()
    resolver: FakeResolver = FakeResolver()
    analyzer: FakeAnalyzer = FakeAnalyzer()
    aggregator: FakeAggregator = FakeAggregator()
    scorer: FakeScoringEngine = FakeScoringEngine()
    recommender: FakeRecommendationEngine = FakeRecommendationEngine()
    workflow: ScreeningWorkflow = ScreeningWorkflow(
        evaluator=evaluator,
        extractor=extractor,
        screener=screener,
        cross_validator=cross_validator,
        resolver=resolver,
        resolve_policy=DefaultResolvePolicy(),
        impact_analyzer=analyzer,
        evidence_aggregator=aggregator,
        scoring_engine=scorer,
        recommendation_engine=recommender,
    )
    return (
        workflow,
        evaluator,
        extractor,
        screener,
        cross_validator,
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
    workflow, evaluator, extractor, screener, cross_validator, resolver, analyzer, aggregator, scorer, recommender = (
        build_workflow(("article-1", "article-2"))
    )

    result = await workflow.run(articles, context=WorkflowContext())

    assert evaluator.calls == [articles]
    assert extractor.calls == [articles]
    assert screener.calls[0][0].events[0] is extractor.events[0]
    assert cross_validator.calls == []
    assert resolver.calls[0] == extractor.events
    assert resolver.calls[0][0] is extractor.events[0]
    assert analyzer.calls[0][0].event is extractor.events[0]
    assert len(aggregator.calls) == len(scorer.calls) == len(recommender.calls) == 1
    assert result.recommendation is recommender.result
    assert result.statistics.total_articles == 2
    assert result.statistics.accepted_articles == 2
    assert result.statistics.rejected_articles == 0
    assert result.statistics.extracted_events == 2
    assert result.statistics.successful_batches == 1
    assert result.decisions[0].event is extractor.events[0]
    assert result.statistics.accepted_events == 2
    assert result.statistics.review_events == 0
    assert result.statistics.rejected_events == 0


@pytest.mark.anyio
async def test_workflow_skips_llm_for_empty_or_all_rejected_input() -> None:
    article: Article = build_article(1)
    workflow, _, extractor, screener, _, resolver, analyzer, aggregator, scorer, recommender = (
        build_workflow(())
    )

    result = await workflow.run((article,))

    assert extractor.calls == []
    assert screener.calls == []
    assert resolver.calls == []
    assert analyzer.calls == []
    assert aggregator.calls == [[]]
    assert len(scorer.calls) == len(recommender.calls) == 1
    assert result.recommendation.companies == ()
    assert result.statistics.rejected_articles == 1
    assert result.statistics.extracted_events == 0
    assert result.statistics.successful_batches == 0


@pytest.mark.anyio
async def test_workflow_handles_empty_input_as_a_normal_empty_result() -> None:
    workflow, _, extractor, screener, _, _, _, aggregator, _, _ = build_workflow(())

    result = await workflow.run(())

    assert extractor.calls == []
    assert screener.calls == []
    assert aggregator.calls == [[]]
    assert result.recommendation.companies == ()
    assert result.statistics.total_articles == 0
    assert result.statistics.successful_batches == 0


@pytest.mark.anyio
async def test_workflow_accepts_none_or_an_immutable_context() -> None:
    workflow, _, _, _, _, _, _, _, _, _ = build_workflow(())
    context: WorkflowContext = WorkflowContext()

    none_result = await workflow.run((), context=None)
    supplied_result = await workflow.run((), context=context)

    assert none_result.recommendation.companies == ()
    assert supplied_result.recommendation.companies == ()
    assert context == WorkflowContext()


@pytest.mark.anyio
async def test_workflow_propagates_extractor_error_without_wrapping() -> None:
    expected_error: RuntimeError = RuntimeError("LLM failed")
    workflow, _, extractor, _, _, _, _, _, _, _ = build_workflow(
        ("article-1",),
        extractor_error=expected_error,
    )

    with pytest.raises(RuntimeError) as error_info:
        await workflow.run((build_article(1),))

    assert error_info.value is expected_error
    assert len(extractor.calls) == 1


@pytest.mark.anyio
async def test_workflow_records_rejection_without_removing_downstream_event() -> None:
    article: Article = build_article(1)
    workflow, _, extractor, _, _, resolver, _, _, _, _ = build_workflow(
        ("article-1",),
        decisions=(ScreeningDecisionType.REJECT,),
    )

    result = await workflow.run((article,))

    assert result.decisions[0].decision is ScreeningDecisionType.REJECT
    assert resolver.calls[0][0] is extractor.events[0]
    assert result.statistics.accepted_events == 0
    assert result.statistics.review_events == 0
    assert result.statistics.rejected_events == 1
    assert (
        result.statistics.accepted_events
        + result.statistics.review_events
        + result.statistics.rejected_events
        == len(result.decisions)
    )


@pytest.mark.anyio
async def test_workflow_cross_validates_only_review_events_with_article_context() -> None:
    articles: Tuple[Article, ...] = (build_article(1), build_article(2), build_article(3))
    workflow, _, extractor, _, cross_validator, resolver, _, _, _, _ = build_workflow(
        ("article-1", "article-2", "article-3"),
        decisions=(
            ScreeningDecisionType.ACCEPT,
            ScreeningDecisionType.REVIEW,
            ScreeningDecisionType.REJECT,
        ),
    )

    result: ScreeningResult = await workflow.run(articles)

    assert len(cross_validator.calls) == 1
    candidates: Tuple[CrossValidationCandidate, ...] = cross_validator.calls[0]
    assert len(candidates) == 1
    assert candidates[0].decision.event is extractor.events[1]
    assert candidates[0].source_article is articles[1]
    assert tuple(article.id for article in candidates[0].related_articles) == (
        "article-1",
        "article-3",
    )
    assert result.cross_validation_results[0].event is extractor.events[1]
    assert result.statistics.insufficient_evidence_events == 1
    assert result.statistics.verified_events == 0
    assert resolver.calls[0] == extractor.events


@pytest.mark.anyio
async def test_workflow_allows_screener_partial_decisions() -> None:
    articles: Tuple[Article, ...] = (build_article(1), build_article(2))
    workflow, _, extractor, _, cross_validator, resolver, _, _, _, _ = build_workflow(
        ("article-1", "article-2"),
        decisions=(ScreeningDecisionType.REVIEW,),
        returned_event_count=1,
    )

    result: ScreeningResult = await workflow.run(articles)

    assert len(result.decisions) == 1
    assert result.decisions[0].event is extractor.events[0]
    assert len(cross_validator.calls) == 1
    assert cross_validator.calls[0][0].decision.event is extractor.events[0]
    assert resolver.calls[0] == [extractor.events[0]]
    assert "screening_errors" not in result.model_dump()


@pytest.mark.anyio
async def test_workflow_applies_verified_cross_validation_to_final_resolve_decision() -> None:
    articles: Tuple[Article, ...] = (build_article(1), build_article(2))
    workflow, _, extractor, _, cross_validator, _, analyzer, _, _, _ = build_workflow(
        ("article-1", "article-2"), decisions=(ScreeningDecisionType.REVIEW, ScreeningDecisionType.ACCEPT)
    )
    cross_validator.statuses = (CrossValidationStatus.VERIFIED,)

    result: ScreeningResult = await workflow.run(articles)

    assert result.resolved_events[0].event is extractor.events[0]
    assert result.resolved_events[0].decision is ResolvedDecisionType.ACCEPT
    assert result.resolved_events[1].decision is ResolvedDecisionType.ACCEPT
    assert result.statistics.resolved_accept_count == 2
    assert analyzer.calls[0] == list(result.resolved_events)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("mode", "message"),
    (
        ("missing", "No ticker snapshot"),
        ("duplicate", "Multiple ticker snapshots"),
        ("unknown", "ticker snapshot references an Event object"),
    ),
)
async def test_workflow_rejects_invalid_ticker_result_identity_contract(
    mode: str,
    message: str,
) -> None:
    articles: Tuple[Article, ...] = (build_article(1), build_article(2))
    workflow, _, extractor, _, _, resolver, _, _, _, _ = build_workflow(
        ("article-1", "article-2")
    )
    resolver.mode = mode
    with pytest.raises(ValueError, match=message):
        await workflow.run(articles)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("mode", "message"),
    (
        ("duplicate", "Multiple cross-validation results"),
        ("unknown", "cross-validation result references an Event object"),
    ),
)
async def test_workflow_rejects_invalid_cross_validation_identity_contract(
    mode: str,
    message: str,
) -> None:
    articles: Tuple[Article, ...] = (build_article(1), build_article(2))
    workflow, _, _, _, cross_validator, _, _, _, _, _ = build_workflow(
        ("article-1", "article-2"),
        decisions=(ScreeningDecisionType.REVIEW, ScreeningDecisionType.ACCEPT),
    )
    cross_validator.mode = mode

    with pytest.raises(ValueError, match=message):
        await workflow.run(articles)


@pytest.mark.anyio
async def test_workflow_calculates_statistics_from_mixed_final_decisions() -> None:
    articles: Tuple[Article, ...] = (
        build_article(1),
        build_article(2),
        build_article(3),
    )
    workflow, _, _, _, _, _, _, _, _, _ = build_workflow(
        ("article-1", "article-2", "article-3"),
        decisions=(
            ScreeningDecisionType.ACCEPT,
            ScreeningDecisionType.REVIEW,
            ScreeningDecisionType.REJECT,
        ),
    )

    result = await workflow.run(articles)

    assert result.statistics.accepted_events == 1
    assert result.statistics.review_events == 1
    assert result.statistics.rejected_events == 1
    assert len(result.decisions) == 3


@pytest.mark.anyio
async def test_screening_result_rejects_statistics_that_do_not_match_decisions() -> None:
    article: Article = build_article(1)
    workflow, _, _, _, _, _, _, _, _, _ = build_workflow(("article-1",))
    result = await workflow.run((article,))

    with pytest.raises(ValidationError):
        ScreeningResult(
            recommendation=result.recommendation,
            decisions=result.decisions,
            statistics=WorkflowStatistics(
                total_articles=1,
                accepted_articles=1,
                rejected_articles=0,
                extracted_events=1,
                successful_batches=1,
                accepted_events=0,
                review_events=0,
                rejected_events=0,
            ),
        )
