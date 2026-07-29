from __future__ import annotations

from typing import Optional, Protocol

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

    reject_relevance_below: int = Field(default=40, ge=0, le=100)
    reject_importance_below: int = Field(default=40, ge=0, le=100)
    accept_relevance_at_least: int = Field(default=70, ge=0, le=100)
    accept_importance_at_least: int = Field(default=70, ge=0, le=100)
    accept_credibility_at_least: int = Field(default=70, ge=0, le=100)

    @model_validator(mode="after")
    def _validate_threshold_order(self) -> "ScreeningPolicyConfig":
        if self.reject_relevance_below > self.accept_relevance_at_least:
            raise ValueError(
                "Reject relevance boundary must not exceed accept relevance boundary"
            )
        if self.reject_importance_below > self.accept_importance_at_least:
            raise ValueError(
                "Reject importance boundary must not exceed accept importance boundary"
            )
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

    def __init__(self, config: Optional[ScreeningPolicyConfig] = None) -> None:
        self._config: ScreeningPolicyConfig = (
            config if config is not None else ScreeningPolicyConfig()
        )

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
            assessment.relevance < self._config.reject_relevance_below
            or assessment.importance < self._config.reject_importance_below
        ):
            return ScreeningDecisionType.REJECT
        if assessment.requires_cross_validation:
            return ScreeningDecisionType.REVIEW
        if (
            assessment.relevance >= self._config.accept_relevance_at_least
            and assessment.importance >= self._config.accept_importance_at_least
            and assessment.credibility >= self._config.accept_credibility_at_least
        ):
            return ScreeningDecisionType.ACCEPT
        return ScreeningDecisionType.REVIEW
