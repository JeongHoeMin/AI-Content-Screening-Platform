from __future__ import annotations

from typing import List, Optional

import pytest

from app.models import (
    DEFAULT_RECOMMENDATION_POLICY_CONFIG,
    CompanyRelation,
    CompanyScore,
    RecommendationResult,
    ResolvedCompany,
    ResolvedTicker,
    ScoringResult,
)
from app.recommenders import DefaultRecommendationEngine, RecommendationEngine, RecommendationPolicy, RuleRecommendationPolicy


class FakeRecommendationPolicy(RecommendationPolicy):
    def __init__(self, result: RecommendationResult, error: Optional[Exception] = None) -> None:
        self.result: RecommendationResult = result
        self.error: Optional[Exception] = error
        self.calls: List[ScoringResult] = []

    def recommend(self, scoring: ScoringResult) -> RecommendationResult:
        self.calls.append(scoring)
        if self.error is not None:
            raise self.error
        return self.result


def build_scoring() -> ScoringResult:
    company = ResolvedCompany(
        name="Samsung Electronics",
        relation=CompanyRelation.DIRECT,
        ticker=ResolvedTicker(ticker="005930", exchange="KRX"),
    )
    return ScoringResult(
        policy_version="score-v1",
        companies=(CompanyScore(company=company, score=0.0, contributions=()),),
    )


def build_result(scoring: ScoringResult) -> RecommendationResult:
    return RuleRecommendationPolicy(DEFAULT_RECOMMENDATION_POLICY_CONFIG).recommend(scoring)


def test_engine_returns_exact_policy_result_once() -> None:
    scoring = build_scoring()
    expected = build_result(scoring)
    policy = FakeRecommendationPolicy(expected)
    engine: RecommendationEngine = DefaultRecommendationEngine(policy)

    assert engine.recommend(scoring) is expected
    assert policy.calls == [scoring]


def test_engine_propagates_policy_error_without_wrapping() -> None:
    scoring = build_scoring()
    expected_error = RuntimeError("recommendation failed")
    policy = FakeRecommendationPolicy(build_result(scoring), error=expected_error)

    with pytest.raises(RuntimeError) as error_info:
        DefaultRecommendationEngine(policy).recommend(scoring)

    assert error_info.value is expected_error
    assert policy.calls == [scoring]
