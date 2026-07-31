from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.models.article import Article
from app.models.news_event import NewsEvent


class BatchExtractionConfig(BaseModel):
    """Immutable policy controlling the maximum articles in one LLM batch."""

    model_config = ConfigDict(frozen=True)

    max_articles_per_batch: int = Field(default=20, gt=0)


class LLMInferenceResult(BaseModel):
    """Immutable article-level snapshot of validated LLM structured output.

    Confidence is the LLM's self-reported extraction confidence: whether the
    Event is explicitly supported by the article, not a fact-truth probability.
    Reasoning is a user-readable rationale, never internal chain of thought.
    The contained NewsEvent instances remain identical throughout the workflow
    and are consumed unchanged by downstream Domain services.
    """

    model_config = ConfigDict(frozen=True)

    article: Article
    events: Tuple[NewsEvent, ...]
    summary: str = Field(min_length=1)
    reasoning: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractionErrorKind(str, Enum):
    """Recoverable extraction failure categories safe for execution observation."""

    EVENT_VALIDATION = "event_validation"
    FACT_VALIDATION = "fact_validation"
    API_CALL = "api_call"
    RESPONSE_PROCESSING = "response_processing"


class ExtractionError(BaseModel):
    """Safe, non-sensitive observation of a recoverable extraction failure."""

    model_config = ConfigDict(frozen=True)

    kind: ExtractionErrorKind
    message: str = Field(min_length=1)
    article_ids: Tuple[str, ...] = ()
    event_index: Optional[int] = Field(default=None, ge=0)
    fact_index: Optional[int] = Field(default=None, ge=0)


class NewsEventParseResult(BaseModel):
    """Parser output preserving valid inferences beside rejected event observations."""

    model_config = ConfigDict(frozen=True)

    inferences: Tuple[LLMInferenceResult, ...]
    errors: Tuple[ExtractionError, ...] = ()


class LLMExtractionResult(BaseModel):
    """Immutable result of one extractor execution and successful batch count."""

    model_config = ConfigDict(frozen=True)

    inferences: Tuple[LLMInferenceResult, ...]
    successful_batches: int = Field(ge=0)
    errors: Tuple[ExtractionError, ...] = ()
