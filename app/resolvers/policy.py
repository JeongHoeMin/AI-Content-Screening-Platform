from __future__ import annotations

from typing import Iterable, Optional, Protocol, Tuple

from app.models.cross_validation import CrossValidationResult, CrossValidationStatus
from app.models.resolve import ResolveDecision
from app.models.resolved_news_event import ResolvedDecisionType
from app.models.screening import ScreeningDecision, ScreeningDecisionType


class ResolvePolicy(Protocol):
    def resolve(self, decision: ScreeningDecision, validation: Optional[CrossValidationResult]) -> ResolveDecision:
        ...


class DefaultResolvePolicy(ResolvePolicy):
    def resolve(self, decision: ScreeningDecision, validation: Optional[CrossValidationResult]) -> ResolveDecision:
        final_decision: ResolvedDecisionType
        transition_reason: str = ""
        if decision.decision is ScreeningDecisionType.REJECT:
            final_decision = ResolvedDecisionType.REJECT
            transition_reason = "Screening rejected the event."
        elif validation is None or validation.status is CrossValidationStatus.INSUFFICIENT_EVIDENCE:
            final_decision = ResolvedDecisionType(decision.decision.value)
            transition_reason = "Cross validation did not change the screening decision."
        elif validation.status is CrossValidationStatus.VERIFIED:
            final_decision = ResolvedDecisionType.ACCEPT
            transition_reason = "Cross validation verified the event using independent supporting sources."
        elif validation.status is CrossValidationStatus.PARTIALLY_VERIFIED:
            final_decision = ResolvedDecisionType.REVIEW
            transition_reason = "Cross validation found partial supporting evidence."
        else:
            final_decision = ResolvedDecisionType.REJECT
            transition_reason = "Cross validation found contradicting evidence."
        validation_reasons: Tuple[str, ...] = validation.reasons if validation is not None else ()
        reasons: Tuple[str, ...] = self._deduplicate_reasons(
            (*decision.reasons, *validation_reasons, transition_reason)
        )
        return ResolveDecision(decision=final_decision, reasons=reasons)

    @staticmethod
    def _deduplicate_reasons(reasons: Iterable[str]) -> Tuple[str, ...]:
        normalized_reasons: list[str] = []
        seen: set[str] = set()
        for reason in reasons:
            normalized_reason: str = reason.strip()
            if not normalized_reason or normalized_reason in seen:
                continue
            seen.add(normalized_reason)
            normalized_reasons.append(normalized_reason)
        return tuple(normalized_reasons)
