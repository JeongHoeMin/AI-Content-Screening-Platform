from __future__ import annotations

from datetime import datetime, timezone

from app.deduplicators.event_candidates import DeduplicationEvent, EventCandidateGenerator
from app.models.news_event import CompanyRelation, EventType, ExtractedCompany, NewsEvent


def event(title: str, keywords: list[str]) -> NewsEvent:
    return NewsEvent(
        title=title,
        summary="summary",
        event_type=EventType.FINANCIAL_EVENT,
        companies=[ExtractedCompany(name="Samsung", relation=CompanyRelation.DIRECT)],
        industries=["semiconductors"],
        keywords=keywords,
        reasons=["source"],
    )


def test_candidate_generator_selects_same_company_and_keyword_overlap() -> None:
    created_at = datetime(2026, 8, 4, tzinfo=timezone.utc)
    candidates = EventCandidateGenerator().generate(
        (
            DeduplicationEvent("a", event("Samsung supply deal", ["HBM", "supply"]), created_at),
            DeduplicationEvent("b", event("Samsung signs supply contract", ["HBM", "supply"]), created_at),
        )
    )

    assert [(item.left.id, item.right.id) for item in candidates] == [("a", "b")]
