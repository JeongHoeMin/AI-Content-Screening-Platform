from __future__ import annotations

from typing import Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.recommendation import RecommendationResult
from app.models.screening import ScreeningDecision


class WorkflowContext(BaseModel):
    """Immutable extension point for future workflow execution context."""

    model_config = ConfigDict(frozen=True)


class WorkflowStatistics(BaseModel):
    """Immutable observability metadata for one workflow execution."""

    model_config = ConfigDict(frozen=True)

    total_articles: int = Field(ge=0)
    accepted_articles: int = Field(ge=0)
    rejected_articles: int = Field(ge=0)
    extracted_events: int = Field(ge=0)
    successful_batches: int = Field(ge=0)
    accepted_events: int = Field(ge=0)
    review_events: int = Field(ge=0)
    rejected_events: int = Field(ge=0)


class ScreeningResult(BaseModel):
    """Separates decisions and recommendation output from execution metadata."""

    model_config = ConfigDict(frozen=True)

    recommendation: RecommendationResult
    decisions: Tuple[ScreeningDecision, ...]
    statistics: WorkflowStatistics

    @model_validator(mode="after")
    def _validate_decision_statistics(self) -> "ScreeningResult":
        decision_total: int = (
            self.statistics.accepted_events
            + self.statistics.review_events
            + self.statistics.rejected_events
        )
        if decision_total != len(self.decisions):
            raise ValueError("Decision statistics must equal the decision count")
        return self
