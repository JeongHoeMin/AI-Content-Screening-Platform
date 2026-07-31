from __future__ import annotations

import re
from typing import Tuple

from app.models.article import Article
from app.models.llm_inference import LLMExtractionResult, LLMInferenceResult
from app.models.news_event import (
    CompanyRelation,
    EventFact,
    EventType,
    ExtractedCompany,
    NewsEvent,
)


class DartFilingEventAugmenter:
    """Adds only explicitly titled DART supply-contract facts to an inference."""

    _SOURCE: str = "dart"
    _COMPANY_NAME_PATTERN: re.Pattern[str] = re.compile(
        r"^(?P<company_name>.+?)\s*\(종목코드:",
    )

    def augment(self, result: LLMExtractionResult) -> LLMExtractionResult:
        """Append a missing official-contract observation to each matching inference."""
        inferences: Tuple[LLMInferenceResult, ...] = tuple(
            self._augment_inference(inference) for inference in result.inferences
        )
        return result.model_copy(update={"inferences": inferences})

    def _augment_inference(self, inference: LLMInferenceResult) -> LLMInferenceResult:
        event: NewsEvent | None = self._event_for(inference.article)
        if event is None or self._contains_major_supply_contract(inference.events):
            return inference
        return inference.model_copy(update={"events": inference.events + (event,)})

    @classmethod
    def _event_for(cls, article: Article) -> NewsEvent | None:
        if article.source.strip().casefold() != cls._SOURCE:
            return None
        if "단일판매" not in article.title or "공급계약체결" not in article.title:
            return None
        company_name: str | None = cls._company_name(article.content)
        if company_name is None:
            return None
        return NewsEvent(
            title="단일판매·공급계약체결",
            summary="DART 공시 제목에 단일판매·공급계약체결이 명시되었습니다.",
            event_type=EventType.FINANCIAL_EVENT,
            event_facts=(EventFact.MAJOR_SUPPLY_CONTRACT,),
            companies=[
                ExtractedCompany(
                    name=company_name,
                    relation=CompanyRelation.DIRECT,
                )
            ],
            industries=[],
            keywords=["단일판매", "공급계약"],
            reasons=["DART 공식 공시 제목과 종목명이 직접 명시되었습니다."],
        )

    @classmethod
    def _company_name(cls, content: str) -> str | None:
        match: re.Match[str] | None = cls._COMPANY_NAME_PATTERN.search(content)
        if match is None:
            return None
        company_name: str = " ".join(match.group("company_name").split())
        return company_name or None

    @staticmethod
    def _contains_major_supply_contract(events: Tuple[NewsEvent, ...]) -> bool:
        return any(
            EventFact.MAJOR_SUPPLY_CONTRACT in event.event_facts for event in events
        )
