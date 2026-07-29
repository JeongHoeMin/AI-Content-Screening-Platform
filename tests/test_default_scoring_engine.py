from __future__ import annotations

from typing import List, Optional, Tuple

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
    ScoringResult,
)
from app.scorers import DefaultScoringEngine, ScoringEngine, ScoringStrategy


class FakeScoringStrategy(ScoringStrategy):
    def __init__(
        self,
        companies: Tuple[CompanyScore, ...],
        error: Optional[Exception] = None,
    ) -> None:
        self.companies: Tuple[CompanyScore, ...] = companies
        self.error: Optional[Exception] = error
        self.calls: List[EvidenceAggregation] = []

    def score(
        self,
        aggregation: EvidenceAggregation,
    ) -> Tuple[CompanyScore, ...]:
        self.calls.append(aggregation)
        if self.error is not None:
            raise self.error
        return self.companies


def build_aggregation() -> EvidenceAggregation:
    company: ResolvedCompany = ResolvedCompany(
        name="Samsung Electronics",
        relation=CompanyRelation.DIRECT,
        ticker=ResolvedTicker(ticker="005930", exchange="KRX"),
    )
    impact: CompanyImpact = CompanyImpact(
        company=company,
        direction=ImpactDirection.POSITIVE,
    )
    evidence: CompanyEvidence = CompanyEvidence(
        company=company,
        impacts=(impact,),
    )
    return EvidenceAggregation(companies=(evidence,))


def build_scores(aggregation: EvidenceAggregation) -> Tuple[CompanyScore, ...]:
    evidence: CompanyEvidence = aggregation.companies[0]
    return (
        CompanyScore(
            company=evidence.company,
            score=1.0,
            evidences=evidence.impacts,
        ),
    )


def test_constructor_stores_strategy_without_side_effects() -> None:
    aggregation: EvidenceAggregation = build_aggregation()
    strategy: FakeScoringStrategy = FakeScoringStrategy(build_scores(aggregation))

    engine: DefaultScoringEngine = DefaultScoringEngine(strategy)

    assert engine._strategy is strategy
    assert strategy.calls == []


def test_engine_preserves_strategy_tuple_identity_without_copying() -> None:
    aggregation: EvidenceAggregation = build_aggregation()
    companies: Tuple[CompanyScore, ...] = build_scores(aggregation)
    strategy: FakeScoringStrategy = FakeScoringStrategy(companies)
    engine: ScoringEngine = DefaultScoringEngine(strategy)

    result: ScoringResult = engine.score(aggregation)

    assert result.companies is companies
    assert strategy.calls == [aggregation]


def test_engine_handles_empty_input() -> None:
    aggregation: EvidenceAggregation = EvidenceAggregation(companies=())
    strategy: FakeScoringStrategy = FakeScoringStrategy(())
    engine: DefaultScoringEngine = DefaultScoringEngine(strategy)

    result: ScoringResult = engine.score(aggregation)

    assert result.companies == ()
    assert strategy.calls == [aggregation]


def test_engine_propagates_strategy_error_without_wrapping() -> None:
    aggregation: EvidenceAggregation = build_aggregation()
    expected_error: RuntimeError = RuntimeError("scoring failed")
    strategy: FakeScoringStrategy = FakeScoringStrategy(
        companies=(),
        error=expected_error,
    )
    engine: DefaultScoringEngine = DefaultScoringEngine(strategy)

    with pytest.raises(RuntimeError) as error_info:
        engine.score(aggregation)

    assert error_info.value is expected_error
    assert strategy.calls == [aggregation]
