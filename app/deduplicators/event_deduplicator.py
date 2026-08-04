from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Protocol, Tuple

from app.deduplicators.canonical_selector import CanonicalEventSelector, CanonicalEventSnapshot
from app.deduplicators.event_candidates import (
    DeduplicationEvent,
    EventCandidateGenerator,
    EventComparisonCandidate,
)
from app.deduplicators.event_policy import DeduplicationRelation, EventDeduplicationPolicy


@dataclass(frozen=True)
class EventComparisonObservation:
    """One validated same-event observation; policy retains decision ownership."""

    left_event_id: str
    right_event_id: str
    relation: DeduplicationRelation
    confidence: int
    reasons: Tuple[str, ...] = ()


class EventComparator(Protocol):
    """Compares only deterministic candidate pairs and returns observations."""

    async def compare(
        self,
        candidates: Tuple[EventComparisonCandidate, ...],
    ) -> Tuple[EventComparisonObservation, ...]:
        """Return at most one observation for each requested candidate pair."""


@dataclass(frozen=True)
class EventDeduplicationResult:
    """Canonical projection plus durable observations for harness persistence."""

    canonical_events: Tuple[DeduplicationEvent, ...]
    canonical_by_event_id: Dict[str, str]
    observations: Tuple[EventComparisonObservation, ...]


class EventDeduplicator:
    """Clusters only policy-approved same-event observations transitively."""

    def __init__(
        self,
        comparator: EventComparator,
        candidate_generator: EventCandidateGenerator | None = None,
        policy: EventDeduplicationPolicy | None = None,
        canonical_selector: CanonicalEventSelector | None = None,
    ) -> None:
        self._comparator: EventComparator = comparator
        self._candidate_generator: EventCandidateGenerator = (
            candidate_generator or EventCandidateGenerator()
        )
        self._policy: EventDeduplicationPolicy = policy or EventDeduplicationPolicy()
        self._canonical_selector: CanonicalEventSelector = (
            canonical_selector or CanonicalEventSelector()
        )

    async def deduplicate(
        self,
        events: Tuple[DeduplicationEvent, ...],
    ) -> EventDeduplicationResult:
        candidates: Tuple[EventComparisonCandidate, ...] = self._candidate_generator.generate(events)
        observations: Tuple[EventComparisonObservation, ...] = await self._comparator.compare(candidates)
        candidate_keys: set[tuple[str, str]] = {
            self._pair_key(candidate.left.id, candidate.right.id) for candidate in candidates
        }
        parents: Dict[str, str] = {event.id: event.id for event in events}
        for observation in observations:
            key: tuple[str, str] = self._pair_key(
                observation.left_event_id,
                observation.right_event_id,
            )
            if key not in candidate_keys:
                continue
            if self._policy.should_merge(observation.relation, observation.confidence):
                self._union(parents, observation.left_event_id, observation.right_event_id)
        clusters: Dict[str, list[DeduplicationEvent]] = {}
        for event in events:
            clusters.setdefault(self._find(parents, event.id), []).append(event)
        canonical_by_event_id: Dict[str, str] = {}
        canonical_events: list[DeduplicationEvent] = []
        for cluster in clusters.values():
            canonical: DeduplicationEvent = self._select_canonical(tuple(cluster))
            canonical_events.append(canonical)
            for event in cluster:
                canonical_by_event_id[event.id] = canonical.id
        return EventDeduplicationResult(
            canonical_events=tuple(canonical_events),
            canonical_by_event_id=canonical_by_event_id,
            observations=observations,
        )

    def _select_canonical(
        self,
        events: Tuple[DeduplicationEvent, ...],
    ) -> DeduplicationEvent:
        snapshots: Tuple[CanonicalEventSnapshot, ...] = tuple(
            CanonicalEventSnapshot(
                id=item.id,
                source=item.source,
                evidence_count=len(item.event.evidence),
                content_length=item.content_length,
                published_at=item.published_at,
            )
            for item in events
        )
        selected: CanonicalEventSnapshot = self._canonical_selector.select(snapshots)
        return next(event for event in events if event.id == selected.id)

    @staticmethod
    def _pair_key(left: str, right: str) -> tuple[str, str]:
        return tuple(sorted((left, right)))

    @staticmethod
    def _find(parents: Dict[str, str], event_id: str) -> str:
        parent: str = parents[event_id]
        if parent != event_id:
            parents[event_id] = EventDeduplicator._find(parents, parent)
        return parents[event_id]

    @classmethod
    def _union(cls, parents: Dict[str, str], left: str, right: str) -> None:
        left_root: str = cls._find(parents, left)
        right_root: str = cls._find(parents, right)
        if left_root != right_root:
            parents[right_root] = left_root


class DeterministicEventComparator:
    """Mock-mode comparator with the same observation contract as an LLM comparator."""

    async def compare(
        self,
        candidates: Tuple[EventComparisonCandidate, ...],
    ) -> Tuple[EventComparisonObservation, ...]:
        return tuple(
            EventComparisonObservation(
                left_event_id=candidate.left.id,
                right_event_id=candidate.right.id,
                relation=DeduplicationRelation.UNCERTAIN,
                confidence=0,
                reasons=("Mock mode cannot establish same-event identity.",),
            )
            for candidate in candidates
        )
