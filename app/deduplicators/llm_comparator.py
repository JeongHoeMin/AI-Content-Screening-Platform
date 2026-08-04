from __future__ import annotations

from collections import Counter
from typing import List, Tuple

from app.deduplicators.event_candidates import EventComparisonCandidate
from app.deduplicators.event_deduplicator import EventComparator, EventComparisonObservation
from app.deduplicators.event_policy import DeduplicationRelation
from app.llms.structured import StructuredOutputLLM
from app.models.deduplication_comparison import DeduplicationComparisonResponse
from app.prompts.deduplication_comparison import (
    DeduplicationComparisonPromptBuilder,
    DeduplicationComparisonPromptInput,
)


class LLMEventComparator(EventComparator):
    """Calls an injected structured LLM and retains only parser-validated observations."""

    def __init__(
        self,
        structured_llm: StructuredOutputLLM,
        prompt_builder: DeduplicationComparisonPromptBuilder,
    ) -> None:
        self._structured_llm: StructuredOutputLLM = structured_llm
        self._prompt_builder: DeduplicationComparisonPromptBuilder = prompt_builder

    async def compare(
        self,
        candidates: Tuple[EventComparisonCandidate, ...],
    ) -> Tuple[EventComparisonObservation, ...]:
        if not candidates:
            return ()
        response: DeduplicationComparisonResponse = await self._structured_llm.generate(
            self._prompt_builder.build(DeduplicationComparisonPromptInput(candidates)),
            DeduplicationComparisonResponse,
        )
        return self._parse(response, candidates)

    @staticmethod
    def _parse(
        response: DeduplicationComparisonResponse,
        candidates: Tuple[EventComparisonCandidate, ...],
    ) -> Tuple[EventComparisonObservation, ...]:
        indexed: List[tuple[int, object]] = []
        for item in response.comparisons:
            if isinstance(item.candidate_index, bool) or not isinstance(item.candidate_index, int):
                continue
            indexed.append((item.candidate_index, item))
        counts: Counter[int] = Counter(index for index, _ in indexed)
        observations: List[EventComparisonObservation] = []
        for index, item in indexed:
            if index < 0 or index >= len(candidates) or counts[index] != 1:
                continue
            relation: DeduplicationRelation | None = LLMEventComparator._relation(item.relation)
            confidence: int | None = LLMEventComparator._confidence(item.confidence)
            reasons: Tuple[str, ...] | None = LLMEventComparator._reasons(item.reasons)
            if relation is None or confidence is None or reasons is None:
                continue
            candidate: EventComparisonCandidate = candidates[index]
            observations.append(
                EventComparisonObservation(
                    left_event_id=candidate.left.id,
                    right_event_id=candidate.right.id,
                    relation=relation,
                    confidence=confidence,
                    reasons=reasons,
                )
            )
        return tuple(observations)

    @staticmethod
    def _relation(value: object) -> DeduplicationRelation | None:
        if not isinstance(value, str):
            return None
        try:
            return DeduplicationRelation(value)
        except ValueError:
            return None

    @staticmethod
    def _confidence(value: object) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            return None
        return value

    @staticmethod
    def _reasons(value: object) -> Tuple[str, ...] | None:
        if not isinstance(value, list):
            return None
        reasons: list[str] = []
        for item in value:
            if not isinstance(item, str):
                return None
            text: str = " ".join(item.split())
            if text and text not in reasons:
                reasons.append(text)
        if not 1 <= len(reasons) <= 2:
            return None
        return tuple(reasons)
