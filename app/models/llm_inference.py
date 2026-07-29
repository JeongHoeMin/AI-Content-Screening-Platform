from __future__ import annotations

from typing import Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.models.article import Article
from app.models.news_event import NewsEvent


class BatchExtractionConfig(BaseModel):
    """Immutable policy controlling the maximum articles in one LLM request."""

    model_config = ConfigDict(frozen=True)

    max_articles_per_request: int = Field(default=20, gt=0)


class LLMInferenceResult(BaseModel):
    """Immutable article-level snapshot of validated LLM structured output.

    Confidence is the LLM's self-reported confidence, not a Domain correctness
    probability. Reasoning is a user-readable rationale, never internal chain
    of thought. The contained NewsEvent instances remain identical throughout
    the workflow and are consumed unchanged by downstream Domain services.
    """

    model_config = ConfigDict(frozen=True)

    article: Article
    events: Tuple[NewsEvent, ...]
    summary: str = Field(min_length=1)
    reasoning: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
