from __future__ import annotations

from datetime import datetime, timedelta
from itertools import combinations
from typing import Tuple

from app.models.news_event import NewsEvent
from pydantic import BaseModel, ConfigDict, Field


class DeduplicationEvent(BaseModel):
    id: str
    event: NewsEvent
    published_at: datetime
    source: str = ""
    content_length: int = 0


class EventComparisonCandidate(BaseModel):
    left: DeduplicationEvent
    right: DeduplicationEvent


class EventCandidateGenerator:
    """Build a bounded, deterministic set of plausible same-event pairs."""

    _MAX_AGE: timedelta = timedelta(days=7)
    _SIMILARITY: float = 0.5
    _MAX_CANDIDATES: int = 100

    def generate(
        self,
        events: Tuple[DeduplicationEvent, ...],
    ) -> Tuple[EventComparisonCandidate, ...]:
        candidates: Tuple[EventComparisonCandidate, ...] = tuple(
            EventComparisonCandidate(left=left, right=right)
            for left, right in combinations(events, 2)
            if self._is_candidate(left, right)
        )
        return candidates[: self._MAX_CANDIDATES]

    def _is_candidate(self, left: DeduplicationEvent, right: DeduplicationEvent) -> bool:
        if abs(left.published_at - right.published_at) > self._MAX_AGE:
            return False
        if self._normalize(left.event.title) == self._normalize(right.event.title):
            return True
        if left.event.event_type is not right.event.event_type:
            return False
        left_companies = {item.name.casefold() for item in left.event.companies}
        right_companies = {item.name.casefold() for item in right.event.companies}
        if not left_companies.intersection(right_companies):
            return False
        return (
            self._jaccard(set(left.event.keywords), set(right.event.keywords)) >= self._SIMILARITY
            or self._jaccard(set(self._tokens(left.event.title)), set(self._tokens(right.event.title))) >= self._SIMILARITY
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().split())

    @classmethod
    def _tokens(cls, value: str) -> Tuple[str, ...]:
        return tuple(token for token in cls._normalize(value).split(" ") if token)

    @staticmethod
    def _jaccard(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)
    model_config = ConfigDict(frozen=True)

    model_config = ConfigDict(frozen=True)
