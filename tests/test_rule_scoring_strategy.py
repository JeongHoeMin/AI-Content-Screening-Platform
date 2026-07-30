from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Tuple

import pytest

from app.models import (
    DEFAULT_SCORING_POLICY_CONFIG,
    CompanyEvidence,
    CompanyImpact,
    CompanyRelation,
    EvidenceAggregation,
    ImpactDirection,
    ResolvedCompany,
    ResolvedTicker,
    ScoreFactor,
    ScoreReasonCode,
    ScoringResult,
)
from app.scorers import EvidenceAwareScoringStrategy, ScoringStrategy


def build_company(index: int) -> ResolvedCompany:
    return ResolvedCompany(name=f"Company {index}", relation=CompanyRelation.DIRECT, ticker=ResolvedTicker(ticker=f"0000{index}", exchange="KRX"))


def build_evidence(index: int, directions: Tuple[ImpactDirection, ...]) -> CompanyEvidence:
    company: ResolvedCompany = build_company(index)
    return CompanyEvidence(company=company, impacts=tuple(CompanyImpact(company=company, direction=direction) for direction in directions))


@pytest.mark.parametrize(
    ("direction", "factor", "weight", "reason_code"),
    [
        (ImpactDirection.POSITIVE, ScoreFactor.POSITIVE_EVIDENCE, 1.0, ScoreReasonCode.POSITIVE_DIRECTION_WEIGHT),
        (ImpactDirection.NEGATIVE, ScoreFactor.NEGATIVE_EVIDENCE, -1.0, ScoreReasonCode.NEGATIVE_DIRECTION_WEIGHT),
        (ImpactDirection.NEUTRAL, ScoreFactor.NON_DIRECTIONAL_EVIDENCE, 0.0, ScoreReasonCode.NEUTRAL_DIRECTION_WEIGHT),
        (ImpactDirection.UNKNOWN, ScoreFactor.NON_DIRECTIONAL_EVIDENCE, 0.0, ScoreReasonCode.UNKNOWN_DIRECTION_WEIGHT),
    ],
)
def test_strategy_applies_default_catalog_mapping(
    direction: ImpactDirection,
    factor: ScoreFactor,
    weight: float,
    reason_code: ScoreReasonCode,
) -> None:
    evidence: CompanyEvidence = build_evidence(1, (direction,))
    result: ScoringResult = EvidenceAwareScoringStrategy(DEFAULT_SCORING_POLICY_CONFIG).score(EvidenceAggregation(companies=(evidence,)))

    contribution = result.companies[0].contributions[0]
    assert contribution.impact is evidence.impacts[0]
    assert (contribution.factor, contribution.weight, contribution.value, contribution.reason_code) == (factor, weight, weight, reason_code)
    assert result.companies[0].score == weight
    assert result.policy_version == DEFAULT_SCORING_POLICY_CONFIG.policy_version


def test_strategy_preserves_conflicting_evidence_as_independent_contributions() -> None:
    evidence: CompanyEvidence = build_evidence(1, (ImpactDirection.POSITIVE, ImpactDirection.NEGATIVE))
    result: ScoringResult = EvidenceAwareScoringStrategy(DEFAULT_SCORING_POLICY_CONFIG).score(EvidenceAggregation(companies=(evidence,)))
    score = result.companies[0]

    assert score.score == 0.0
    assert score.evidences == evidence.impacts
    assert all(score.evidences[index] is evidence.impacts[index] for index in range(2))
    assert [item.value for item in score.contributions] == [1.0, -1.0]


def test_strategy_preserves_company_order_identity_and_cardinality() -> None:
    aggregation: EvidenceAggregation = EvidenceAggregation(companies=(build_evidence(1, (ImpactDirection.POSITIVE,)), build_evidence(2, (ImpactDirection.NEGATIVE,)), build_evidence(3, (ImpactDirection.UNKNOWN,))))
    strategy: ScoringStrategy = EvidenceAwareScoringStrategy(DEFAULT_SCORING_POLICY_CONFIG)
    result: ScoringResult = strategy.score(aggregation)

    assert [score.company for score in result.companies] == [item.company for item in aggregation.companies]
    assert all(score.company is aggregation.companies[index].company for index, score in enumerate(result.companies))
    assert len(result.companies) == len(aggregation.companies)


def test_strategy_handles_empty_aggregation_and_is_deterministic() -> None:
    strategy: EvidenceAwareScoringStrategy = EvidenceAwareScoringStrategy(DEFAULT_SCORING_POLICY_CONFIG)
    empty: EvidenceAggregation = EvidenceAggregation(companies=())

    assert strategy.score(empty) == ScoringResult(policy_version="v1", companies=())
    evidence: CompanyEvidence = build_evidence(1, (ImpactDirection.POSITIVE, ImpactDirection.NEGATIVE))
    aggregation: EvidenceAggregation = EvidenceAggregation(companies=(evidence,))
    assert strategy.score(aggregation) == strategy.score(aggregation)


def test_strategy_is_immutable() -> None:
    strategy: EvidenceAwareScoringStrategy = EvidenceAwareScoringStrategy(DEFAULT_SCORING_POLICY_CONFIG)

    with pytest.raises(FrozenInstanceError):
        strategy.config = DEFAULT_SCORING_POLICY_CONFIG
