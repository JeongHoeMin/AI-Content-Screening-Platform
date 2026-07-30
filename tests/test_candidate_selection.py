from __future__ import annotations

from typing import List, Optional, Tuple

import pytest
from pydantic import ValidationError

from app.candidates import (
    CandidateSelectionEngine,
    CandidateSelectionPolicy,
    DefaultCandidateSelectionEngine,
    RuleCandidateSelectionPolicy,
)
from app.models import (
    DEFAULT_RANKING_POLICY_CONFIG,
    DEFAULT_RECOMMENDATION_RANK_CATALOG,
    CandidateEvaluation,
    CandidateReasonCode,
    CandidateSelectionResult,
    CandidateStatus,
    CompanyImpact,
    CompanyRelation,
    CompanyScore,
    ImpactDirection,
    RankingPolicyConfig,
    RecommendationAction,
    RecommendationRankCatalog,
    RecommendationRankEntry,
    ResolvedCompany,
    ResolvedTicker,
    ScoreContribution,
    ScoreFactor,
    ScoreReasonCode,
    ScoringResult,
)
from app.recommenders import RuleRecommendationPolicy


def build_score(index: int, value: float) -> CompanyScore:
    company = ResolvedCompany(
        name=f"Company {index}",
        relation=CompanyRelation.DIRECT,
        ticker=ResolvedTicker(ticker=f"0000{index}", exchange="KRX"),
    )
    if value == 0.0:
        return CompanyScore(company=company, score=0.0, contributions=())
    direction = ImpactDirection.POSITIVE if value > 0.0 else ImpactDirection.NEGATIVE
    contribution = ScoreContribution(
        impact=CompanyImpact(company=company, direction=direction),
        factor=(ScoreFactor.POSITIVE_EVIDENCE if value > 0.0 else ScoreFactor.NEGATIVE_EVIDENCE),
        weight=value,
        value=value,
        reason_code=(ScoreReasonCode.POSITIVE_DIRECTION_WEIGHT if value > 0.0 else ScoreReasonCode.NEGATIVE_DIRECTION_WEIGHT),
    )
    return CompanyScore(company=company, score=value, contributions=(contribution,))


def build_recommendation(values: Tuple[float, ...]):
    scores = tuple(build_score(index, value) for index, value in enumerate(values))
    return RuleRecommendationPolicy().recommend(
        ScoringResult(policy_version="score-v1", companies=scores)
    )


def test_catalog_requires_complete_unique_actions_and_priorities() -> None:
    entries = DEFAULT_RECOMMENDATION_RANK_CATALOG.entries
    with pytest.raises(ValidationError):
        RecommendationRankCatalog(entries=entries[:-1])
    with pytest.raises(ValidationError):
        RecommendationRankCatalog(entries=entries + (entries[0],))
    with pytest.raises(ValidationError):
        RecommendationRankCatalog(
            entries=(
                RecommendationRankEntry(
                    action=RecommendationAction.STRONG_BUY,
                    eligible=True,
                    priority=0,
                ),
                RecommendationRankEntry(
                    action=RecommendationAction.BUY,
                    eligible=True,
                    priority=0,
                ),
                *entries[2:],
            )
        )
    with pytest.raises(ValidationError):
        RecommendationRankEntry(
            action=RecommendationAction.STRONG_BUY,
            eligible=True,
            priority=-1,
        )


def test_default_catalog_and_config_define_v1_ranking_policy() -> None:
    assert tuple(
        (entry.action, entry.eligible, entry.priority)
        for entry in DEFAULT_RECOMMENDATION_RANK_CATALOG.entries
    ) == (
        (RecommendationAction.STRONG_BUY, True, 0),
        (RecommendationAction.BUY, True, 1),
        (RecommendationAction.HOLD, False, 2),
        (RecommendationAction.SELL, False, 3),
        (RecommendationAction.STRONG_SELL, False, 4),
    )
    assert DEFAULT_RANKING_POLICY_CONFIG.max_candidates == 10


def test_config_rejects_blank_version_and_invalid_limit() -> None:
    with pytest.raises(ValidationError):
        RankingPolicyConfig(
            policy_version="  ",
            max_candidates=10,
            catalog=DEFAULT_RECOMMENDATION_RANK_CATALOG,
        )
    with pytest.raises(ValidationError):
        RankingPolicyConfig(
            policy_version="v1",
            max_candidates=0,
            catalog=DEFAULT_RECOMMENDATION_RANK_CATALOG,
        )


def test_policy_selects_and_excludes_actions_with_original_identity() -> None:
    recommendation = build_recommendation((3.0, 1.0, 0.0, -1.0, -2.0))
    result = RuleCandidateSelectionPolicy().select(recommendation)

    assert tuple(item.status for item in result.evaluations) == (
        CandidateStatus.SELECTED,
        CandidateStatus.SELECTED,
        CandidateStatus.NOT_ELIGIBLE,
        CandidateStatus.NOT_ELIGIBLE,
        CandidateStatus.NOT_ELIGIBLE,
    )
    assert tuple(item.reason_code for item in result.evaluations) == (
        CandidateReasonCode.SELECTED_STRONG_BUY,
        CandidateReasonCode.SELECTED_BUY,
        CandidateReasonCode.EXCLUDED_HOLD,
        CandidateReasonCode.EXCLUDED_SELL,
        CandidateReasonCode.EXCLUDED_STRONG_SELL,
    )
    assert tuple(item.input_index for item in result.evaluations) == tuple(range(5))
    assert tuple(item.rank for item in result.candidates) == (1, 2)
    assert result.decisions == recommendation.decisions
    assert all(
        actual is expected
        for actual, expected in zip(result.decisions, recommendation.decisions)
    )


def test_policy_uses_priority_score_and_input_index_for_deterministic_order() -> None:
    recommendation = build_recommendation((2.0, 4.0, 3.0, 1.0, 1.0))
    result = RuleCandidateSelectionPolicy().select(recommendation)

    assert tuple(item.input_index for item in result.candidates) == (1, 2, 0, 3, 4)
    assert tuple(item.rank for item in result.candidates) == (1, 2, 3, 4, 5)
    assert tuple(item.input_index for item in result.evaluations) == tuple(range(5))


def test_policy_marks_eligible_decisions_outside_limit() -> None:
    recommendation = build_recommendation((3.0, 2.0, 1.0))
    config = RankingPolicyConfig(
        policy_version="limited-v1",
        max_candidates=2,
        catalog=DEFAULT_RECOMMENDATION_RANK_CATALOG,
    )
    result = RuleCandidateSelectionPolicy(config).select(recommendation)

    assert result.policy_version == "limited-v1"
    assert result.evaluations[2].status is CandidateStatus.OUTSIDE_LIMIT
    assert result.evaluations[2].reason_code is CandidateReasonCode.EXCLUDED_OUTSIDE_CANDIDATE_LIMIT
    assert result.evaluations[2].rank is None
    assert tuple(item.input_index for item in result.excluded) == (2,)


def test_evaluation_and_result_reject_inconsistent_contracts() -> None:
    decision = build_recommendation((3.0,)).decisions[0]
    with pytest.raises(ValidationError):
        CandidateEvaluation(
            decision=decision,
            status=CandidateStatus.SELECTED,
            reason_code=CandidateReasonCode.SELECTED_STRONG_BUY,
            input_index=0,
        )
    with pytest.raises(ValidationError):
        CandidateEvaluation(
            decision=decision,
            status=CandidateStatus.OUTSIDE_LIMIT,
            reason_code=CandidateReasonCode.EXCLUDED_OUTSIDE_CANDIDATE_LIMIT,
            input_index=0,
            rank=1,
        )


def test_policy_handles_empty_recommendation_result() -> None:
    result = RuleCandidateSelectionPolicy().select(build_recommendation(()))

    assert result.evaluations == ()
    assert result.candidates == ()
    assert result.excluded == ()


class FakeCandidateSelectionPolicy(CandidateSelectionPolicy):
    def __init__(self, result: CandidateSelectionResult, error: Optional[Exception] = None) -> None:
        self.result = result
        self.error = error
        self.calls: List[object] = []

    def select(self, recommendation):
        self.calls.append(recommendation)
        if self.error is not None:
            raise self.error
        return self.result


def test_engine_returns_exact_policy_result_once() -> None:
    recommendation = build_recommendation(())
    expected = CandidateSelectionResult(policy_version="v1", evaluations=())
    policy = FakeCandidateSelectionPolicy(expected)
    engine: CandidateSelectionEngine = DefaultCandidateSelectionEngine(policy)

    assert engine.select(recommendation) is expected
    assert policy.calls == [recommendation]
