from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

import pytest

from app.cross_validators import DefaultCrossValidationPolicy
from app.models import Article, CompanyRelation, CrossValidationAssessment, CrossValidationAssessmentEvidence, CrossValidationCandidate, CrossValidationStatus, EventType, EvidenceRelation, ExtractedCompany, NewsEvent, ScreeningDecision, ScreeningDecisionType


def article(identifier: str, source: str, host: str | None = None) -> Article:
    domain: str = host if host is not None else f"{identifier}.example.com"
    return Article(id=identifier, title=identifier, content="content", source=source, published_at=datetime(2026, 7, 29, tzinfo=timezone.utc), url=f"https://{domain}/{identifier}")


def candidate(related: Tuple[Article, ...]) -> CrossValidationCandidate:
    event = NewsEvent(title="Event", summary="Summary", event_type=EventType.CORPORATE_EVENT, companies=[ExtractedCompany(name="Company", relation=CompanyRelation.DIRECT)], industries=["Industry"], keywords=["Keyword"], reasons=["Reason"])
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


@pytest.mark.parametrize("source", [None, "", "   ", "Unknown", "UNKNOWN", " unknown source ", "N/A", "News", "Newsroom"])
def test_policy_normalizes_non_identifying_sources_to_none(source: str | None) -> None:
    assert DefaultCrossValidationPolicy._normalize_source(source) is None


@pytest.mark.parametrize(
    "source",
    [
        "Reuters",
        "ABC News",
        "Yonhap News",
        "Associated Press",
        "Financial Publisher",
        "Open Source Initiative",
        "Publisher",
        "Media",
        "Press",
        "Source",
    ],
)
def test_policy_preserves_identifying_sources(source: str) -> None:
    assert DefaultCrossValidationPolicy._normalize_source(source) == " ".join(source.split()).casefold()


def test_policy_does_not_merge_different_domains_with_generic_source() -> None:
    item = candidate((article("a", "News", "a.example"), article("b", "News", "b.example")))
    result = DefaultCrossValidationPolicy().decide(item, assessment(support("a"), support("b"), confidence=100))
    assert result.independent_source_count == 2
    assert result.status is CrossValidationStatus.VERIFIED


def test_policy_merges_matching_domain_despite_generic_sources() -> None:
    item = candidate((article("a", "News", "example.com"), article("b", "Unknown", "example.com")))
    result = DefaultCrossValidationPolicy().decide(item, assessment(support("a"), support("b"), confidence=100))
    assert result.independent_source_count == 1
