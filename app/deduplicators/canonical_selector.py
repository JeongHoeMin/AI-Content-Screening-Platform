from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Tuple


@dataclass(frozen=True)
class CanonicalEventSnapshot:
    id: str
    source: str
    evidence_count: int
    content_length: int
    published_at: datetime


class CanonicalEventSelector:
    """Select one reproducible representative without mutating cluster members."""

    def select(self, events: Tuple[CanonicalEventSnapshot, ...]) -> CanonicalEventSnapshot:
        if not events:
            raise ValueError("Canonical event selection requires at least one event")
        return min(events, key=self._rank)

    @staticmethod
    def _rank(event: CanonicalEventSnapshot) -> tuple[int, int, int, datetime, str]:
        return (
            0 if event.source == "dart" else 1,
            -event.evidence_count,
            -event.content_length,
            event.published_at,
            event.id,
        )
