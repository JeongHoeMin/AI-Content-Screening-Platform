from __future__ import annotations

from enum import Enum
from typing import List, Optional, Tuple, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
)

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
    """Strict OpenAI DTO that is intentionally separate from Domain assessments."""

    model_config = ConfigDict(extra="forbid")

    assessments: List["ScreeningAssessmentResponseItem"]


IndexValue = Union[StrictInt, StrictStr, StrictBool, None]
ScoreValue = Union[StrictInt, StrictFloat, StrictStr, StrictBool, None]
BooleanValue = Union[StrictBool, StrictInt, StrictStr, None]
ReasonValue = Union[StrictStr, StrictInt, StrictFloat, StrictBool, None]


class ScreeningAssessmentResponseItem(BaseModel):
    """One loose-score LLM response correlated by request-local event index."""

    model_config = ConfigDict(extra="forbid")

    event_index: IndexValue = None
    relevance: ScoreValue = None
    importance: ScoreValue = None
    credibility: ScoreValue = None
    requires_cross_validation: BooleanValue = None
    reasons: List[ReasonValue] = Field(default_factory=list)


class ScreeningParseErrorKind(str, Enum):
    """Safe, bounded categories for rejected LLM screening output."""

    INVALID_EVENT_INDEX = "invalid_event_index"
    DUPLICATE_EVENT_INDEX = "duplicate_event_index"
    MISSING_EVENT_INDEX = "missing_event_index"
    INVALID_SCORE = "invalid_score"
    INVALID_CROSS_VALIDATION_FLAG = "invalid_cross_validation_flag"
    INVALID_REASONS = "invalid_reasons"
    DOMAIN_CONVERSION = "domain_conversion"


class ScreeningParseError(BaseModel):
    """Non-sensitive observation of one invalid screening response item."""

    model_config = ConfigDict(frozen=True)

    kind: ScreeningParseErrorKind
    event_index: Optional[int] = None
    candidate_id: Optional[str] = Field(default=None, min_length=1)


class ScreeningParseResult(BaseModel):
    """Immutable parser outcome preserving valid assessments beside errors."""

    model_config = ConfigDict(frozen=True)

    assessments: Tuple[ScreeningAssessment, ...]
    errors: Tuple[ScreeningParseError, ...] = ()


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
