from __future__ import annotations

import json

from app.cli import _serialize_result
from app.models import (
    DEFAULT_RECOMMENDATION_POLICY_CONFIG,
    CompanyRelation,
    CompanyResolutionStatus,
    EventType,
    ExtractedCompany,
    KRXExchange,
    NewsEvent,
    RecommendationResult,
    ResolvedCompany,
    ResolvedNewsEvent,
    ResolvedTicker,
    CompanyScore,
    ScreeningDecision,
    ScreeningDecisionType,
    ScoringResult,
)
from app.candidates import RuleCandidateSelectionPolicy
from app.recommenders import RuleRecommendationPolicy
from app.workflows import ScreeningResult, WorkflowStatistics


def test_cli_serialization_excludes_internal_company_resolution_fields() -> None:
    event = NewsEvent(
        title="Samsung event",
        summary="Samsung event summary",
        event_type=EventType.CORPORATE_EVENT,
        companies=[
            ExtractedCompany(name="Samsung Electronics", relation=CompanyRelation.DIRECT)
        ],
        industries=["Semiconductors"],
        keywords=["HBM"],
        reasons=["Article evidence"],
    )
    company = ResolvedCompany(
        name="Samsung Electronics",
        relation=CompanyRelation.DIRECT,
        ticker=ResolvedTicker(ticker="005930", exchange=KRXExchange.KOSPI),
        company_id="KRX-COMPANY-000001",
        resolution_status=CompanyResolutionStatus.RESOLVED,
        directory_version="2026-07-30",
    )
    decision = ScreeningDecision(
        event=event,
        decision=ScreeningDecisionType.REVIEW,
        relevance=50,
        importance=50,
        credibility=50,
        requires_cross_validation=True,
        reasons=("Screening evidence",),
    )
    result = ScreeningResult(
        recommendation=RecommendationResult(
            policy_version=DEFAULT_RECOMMENDATION_POLICY_CONFIG.policy_version,
            decisions=(),
        ),
        candidate_selection=RuleCandidateSelectionPolicy().select(
            RecommendationResult(
                policy_version=DEFAULT_RECOMMENDATION_POLICY_CONFIG.policy_version,
                decisions=(),
            )
        ),
        decisions=(decision,),
        cross_validation_results=(),
        resolved_events=(ResolvedNewsEvent(event=event, companies=(company,)),),
        statistics=WorkflowStatistics(
            total_articles=1,
            accepted_articles=1,
            rejected_articles=0,
            extracted_events=1,
            successful_batches=1,
            accepted_events=0,
            review_events=1,
            rejected_events=0,
            verified_events=0,
            partially_verified_events=0,
            conflicted_events=0,
            insufficient_evidence_events=0,
            resolved_accept_count=0,
            resolved_review_count=1,
            resolved_reject_count=0,
        ),
    )

    payload: dict[str, object] = json.loads(_serialize_result(result))
    company_payload = payload["resolved_events"][0]["companies"][0]

    assert "company_id" not in company_payload
    assert "resolution_status" not in company_payload
    assert "directory_version" not in company_payload
    assert payload["recommendation"] == {"companies": []}


def test_cli_serialization_preserves_legacy_recommendation_shape() -> None:
    company = ResolvedCompany(
        name="Samsung Electronics",
        relation=CompanyRelation.DIRECT,
        ticker=ResolvedTicker(ticker="005930", exchange=KRXExchange.KOSPI),
    )
    scoring = CompanyScore(company=company, score=0.0, contributions=())
    recommendation = RuleRecommendationPolicy().recommend(
        ScoringResult(policy_version="score-v1", companies=(scoring,))
    )
    result = ScreeningResult(
        recommendation=recommendation,
        candidate_selection=RuleCandidateSelectionPolicy().select(recommendation),
        decisions=(),
        cross_validation_results=(),
        resolved_events=(),
        statistics=WorkflowStatistics(
            total_articles=0,
            accepted_articles=0,
            rejected_articles=0,
            extracted_events=0,
            successful_batches=0,
            accepted_events=0,
            review_events=0,
            rejected_events=0,
            verified_events=0,
            partially_verified_events=0,
            conflicted_events=0,
            insufficient_evidence_events=0,
            resolved_accept_count=0,
            resolved_review_count=0,
            resolved_reject_count=0,
        ),
    )

    payload: dict[str, object] = json.loads(_serialize_result(result))
    decision_payload = payload["recommendation"]["companies"][0]

    assert decision_payload["recommendation"] == "hold"
    assert decision_payload["score"]["score"] == 0.0
    assert "reason_code" not in decision_payload
    assert "threshold_snapshot" not in decision_payload
