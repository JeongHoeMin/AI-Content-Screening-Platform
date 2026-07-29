from __future__ import annotations

from typing import Optional

import pytest

from app.models import (
    CrossValidationResult, CrossValidationStatus, ResolveDecision, ResolvedDecisionType,
    ScreeningDecision, ScreeningDecisionType,
)
from app.resolvers import DefaultResolvePolicy
from tests.test_cross_validation_policy import candidate


def decision(decision_type: ScreeningDecisionType) -> ScreeningDecision:
    return candidate(()).decision.model_copy(update={"decision": decision_type})


def validation(status: CrossValidationStatus, reasons: tuple[str, ...] = ("Validation reason.",)) -> CrossValidationResult:
    event = decision(ScreeningDecisionType.REVIEW).event
    return CrossValidationResult(event=event, status=status, confidence=70, independent_source_count=0, evidence=(), reasons=reasons)


@pytest.mark.parametrize(
    ("screening", "status", "expected"),
    [
        (ScreeningDecisionType.REJECT, CrossValidationStatus.VERIFIED, ResolvedDecisionType.REJECT),
        (ScreeningDecisionType.REVIEW, CrossValidationStatus.VERIFIED, ResolvedDecisionType.ACCEPT),
        (ScreeningDecisionType.REVIEW, CrossValidationStatus.PARTIALLY_VERIFIED, ResolvedDecisionType.REVIEW),
        (ScreeningDecisionType.REVIEW, CrossValidationStatus.CONFLICTED, ResolvedDecisionType.REJECT),
        (ScreeningDecisionType.REVIEW, CrossValidationStatus.INSUFFICIENT_EVIDENCE, ResolvedDecisionType.REVIEW),
    ],
)
def test_policy_applies_resolve_status_precedence(screening: ScreeningDecisionType, status: CrossValidationStatus, expected: ResolvedDecisionType) -> None:
    screening_decision = decision(screening)
    item = validation(status).model_copy(update={"event": screening_decision.event})
    assert DefaultResolvePolicy().resolve(screening_decision, item).decision is expected


def test_policy_keeps_accept_without_validation_and_deduplicates_reasons() -> None:
    screening_decision = decision(ScreeningDecisionType.ACCEPT).model_copy(update={"reasons": ("Same.",)})
    result: ResolveDecision = DefaultResolvePolicy().resolve(screening_decision, None)
    assert result.decision is ResolvedDecisionType.ACCEPT
    assert result.reasons.count("Same.") == 1
