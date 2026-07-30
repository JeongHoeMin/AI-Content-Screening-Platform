from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from app.deduplicators import (
    ArticleDeduplicator,
    DefaultArticleDeduplicator,
    DuplicateStrategy,
)
from app.models import CompanyRelation, EventType, ExtractedCompany, NewsEvent


class FakeDuplicateStrategy(DuplicateStrategy):
    def __init__(
        self,
        error: Optional[Exception] = None,
    ) -> None:
        self.error: Optional[Exception] = error
        self.calls: int = 0

    def is_duplicate(
        self,
        left: NewsEvent,
        right: NewsEvent,
    ) -> bool:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return left.title == right.title


def build_event(title: str) -> NewsEvent:
    return NewsEvent(
        title=title,
        summary=f"Summary for {title}",
        event_type=EventType.CORPORATE_EVENT,
        companies=[
            ExtractedCompany(
                name="Samsung Electronics",
                relation=CompanyRelation.DIRECT,
            )
        ],
        industries=["Semiconductors"],
        keywords=["HBM"],
        reasons=["Fact is stated in the article"],
    )


def test_constructor_stores_strategy_without_side_effects() -> None:
    strategy: FakeDuplicateStrategy = FakeDuplicateStrategy()

    deduplicator: DefaultArticleDeduplicator = DefaultArticleDeduplicator(strategy)

    assert deduplicator._strategy is strategy
    assert strategy.calls == 0


def test_deduplicator_keeps_first_canonical_events_in_input_order() -> None:
    first_a: NewsEvent = build_event("A")
    duplicate_a: NewsEvent = build_event("A")
    first_b: NewsEvent = build_event("B")
    first_c: NewsEvent = build_event("C")
    duplicate_c: NewsEvent = build_event("C")
    events: List[NewsEvent] = [
        first_a,
        duplicate_a,
        first_b,
        first_c,
        duplicate_c,
    ]
    original_events: List[NewsEvent] = list(events)
    event_snapshots: List[Dict[str, Any]] = [
        event.model_dump(mode="json") for event in events
    ]
    strategy: FakeDuplicateStrategy = FakeDuplicateStrategy()
    deduplicator: ArticleDeduplicator = DefaultArticleDeduplicator(strategy)

    result: List[NewsEvent] = deduplicator.deduplicate(events)

    assert result == [first_a, first_b, first_c]
    assert result[0] is first_a
    assert result[1] is first_b
    assert result[2] is first_c
    assert events == original_events
    assert events[0] is first_a
    assert events[1] is duplicate_a
    assert [event.model_dump(mode="json") for event in events] == event_snapshots
    assert strategy.calls == 7


def test_deduplicator_returns_new_empty_list() -> None:
    events: List[NewsEvent] = []
    deduplicator: DefaultArticleDeduplicator = DefaultArticleDeduplicator(
        FakeDuplicateStrategy()
    )

    result: List[NewsEvent] = deduplicator.deduplicate(events)

    assert result == []
    assert result is not events


def test_deduplicator_returns_single_original_event() -> None:
    event: NewsEvent = build_event("A")
    events: List[NewsEvent] = [event]
    deduplicator: DefaultArticleDeduplicator = DefaultArticleDeduplicator(
        FakeDuplicateStrategy()
    )

    result: List[NewsEvent] = deduplicator.deduplicate(events)

    assert result == [event]
    assert result[0] is event


def test_deduplicator_propagates_strategy_errors_without_wrapping() -> None:
    expected_error: RuntimeError = RuntimeError("strategy failed")
    deduplicator: DefaultArticleDeduplicator = DefaultArticleDeduplicator(
        FakeDuplicateStrategy(error=expected_error)
    )

    with pytest.raises(RuntimeError) as error_info:
        deduplicator.deduplicate([build_event("A"), build_event("A")])

    assert error_info.value is expected_error
