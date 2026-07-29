from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from app.aggregators import DefaultAggregationStrategy, DefaultEvidenceAggregator
from app.analyzers import DefaultImpactAnalyzer, RuleImpactStrategy
from app.cross_validators import DefaultCrossValidationPolicy
from app.evaluators import RuleArticleEvaluator, RuleArticleEvaluatorConfig
from app.mock_screening import (
    DeterministicMockCrossValidator,
    DeterministicMockExtractor,
    DeterministicMockScreener,
)
from app.recommenders import DefaultRecommendationEngine, RuleRecommendationPolicy
from app.resolvers import DefaultResolvePolicy, DefaultTickerResolver, StaticTickerLookup
from app.scorers import DefaultScoringEngine, RuleScoringStrategy
from app.screeners import DefaultScreeningPolicy
from app.workflows import ScreeningWorkflow


class ExecutionMode(str, Enum):
    MOCK = "mock"


WorkflowFactory = Callable[[], ScreeningWorkflow]


def create_screening_workflow(
    mode: ExecutionMode = ExecutionMode.MOCK,
) -> ScreeningWorkflow:
    factory: WorkflowFactory | None = _WORKFLOW_FACTORIES.get(mode)
    if factory is None:
        mode_name: str = mode.value if isinstance(mode, ExecutionMode) else repr(mode)
        raise ValueError(f"Unsupported execution mode: {mode_name}")
    return factory()


def _create_mock_workflow() -> ScreeningWorkflow:
    screening_policy: DefaultScreeningPolicy = DefaultScreeningPolicy()
    cross_validation_policy: DefaultCrossValidationPolicy = (
        DefaultCrossValidationPolicy()
    )
    return ScreeningWorkflow(
        evaluator=RuleArticleEvaluator(RuleArticleEvaluatorConfig()),
        extractor=DeterministicMockExtractor(),
        screener=DeterministicMockScreener(screening_policy),
        cross_validator=DeterministicMockCrossValidator(cross_validation_policy),
        resolver=DefaultTickerResolver(StaticTickerLookup({})),
        resolve_policy=DefaultResolvePolicy(),
        impact_analyzer=DefaultImpactAnalyzer(RuleImpactStrategy()),
        evidence_aggregator=DefaultEvidenceAggregator(DefaultAggregationStrategy()),
        scoring_engine=DefaultScoringEngine(RuleScoringStrategy()),
        recommendation_engine=DefaultRecommendationEngine(RuleRecommendationPolicy()),
    )


_WORKFLOW_FACTORIES: dict[ExecutionMode, WorkflowFactory] = {
    ExecutionMode.MOCK: _create_mock_workflow,
}
