from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from app.cross_validators import DefaultCrossValidationPolicy
from app.models import (
    Article, CompanyRelation, CrossValidationAssessment, CrossValidationCandidate,
    CrossValidationStatus, ExtractedCompany, NewsEvent, ScreeningDecision,
    ScreeningDecisionType,
)


def article(identifier: str, source: str) -> Article:
    return Article(id=identifier, title=identifier, content="content", source=source, published_at=datetime(2026, 7, 29, tzinfo=timezone.utc), url=f"https://example.com/{identifier}")


def candidate(related: Tuple[Article, ...]) -> CrossValidationCandidate:
    event: NewsEvent = NewsEvent(title="Event", summary="Summary", companies=[ExtractedCompany(name="Company", relation=CompanyRelation.DIRECT)], industries=["Industry"], keywords=["Keyword"], reasons=["Reason"])
    return CrossValidationCandidate(candidate_id="source:0", decision=ScreeningDecision(event=event, decision=ScreeningDecisionType.REVIEW, relevance=50, importance=50, credibility=50, requires_cross_validation=True, reasons=("Review",)), source_article=article("source", "Source"), related_articles=related)


def assessment(*, supports: Tuple[str, ...] = (), partial: Tuple[str, ...] = (), contradicts: Tuple[str, ...] = (), confidence: int = 70) -> CrossValidationAssessment:
    return CrossValidationAssessment(candidate_id="source:0", confidence=confidence, supporting_article_ids=supports, partially_matching_article_ids=partial, contradicting_article_ids=contradicts, reasons=("Compared articles.",))


def test_policy_confidence_boundaries_and_source_normalization() -> None:
    item: CrossValidationCandidate = candidate((article("a", "Reuters"), article("b", " Bloomberg ")))
    policy: DefaultCrossValidationPolicy = DefaultCrossValidationPolicy()
    assert policy.decide(item, assessment(supports=("a", "b"), confidence=69)).status is CrossValidationStatus.PARTIALLY_VERIFIED
    assert policy.decide(item, assessment(supports=("a", "b"), confidence=70)).status is CrossValidationStatus.VERIFIED
    same_source: CrossValidationCandidate = candidate((article("a", "Reuters"), article("b", " reuters")))
    assert policy.decide(same_source, assessment(supports=("a", "b"), confidence=90)).status is CrossValidationStatus.PARTIALLY_VERIFIED


def test_policy_conflict_precedes_verified_conditions_and_partial_is_verified() -> None:
    item: CrossValidationCandidate = candidate((article("a", "Reuters"), article("b", "Bloomberg"), article("c", "AP")))
    policy: DefaultCrossValidationPolicy = DefaultCrossValidationPolicy()
    assert policy.decide(item, assessment(supports=("a", "b"), contradicts=("c",), confidence=90)).status is CrossValidationStatus.CONFLICTED
    assert policy.decide(item, assessment(partial=("a",))).status is CrossValidationStatus.PARTIALLY_VERIFIED


def test_policy_creates_unrelated_evidence_and_preserves_event_identity() -> None:
    item: CrossValidationCandidate = candidate((article("a", "Reuters"),))
    result = DefaultCrossValidationPolicy().decide(item, assessment(confidence=95))
    assert result.status is CrossValidationStatus.INSUFFICIENT_EVIDENCE
    assert result.event is item.decision.event
    assert result.evidence[0].relation.value == "unrelated"
