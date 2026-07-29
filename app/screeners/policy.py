from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.news_event import NewsEvent
from app.models.screening import (
    ScreeningAssessment,
    ScreeningDecision,
    ScreeningDecisionType,
)


class ScreeningPolicyConfig(BaseModel):
    """Immutable, injectable thresholds for the v1 screening policy."""

    model_config = ConfigDict(frozen=True)

    reject_relevance_threshold: int = Field(default=40, ge=0, le=100)
    reject_importance_threshold: int = Field(default=40, ge=0, le=100)
    accept_relevance_threshold: int = Field(default=70, ge=0, le=100)
    accept_importance_threshold: int = Field(default=70, ge=0, le=100)
    accept_credibility_threshold: int = Field(default=70, ge=0, le=100)

    @model_validator(mode="after")
    def _validate_threshold_order(self) -> "ScreeningPolicyConfig":
        if self.reject_relevance_threshold > self.accept_relevance_threshold:
            raise ValueError("Reject relevance threshold must not exceed accept threshold")
        if self.reject_importance_threshold > self.accept_importance_threshold:
            raise ValueError("Reject importance threshold must not exceed accept threshold")
        return self


class ScreeningPolicy(Protocol):
    """Deterministically converts one LLM assessment into a final decision."""

    def decide(
        self,
        event: NewsEvent,
        assessment: ScreeningAssessment,
    ) -> ScreeningDecision:
        """Return a decision without replacing the supplied NewsEvent instance."""
        ...


class DefaultScreeningPolicy(ScreeningPolicy):
    """Applies the v1 reject, review, accept, then default review order."""

    def __init__(self, config: ScreeningPolicyConfig = ScreeningPolicyConfig()) -> None:
        self._config: ScreeningPolicyConfig = config

    def decide(
        self,
        event: NewsEvent,
        assessment: ScreeningAssessment,
    ) -> ScreeningDecision:
        return ScreeningDecision(
            event=event,
            decision=self._decision_type(assessment),
            relevance=assessment.relevance,
            importance=assessment.importance,
            credibility=assessment.credibility,
            requires_cross_validation=assessment.requires_cross_validation,
            reasons=assessment.reasons,
        )

    def _decision_type(
        self,
        assessment: ScreeningAssessment,
    ) -> ScreeningDecisionType:
        if (
            assessment.relevance < self._config.reject_relevance_threshold
            or assessment.importance < self._config.reject_importance_threshold
        ):
            return ScreeningDecisionType.REJECT
        if assessment.requires_cross_validation:
            return ScreeningDecisionType.REVIEW
        if (
            assessment.relevance >= self._config.accept_relevance_threshold
            and assessment.importance >= self._config.accept_importance_threshold
            and assessment.credibility >= self._config.accept_credibility_threshold
        ):
            return ScreeningDecisionType.ACCEPT
        return ScreeningDecisionType.REVIEW
