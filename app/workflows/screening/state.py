from __future__ import annotations

from typing import Tuple, TypedDict

from app.models.article import Article, ArticleEvaluationResult
from app.models.candidate_selection import CandidateSelectionResult
from app.models.evidence import EvidenceAggregation
from app.models.impact_analysis import ImpactAnalysis
from app.models.llm_inference import ExtractionError, LLMInferenceResult
from app.models.news_event import NewsEvent
from app.models.recommendation import RecommendationResult
from app.models.resolved_news_event import ResolvedNewsEvent
from app.models.scoring import ScoringResult
from app.models.screening import ScreeningDecision
from app.models.cross_validation import CrossValidationResult
from app.workflows.screening.result import WorkflowContext, WorkflowStatistics


class ScreeningState(TypedDict, total=False):
    """Private LangGraph state containing immutable workflow snapshots."""

    context: WorkflowContext
    articles: Tuple[Article, ...]
    evaluations: Tuple[ArticleEvaluationResult, ...]
    inferences: Tuple[LLMInferenceResult, ...]
    extraction_errors: Tuple[ExtractionError, ...]
    successful_batches: int
    events: Tuple[NewsEvent, ...]
    decisions: Tuple[ScreeningDecision, ...]
    cross_validation_results: Tuple[CrossValidationResult, ...]
    resolved_events: Tuple[ResolvedNewsEvent, ...]
    analyses: Tuple[ImpactAnalysis, ...]
    evidence: EvidenceAggregation
    scoring: ScoringResult
    recommendation: RecommendationResult
    candidate_selection: CandidateSelectionResult
    statistics: WorkflowStatistics
