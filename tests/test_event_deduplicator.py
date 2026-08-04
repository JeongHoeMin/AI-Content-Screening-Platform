from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Tuple

from app.deduplicators.event_candidates import DeduplicationEvent
from app.deduplicators.event_deduplicator import (
    EventComparisonObservation,
    EventComparator,
    EventDeduplicator,
)
from app.deduplicators.event_policy import DeduplicationRelation
from app.models.news_event import EventType, NewsEvent


def _event(title: str) -> NewsEvent:
    return NewsEvent(
        title=title,
        summary="동일한 사건 요약입니다.",
        event_type=EventType.CORPORATE_EVENT,
        companies=[],
        industries=[],
        keywords=["실적"],
        reasons=["기사에 명시되어 있습니다."],
    )


class _Comparator(EventComparator):
    async def compare(
        self,
        candidates: Tuple[object, ...],
    ) -> Tuple[EventComparisonObservation, ...]:
        return (
            EventComparisonObservation(
                left_event_id="one",
                right_event_id="two",
                relation=DeduplicationRelation.SAME,
                confidence=80,
                reasons=("같은 실적 발표입니다.",),
            ),
            EventComparisonObservation(
                left_event_id="two",
                right_event_id="three",
                relation=DeduplicationRelation.SAME,
                confidence=80,
                reasons=("같은 발표의 후속 보도입니다.",),
            ),
        )


def test_event_deduplicator_merges_transitive_same_event_cluster() -> None:
    now = datetime(2026, 8, 4, tzinfo=timezone.utc)
    result = asyncio.run(
        EventDeduplicator(_Comparator()).deduplicate(
            (
            DeduplicationEvent(id="one", event=_event("A사 실적 발표"), published_at=now),
            DeduplicationEvent(id="two", event=_event("A사 실적 발표"), published_at=now),
            DeduplicationEvent(id="three", event=_event("A사 실적 발표"), published_at=now),
            )
        )
    )

    assert tuple(item.id for item in result.canonical_events) == ("one",)
    assert result.canonical_by_event_id == {"one": "one", "two": "one", "three": "one"}
    assert len(result.observations) == 2
