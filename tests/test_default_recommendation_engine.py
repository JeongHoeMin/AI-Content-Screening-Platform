from __future__ import annotations

from typing import List, Optional, Tuple

import pytest

from app.models import (
    CompanyRecommendation,
    CompanyRelation,
    CompanyScore,
    Recommendation,
    RecommendationResult,
    ResolvedCompany,
    ResolvedTicker,
    ScoringResult,
)
from app.recommenders import (
    DefaultRecommendationEngine,
    RecommendationEngine,
    RecommendationPolicy,
)


class FakeRecommendationPolicy(RecommendationPolicy):
    def __init__(
        self,
        companies: Tuple[CompanyRecommendation, ...],
        error: Optional[Exception] = None,
    ) -> None:
        self.companies: Tuple[CompanyRecommendation, ...] = companies
        self.error: Optional[Exception] = error
        self.calls: List[ScoringResult] = []

    def recommend(
        self,
        scoring: ScoringResult,
    ) -> Tuple[CompanyRecommendation, ...]:
        self.calls.append(scoring)
        if self.error is not None:
            raise self.error
        return self.companies


def build_scoring() -> ScoringResult:
    company: ResolvedCompany = ResolvedCompany(
        name="Samsung Electronics",
        relation=CompanyRelation.DIRECT,
        ticker=ResolvedTicker(ticker="005930", exchange="KRX"),
    )
    score: CompanyScore = CompanyScore(company=company, score=1.0, evidences=())
    return ScoringResult(companies=(score,))


def build_recommendations(
    scoring: ScoringResult,
) -> Tuple[CompanyRecommendation, ...]:
    return (
        CompanyRecommendation(
            score=scoring.companies[0],
            recommendation=Recommendation.BUY,
        ),
    )


def test_constructor_stores_policy_without_side_effects() -> None:
    scoring: ScoringResult = build_scoring()
    policy: FakeRecommendationPolicy = FakeRecommendationPolicy(
        build_recommendations(scoring)
    )

    engine: DefaultRecommendationEngine = DefaultRecommendationEngine(policy)

    assert engine._policy is policy
    assert policy.calls == []


def test_engine_preserves_policy_tuple_identity_without_copying() -> None:
    scoring: ScoringResult = build_scoring()
    companies: Tuple[CompanyRecommendation, ...] = build_recommendations(scoring)
    policy: FakeRecommendationPolicy = FakeRecommendationPolicy(companies)
    engine: RecommendationEngine = DefaultRecommendationEngine(policy)

    result: RecommendationResult = engine.recommend(scoring)

    assert result.companies is companies
    assert policy.calls == [scoring]


def test_engine_handles_empty_policy_result() -> None:
    scoring: ScoringResult = ScoringResult(companies=())
    policy: FakeRecommendationPolicy = FakeRecommendationPolicy(())
    engine: DefaultRecommendationEngine = DefaultRecommendationEngine(policy)

    result: RecommendationResult = engine.recommend(scoring)

    assert result.companies == ()
    assert policy.calls == [scoring]


def test_engine_propagates_policy_error_without_wrapping() -> None:
    scoring: ScoringResult = build_scoring()
    expected_error: RuntimeError = RuntimeError("recommendation failed")
    policy: FakeRecommendationPolicy = FakeRecommendationPolicy(
        companies=(),
        error=expected_error,
    )
    engine: DefaultRecommendationEngine = DefaultRecommendationEngine(policy)

    with pytest.raises(RuntimeError) as error_info:
        engine.recommend(scoring)

    assert error_info.value is expected_error
    assert policy.calls == [scoring]
