from __future__ import annotations

from typing import List, Optional, Tuple

import pytest

from app.analyzers import DefaultImpactAnalyzer, ImpactPolicy, ImpactStrategy
from app.models import (
    CompanyRelation, EventFact, EventType, ExtractedCompany, ImpactAnalysis,
    ImpactFilterResult, ImpactObservation, ImpactDirection, ImpactReasonCode,
    ImpactScope, ImpactUncertainty, NewsEvent, ResolvedCompany, ResolvedNewsEvent,
    ResolvedTicker,
)


class FakeImpactStrategy(ImpactStrategy):
    def __init__(self, observations: Tuple[ImpactObservation, ...], error: Optional[Exception] = None) -> None:
        self.observations: Tuple[ImpactObservation, ...] = observations
        self.error: Optional[Exception] = error
        self.calls: List[ResolvedNewsEvent] = []

    def analyze(self, event: ResolvedNewsEvent) -> Tuple[ImpactObservation, ...]:
        self.calls.append(event)
        if self.error is not None:
            raise self.error
        return self.observations


class FakeImpactPolicy(ImpactPolicy):
    def __init__(self, filters: Tuple[ImpactFilterResult, ...]) -> None:
        self.filters: Tuple[ImpactFilterResult, ...] = filters
        self.calls: List[Tuple[ResolvedNewsEvent, Tuple[ImpactObservation, ...]]] = []

    def filter(self, event: ResolvedNewsEvent, observations: Tuple[ImpactObservation, ...]) -> Tuple[ImpactFilterResult, ...]:
        self.calls.append((event, observations))
        return self.filters


def build_resolved_event(title: str) -> ResolvedNewsEvent:
    company: ResolvedCompany = ResolvedCompany(name="Samsung Electronics", relation=CompanyRelation.DIRECT, ticker=ResolvedTicker(ticker="005930", exchange="KRX"))
    event: NewsEvent = NewsEvent(title=title, summary=f"Summary for {title}", event_type=EventType.CORPORATE_EVENT, event_facts=(EventFact.FACTORY_EXPANSION,), companies=[ExtractedCompany(name=company.name, relation=company.relation)], industries=["Semiconductors"], keywords=["HBM"], reasons=["Fact is stated in the article"])
    return ResolvedNewsEvent(event=event, companies=(company,))


def build_observations(event: ResolvedNewsEvent) -> Tuple[ImpactObservation, ...]:
    return (ImpactObservation(scope=ImpactScope.COMPANY, company=event.companies[0], event_fact=EventFact.FACTORY_EXPANSION, direction=ImpactDirection.POSITIVE, uncertainty=ImpactUncertainty.HIGH, reason_code=ImpactReasonCode.FACTORY_EXPANSION_POSITIVE),)


def test_analyzer_preserves_event_identity_observation_tuple_and_filter_alignment() -> None:
    first_event: ResolvedNewsEvent = build_resolved_event("First")
    second_event: ResolvedNewsEvent = build_resolved_event("Second")
    observations: Tuple[ImpactObservation, ...] = build_observations(first_event)
    strategy: FakeImpactStrategy = FakeImpactStrategy(observations)
    policy: FakeImpactPolicy = FakeImpactPolicy((ImpactFilterResult(eligible=True),))

    result: List[ImpactAnalysis] = DefaultImpactAnalyzer(strategy, policy).analyze([first_event, second_event])

    assert [analysis.event for analysis in result] == [first_event, second_event]
    assert result[0].event is first_event and result[1].event is second_event
    assert result[0].observations == observations and result[1].observations == observations
    assert result[0].observations[0] is observations[0]
    assert all(analysis.filters == (ImpactFilterResult(eligible=True),) for analysis in result)
    assert policy.calls == [(first_event, observations), (second_event, observations)]


def test_analyzer_returns_empty_list_for_empty_input() -> None:
    strategy: FakeImpactStrategy = FakeImpactStrategy(())
    policy: FakeImpactPolicy = FakeImpactPolicy(())
    assert DefaultImpactAnalyzer(strategy, policy).analyze([]) == []
    assert strategy.calls == [] and policy.calls == []


def test_analyzer_propagates_strategy_error_without_wrapping() -> None:
    event: ResolvedNewsEvent = build_resolved_event("First")
    expected_error: RuntimeError = RuntimeError("strategy failed")
    strategy: FakeImpactStrategy = FakeImpactStrategy((), expected_error)
    policy: FakeImpactPolicy = FakeImpactPolicy(())

    with pytest.raises(RuntimeError) as error_info:
        DefaultImpactAnalyzer(strategy, policy).analyze([event])

    assert error_info.value is expected_error
