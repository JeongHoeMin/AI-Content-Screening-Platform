from __future__ import annotations

from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.recommendation import RecommendationResult
from app.models.candidate_selection import CandidateSelectionResult
from app.models.screening import ScreeningDecision
from app.models.cross_validation import CrossValidationResult
from app.models.resolved_news_event import ResolvedNewsEvent


class WorkflowImpactDiagnostics(BaseModel):
    """Safe counts explaining how resolved events reached stock evidence."""

    model_config = ConfigDict(frozen=True)

    events_without_impact_observations: int = Field(default=0, ge=0)
    failed_extraction_batches: int = Field(default=0, ge=0)
    malformed_extraction_items: int = Field(default=0, ge=0)
    total_impact_observations: int = Field(default=0, ge=0)
    eligible_impact_observations: int = Field(default=0, ge=0)
    event_rejected_exclusions: int = Field(default=0, ge=0)
    review_not_verified_exclusions: int = Field(default=0, ge=0)
    unresolved_company_exclusions: int = Field(default=0, ge=0)
    missing_company_identity_exclusions: int = Field(default=0, ge=0)
    unsupported_scope_exclusions: int = Field(default=0, ge=0)
    unknown_direction_exclusions: int = Field(default=0, ge=0)
    scored_company_count: int = Field(default=0, ge=0)


class WorkflowArticleAnalysisProgress(BaseModel):
    """Safe extraction summary for one article in a live workflow consumer."""

    model_config = ConfigDict(frozen=True)

    article_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    reasoning: str = Field(min_length=1)
    event_titles: Tuple[str, ...] = ()
    event_evidence: Tuple["WorkflowEventEvidenceProgress", ...] = ()


class WorkflowEvidenceQuote(BaseModel):
    """One quoted source paragraph rendered for a workflow event."""

    model_config = ConfigDict(frozen=True)

    paragraph_index: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=280)


class WorkflowEventEvidenceProgress(BaseModel):
    """Display-safe evidence for one event extracted from an article."""

    model_config = ConfigDict(frozen=True)

    event_title: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    quotes: Tuple[WorkflowEvidenceQuote, ...] = Field(max_length=2)


class WorkflowScreeningAnalysisProgress(BaseModel):
    """Safe screening observation correlated to its source article."""

    model_config = ConfigDict(frozen=True)

    article_id: str = Field(min_length=1)
    event_title: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    relevance: int = Field(ge=0, le=100)
    importance: int = Field(ge=0, le=100)
    credibility: int = Field(ge=0, le=100)
    reasons: Tuple[str, ...] = ()
    scorecard: Optional["WorkflowScorecardProgress"] = None


class WorkflowScorecardProgress(BaseModel):
    """Safe detailed scorecard values used by dashboard progress consumers."""

    model_config = ConfigDict(frozen=True)

    theme_directness: int = Field(ge=0, le=100)
    topic_match: int = Field(ge=0, le=100)
    market_transmission_path: int = Field(ge=0, le=100)
    relevance_reason: str = Field(min_length=1, max_length=280)
    impact_magnitude: int = Field(ge=0, le=100)
    scope_and_spillover: int = Field(ge=0, le=100)
    time_sensitivity: int = Field(ge=0, le=100)
    importance_reason: str = Field(min_length=1, max_length=280)
    source_authority: int = Field(ge=0, le=100)
    evidence_specificity: int = Field(ge=0, le=100)
    corroboration_and_uncertainty: int = Field(ge=0, le=100)
    credibility_reason: str = Field(min_length=1, max_length=280)


class WorkflowValidationAnalysisProgress(BaseModel):
    """Safe cross-validation status correlated to its source article."""

    model_config = ConfigDict(frozen=True)

    article_id: str = Field(min_length=1)
    event_title: str = Field(min_length=1)
    status: str = Field(min_length=1)


class WorkflowContext(BaseModel):
    """Immutable extension point for future workflow execution context."""

    model_config = ConfigDict(frozen=True)


class WorkflowProgressEvent(BaseModel):
    """Safe LangGraph node completion observation for a live consumer."""

    model_config = ConfigDict(frozen=True)

    node: str = Field(min_length=1)
    completed_node_count: int = Field(ge=1)
    output_keys: Tuple[str, ...]
    article_analyses: Tuple[WorkflowArticleAnalysisProgress, ...] = ()
    screening_analyses: Tuple[WorkflowScreeningAnalysisProgress, ...] = ()
    validation_analyses: Tuple[WorkflowValidationAnalysisProgress, ...] = ()


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
    verified_events: int = Field(ge=0)
    partially_verified_events: int = Field(ge=0)
    conflicted_events: int = Field(ge=0)
    insufficient_evidence_events: int = Field(ge=0)
    resolved_accept_count: int = Field(ge=0)
    resolved_review_count: int = Field(ge=0)
    resolved_reject_count: int = Field(ge=0)
    impact_diagnostics: WorkflowImpactDiagnostics = Field(
        default_factory=WorkflowImpactDiagnostics
    )


class ScreeningResult(BaseModel):
    """Separates decisions and recommendation output from execution metadata."""

    model_config = ConfigDict(frozen=True)

    recommendation: RecommendationResult
    candidate_selection: CandidateSelectionResult
    decisions: Tuple[ScreeningDecision, ...]
    cross_validation_results: Tuple[CrossValidationResult, ...]
    resolved_events: Tuple[ResolvedNewsEvent, ...]
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
        validation_total: int = (
            self.statistics.verified_events
            + self.statistics.partially_verified_events
            + self.statistics.conflicted_events
            + self.statistics.insufficient_evidence_events
        )
        if validation_total != len(self.cross_validation_results):
            raise ValueError("Cross validation statistics must equal the result count")
        if (
            self.statistics.resolved_accept_count
            + self.statistics.resolved_review_count
            + self.statistics.resolved_reject_count
            != len(self.resolved_events)
        ):
            raise ValueError("Resolved decision statistics must equal the result count")
        return self
