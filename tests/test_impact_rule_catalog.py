from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.analyzers import DEFAULT_IMPACT_RULE_CATALOG, ImpactRule, ImpactRuleCatalog
from app.models import EventFact, ImpactDirection, ImpactReasonCode


def test_default_catalog_assigns_each_event_fact_once() -> None:
    assert {rule.event_fact for rule in DEFAULT_IMPACT_RULE_CATALOG.rules} == set(EventFact)
    assert len(DEFAULT_IMPACT_RULE_CATALOG.rules) == len(EventFact)


def test_default_catalog_has_the_approved_direction_and_reason_mapping() -> None:
    expected: dict[EventFact, tuple[ImpactDirection, ImpactReasonCode]] = {
        EventFact.FACTORY_EXPANSION: (ImpactDirection.POSITIVE, ImpactReasonCode.FACTORY_EXPANSION_POSITIVE),
        EventFact.MASS_LAYOFF: (ImpactDirection.NEGATIVE, ImpactReasonCode.MASS_LAYOFF_NEGATIVE),
        EventFact.BANKRUPTCY: (ImpactDirection.NEGATIVE, ImpactReasonCode.BANKRUPTCY_NEGATIVE),
        EventFact.PRODUCT_RELEASE: (ImpactDirection.UNKNOWN, ImpactReasonCode.PRODUCT_RELEASE_DIRECTION_UNKNOWN),
        EventFact.CEO_INTERVIEW: (ImpactDirection.UNKNOWN, ImpactReasonCode.CEO_INTERVIEW_DIRECTION_UNKNOWN),
    }

    assert {
        rule.event_fact: (rule.direction, rule.reason_code)
        for rule in DEFAULT_IMPACT_RULE_CATALOG.rules
    } == expected


def test_catalog_rejects_duplicate_fact_rules() -> None:
    rules: tuple[ImpactRule, ...] = DEFAULT_IMPACT_RULE_CATALOG.rules + (
        ImpactRule(event_fact=EventFact.FACTORY_EXPANSION, direction=ImpactDirection.POSITIVE, reason_code=ImpactReasonCode.FACTORY_EXPANSION_POSITIVE),
    )

    with pytest.raises(ValidationError, match="Duplicate facts: FACTORY_EXPANSION"):
        ImpactRuleCatalog(rules=rules)


def test_catalog_rejects_missing_fact_rules() -> None:
    rules: tuple[ImpactRule, ...] = tuple(
        rule for rule in DEFAULT_IMPACT_RULE_CATALOG.rules
        if rule.event_fact is not EventFact.MASS_LAYOFF
    )

    with pytest.raises(ValidationError, match="Missing facts: MASS_LAYOFF"):
        ImpactRuleCatalog(rules=rules)
