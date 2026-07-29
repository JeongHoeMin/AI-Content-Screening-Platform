from __future__ import annotations

from typing import Protocol

from app.models.news_event import NewsEvent


class DuplicateStrategy(Protocol):
    """Determines whether two events represent the same real-world event.

    Implementations are deterministic and side-effect free. They do not mutate
    either input, create domain objects, merge events, or wrap exceptions.
    Duplicate decisions are symmetric and reflexive.
    """

    def is_duplicate(
        self,
        left: NewsEvent,
        right: NewsEvent,
    ) -> bool:
        """Return whether the two events represent the same incident."""
        ...
