from __future__ import annotations

from typing import Dict, Optional, Protocol, Set, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.models.article import Article
from app.models.cross_validation import (
    CrossValidationAssessment,
    CrossValidationCandidate,
    CrossValidationResult,
    CrossValidationStatus,
    EvidenceRelation,
    ValidationEvidence,
)


class CrossValidationPolicyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    minimum_supporting_articles: int = Field(default=2, gt=0)
    minimum_independent_sources: int = Field(default=2, gt=0)
    verified_confidence_at_least: int = Field(default=70, ge=0, le=100)
    use_url_domain_identity: bool = True


class CrossValidationPolicy(Protocol):
    def decide(self, candidate: CrossValidationCandidate, assessment: CrossValidationAssessment) -> CrossValidationResult: ...
    def insufficient_evidence(self, candidate: CrossValidationCandidate, reasons: Tuple[str, ...]) -> CrossValidationResult: ...


class DefaultCrossValidationPolicy(CrossValidationPolicy):
    def __init__(self, config: Optional[CrossValidationPolicyConfig] = None) -> None:
        self._config: CrossValidationPolicyConfig = config or CrossValidationPolicyConfig()

    def insufficient_evidence(self, candidate: CrossValidationCandidate, reasons: Tuple[str, ...]) -> CrossValidationResult:
        return CrossValidationResult(event=candidate.decision.event, status=CrossValidationStatus.INSUFFICIENT_EVIDENCE, confidence=0, independent_source_count=0, evidence=(), reasons=reasons)

    def decide(self, candidate: CrossValidationCandidate, assessment: CrossValidationAssessment) -> CrossValidationResult:
        evidence: Tuple[ValidationEvidence, ...] = self._evidence(candidate, assessment)
        supports: Tuple[ValidationEvidence, ...] = tuple(item for item in evidence if item.relation is EvidenceRelation.SUPPORTS)
        source_count: int = self._independent_source_count(candidate, supports)
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
    def _evidence(candidate: CrossValidationCandidate, assessment: CrossValidationAssessment) -> Tuple[ValidationEvidence, ...]:
        by_id: Dict[str, Article] = {article.id: article for article in candidate.related_articles}
        observed: Dict[str, object] = {item.article_id: item for item in assessment.evidence}
        return tuple(
            ValidationEvidence(article_id=article.id, source_name=article.source, source_type="news", relation=(observed[article.id].relation if article.id in observed else EvidenceRelation.UNRELATED), matched_claims=(observed[article.id].matched_claims if article.id in observed else ()), conflicting_claims=(observed[article.id].conflicting_claims if article.id in observed else ()))
            for article in candidate.related_articles
            if article.id in by_id
        )

    def _independent_source_count(self, candidate: CrossValidationCandidate, supports: Tuple[ValidationEvidence, ...]) -> int:
        articles_by_id: Dict[str, Article] = {article.id: article for article in candidate.related_articles}
        articles: list[Article] = [articles_by_id[item.article_id] for item in supports if item.article_id in articles_by_id and self._has_identity(articles_by_id[item.article_id])]
        parent: list[int] = list(range(len(articles)))
        for left in range(len(articles)):
            for right in range(left + 1, len(articles)):
                if self._same_source(articles[left], articles[right]):
                    self._union(parent, left, right)
        return len({self._find(parent, index) for index in range(len(articles))})

    @staticmethod
    def _normalize_domain(article: Article) -> Optional[str]:
        host: str | None = article.url.host
        if not host:
            return None
        normalized: str = host.strip().casefold().rstrip(".")
        if normalized.startswith("www."):
            normalized = normalized[4:]
        return normalized or None

    @staticmethod
    def _normalize_source(article: Article) -> Optional[str]:
        normalized: str = article.source.strip().casefold()
        return normalized or None

    def _has_identity(self, article: Article) -> bool:
        return self._normalize_domain(article) is not None or self._normalize_source(article) is not None

    def _same_source(self, left: Article, right: Article) -> bool:
        left_domain: Optional[str] = self._normalize_domain(left)
        right_domain: Optional[str] = self._normalize_domain(right)
        if self._config.use_url_domain_identity and left_domain is not None and left_domain == right_domain:
            return True
        left_source: Optional[str] = self._normalize_source(left)
        right_source: Optional[str] = self._normalize_source(right)
        return left_source is not None and left_source == right_source

    @staticmethod
    def _find(parent: list[int], index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    @classmethod
    def _union(cls, parent: list[int], left: int, right: int) -> None:
        left_root: int = cls._find(parent, left)
        right_root: int = cls._find(parent, right)
        if left_root != right_root:
            parent[right_root] = left_root
