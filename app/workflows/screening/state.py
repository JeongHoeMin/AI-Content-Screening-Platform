from __future__ import annotations

from typing import Tuple, TypedDict

from app.models.article import Article, ArticleEvaluationResult
from app.models.evidence import EvidenceAggregation
from app.models.impact_analysis import ImpactAnalysis
from app.models.llm_inference import LLMInferenceResult
from app.models.news_event import NewsEvent
from app.models.recommendation import RecommendationResult
from app.models.resolved_news_event import ResolvedNewsEvent
from app.models.scoring import ScoringResult
from app.workflows.screening.result import WorkflowContext, WorkflowStatistics


class ScreeningState(TypedDict, total=False):
    """Private LangGraph state containing immutable workflow snapshots."""

    context: WorkflowContext
    articles: Tuple[Article, ...]
    evaluations: Tuple[ArticleEvaluationResult, ...]
    inferences: Tuple[LLMInferenceResult, ...]
    events: Tuple[NewsEvent, ...]
    resolved_events: Tuple[ResolvedNewsEvent, ...]
    analyses: Tuple[ImpactAnalysis, ...]
    evidence: EvidenceAggregation
    scoring: ScoringResult
    recommendation: RecommendationResult
    statistics: WorkflowStatistics
