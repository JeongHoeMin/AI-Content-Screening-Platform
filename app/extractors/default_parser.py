from __future__ import annotations

from typing import Dict, List, Set, Tuple

from app.extractors.errors import InferenceResultValidationError
from app.extractors.parser import NewsEventParser
from app.models.article import Article
from app.models.llm_inference import LLMInferenceResult
from app.models.news_event import ExtractedCompany, NewsEvent
from app.models.news_event_response import (
    ArticleInferenceResponseItem,
    ExtractedCompanyResponseItem,
    NewsEventExtractionResponse,
    NewsEventResponseItem,
)


class DefaultNewsEventParser(NewsEventParser):
    """Validates batch inference identity and maps events without reordering."""

    def parse(
        self,
        response: NewsEventExtractionResponse,
        articles: Tuple[Article, ...],
    ) -> Tuple[LLMInferenceResult, ...]:
        articles_by_id: Dict[str, Article] = self._index_articles(articles)
        responses_by_id: Dict[str, ArticleInferenceResponseItem] = (
            self._index_responses(response.articles)
        )
        self._validate_matching_ids(articles_by_id, responses_by_id)
        return tuple(
            self._map_inference(article, responses_by_id[article.id])
            for article in articles
        )

    @staticmethod
    def _index_articles(articles: Tuple[Article, ...]) -> Dict[str, Article]:
        articles_by_id: Dict[str, Article] = {article.id: article for article in articles}
        if len(articles_by_id) != len(articles):
            raise InferenceResultValidationError("Input articles contain duplicate IDs")
        return articles_by_id

    @staticmethod
    def _index_responses(
        responses: List[ArticleInferenceResponseItem],
    ) -> Dict[str, ArticleInferenceResponseItem]:
        responses_by_id: Dict[str, ArticleInferenceResponseItem] = {
            response.article_id: response for response in responses
        }
        if len(responses_by_id) != len(responses):
            raise InferenceResultValidationError("LLM output contains duplicate article IDs")
        return responses_by_id

    @staticmethod
    def _validate_matching_ids(
        articles_by_id: Dict[str, Article],
        responses_by_id: Dict[str, ArticleInferenceResponseItem],
    ) -> None:
        article_ids: Set[str] = set(articles_by_id)
        response_ids: Set[str] = set(responses_by_id)
        if article_ids != response_ids:
            raise InferenceResultValidationError(
                "LLM output article IDs do not match input article IDs"
            )

    @staticmethod
    def _map_inference(
        article: Article,
        response_item: ArticleInferenceResponseItem,
    ) -> LLMInferenceResult:
        events: Tuple[NewsEvent, ...] = tuple(
            DefaultNewsEventParser._map_event(event)
            for event in response_item.events
        )
        return LLMInferenceResult(
            article=article,
            events=events,
            summary=response_item.summary,
            reasoning=response_item.reasoning,
            confidence=response_item.confidence,
        )

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
