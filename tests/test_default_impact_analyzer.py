from __future__ import annotations

from typing import List, Optional, Tuple

import pytest

from app.analyzers import DefaultImpactAnalyzer, ImpactAnalyzer, ImpactStrategy
from app.models import (
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


class FakeImpactStrategy(ImpactStrategy):
    def __init__(
        self,
        impacts: Tuple[CompanyImpact, ...],
        error: Optional[Exception] = None,
    ) -> None:
        self.impacts: Tuple[CompanyImpact, ...] = impacts
        self.error: Optional[Exception] = error
        self.calls: List[ResolvedNewsEvent] = []

    def analyze(self, event: ResolvedNewsEvent) -> Tuple[CompanyImpact, ...]:
        self.calls.append(event)
        if self.error is not None:
            raise self.error
        return self.impacts


def build_resolved_event(title: str) -> ResolvedNewsEvent:
    company: ResolvedCompany = ResolvedCompany(
        name="Samsung Electronics",
        relation=CompanyRelation.DIRECT,
        ticker=ResolvedTicker(ticker="005930", exchange="KRX"),
    )
    event: NewsEvent = NewsEvent(
        title=title,
        summary=f"Summary for {title}",
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
    return ResolvedNewsEvent(event=event, companies=(company,))


def build_impacts(event: ResolvedNewsEvent) -> Tuple[CompanyImpact, ...]:
    return (
        CompanyImpact(
            company=event.companies[0],
            direction=ImpactDirection.POSITIVE,
        ),
    )


def test_constructor_stores_strategy_without_side_effects() -> None:
    event: ResolvedNewsEvent = build_resolved_event("First")
    strategy: FakeImpactStrategy = FakeImpactStrategy(build_impacts(event))

    analyzer: DefaultImpactAnalyzer = DefaultImpactAnalyzer(strategy)

    assert analyzer._strategy is strategy
    assert strategy.calls == []


def test_analyzer_preserves_event_order_identity_and_strategy_tuple() -> None:
    first_event: ResolvedNewsEvent = build_resolved_event("First")
    second_event: ResolvedNewsEvent = build_resolved_event("Second")
    impacts: Tuple[CompanyImpact, ...] = build_impacts(first_event)
    strategy: FakeImpactStrategy = FakeImpactStrategy(impacts)
    analyzer: ImpactAnalyzer = DefaultImpactAnalyzer(strategy)

    result: List[ImpactAnalysis] = analyzer.analyze([first_event, second_event])

    assert [analysis.event for analysis in result] == [first_event, second_event]
    assert result[0].event is first_event
    assert result[1].event is second_event
    assert result[0].impacts is impacts
    assert result[1].impacts is impacts
    assert strategy.calls == [first_event, second_event]


def test_analyzer_returns_new_empty_list_for_empty_input() -> None:
    strategy: FakeImpactStrategy = FakeImpactStrategy(())
    analyzer: DefaultImpactAnalyzer = DefaultImpactAnalyzer(strategy)
    events: List[ResolvedNewsEvent] = []

    result: List[ImpactAnalysis] = analyzer.analyze(events)

    assert result == []
    assert result is not events
    assert strategy.calls == []


def test_analyzer_propagates_strategy_error_without_wrapping() -> None:
    event: ResolvedNewsEvent = build_resolved_event("First")
    expected_error: RuntimeError = RuntimeError("strategy failed")
    strategy: FakeImpactStrategy = FakeImpactStrategy(
        impacts=build_impacts(event),
        error=expected_error,
    )
    analyzer: DefaultImpactAnalyzer = DefaultImpactAnalyzer(strategy)

    with pytest.raises(RuntimeError) as error_info:
        analyzer.analyze([event])

    assert error_info.value is expected_error
    assert strategy.calls == [event]
