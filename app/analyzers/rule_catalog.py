from __future__ import annotations

from typing import Tuple

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.impact_analysis import ImpactDirection, ImpactReasonCode
from app.models.news_event import EventFact


class ImpactRule(BaseModel):
    """One deterministic impact interpretation registered for an event fact."""

    model_config = ConfigDict(frozen=True)

    event_fact: EventFact
    direction: ImpactDirection
    reason_code: ImpactReasonCode


class ImpactRuleCatalog(BaseModel):
    """Exhaustive immutable registry of v1 fact-to-impact rules."""

    model_config = ConfigDict(frozen=True)

    rules: Tuple[ImpactRule, ...]

    @model_validator(mode="after")
    def _validate_complete_unique_coverage(self) -> "ImpactRuleCatalog":
        facts: Tuple[EventFact, ...] = tuple(rule.event_fact for rule in self.rules)
        duplicate_facts: Tuple[EventFact, ...] = tuple(
            fact for fact in EventFact if facts.count(fact) > 1
        )
        missing_facts: Tuple[EventFact, ...] = tuple(
            fact for fact in EventFact if fact not in facts
        )
        if duplicate_facts or missing_facts:
            details: list[str] = []
            if duplicate_facts:
                details.append(
                    "Duplicate facts: " + ", ".join(fact.name for fact in duplicate_facts)
                )
            if missing_facts:
                details.append(
                    "Missing facts: " + ", ".join(fact.name for fact in missing_facts)
                )
            raise ValueError(
                "Impact Rule Catalog must assign every event fact exactly once. "
                + "; ".join(details)
            )
        return self

    def rule_for(self, event_fact: EventFact) -> ImpactRule:
        """Return the guaranteed registered rule for one valid event fact."""
        for rule in self.rules:
            if rule.event_fact is event_fact:
                return rule
        raise RuntimeError(f"Missing impact rule for event fact: {event_fact.name}")


DEFAULT_IMPACT_RULE_CATALOG = ImpactRuleCatalog(
    rules=(
        ImpactRule(
            event_fact=EventFact.FACTORY_EXPANSION,
            direction=ImpactDirection.POSITIVE,
            reason_code=ImpactReasonCode.FACTORY_EXPANSION_POSITIVE,
        ),
        ImpactRule(
            event_fact=EventFact.MASS_LAYOFF,
            direction=ImpactDirection.NEGATIVE,
            reason_code=ImpactReasonCode.MASS_LAYOFF_NEGATIVE,
        ),
        ImpactRule(
            event_fact=EventFact.BANKRUPTCY,
            direction=ImpactDirection.NEGATIVE,
            reason_code=ImpactReasonCode.BANKRUPTCY_NEGATIVE,
        ),
        ImpactRule(
            event_fact=EventFact.PRODUCT_RELEASE,
            direction=ImpactDirection.UNKNOWN,
            reason_code=ImpactReasonCode.PRODUCT_RELEASE_DIRECTION_UNKNOWN,
        ),
        ImpactRule(
            event_fact=EventFact.CEO_INTERVIEW,
            direction=ImpactDirection.UNKNOWN,
            reason_code=ImpactReasonCode.CEO_INTERVIEW_DIRECTION_UNKNOWN,
        ),
        ImpactRule(
            event_fact=EventFact.MAJOR_SUPPLY_CONTRACT,
            direction=ImpactDirection.POSITIVE,
            reason_code=ImpactReasonCode.MAJOR_SUPPLY_CONTRACT_POSITIVE,
        ),
    )
)
