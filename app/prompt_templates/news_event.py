from __future__ import annotations

import json
from typing import Any, Dict

from app.models.article import ArticleEvaluationResult
from app.models.news_event_response import NewsEventExtractionResponse

_SYSTEM_PROMPT: str = """You are a news event fact extractor.
Extract only facts explicitly stated or directly implied by the article.
Do not infer investment opportunities.
Do not classify companies as beneficiaries, victims, or competitors.
Do not recommend stocks or predict stock prices.
Do not produce ticker, sentiment, confidence, impact, or recommendation fields.
Use "direct" only for a central party to the event.
Use "indirect" only for a company explicitly mentioned and clearly connected to the event.
Do not infer companies that are absent from the article using external industry knowledge.
Return only valid JSON matching this schema:
{response_schema}
Do not add properties, markdown fences, or explanatory text.
"""
_USER_PROMPT: str = "Extract news events from this evaluated article:\n{evaluation_json}"


def build_news_event_system_prompt() -> str:
    """Render extraction rules with the shared LLM response contract."""
    response_schema: Dict[str, Any] = (
        NewsEventExtractionResponse.model_json_schema()
    )
    schema_json: str = json.dumps(response_schema, ensure_ascii=False)
    return _SYSTEM_PROMPT.format(response_schema=schema_json)


def build_news_event_user_prompt(
    evaluation: ArticleEvaluationResult,
) -> str:
    """Render an evaluated article for news event extraction."""
    evaluation_json: str = json.dumps(
        evaluation.model_dump(mode="json"),
        ensure_ascii=False,
    )
    return _USER_PROMPT.format(evaluation_json=evaluation_json)
