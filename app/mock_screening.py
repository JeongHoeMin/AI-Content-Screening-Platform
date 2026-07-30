from __future__ import annotations

from typing import Tuple

from app.cross_validators.base import CrossValidator
from app.cross_validators.policy import CrossValidationPolicy
from app.extractors.base import NewsEventExtractor
from app.models.article import Article
from app.models.cross_validation import (
    CrossValidationAssessment,
    CrossValidationAssessmentEvidence,
    CrossValidationCandidate,
    CrossValidationResult,
    EvidenceRelation,
)
from app.models.llm_inference import LLMExtractionResult, LLMInferenceResult
from app.models.news_event import EventType, NewsEvent
from app.models.screening import (
    ScreeningAssessment,
    ScreeningDecision,
    ScreeningCandidate,
)
from app.mock_grouping import build_mock_grouping_key
from app.screeners.base import EventScreener
from app.screeners.policy import ScreeningPolicy


class DeterministicMockExtractor(NewsEventExtractor):
    """Creates one stable event per article for local workflow execution."""

    async def extract(self, articles: Tuple[Article, ...]) -> LLMExtractionResult:
        return LLMExtractionResult(
            inferences=tuple(self._inference(article) for article in articles),
            successful_batches=1 if articles else 0,
        )

    @staticmethod
    def _inference(article: Article) -> LLMInferenceResult:
        summary: str = DeterministicMockExtractor._build_summary(article)
        event: NewsEvent = NewsEvent(
            title=article.title,
            summary=summary,
            event_type=EventType.CORPORATE_EVENT,
            event_facts=(),
            companies=[],
            industries=[],
            keywords=[build_mock_grouping_key(article)],
            reasons=("Deterministic mock extraction.",),
        )
        return LLMInferenceResult(
            article=article,
            events=(event,),
            summary=summary,
            reasoning="Deterministic mock extraction.",
            confidence=1.0,
        )

    @staticmethod
    def _build_summary(article: Article) -> str:
        normalized_content: str = " ".join(article.content.split())
        if normalized_content:
            return normalized_content[:500]
        return " ".join(article.title.split())


class DeterministicMockScreener(EventScreener):
    """Creates REVIEW assessments and delegates final decisions to policy."""

    def __init__(self, policy: ScreeningPolicy) -> None:
        self._policy: ScreeningPolicy = policy

    async def screen(
        self, inferences: Tuple[LLMInferenceResult, ...]
    ) -> Tuple[ScreeningDecision, ...]:
        candidates: Tuple[ScreeningCandidate, ...] = tuple(
            ScreeningCandidate(
                candidate_id=f"{inference.article.id}:{event_index}",
                article=inference.article,
                event=event,
            )
            for inference in inferences
            for event_index, event in enumerate(inference.events)
        )
        return tuple(
            self._policy.decide(
                candidate.event,
                ScreeningAssessment(
                    candidate_id=candidate.candidate_id,
                    relevance=60,
                    importance=60,
                    credibility=60,
                    requires_cross_validation=True,
                    reasons=("Deterministic mock review assessment.",),
                ),
            )
            for candidate in candidates
        )


class DeterministicMockCrossValidator(CrossValidator):
    """Builds stable assessments; the injected policy owns final statuses."""

    def __init__(self, policy: CrossValidationPolicy) -> None:
        self._policy: CrossValidationPolicy = policy

    async def validate(
        self, candidates: Tuple[CrossValidationCandidate, ...]
    ) -> Tuple[CrossValidationResult, ...]:
        return tuple(self._validate(candidate) for candidate in candidates)

    def _validate(self, candidate: CrossValidationCandidate) -> CrossValidationResult:
        if not candidate.related_articles:
            return self._policy.insufficient_evidence(
                candidate,
                reasons=("No related articles are available for cross validation.",),
            )
        related: Tuple[Article, ...] = tuple(
            article
            for article in candidate.related_articles
            if build_mock_grouping_key(article)
            == build_mock_grouping_key(candidate.source_article)
        )
        unique_sources: set[str] = {
            article.source.strip().casefold()
            for article in related
            if article.source.strip()
        }
        if len(related) >= 2 and len(unique_sources) >= 2:
            assessment: CrossValidationAssessment = CrossValidationAssessment(
                candidate_id=candidate.candidate_id,
                confidence=100,
                evidence=tuple(CrossValidationAssessmentEvidence(article_id=article.id, relation=EvidenceRelation.SUPPORTS, matched_claims=("Deterministic mock support.",)) for article in related),
                reasons=("Deterministic mock supporting evidence.",),
            )
        elif len(related) == 1:
            assessment = CrossValidationAssessment(
                candidate_id=candidate.candidate_id,
                confidence=100,
                evidence=(CrossValidationAssessmentEvidence(article_id=related[0].id, relation=EvidenceRelation.PARTIAL),),
                reasons=("Deterministic mock partial evidence.",),
            )
        else:
            assessment = CrossValidationAssessment(
                candidate_id=candidate.candidate_id,
                confidence=0,
                reasons=("No deterministic mock related evidence.",),
            )
        return self._policy.decide(candidate, assessment)
