from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.recommendation import RecommendationResult


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


class ScreeningResult(BaseModel):
    """Separates recommendation output from workflow execution metadata."""

    model_config = ConfigDict(frozen=True)

    recommendation: RecommendationResult
    statistics: WorkflowStatistics
