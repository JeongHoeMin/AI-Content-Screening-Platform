from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Tuple

import pytest

from app.models import (
    CompanyRecommendation,
    CompanyRelation,
    CompanyScore,
    Recommendation,
    ResolvedCompany,
    ResolvedTicker,
    ScoringResult,
)
from app.recommenders import RecommendationPolicy, RuleRecommendationPolicy
from app.recommenders.rule_recommendation_policy import _RULES


def build_company(index: int) -> ResolvedCompany:
    return ResolvedCompany(
        name=f"Company {index}",
        relation=CompanyRelation.DIRECT,
        ticker=ResolvedTicker(ticker=f"0000{index}", exchange="KRX"),
    )


def build_score(index: int, value: float) -> CompanyScore:
    return CompanyScore(
        company=build_company(index),
        score=value,
        evidences=(),
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
    scoring: ScoringResult = ScoringResult(companies=(company_score,))
    policy: RecommendationPolicy = RuleRecommendationPolicy()

    result: Tuple[CompanyRecommendation, ...] = policy.recommend(scoring)

    assert result[0].recommendation is expected
    assert result[0].score is company_score


def test_rule_policy_uses_the_first_matching_rule() -> None:
    company_score: CompanyScore = build_score(1, 3.0)
    scoring: ScoringResult = ScoringResult(companies=(company_score,))
    policy: RuleRecommendationPolicy = RuleRecommendationPolicy()

    result: Tuple[CompanyRecommendation, ...] = policy.recommend(scoring)

    assert result[0].recommendation is Recommendation.STRONG_BUY


def test_rule_policy_preserves_score_order_identity_and_cardinality() -> None:
    first_score: CompanyScore = build_score(1, 1.0)
    second_score: CompanyScore = build_score(2, -1.0)
    third_score: CompanyScore = build_score(3, 1.0)
    scoring: ScoringResult = ScoringResult(
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
    scoring: ScoringResult = ScoringResult(companies=())
    policy: RuleRecommendationPolicy = RuleRecommendationPolicy()

    result: Tuple[CompanyRecommendation, ...] = policy.recommend(scoring)

    assert result == ()


def test_rule_policy_is_deterministic_and_does_not_mutate_scores() -> None:
    company_score: CompanyScore = build_score(1, -1.5)
    scoring: ScoringResult = ScoringResult(companies=(company_score,))
    companies_snapshot: Tuple[CompanyScore, ...] = scoring.companies
    policy: RuleRecommendationPolicy = RuleRecommendationPolicy()

    first_result: Tuple[CompanyRecommendation, ...] = policy.recommend(scoring)
    second_result: Tuple[CompanyRecommendation, ...] = policy.recommend(scoring)

    assert first_result == second_result
    assert scoring.companies is companies_snapshot
    assert scoring.companies[0] is company_score


def test_rule_policy_and_rules_are_immutable() -> None:
    policy: RuleRecommendationPolicy = RuleRecommendationPolicy()

    with pytest.raises(FrozenInstanceError):
        policy._rules = ()
    with pytest.raises(FrozenInstanceError):
        _RULES[0].recommendation = Recommendation.BUY
    with pytest.raises(TypeError):
        _RULES[0] = _RULES[1]
