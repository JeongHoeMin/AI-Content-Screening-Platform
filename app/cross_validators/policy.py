from __future__ import annotations

from typing import Optional, Protocol, Set, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.models.article import Article
from app.models.cross_validation import (
    CrossValidationAssessment, CrossValidationCandidate, CrossValidationResult,
    CrossValidationStatus, EvidenceRelation, ValidationEvidence,
)


class CrossValidationPolicyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    minimum_supporting_articles: int = Field(default=2, gt=0)
    minimum_independent_sources: int = Field(default=2, gt=0)
    verified_confidence_at_least: int = Field(default=70, ge=0, le=100)


class CrossValidationPolicy(Protocol):
    def decide(self, candidate: CrossValidationCandidate, assessment: CrossValidationAssessment) -> CrossValidationResult: ...
    def insufficient_evidence(self, candidate: CrossValidationCandidate, reasons: Tuple[str, ...]) -> CrossValidationResult: ...


class DefaultCrossValidationPolicy(CrossValidationPolicy):
    def __init__(self, config: Optional[CrossValidationPolicyConfig] = None) -> None:
        self._config: CrossValidationPolicyConfig = config or CrossValidationPolicyConfig()

    def insufficient_evidence(self, candidate: CrossValidationCandidate, reasons: Tuple[str, ...]) -> CrossValidationResult:
        return CrossValidationResult(event=candidate.decision.event, status=CrossValidationStatus.INSUFFICIENT_EVIDENCE, confidence=0, independent_source_count=0, evidence=(), reasons=reasons)

    def decide(self, candidate: CrossValidationCandidate, assessment: CrossValidationAssessment) -> CrossValidationResult:
        if not candidate.related_articles:
            return self.insufficient_evidence(candidate, ("No related articles are available for cross validation.",))
        evidence: Tuple[ValidationEvidence, ...] = self._evidence(candidate, assessment)
        supports: Tuple[ValidationEvidence, ...] = tuple(item for item in evidence if item.relation is EvidenceRelation.SUPPORTS)
        source_count: int = len({source for source in (self._source(article) for article in candidate.related_articles if article.id in set(assessment.supporting_article_ids)) if source})
        if any(item.relation is EvidenceRelation.CONTRADICTS for item in evidence):
            status: CrossValidationStatus = CrossValidationStatus.CONFLICTED
        elif len(supports) >= self._config.minimum_supporting_articles and source_count >= self._config.minimum_independent_sources and assessment.confidence >= self._config.verified_confidence_at_least:
            status = CrossValidationStatus.VERIFIED
        elif any(item.relation in (EvidenceRelation.SUPPORTS, EvidenceRelation.PARTIAL) for item in evidence):
            status = CrossValidationStatus.PARTIALLY_VERIFIED
        else:
            status = CrossValidationStatus.INSUFFICIENT_EVIDENCE
        return CrossValidationResult(event=candidate.decision.event, status=status, confidence=assessment.confidence, independent_source_count=source_count, evidence=evidence, reasons=assessment.reasons)

    @staticmethod
    def _source(article: Article) -> str:
        return article.source.strip().casefold()

    @staticmethod
    def _evidence(candidate: CrossValidationCandidate, assessment: CrossValidationAssessment) -> Tuple[ValidationEvidence, ...]:
        support: Set[str] = set(assessment.supporting_article_ids)
        partial: Set[str] = set(assessment.partially_matching_article_ids)
        contradict: Set[str] = set(assessment.contradicting_article_ids)
        def relation(article_id: str) -> EvidenceRelation:
            if article_id in support: return EvidenceRelation.SUPPORTS
            if article_id in partial: return EvidenceRelation.PARTIAL
            if article_id in contradict: return EvidenceRelation.CONTRADICTS
            return EvidenceRelation.UNRELATED
        # v1 assessment claims describe the candidate comparison as a whole, not
        # a particular article. Do not incorrectly copy them onto every evidence.
        return tuple(ValidationEvidence(article_id=article.id, source_name=article.source, source_type="news", relation=relation(article.id), matched_claims=(), conflicting_claims=()) for article in candidate.related_articles)
