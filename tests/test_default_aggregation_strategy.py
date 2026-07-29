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
    NewsEvent,
    ResolvedCompany,
    ResolvedNewsEvent,
    ResolvedTicker,
)


def build_company(
    name: str,
    ticker: Optional[ResolvedTicker],
) -> ResolvedCompany:
    return ResolvedCompany(
        name=name,
        relation=CompanyRelation.DIRECT,
        ticker=ticker,
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
    return ImpactAnalysis(event=resolved_event, impacts=impacts)


def test_strategy_groups_equal_ticker_values_and_preserves_first_company() -> None:
    first_company: ResolvedCompany = build_company(
        "Samsung Electronics",
        ResolvedTicker(ticker="005930", exchange="KRX"),
    )
    second_company: ResolvedCompany = build_company(
        "Samsung Elec.",
        ResolvedTicker(ticker="005930", exchange="KRX"),
    )
    third_company: ResolvedCompany = build_company(
        "Samsung",
        ResolvedTicker(ticker="005930", exchange="KRX"),
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
    assert result[0].impacts == impacts
    assert all(
        result[0].impacts[index] is impacts[index]
        for index in range(len(impacts))
    )


def test_strategy_preserves_unresolved_impacts_as_independent_groups() -> None:
    first_company: ResolvedCompany = build_company("OpenAI", None)
    second_company: ResolvedCompany = build_company("OpenAI", None)
    impacts: Tuple[CompanyImpact, ...] = (
        build_impact(first_company),
        build_impact(second_company),
    )
    strategy: DefaultAggregationStrategy = DefaultAggregationStrategy()

    result: Tuple[CompanyEvidence, ...] = strategy.aggregate(
        [build_analysis("Unresolved", impacts)]
    )

    assert len(result) == 2
    assert result[0].company is first_company
    assert result[1].company is second_company
    assert result[0].impacts == (impacts[0],)
    assert result[1].impacts == (impacts[1],)


def test_strategy_preserves_flatten_group_and_impact_order() -> None:
    ticker_a: ResolvedTicker = ResolvedTicker(ticker="005930", exchange="KRX")
    ticker_b: ResolvedTicker = ResolvedTicker(ticker="000660", exchange="KRX")
    ticker_c: ResolvedTicker = ResolvedTicker(ticker="035420", exchange="KRX")
    impact_a1: CompanyImpact = build_impact(build_company("A1", ticker_a))
    impact_b: CompanyImpact = build_impact(build_company("B", ticker_b))
    impact_a2: CompanyImpact = build_impact(
        build_company("A2", ResolvedTicker(ticker="005930", exchange="KRX"))
    )
    impact_c: CompanyImpact = build_impact(build_company("C", ticker_c))
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
    assert result[0].impacts == (impact_a1, impact_a2)
    assert flattened_impacts == [impact_a1, impact_a2, impact_b, impact_c]
    assert sorted(id(impact) for impact in flattened_impacts) == sorted(
        id(impact)
        for impact in (impact_a1, impact_b, impact_a2, impact_c)
    )


def test_strategy_handles_empty_input_and_does_not_mutate_analyses() -> None:
    company: ResolvedCompany = build_company(
        "Samsung",
        ResolvedTicker(ticker="005930", exchange="KRX"),
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
    assert first_result[0].impacts[0] is impact


def test_strategy_is_immutable() -> None:
    strategy: DefaultAggregationStrategy = DefaultAggregationStrategy()

    with pytest.raises(FrozenInstanceError):
        strategy._policy = "changed"
