from __future__ import annotations

from enum import Enum
from typing import Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class CrossValidationAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(min_length=1)
    confidence: int = Field(ge=0, le=100)
    supporting_article_ids: Tuple[str, ...] = ()
    partially_matching_article_ids: Tuple[str, ...] = ()
    contradicting_article_ids: Tuple[str, ...] = ()
    matched_claims: Tuple[str, ...] = ()
    conflicting_claims: Tuple[str, ...] = ()
    reasons: Tuple[str, ...] = Field(min_length=1, max_length=3)

    @field_validator("reasons")
    @classmethod
    def _validate_reasons(cls, reasons: Tuple[str, ...]) -> Tuple[str, ...]:
        if any(not reason.strip() for reason in reasons):
            raise ValueError("Cross validation assessment reasons must not be blank")
        return reasons


class CrossValidationAssessmentResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    assessments: Tuple[CrossValidationAssessment, ...]


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
