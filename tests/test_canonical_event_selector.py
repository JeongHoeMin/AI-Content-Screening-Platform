from __future__ import annotations

from datetime import datetime, timezone

from app.deduplicators.canonical_selector import CanonicalEventSelector, CanonicalEventSnapshot


def test_selector_prefers_dart_before_longer_non_dart_content() -> None:
    selected = CanonicalEventSelector().select(
        (
            CanonicalEventSnapshot("rss", "ir_rss", 2, 5000, datetime(2026, 8, 3, tzinfo=timezone.utc)),
            CanonicalEventSnapshot("dart", "dart", 1, 100, datetime(2026, 8, 4, tzinfo=timezone.utc)),
        )
    )

    assert selected.id == "dart"
