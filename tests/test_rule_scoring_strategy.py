from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Tuple

import pytest

from app.models import (
    CompanyEvidence,
    CompanyImpact,
    CompanyRelation,
    CompanyScore,
    EvidenceAggregation,
    ImpactDirection,
    ResolvedCompany,
    ResolvedTicker,
)
from app.scorers import RuleScoringStrategy, ScoringStrategy
from app.scorers.rule_strategy import _DIRECTION_SCORES


def build_company(index: int) -> ResolvedCompany:
    return ResolvedCompany(
        name=f"Company {index}",
        relation=CompanyRelation.DIRECT,
        ticker=ResolvedTicker(ticker=f"0000{index}", exchange="KRX"),
    )


def build_evidence(
    index: int,
    directions: Tuple[ImpactDirection, ...],
) -> CompanyEvidence:
    company: ResolvedCompany = build_company(index)
    impacts: Tuple[CompanyImpact, ...] = tuple(
        CompanyImpact(company=company, direction=direction)
        for direction in directions
    )
    return CompanyEvidence(company=company, impacts=impacts)


@pytest.mark.parametrize(
    ("directions", "expected_score"),
    [
        ((ImpactDirection.POSITIVE,), 1.0),
        ((ImpactDirection.NEGATIVE,), -1.0),
        ((ImpactDirection.UNKNOWN,), 0.0),
        ((ImpactDirection.NEUTRAL,), 0.0),
        (
            (
                ImpactDirection.POSITIVE,
                ImpactDirection.POSITIVE,
                ImpactDirection.NEGATIVE,
            ),
            1.0,
        ),
        (
            (
                ImpactDirection.POSITIVE,
                ImpactDirection.UNKNOWN,
                ImpactDirection.NEUTRAL,
                ImpactDirection.NEGATIVE,
            ),
            0.0,
        ),
    ],
)
def test_rule_strategy_applies_direction_score_policy(
    directions: Tuple[ImpactDirection, ...],
    expected_score: float,
) -> None:
    evidence: CompanyEvidence = build_evidence(1, directions)
    aggregation: EvidenceAggregation = EvidenceAggregation(companies=(evidence,))
    strategy: ScoringStrategy = RuleScoringStrategy()

    result: Tuple[CompanyScore, ...] = strategy.score(aggregation)

    assert len(result) == 1
    assert result[0].score == expected_score
    assert result[0].company is evidence.company
    assert result[0].evidences is evidence.impacts


def test_rule_strategy_preserves_company_order_identity_and_cardinality() -> None:
    first_evidence: CompanyEvidence = build_evidence(
        1,
        (ImpactDirection.POSITIVE,),
    )
    second_evidence: CompanyEvidence = build_evidence(
        2,
        (ImpactDirection.NEGATIVE,),
    )
    third_evidence: CompanyEvidence = build_evidence(
        3,
        (ImpactDirection.UNKNOWN,),
    )
    aggregation: EvidenceAggregation = EvidenceAggregation(
        companies=(first_evidence, second_evidence, third_evidence)
    )
    strategy: RuleScoringStrategy = RuleScoringStrategy()

    result: Tuple[CompanyScore, ...] = strategy.score(aggregation)

    assert len(result) == len(aggregation.companies)
    assert [score.company for score in result] == [
        evidence.company for evidence in aggregation.companies
    ]
    assert all(
        score.company is aggregation.companies[index].company
        and score.evidences is aggregation.companies[index].impacts
        for index, score in enumerate(result)
    )


def test_rule_strategy_handles_empty_aggregation() -> None:
    aggregation: EvidenceAggregation = EvidenceAggregation(companies=())
    strategy: RuleScoringStrategy = RuleScoringStrategy()

    result: Tuple[CompanyScore, ...] = strategy.score(aggregation)

    assert result == ()


def test_rule_strategy_is_deterministic_and_does_not_mutate_evidence() -> None:
    evidence: CompanyEvidence = build_evidence(
        1,
        (ImpactDirection.POSITIVE, ImpactDirection.NEGATIVE),
    )
    aggregation: EvidenceAggregation = EvidenceAggregation(companies=(evidence,))
    snapshot: Tuple[CompanyImpact, ...] = evidence.impacts
    strategy: RuleScoringStrategy = RuleScoringStrategy()

    first_result: Tuple[CompanyScore, ...] = strategy.score(aggregation)
    second_result: Tuple[CompanyScore, ...] = strategy.score(aggregation)

    assert first_result == second_result
    assert evidence.impacts is snapshot
    assert aggregation.companies == (evidence,)


def test_rule_strategy_and_direction_policy_are_immutable() -> None:
    strategy: RuleScoringStrategy = RuleScoringStrategy()

    with pytest.raises(FrozenInstanceError):
        strategy._policy = "changed"
    with pytest.raises(TypeError):
        _DIRECTION_SCORES[ImpactDirection.POSITIVE] = 2.0


def test_empty_company_evidence_receives_float_zero_score() -> None:
    evidence: CompanyEvidence = build_evidence(1, ())
    aggregation: EvidenceAggregation = EvidenceAggregation(companies=(evidence,))
    strategy: RuleScoringStrategy = RuleScoringStrategy()

    result: Tuple[CompanyScore, ...] = strategy.score(aggregation)

    assert result[0].score == 0.0
    assert isinstance(result[0].score, float)
