from __future__ import annotations

from enum import Enum
from typing import List, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, field_validator, model_validator

from app.models.article import Article
from app.models.news_event import NewsEvent
from app.models.screening import ScreeningDecision


class CrossValidationStatus(str, Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    CONFLICTED = "conflicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class EvidenceRelation(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    PARTIAL = "partial"
    UNRELATED = "unrelated"


class ValidationEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)
    article_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    relation: EvidenceRelation
    matched_claims: Tuple[str, ...]
    conflicting_claims: Tuple[str, ...]


class CrossValidationCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    candidate_id: str = Field(min_length=1)
    decision: ScreeningDecision
    source_article: Article
    related_articles: Tuple[Article, ...]

    @model_validator(mode="after")
    def _exclude_source_article(self) -> "CrossValidationCandidate":
        if any(article.id == self.source_article.id for article in self.related_articles):
            raise ValueError("Source article cannot be included in related articles")
        if len({article.id for article in self.related_articles}) != len(self.related_articles):
            raise ValueError("Related article IDs must be unique")
        return self


class CrossValidationAssessmentEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)
    article_id: str = Field(min_length=1)
    relation: EvidenceRelation
    matched_claims: Tuple[str, ...] = ()
    conflicting_claims: Tuple[str, ...] = ()


class CrossValidationAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    candidate_id: str = Field(min_length=1)
    confidence: int = Field(ge=0, le=100)
    evidence: Tuple[CrossValidationAssessmentEvidence, ...] = ()
    reasons: Tuple[str, ...] = Field(min_length=1, max_length=3)

    @field_validator("reasons")
    @classmethod
    def _validate_reasons(cls, reasons: Tuple[str, ...]) -> Tuple[str, ...]:
        if any(not reason.strip() for reason in reasons):
            raise ValueError("Cross validation assessment reasons must not be blank")
        return reasons


IndexValue = Union[StrictInt, StrictStr, StrictBool, None]
ScoreValue = Union[StrictInt, StrictFloat, StrictStr, StrictBool, None]
RelationValue = Union[StrictStr, StrictInt, StrictBool, None]
TextListValue = Union[StrictStr, StrictInt, StrictFloat, StrictBool, None]


class CrossValidationEvidenceResponseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_index: IndexValue = None
    relation: RelationValue = None
    matched_claims: List[TextListValue] = Field(default_factory=list)
    conflicting_claims: List[TextListValue] = Field(default_factory=list)


class CrossValidationAssessmentResponseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_index: IndexValue = None
    evidence: List[CrossValidationEvidenceResponseItem] = Field(default_factory=list)
    confidence: ScoreValue = None
    reasons: List[TextListValue] = Field(default_factory=list)


class CrossValidationAssessmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessments: List[CrossValidationAssessmentResponseItem]


class CrossValidationParseErrorKind(str, Enum):
    INVALID_EVENT_INDEX = "invalid_event_index"
    DUPLICATE_EVENT_INDEX = "duplicate_event_index"
    MISSING_EVENT_INDEX = "missing_event_index"
    INVALID_EVIDENCE_INDEX = "invalid_evidence_index"
    DUPLICATE_EVIDENCE_INDEX = "duplicate_evidence_index"
    INVALID_RELATION = "invalid_relation"
    INVALID_MATCHED_CLAIMS = "invalid_matched_claims"
    INVALID_CONFLICTING_CLAIMS = "invalid_conflicting_claims"
    INVALID_CONFIDENCE = "invalid_confidence"
    INVALID_REASONS = "invalid_reasons"
    DOMAIN_CONVERSION = "domain_conversion"


class CrossValidationParseError(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: CrossValidationParseErrorKind
    event_index: Optional[int] = None
    evidence_index: Optional[int] = None
    candidate_id: Optional[str] = Field(default=None, min_length=1)
    article_id: Optional[str] = Field(default=None, min_length=1)


class CrossValidationParseResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    assessments: Tuple[CrossValidationAssessment, ...]
    errors: Tuple[CrossValidationParseError, ...] = ()


class CrossValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    event: NewsEvent
    status: CrossValidationStatus
    confidence: int = Field(ge=0, le=100)
    independent_source_count: int = Field(ge=0)
    evidence: Tuple[ValidationEvidence, ...]
    reasons: Tuple[str, ...] = Field(min_length=1, max_length=3)

    @field_validator("reasons")
    @classmethod
    def _validate_reasons(cls, reasons: Tuple[str, ...]) -> Tuple[str, ...]:
        if any(not reason.strip() for reason in reasons):
            raise ValueError("Cross validation result reasons must not be blank")
        return reasons


class BatchCrossValidationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_candidates_per_batch: int = Field(default=20, gt=0)
