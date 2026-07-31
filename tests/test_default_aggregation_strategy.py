from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, List, Optional, Tuple

import pytest

from app.aggregators import AggregationStrategy, DefaultAggregationStrategy
from app.models import (
    CompanyEvidence,
    CompanyImpact,
    CompanyRelation,
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
    CompanyResolutionStatus,
    EventType,
)


def build_company(
    name: str,
    ticker: Optional[ResolvedTicker],
    company_id: Optional[str] = None,
    resolution_status: CompanyResolutionStatus = CompanyResolutionStatus.UNRESOLVED,
) -> ResolvedCompany:
    return ResolvedCompany(
        name=name,
        relation=CompanyRelation.DIRECT,
        ticker=ticker,
        company_id=company_id,
        resolution_status=resolution_status,
    )


def build_impact(
    company: ResolvedCompany,
    direction: ImpactDirection = ImpactDirection.POSITIVE,
) -> CompanyImpact:
    return CompanyImpact(company=company, direction=direction)


def build_analysis(
    title: str,
    impacts: Tuple[CompanyImpact, ...],
) -> ImpactAnalysis:
    companies: Tuple[ResolvedCompany, ...] = tuple(
        impact.company for impact in impacts
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
            for company in companies
        ],
        industries=["Semiconductors"],
        keywords=["HBM"],
        reasons=["Fact is stated in the article"],
    )
    resolved_event: ResolvedNewsEvent = ResolvedNewsEvent(
        event=event,
        companies=companies,
    )
    observations: Tuple[ImpactObservation, ...] = tuple(
        ImpactObservation(
            scope=ImpactScope.COMPANY,
            company=impact.company,
            event_fact=EventFact.FACTORY_EXPANSION,
            direction=impact.direction,
            uncertainty=ImpactUncertainty.HIGH,
            reason_code=ImpactReasonCode.FACTORY_EXPANSION_POSITIVE,
        )
        for impact in impacts
    )
    return ImpactAnalysis(
        event=resolved_event,
        evaluations=tuple(
            ImpactEvaluation(observation=observation, eligible=True)
            for observation in observations
        ),
    )


def test_strategy_groups_equal_company_ids_and_preserves_first_company() -> None:
    first_company: ResolvedCompany = build_company(
        "Samsung Electronics",
        ResolvedTicker(ticker="005930", exchange="KRX"),
        "KRX-COMPANY-000001",
        CompanyResolutionStatus.RESOLVED,
    )
    second_company: ResolvedCompany = build_company(
        "Samsung Elec.",
        ResolvedTicker(ticker="005930", exchange="KRX"),
        "KRX-COMPANY-000001",
        CompanyResolutionStatus.RESOLVED,
    )
    third_company: ResolvedCompany = build_company(
        "Samsung",
        ResolvedTicker(ticker="005930", exchange="KRX"),
        "KRX-COMPANY-000001",
        CompanyResolutionStatus.RESOLVED,
    )
    impacts: Tuple[CompanyImpact, ...] = (
        build_impact(first_company),
        build_impact(second_company, ImpactDirection.NEGATIVE),
        build_impact(third_company),
    )
    strategy: AggregationStrategy = DefaultAggregationStrategy()

    result: Tuple[CompanyEvidence, ...] = strategy.aggregate(
        [build_analysis("First", impacts)]
    )

    assert len(result) == 1
    assert result[0].company is first_company
    assert [impact.direction for impact in result[0].impacts] == [
        impact.direction for impact in impacts
    ]


def test_strategy_excludes_ambiguous_and_unresolved_impacts() -> None:
    first_company: ResolvedCompany = build_company("OpenAI", None)
    second_company: ResolvedCompany = build_company(
        "Anthropic",
        None,
        resolution_status=CompanyResolutionStatus.AMBIGUOUS,
    )
    impacts: Tuple[CompanyImpact, ...] = (
        build_impact(first_company),
        build_impact(second_company),
    )
    strategy: DefaultAggregationStrategy = DefaultAggregationStrategy()

    result: Tuple[CompanyEvidence, ...] = strategy.aggregate(
        [build_analysis("Unresolved", impacts)]
    )

    assert result == ()


def test_strategy_converts_only_the_eligible_conflicting_evaluation() -> None:
    company: ResolvedCompany = build_company(
        "Samsung",
        ResolvedTicker(ticker="005930", exchange="KRX"),
        "KRX-COMPANY-000001",
        CompanyResolutionStatus.RESOLVED,
    )
    base: ImpactAnalysis = build_analysis(
        "Conflict",
        (build_impact(company, ImpactDirection.POSITIVE), build_impact(company, ImpactDirection.NEGATIVE)),
    )
    analysis: ImpactAnalysis = ImpactAnalysis(
        event=base.event,
        evaluations=(
            ImpactEvaluation(observation=base.observations[0], eligible=False, exclusion_reason="unknown_direction"),
            ImpactEvaluation(observation=base.observations[1], eligible=True),
        ),
    )

    result: Tuple[CompanyEvidence, ...] = DefaultAggregationStrategy().aggregate([analysis])

    assert [impact.direction for impact in result[0].impacts] == [ImpactDirection.NEGATIVE]


def test_strategy_does_not_merge_distinct_company_ids_with_the_same_ticker() -> None:
    ticker: ResolvedTicker = ResolvedTicker(ticker="005930", exchange="KRX")
    first: CompanyImpact = build_impact(
        build_company(
            "First",
            ticker,
            "KRX-COMPANY-000001",
            CompanyResolutionStatus.RESOLVED,
        )
    )
    second: CompanyImpact = build_impact(
        build_company(
            "Second",
            ticker,
            "KRX-COMPANY-000002",
            CompanyResolutionStatus.RESOLVED,
        )
    )
    strategy: DefaultAggregationStrategy = DefaultAggregationStrategy()

    result: Tuple[CompanyEvidence, ...] = strategy.aggregate(
        [build_analysis("Distinct", (first, second))]
    )

    assert [evidence.company.company_id for evidence in result] == [
        "KRX-COMPANY-000001",
        "KRX-COMPANY-000002",
    ]


def test_strategy_preserves_flatten_group_and_impact_order() -> None:
    ticker_a: ResolvedTicker = ResolvedTicker(ticker="005930", exchange="KRX")
    ticker_b: ResolvedTicker = ResolvedTicker(ticker="000660", exchange="KRX")
    ticker_c: ResolvedTicker = ResolvedTicker(ticker="035420", exchange="KRX")
    impact_a1: CompanyImpact = build_impact(
        build_company("A1", ticker_a, "KRX-COMPANY-000001", CompanyResolutionStatus.RESOLVED)
    )
    impact_b: CompanyImpact = build_impact(
        build_company("B", ticker_b, "KRX-COMPANY-000002", CompanyResolutionStatus.RESOLVED)
    )
    impact_a2: CompanyImpact = build_impact(
        build_company(
            "A2",
            ResolvedTicker(ticker="005930", exchange="KRX"),
            "KRX-COMPANY-000001",
            CompanyResolutionStatus.RESOLVED,
        )
    )
    impact_c: CompanyImpact = build_impact(
        build_company("C", ticker_c, "KRX-COMPANY-000003", CompanyResolutionStatus.RESOLVED)
    )
    first_analysis: ImpactAnalysis = build_analysis(
        "First",
        (impact_a1, impact_b),
    )
    second_analysis: ImpactAnalysis = build_analysis(
        "Second",
        (impact_a2, impact_c),
    )
    strategy: DefaultAggregationStrategy = DefaultAggregationStrategy()

    result: Tuple[CompanyEvidence, ...] = strategy.aggregate(
        [first_analysis, second_analysis]
    )
    flattened_impacts: List[CompanyImpact] = [
        impact for evidence in result for impact in evidence.impacts
    ]

    assert [evidence.company.name for evidence in result] == ["A1", "B", "C"]
    assert [impact.direction for impact in result[0].impacts] == [
        impact_a1.direction, impact_a2.direction
    ]
    assert [impact.direction for impact in flattened_impacts] == [
        impact_a1.direction, impact_a2.direction, impact_b.direction, impact_c.direction
    ]


def test_strategy_handles_empty_input_and_does_not_mutate_analyses() -> None:
    company: ResolvedCompany = build_company(
        "Samsung",
        ResolvedTicker(ticker="005930", exchange="KRX"),
        "KRX-COMPANY-000001",
        CompanyResolutionStatus.RESOLVED,
    )
    impact: CompanyImpact = build_impact(company)
    analysis: ImpactAnalysis = build_analysis("Original", (impact,))
    snapshot: dict[str, Any] = analysis.event.event.model_dump(mode="json")
    strategy: DefaultAggregationStrategy = DefaultAggregationStrategy()

    empty_result: Tuple[CompanyEvidence, ...] = strategy.aggregate([])
    first_result: Tuple[CompanyEvidence, ...] = strategy.aggregate([analysis])
    second_result: Tuple[CompanyEvidence, ...] = strategy.aggregate([analysis])

    assert empty_result == ()
    assert first_result == second_result
    assert analysis.event.event.model_dump(mode="json") == snapshot
    assert first_result[0].impacts[0].company is impact.company
    assert first_result[0].impacts[0].direction is impact.direction


def test_strategy_is_immutable() -> None:
    strategy: DefaultAggregationStrategy = DefaultAggregationStrategy()

    with pytest.raises(FrozenInstanceError):
        strategy._policy = "changed"
