from __future__ import annotations

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


def create_screening_workflow(
    mode: ExecutionMode = ExecutionMode.MOCK,
) -> ScreeningWorkflow:
    if mode is ExecutionMode.MOCK:
        return _create_mock_workflow()
    raise ValueError(f"Unsupported execution mode: {mode}")


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
