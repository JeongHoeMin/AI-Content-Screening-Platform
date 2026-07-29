from __future__ import annotations

from enum import Enum
from typing import Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.article import Article
from app.models.news_event import NewsEvent


class ScreeningDecisionType(str, Enum):
    """Final action selected by the deterministic screening policy."""

    ACCEPT = "accept"
    REVIEW = "review"
    REJECT = "reject"


class ScreeningCandidate(BaseModel):
    """Immutable event input that preserves Article context and Event identity.

    candidate_id is a request-local correlation key for matching a structured
    LLM assessment to its input event. It is not a persistent NewsEvent ID.
    """

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(min_length=1)
    article: Article
    event: NewsEvent


class ScreeningAssessment(BaseModel):
    """Immutable structured LLM assessment without a final policy decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(min_length=1)
    relevance: int = Field(ge=0, le=100)
    importance: int = Field(ge=0, le=100)
    credibility: int = Field(ge=0, le=100)
    requires_cross_validation: bool
    reasons: Tuple[str, ...] = Field(min_length=1, max_length=3)

    @field_validator("reasons")
    @classmethod
    def _validate_reasons(cls, reasons: Tuple[str, ...]) -> Tuple[str, ...]:
        if any(not reason.strip() for reason in reasons):
            raise ValueError("Screening assessment reasons must not be blank")
        return reasons


class ScreeningAssessmentResponse(BaseModel):
    """Strict batch response returned by StructuredOutputLLM for screening."""

    model_config = ConfigDict(extra="forbid")

    assessments: Tuple[ScreeningAssessment, ...]


class ScreeningDecision(BaseModel):
    """Immutable policy decision retaining the identical assessed NewsEvent."""

    model_config = ConfigDict(frozen=True)

    event: NewsEvent
    decision: ScreeningDecisionType
    relevance: int = Field(ge=0, le=100)
    importance: int = Field(ge=0, le=100)
    credibility: int = Field(ge=0, le=100)
    requires_cross_validation: bool
    reasons: Tuple[str, ...] = Field(min_length=1, max_length=3)

    @field_validator("reasons")
    @classmethod
    def _validate_reasons(cls, reasons: Tuple[str, ...]) -> Tuple[str, ...]:
        if any(not reason.strip() for reason in reasons):
            raise ValueError("Screening decision reasons must not be blank")
        return reasons


class BatchScreeningConfig(BaseModel):
    """Immutable policy controlling the maximum events in one LLM batch."""

    model_config = ConfigDict(frozen=True)

    max_events_per_batch: int = Field(default=20, gt=0)
