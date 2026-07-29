from __future__ import annotations

import json
from typing import Any, List

from app.extractors.parser import NewsEventParser
from app.llms.models import ChatResponse
from app.models.article import ArticleEvaluationResult
from app.models.news_event import ExtractedCompany, NewsEvent
from app.models.news_event_response import (
    ExtractedCompanyResponseItem,
    NewsEventExtractionResponse,
    NewsEventResponseItem,
)


class DefaultNewsEventParser(NewsEventParser):
    """Validates the LLM contract and maps it to news event values."""

    def parse(
        self,
        response: ChatResponse,
        evaluation: ArticleEvaluationResult,
    ) -> List[NewsEvent]:
        payload: Any = json.loads(response.content)
        extraction_response: NewsEventExtractionResponse = (
            NewsEventExtractionResponse.model_validate(payload)
        )
        return [
            self._map_event(response_item)
            for response_item in extraction_response.events
        ]

    @staticmethod
    def _map_event(response_item: NewsEventResponseItem) -> NewsEvent:
        companies: List[ExtractedCompany] = [
            DefaultNewsEventParser._map_company(company)
            for company in response_item.companies
        ]
        return NewsEvent(
            title=response_item.title,
            summary=response_item.summary,
            companies=companies,
            industries=list(response_item.industries),
            keywords=list(response_item.keywords),
            reasons=list(response_item.reasons),
        )

    @staticmethod
    def _map_company(
        response_item: ExtractedCompanyResponseItem,
    ) -> ExtractedCompany:
        return ExtractedCompany(
            name=response_item.name,
            relation=response_item.relation,
        )
