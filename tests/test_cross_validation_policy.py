from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from app.cross_validators import DefaultCrossValidationPolicy
from app.models import Article, CompanyRelation, CrossValidationAssessment, CrossValidationAssessmentEvidence, CrossValidationCandidate, CrossValidationStatus, EvidenceRelation, ExtractedCompany, NewsEvent, ScreeningDecision, ScreeningDecisionType


def article(identifier: str, source: str, host: str | None = None) -> Article:
    domain: str = host if host is not None else f"{identifier}.example.com"
    return Article(id=identifier, title=identifier, content="content", source=source, published_at=datetime(2026, 7, 29, tzinfo=timezone.utc), url=f"https://{domain}/{identifier}")


def candidate(related: Tuple[Article, ...]) -> CrossValidationCandidate:
    event = NewsEvent(title="Event", summary="Summary", companies=[ExtractedCompany(name="Company", relation=CompanyRelation.DIRECT)], industries=["Industry"], keywords=["Keyword"], reasons=["Reason"])
    return CrossValidationCandidate(candidate_id="source:0", decision=ScreeningDecision(event=event, decision=ScreeningDecisionType.REVIEW, relevance=50, importance=50, credibility=50, requires_cross_validation=True, reasons=("Review",)), source_article=article("source", "Source"), related_articles=related)


def assessment(*evidence: CrossValidationAssessmentEvidence, confidence: int = 70) -> CrossValidationAssessment:
    return CrossValidationAssessment(candidate_id="source:0", confidence=confidence, evidence=evidence, reasons=("Compared articles.",))


def support(identifier: str) -> CrossValidationAssessmentEvidence:
    return CrossValidationAssessmentEvidence(article_id=identifier, relation=EvidenceRelation.SUPPORTS, matched_claims=("Matched claim",))


def test_policy_uses_confidence_and_conservative_source_groups() -> None:
    item = candidate((article("a", "Reuters", "reuters.com"), article("b", "Bloomberg", "bloomberg.com")))
    policy = DefaultCrossValidationPolicy()
    assert policy.decide(item, assessment(support("a"), support("b"), confidence=69)).status is CrossValidationStatus.PARTIALLY_VERIFIED
    assert policy.decide(item, assessment(support("a"), support("b"), confidence=70)).status is CrossValidationStatus.VERIFIED


def test_policy_merges_transitive_domain_or_source_matches() -> None:
    item = candidate((article("a", "Reuters", "reuters.com"), article("b", "Reuters", "yahoo.com"), article("c", "Yahoo News", "reuters.com")))
    result = DefaultCrossValidationPolicy().decide(item, assessment(support("a"), support("b"), support("c"), confidence=100))
    assert result.independent_source_count == 1
    assert result.status is CrossValidationStatus.PARTIALLY_VERIFIED


def test_policy_conflict_precedes_verified_and_preserves_event_identity() -> None:
    item = candidate((article("a", "Reuters"), article("b", "Bloomberg")))
    result = DefaultCrossValidationPolicy().decide(item, assessment(support("a"), CrossValidationAssessmentEvidence(article_id="b", relation=EvidenceRelation.CONTRADICTS, conflicting_claims=("Conflict",)), confidence=100))
    assert result.status is CrossValidationStatus.CONFLICTED
    assert result.event is item.decision.event
