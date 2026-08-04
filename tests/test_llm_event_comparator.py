from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List, Type, TypeVar

from pydantic import BaseModel

from app.deduplicators.event_candidates import DeduplicationEvent, EventCandidateGenerator
from app.deduplicators.llm_comparator import LLMEventComparator
from app.llms.models import ChatMessage
from app.llms.structured import StructuredOutputLLM
from app.models.deduplication_comparison import (
    DeduplicationComparisonResponse,
    DeduplicationComparisonResponseItem,
)
from app.models.news_event import EventType, NewsEvent
from app.prompts.deduplication_comparison import DeduplicationComparisonPromptBuilder

OutputT = TypeVar("OutputT", bound=BaseModel)


class StructuredOutputDouble(StructuredOutputLLM):
    def __init__(self) -> None:
        self.messages: List[ChatMessage] = []

    async def generate(
        self,
        messages: List[ChatMessage],
        response_model: Type[OutputT],
    ) -> OutputT:
        self.messages = messages
        return response_model.model_validate(
            {
                "comparisons": [
                    {
                        "candidate_index": 0,
                        "relation": "same",
                        "confidence": 80,
                        "reasons": ["같은 공시의 재보도입니다."],
                    }
                ]
            }
        )


def _event(title: str) -> NewsEvent:
    return NewsEvent(
        title=title,
        summary="발표 요약입니다.",
        event_type=EventType.CORPORATE_EVENT,
        companies=[],
        industries=[],
        keywords=["실적"],
        reasons=["원문에 명시됨"],
    )


def test_llm_event_comparator_returns_validated_candidate_observation() -> None:
    now = datetime(2026, 8, 4, tzinfo=timezone.utc)
    candidates = EventCandidateGenerator().generate(
        (
            DeduplicationEvent(id="left", event=_event("A사 실적 발표"), published_at=now),
            DeduplicationEvent(id="right", event=_event("A사 실적 발표"), published_at=now),
        )
    )
    llm = StructuredOutputDouble()
    comparator = LLMEventComparator(llm, DeduplicationComparisonPromptBuilder())

    observations = asyncio.run(comparator.compare(candidates))

    assert observations[0].left_event_id == "left"
    assert observations[0].right_event_id == "right"
    assert observations[0].confidence == 80
    assert "candidate_index" in llm.messages[1].content
