from __future__ import annotations

from app.deduplicators.event_policy import DeduplicationRelation, EventDeduplicationPolicy


def test_policy_merges_only_same_event_at_confidence_80_or_higher() -> None:
    policy = EventDeduplicationPolicy()

    assert policy.should_merge(DeduplicationRelation.SAME, 80) is True
    assert policy.should_merge(DeduplicationRelation.SAME, 79) is False
    assert policy.should_merge(DeduplicationRelation.UNCERTAIN, 100) is False
