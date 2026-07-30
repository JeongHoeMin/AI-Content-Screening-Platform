from __future__ import annotations

from typing import Tuple

import pytest

from app.models import (
    CompanyRecommendation,
    CompanyRelation,
    CompanyScore,
    CompanyImpact,
    ImpactDirection,
    Recommendation,
    ScoreContribution,
    ScoreFactor,
    ScoreReasonCode,
    ResolvedCompany,
    ResolvedTicker,
    ScoringResult,
)
from app.recommenders import RecommendationPolicy, RuleRecommendationPolicy


def build_company(index: int) -> ResolvedCompany:
    return ResolvedCompany(
        name=f"Company {index}",
        relation=CompanyRelation.DIRECT,
        ticker=ResolvedTicker(ticker=f"0000{index}", exchange="KRX"),
    )


def build_score(index: int, value: float) -> CompanyScore:
    company: ResolvedCompany = build_company(index)
    if value == 0.0:
        return CompanyScore(company=company, score=0.0, contributions=())
    direction: ImpactDirection = (
        ImpactDirection.POSITIVE if value > 0.0 else ImpactDirection.NEGATIVE
    )
    contribution: ScoreContribution = ScoreContribution(
        impact=CompanyImpact(company=company, direction=direction),
        factor=(ScoreFactor.POSITIVE_EVIDENCE if value > 0.0 else ScoreFactor.NEGATIVE_EVIDENCE),
        weight=value,
        value=value,
        reason_code=(ScoreReasonCode.POSITIVE_DIRECTION_WEIGHT if value > 0.0 else ScoreReasonCode.NEGATIVE_DIRECTION_WEIGHT),
    )
    return CompanyScore(
        company=company,
        score=value,
        contributions=(contribution,),
    )


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (3.0, Recommendation.STRONG_BUY),
        (2.0, Recommendation.STRONG_BUY),
        (1.0, Recommendation.BUY),
        (0.5, Recommendation.HOLD),
        (0.0, Recommendation.HOLD),
        (-0.5, Recommendation.HOLD),
        (-1.0, Recommendation.SELL),
        (-1.5, Recommendation.SELL),
        (-2.0, Recommendation.STRONG_SELL),
        (-3.0, Recommendation.STRONG_SELL),
    ],
)
def test_rule_policy_applies_current_score_policy(
    score: float,
    expected: Recommendation,
) -> None:
    company_score: CompanyScore = build_score(1, score)
    scoring: ScoringResult = ScoringResult(policy_version="test-v1", companies=(company_score,))
    policy: RecommendationPolicy = RuleRecommendationPolicy()

    result: Tuple[CompanyRecommendation, ...] = policy.recommend(scoring)

    assert result[0].recommendation is expected
    assert result[0].score is company_score


def test_rule_policy_uses_the_first_matching_rule() -> None:
    company_score: CompanyScore = build_score(1, 3.0)
    scoring: ScoringResult = ScoringResult(policy_version="test-v1", companies=(company_score,))
    policy: RuleRecommendationPolicy = RuleRecommendationPolicy()

    result: Tuple[CompanyRecommendation, ...] = policy.recommend(scoring)

    assert result[0].recommendation is Recommendation.STRONG_BUY


def test_rule_policy_preserves_score_order_identity_and_cardinality() -> None:
    first_score: CompanyScore = build_score(1, 1.0)
    second_score: CompanyScore = build_score(2, -1.0)
    third_score: CompanyScore = build_score(3, 1.0)
    scoring: ScoringResult = ScoringResult(policy_version="test-v1",
        companies=(first_score, second_score, third_score)
    )
    policy: RuleRecommendationPolicy = RuleRecommendationPolicy()

    result: Tuple[CompanyRecommendation, ...] = policy.recommend(scoring)

    assert len(result) == len(scoring.companies)
    assert tuple(recommendation.score for recommendation in result) == scoring.companies
    assert all(
        recommendation.score is scoring.companies[index]
        for index, recommendation in enumerate(result)
    )


def test_rule_policy_handles_empty_scoring_result() -> None:
    scoring: ScoringResult = ScoringResult(policy_version="test-v1", companies=())
    policy: RuleRecommendationPolicy = RuleRecommendationPolicy()

    result: Tuple[CompanyRecommendation, ...] = policy.recommend(scoring)

    assert result == ()


def test_rule_policy_is_deterministic_and_does_not_mutate_scores() -> None:
    company_score: CompanyScore = build_score(1, -1.5)
    scoring: ScoringResult = ScoringResult(policy_version="test-v1", companies=(company_score,))
    companies_snapshot: Tuple[CompanyScore, ...] = scoring.companies
    policy: RuleRecommendationPolicy = RuleRecommendationPolicy()

    first_result: Tuple[CompanyRecommendation, ...] = policy.recommend(scoring)
    second_result: Tuple[CompanyRecommendation, ...] = policy.recommend(scoring)

    assert first_result == second_result
    assert scoring.companies is companies_snapshot
    assert scoring.companies[0] is company_score
