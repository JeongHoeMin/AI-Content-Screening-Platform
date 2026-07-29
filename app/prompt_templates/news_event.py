from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from app.models.article import Article
from app.models.news_event_response import NewsEventExtractionResponse

_SYSTEM_PROMPT: str = """You are a batch news event fact extractor.
Return exactly one result for every input article using its unchanged article_id.
Extract only facts explicitly stated or directly implied by each article.
Do not infer investment opportunities.
Do not classify companies as beneficiaries, victims, or competitors.
Do not recommend stocks or predict stock prices.
Use "direct" only for a central party to the event.
Use "indirect" only for a company explicitly mentioned and clearly connected to the event.
Do not infer companies that are absent from the article using external industry knowledge.
For each article, provide a concise factual summary, a one or two sentence
user-readable rationale describing the extracted event facts, and a confidence
between 0.0 and 1.0. Do not reveal private chain-of-thought or internal reasoning.
Return only valid JSON matching this schema:
{response_schema}
Do not add properties, markdown fences, or explanatory text.
"""
_USER_PROMPT: str = "Extract news events from these accepted articles:\n{articles_json}"


def build_news_event_system_prompt() -> str:
    """Render extraction rules with the shared LLM response contract."""
    response_schema: Dict[str, Any] = (
        NewsEventExtractionResponse.model_json_schema()
    )
    schema_json: str = json.dumps(response_schema, ensure_ascii=False)
    return _SYSTEM_PROMPT.format(response_schema=schema_json)


def build_news_event_user_prompt(articles: Tuple[Article, ...]) -> str:
    """Render accepted source articles for batch event extraction."""
    article_data: list[Dict[str, Any]] = [
        article.model_dump(mode="json") for article in articles
    ]
    articles_json: str = json.dumps(
        article_data,
        ensure_ascii=False,
    )
    return _USER_PROMPT.format(articles_json=articles_json)
