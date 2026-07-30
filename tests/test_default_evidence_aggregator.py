from __future__ import annotations

from typing import List, Optional, Tuple

import pytest

from app.aggregators import (
    AggregationStrategy,
    DefaultEvidenceAggregator,
    EvidenceAggregator,
)
from app.models import (
    CompanyEvidence,
    CompanyImpact,
    CompanyRelation,
    EvidenceAggregation,
    EventType,
    ExtractedCompany,
    ImpactAnalysis,
    ImpactDirection,
    ImpactEvaluation,
    ImpactObservation,
    ImpactReasonCode,
    ImpactScope,
    ImpactUncertainty,
    EventFact,
    NewsEvent,
    ResolvedCompany,
    ResolvedNewsEvent,
    ResolvedTicker,
)


class FakeAggregationStrategy(AggregationStrategy):
    def __init__(
        self,
        companies: Tuple[CompanyEvidence, ...],
        error: Optional[Exception] = None,
    ) -> None:
        self.companies: Tuple[CompanyEvidence, ...] = companies
        self.error: Optional[Exception] = error
        self.calls: List[List[ImpactAnalysis]] = []

    def aggregate(
        self,
        analyses: List[ImpactAnalysis],
    ) -> Tuple[CompanyEvidence, ...]:
        self.calls.append(analyses)
        if self.error is not None:
            raise self.error
        return self.companies


def build_analysis(title: str) -> ImpactAnalysis:
    company: ResolvedCompany = ResolvedCompany(
        name="Samsung Electronics",
        relation=CompanyRelation.DIRECT,
        ticker=ResolvedTicker(ticker="005930", exchange="KRX"),
    )
    event: NewsEvent = NewsEvent(
        title=title,
        summary=f"Summary for {title}",
        event_type=EventType.CORPORATE_EVENT,
        companies=[
            ExtractedCompany(
                name=company.name,
                relation=company.relation,
            )
        ],
        industries=["Semiconductors"],
        keywords=["HBM"],
        reasons=["Fact is stated in the article"],
    )
    resolved_event: ResolvedNewsEvent = ResolvedNewsEvent(
        event=event,
        companies=(company,),
    )
    observation: ImpactObservation = ImpactObservation(
        scope=ImpactScope.COMPANY,
        company=company,
        event_fact=EventFact.FACTORY_EXPANSION,
        direction=ImpactDirection.POSITIVE,
        uncertainty=ImpactUncertainty.HIGH,
        reason_code=ImpactReasonCode.FACTORY_EXPANSION_POSITIVE,
    )
    return ImpactAnalysis(
        event=resolved_event,
        evaluations=(ImpactEvaluation(observation=observation, eligible=True),),
    )


def build_companies(
    analysis: ImpactAnalysis,
) -> Tuple[CompanyEvidence, ...]:
    return (
        CompanyEvidence(
            company=analysis.observations[0].company,
            impacts=(CompanyImpact(
                company=analysis.observations[0].company,
                direction=analysis.observations[0].direction,
            ),),
        ),
    )


def test_constructor_stores_strategy_without_side_effects() -> None:
    analysis: ImpactAnalysis = build_analysis("First")
    strategy: FakeAggregationStrategy = FakeAggregationStrategy(
        build_companies(analysis)
    )

    aggregator: DefaultEvidenceAggregator = DefaultEvidenceAggregator(strategy)

    assert aggregator._strategy is strategy
    assert strategy.calls == []


def test_aggregator_preserves_strategy_tuple_identity() -> None:
    analysis: ImpactAnalysis = build_analysis("First")
    companies: Tuple[CompanyEvidence, ...] = build_companies(analysis)
    strategy: FakeAggregationStrategy = FakeAggregationStrategy(companies)
    aggregator: EvidenceAggregator = DefaultEvidenceAggregator(strategy)
    analyses: List[ImpactAnalysis] = [analysis]

    result: EvidenceAggregation = aggregator.aggregate(analyses)

    assert result.companies is companies
    assert strategy.calls == [analyses]


def test_aggregator_handles_empty_input() -> None:
    strategy: FakeAggregationStrategy = FakeAggregationStrategy(())
    aggregator: DefaultEvidenceAggregator = DefaultEvidenceAggregator(strategy)
    analyses: List[ImpactAnalysis] = []

    result: EvidenceAggregation = aggregator.aggregate(analyses)

    assert result.companies == ()
    assert strategy.calls == [analyses]


def test_aggregator_propagates_strategy_error_without_wrapping() -> None:
    analysis: ImpactAnalysis = build_analysis("First")
    expected_error: RuntimeError = RuntimeError("aggregation failed")
    strategy: FakeAggregationStrategy = FakeAggregationStrategy(
        companies=(),
        error=expected_error,
    )
    aggregator: DefaultEvidenceAggregator = DefaultEvidenceAggregator(strategy)

    with pytest.raises(RuntimeError) as error_info:
        aggregator.aggregate([analysis])

    assert error_info.value is expected_error
    assert strategy.calls == [[analysis]]
