from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from app.models import (
    CompanyRelation,
    ExtractedCompany,
    NewsEvent,
    ResolvedNewsEvent,
    ResolvedTicker,
)
from app.resolvers import (
    DefaultTickerResolver,
    StaticTickerLookup,
    TickerLookup,
    TickerResolver,
)


class FakeTickerLookup(TickerLookup):
    def __init__(
        self,
        tickers: Dict[str, ResolvedTicker],
        error: Optional[Exception] = None,
    ) -> None:
        self.tickers: Dict[str, ResolvedTicker] = tickers
        self.error: Optional[Exception] = error
        self.calls: List[str] = []

    def resolve(self, company_name: str) -> Optional[ResolvedTicker]:
        self.calls.append(company_name)
        if self.error is not None:
            raise self.error
        return self.tickers.get(company_name)


def build_event(
    title: str,
    companies: List[ExtractedCompany],
) -> NewsEvent:
    return NewsEvent(
        title=title,
        summary=f"Summary for {title}",
        companies=companies,
        industries=["Semiconductors"],
        keywords=["HBM"],
        reasons=["Fact is stated in the article"],
    )


def build_company(
    name: str,
    relation: CompanyRelation = CompanyRelation.DIRECT,
) -> ExtractedCompany:
    return ExtractedCompany(name=name, relation=relation)


def build_ticker(ticker: str) -> ResolvedTicker:
    return ResolvedTicker(ticker=ticker, exchange="KRX")


def test_constructor_stores_lookup_without_side_effects() -> None:
    lookup: FakeTickerLookup = FakeTickerLookup({})

    resolver: DefaultTickerResolver = DefaultTickerResolver(lookup)

    assert resolver._lookup is lookup
    assert lookup.calls == []


def test_resolver_preserves_event_and_company_data_in_new_snapshots() -> None:
    samsung_ticker: ResolvedTicker = build_ticker("005930")
    original_company: ExtractedCompany = build_company(
        " Samsung  Electronics ",
        relation=CompanyRelation.INDIRECT,
    )
    original_event: NewsEvent = build_event("HBM expansion", [original_company])
    events: List[NewsEvent] = [original_event]
    event_snapshot: Dict[str, Any] = original_event.model_dump(mode="json")
    lookup: StaticTickerLookup = StaticTickerLookup(
        {"Samsung Electronics": samsung_ticker}
    )
    resolver: TickerResolver = DefaultTickerResolver(lookup)

    result: List[ResolvedNewsEvent] = resolver.resolve(events)

    assert len(result) == 1
    assert result[0].event is original_event
    assert result[0].companies[0] is not original_company
    assert result[0].companies[0].name == " Samsung  Electronics "
    assert result[0].companies[0].relation is CompanyRelation.INDIRECT
    assert result[0].companies[0].ticker is samsung_ticker
    assert isinstance(result[0].companies, tuple)
    assert events == [original_event]
    assert original_event.model_dump(mode="json") == event_snapshot


def test_resolver_preserves_order_and_represents_lookup_failure_as_none() -> None:
    first_event: NewsEvent = build_event(
        "First",
        [build_company("Samsung Electronics"), build_company("Unknown Company")],
    )
    second_event: NewsEvent = build_event(
        "Second",
        [build_company("Samsung Electronics")],
    )
    samsung_ticker: ResolvedTicker = build_ticker("005930")
    lookup: FakeTickerLookup = FakeTickerLookup(
        {"Samsung Electronics": samsung_ticker}
    )
    resolver: DefaultTickerResolver = DefaultTickerResolver(lookup)

    result: List[ResolvedNewsEvent] = resolver.resolve([first_event, second_event])

    assert [resolved.event for resolved in result] == [first_event, second_event]
    assert result[0].event is first_event
    assert result[1].event is second_event
    assert result[0].companies[0].ticker is samsung_ticker
    assert result[0].companies[1].ticker is None
    assert result[1].companies[0].ticker is samsung_ticker
    assert lookup.calls == [
        "Samsung Electronics",
        "Unknown Company",
        "Samsung Electronics",
    ]


def test_resolver_returns_new_empty_list_for_empty_input() -> None:
    events: List[NewsEvent] = []
    resolver: DefaultTickerResolver = DefaultTickerResolver(FakeTickerLookup({}))

    result: List[ResolvedNewsEvent] = resolver.resolve(events)

    assert result == []
    assert result is not events


def test_resolver_propagates_lookup_errors_without_wrapping() -> None:
    expected_error: RuntimeError = RuntimeError("lookup failed")
    lookup: FakeTickerLookup = FakeTickerLookup({}, error=expected_error)
    resolver: DefaultTickerResolver = DefaultTickerResolver(lookup)
    events: List[NewsEvent] = [build_event("First", [build_company("Samsung")])]

    with pytest.raises(RuntimeError) as error_info:
        resolver.resolve(events)

    assert error_info.value is expected_error
    assert lookup.calls == ["Samsung"]
