from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.analyzers import DEFAULT_IMPACT_RULE_CATALOG, ImpactRule, ImpactRuleCatalog
from app.models import EventFact, ImpactDirection, ImpactReasonCode


def test_default_catalog_assigns_each_event_fact_once() -> None:
    assert {rule.event_fact for rule in DEFAULT_IMPACT_RULE_CATALOG.rules} == set(EventFact)
    assert len(DEFAULT_IMPACT_RULE_CATALOG.rules) == len(EventFact)


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
