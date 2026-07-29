from __future__ import annotations

from typing import Dict, List, Set, Tuple

from pydantic import ValidationError

from app.extractors.errors import InferenceResultValidationError
from app.extractors.parser import NewsEventParser
from app.models.article import Article
from app.models.llm_inference import (
    ExtractionError,
    ExtractionErrorKind,
    LLMInferenceResult,
    NewsEventParseResult,
)
from app.models.news_event import CompanyRelation, ExtractedCompany, NewsEvent
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
    ) -> NewsEventParseResult:
        articles_by_id: Dict[str, Article] = self._index_articles(articles)
        responses_by_id: Dict[str, ArticleInferenceResponseItem] = (
            self._index_responses(response.articles)
        )
        self._validate_matching_ids(articles_by_id, responses_by_id)
        inferences: List[LLMInferenceResult] = []
        errors: List[ExtractionError] = []
        for article in articles:
            inference, inference_errors = self._map_inference(
                article,
                responses_by_id[article.id],
            )
            inferences.append(inference)
            errors.extend(inference_errors)
        return NewsEventParseResult(
            inferences=tuple(inferences),
            errors=tuple(errors),
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
    ) -> tuple[LLMInferenceResult, Tuple[ExtractionError, ...]]:
        try:
            summary: str = DefaultNewsEventParser._normalize_required(
                response_item.summary,
                "Article summary",
            )
            reasoning: str = DefaultNewsEventParser._normalize_required(
                response_item.reasoning,
                "Article reasoning",
            )
        except ValueError as error:
            raise InferenceResultValidationError(str(error)) from error
        events: List[NewsEvent] = []
        errors: List[ExtractionError] = []
        for event_index, event in enumerate(response_item.events):
            try:
                events.append(DefaultNewsEventParser._map_event(event))
            except (ValueError, ValidationError) as error:
                errors.append(
                    ExtractionError(
                        kind=ExtractionErrorKind.EVENT_VALIDATION,
                        message=str(error),
                        article_ids=(article.id,),
                        event_index=event_index,
                    )
                )
        inference: LLMInferenceResult = LLMInferenceResult(
            article=article,
            events=tuple(events),
            summary=summary,
            reasoning=reasoning,
            confidence=response_item.confidence,
        )
        return inference, tuple(errors)

    @staticmethod
    def _map_event(response_item: NewsEventResponseItem) -> NewsEvent:
        companies: List[ExtractedCompany] = []
        company_names: Set[str] = set()
        for company in response_item.companies:
            extracted: ExtractedCompany = DefaultNewsEventParser._map_company(company)
            company_key: str = extracted.name.casefold()
            if company_key not in company_names:
                company_names.add(company_key)
                companies.append(extracted)
        return NewsEvent(
            title=DefaultNewsEventParser._normalize_required(
                response_item.title,
                "Event title",
            ),
            summary=DefaultNewsEventParser._normalize_required(
                response_item.summary,
                "Event summary",
            ),
            companies=companies,
            industries=DefaultNewsEventParser._normalize_unique(response_item.industries, True),
            keywords=DefaultNewsEventParser._normalize_unique(response_item.keywords, True),
            reasons=DefaultNewsEventParser._normalize_unique(response_item.reasons, False),
        )

    @staticmethod
    def _map_company(
        response_item: ExtractedCompanyResponseItem,
    ) -> ExtractedCompany:
        return ExtractedCompany(
            name=DefaultNewsEventParser._normalize_required(
                response_item.name,
                "Company name",
            ),
            relation=CompanyRelation(response_item.relation),
        )

    @staticmethod
    def _normalize_required(value: str, field_name: str) -> str:
        normalized: str = " ".join(value.split())
        if not normalized:
            raise ValueError(f"{field_name} must not be empty")
        return normalized

    @staticmethod
    def _normalize_unique(values: List[str], case_insensitive: bool) -> List[str]:
        normalized_values: List[str] = []
        seen: Set[str] = set()
        for value in values:
            normalized: str = " ".join(value.split())
            if not normalized:
                continue
            key: str = normalized.casefold() if case_insensitive else normalized
            if key not in seen:
                seen.add(key)
                normalized_values.append(normalized)
        return normalized_values
