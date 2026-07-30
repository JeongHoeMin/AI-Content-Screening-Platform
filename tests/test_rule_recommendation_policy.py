from __future__ import annotations

from math import inf, nan

import pytest
from pydantic import ValidationError

from app.models import (
    DEFAULT_RECOMMENDATION_POLICY_CONFIG,
    CompanyRelation,
    CompanyRecommendation,
    CompanyScore,
    CompanyImpact,
    ImpactDirection,
    RecommendationAction,
    RecommendationDecision,
    RecommendationPolicyConfig,
    RecommendationReasonCode,
    RecommendationThresholdSnapshot,
    ResolvedCompany,
    ResolvedTicker,
    ScoreContribution,
    ScoreFactor,
    ScoreReasonCode,
    ScoringResult,
)
from app.recommenders import RuleRecommendationPolicy


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
        factor=(
            ScoreFactor.POSITIVE_EVIDENCE
            if value > 0.0
            else ScoreFactor.NEGATIVE_EVIDENCE
        ),
        weight=value,
        value=value,
        reason_code=(
            ScoreReasonCode.POSITIVE_DIRECTION_WEIGHT
            if value > 0.0
            else ScoreReasonCode.NEGATIVE_DIRECTION_WEIGHT
        ),
    )
    return CompanyScore(company=company, score=value, contributions=(contribution,))


@pytest.mark.parametrize(
    ("score", "expected_action", "expected_reason"),
    [
        (3.0, RecommendationAction.STRONG_BUY, RecommendationReasonCode.SCORE_AT_OR_ABOVE_STRONG_BUY_THRESHOLD),
        (2.0, RecommendationAction.STRONG_BUY, RecommendationReasonCode.SCORE_AT_OR_ABOVE_STRONG_BUY_THRESHOLD),
        (1.0, RecommendationAction.BUY, RecommendationReasonCode.SCORE_AT_OR_ABOVE_BUY_THRESHOLD),
        (0.5, RecommendationAction.HOLD, RecommendationReasonCode.SCORE_WITHIN_HOLD_RANGE),
        (-1.0, RecommendationAction.SELL, RecommendationReasonCode.SCORE_AT_OR_BELOW_SELL_THRESHOLD),
        (-2.0, RecommendationAction.STRONG_SELL, RecommendationReasonCode.SCORE_AT_OR_BELOW_STRONG_SELL_THRESHOLD),
    ],
)
def test_rule_policy_preserves_actions_boundaries_and_reasons(
    score: float,
    expected_action: RecommendationAction,
    expected_reason: RecommendationReasonCode,
) -> None:
    company_score: CompanyScore = build_score(1, score)
    scoring: ScoringResult = ScoringResult(policy_version="score-v1", companies=(company_score,))

    result = RuleRecommendationPolicy().recommend(scoring)
    decision = result.decisions[0]

    assert decision.action is expected_action
    assert decision.reason_code is expected_reason
    assert decision.company_score is company_score
    assert decision.score == company_score.score
    assert decision.threshold_snapshot is DEFAULT_RECOMMENDATION_POLICY_CONFIG.threshold_snapshot
    assert result.policy_version == DEFAULT_RECOMMENDATION_POLICY_CONFIG.policy_version


def test_policy_preserves_order_identity_and_cardinality() -> None:
    scores = (build_score(1, 1.0), build_score(2, -1.0), build_score(3, 1.0))
    result = RuleRecommendationPolicy().recommend(
        ScoringResult(policy_version="score-v1", companies=scores)
    )

    assert len(result.decisions) == len(scores)
    assert result.companies is result.decisions
    assert CompanyRecommendation is RecommendationDecision
    assert all(isinstance(company, RecommendationDecision) for company in result.companies)
    assert all(
        decision.company_score is scores[index]
        for index, decision in enumerate(result.decisions)
    )


def test_policy_handles_empty_scoring_result() -> None:
    result = RuleRecommendationPolicy().recommend(
        ScoringResult(policy_version="score-v1", companies=())
    )

    assert result.decisions == ()


@pytest.mark.parametrize("value", (nan, inf, -inf))
def test_threshold_snapshot_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValidationError):
        RecommendationThresholdSnapshot(
            strong_buy_threshold=value,
            buy_threshold=1.0,
            sell_threshold=-1.0,
            strong_sell_threshold=-2.0,
        )


def test_threshold_snapshot_rejects_invalid_ordering() -> None:
    with pytest.raises(ValidationError):
        RecommendationThresholdSnapshot(
            strong_buy_threshold=1.0,
            buy_threshold=2.0,
            sell_threshold=-1.0,
            strong_sell_threshold=-2.0,
        )


def test_config_rejects_only_blank_policy_version() -> None:
    snapshot = RecommendationThresholdSnapshot(
        strong_buy_threshold=2.0,
        buy_threshold=1.0,
        sell_threshold=-1.0,
        strong_sell_threshold=-2.0,
    )
    assert RecommendationPolicyConfig(policy_version="v2", threshold_snapshot=snapshot).threshold_snapshot is snapshot
    with pytest.raises(ValidationError):
        RecommendationPolicyConfig(policy_version="  ", threshold_snapshot=snapshot)


def test_decision_rejects_action_reason_mismatch() -> None:
    score = build_score(1, 2.0)
    with pytest.raises(ValidationError):
        RecommendationDecision(
            company_score=score,
            action=RecommendationAction.BUY,
            reason_code=RecommendationReasonCode.SCORE_AT_OR_ABOVE_BUY_THRESHOLD,
            threshold_snapshot=DEFAULT_RECOMMENDATION_POLICY_CONFIG.threshold_snapshot,
        )
