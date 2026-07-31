from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import List, Tuple

import pytest

from app.analyzers import DEFAULT_IMPACT_RULE_CATALOG, ImpactStrategy, RuleImpactStrategy
from app.models import (
    CompanyRelation,
    EventFact,
    EventType,
    ExtractedCompany,
    ImpactDirection,
    ImpactObservation,
    ImpactReasonCode,
    ImpactUncertainty,
    NewsEvent,
    ResolvedCompany,
    ResolvedNewsEvent,
    ResolvedTicker,
)
from app.models.cross_validation import CrossValidationStatus


def build_resolved_event(
    facts: Tuple[EventFact, ...] = (),
    relations: Tuple[CompanyRelation, ...] = (CompanyRelation.DIRECT,),
) -> ResolvedNewsEvent:
    companies: List[ResolvedCompany] = [
        ResolvedCompany(
            name=f"Company {index}",
            relation=relation,
            ticker=ResolvedTicker(ticker=f"0000{index}", exchange="KRX"),
        )
        for index, relation in enumerate(relations)
    ]
    event: NewsEvent = NewsEvent(
        title="Classification event",
        summary="Structured facts determine impact.",
        event_type=EventType.CORPORATE_EVENT,
        event_facts=facts,
        companies=[ExtractedCompany(name=company.name, relation=company.relation) for company in companies],
        industries=["Semiconductors"],
        keywords=["HBM"],
        reasons=["Fact is stated in the article"],
    )
    return ResolvedNewsEvent(event=event, companies=tuple(companies))


def test_rule_strategy_creates_fact_observations_in_original_fact_order() -> None:
    strategy: ImpactStrategy = RuleImpactStrategy(DEFAULT_IMPACT_RULE_CATALOG)
    event: ResolvedNewsEvent = build_resolved_event(
        (EventFact.FACTORY_EXPANSION, EventFact.MASS_LAYOFF),
    )

    observations: Tuple[ImpactObservation, ...] = strategy.analyze(event)

    assert [observation.event_fact for observation in observations] == [
        EventFact.FACTORY_EXPANSION,
        EventFact.MASS_LAYOFF,
    ]
    assert [observation.direction for observation in observations] == [
        ImpactDirection.POSITIVE,
        ImpactDirection.NEGATIVE,
    ]
    assert [observation.reason_code for observation in observations] == [
        ImpactReasonCode.FACTORY_EXPANSION_POSITIVE,
        ImpactReasonCode.MASS_LAYOFF_NEGATIVE,
    ]
    assert all(observation.company is event.companies[0] for observation in observations)


def test_rule_strategy_skips_indirect_companies_and_factless_events() -> None:
    strategy: ImpactStrategy = RuleImpactStrategy(DEFAULT_IMPACT_RULE_CATALOG)
    indirect: ResolvedNewsEvent = build_resolved_event(
        (EventFact.BANKRUPTCY,),
        (CompanyRelation.INDIRECT,),
    )

    assert strategy.analyze(indirect) == ()
    assert strategy.analyze(build_resolved_event()) == ()


def test_rule_strategy_interprets_major_supply_contract_as_positive() -> None:
    strategy: ImpactStrategy = RuleImpactStrategy(DEFAULT_IMPACT_RULE_CATALOG)

    observations: Tuple[ImpactObservation, ...] = strategy.analyze(
        build_resolved_event((EventFact.MAJOR_SUPPLY_CONTRACT,))
    )

    assert observations[0].direction is ImpactDirection.POSITIVE
    assert observations[0].reason_code is ImpactReasonCode.MAJOR_SUPPLY_CONTRACT_POSITIVE


def test_rule_strategy_preserves_conflicting_facts_and_direct_company_order() -> None:
    strategy: ImpactStrategy = RuleImpactStrategy(DEFAULT_IMPACT_RULE_CATALOG)
    event: ResolvedNewsEvent = build_resolved_event(
        (EventFact.FACTORY_EXPANSION, EventFact.MASS_LAYOFF),
        (CompanyRelation.DIRECT, CompanyRelation.INDIRECT, CompanyRelation.DIRECT),
    )

    observations: Tuple[ImpactObservation, ...] = strategy.analyze(event)

    assert [observation.event_fact for observation in observations] == [
        EventFact.FACTORY_EXPANSION,
        EventFact.FACTORY_EXPANSION,
        EventFact.MASS_LAYOFF,
        EventFact.MASS_LAYOFF,
    ]
    assert [observation.company for observation in observations] == [
        event.companies[0], event.companies[2], event.companies[0], event.companies[2]
    ]
    assert [observation.direction for observation in observations] == [
        ImpactDirection.POSITIVE, ImpactDirection.POSITIVE,
        ImpactDirection.NEGATIVE, ImpactDirection.NEGATIVE,
    ]


def test_rule_strategy_assigns_unknown_rules_high_uncertainty_without_validation() -> None:
    strategy: ImpactStrategy = RuleImpactStrategy(DEFAULT_IMPACT_RULE_CATALOG)
    observations: Tuple[ImpactObservation, ...] = strategy.analyze(
        build_resolved_event((EventFact.PRODUCT_RELEASE, EventFact.CEO_INTERVIEW))
    )

    assert [observation.direction for observation in observations] == [
        ImpactDirection.UNKNOWN,
        ImpactDirection.UNKNOWN,
    ]
    assert all(observation.uncertainty is ImpactUncertainty.HIGH for observation in observations)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (CrossValidationStatus.VERIFIED, ImpactUncertainty.LOW),
        (CrossValidationStatus.PARTIALLY_VERIFIED, ImpactUncertainty.MEDIUM),
        (CrossValidationStatus.CONFLICTED, ImpactUncertainty.HIGH),
    ],
)
def test_rule_strategy_derives_uncertainty_from_validation_status(
    status: CrossValidationStatus,
    expected: ImpactUncertainty,
) -> None:
    strategy: RuleImpactStrategy = RuleImpactStrategy(DEFAULT_IMPACT_RULE_CATALOG)
    event: ResolvedNewsEvent = build_resolved_event((EventFact.BANKRUPTCY,))
    event = ResolvedNewsEvent(
        event=event.event,
        companies=event.companies,
        cross_validation_status=status,
    )

    assert strategy.analyze(event)[0].uncertainty is expected


def test_rule_strategy_is_deterministic_and_does_not_mutate_input() -> None:
    strategy: RuleImpactStrategy = RuleImpactStrategy(DEFAULT_IMPACT_RULE_CATALOG)
    event: ResolvedNewsEvent = build_resolved_event((EventFact.BANKRUPTCY,))
    event_snapshot: dict[str, object] = event.event.model_dump(mode="json")

    assert strategy.analyze(event) == strategy.analyze(event)
    assert event.event.model_dump(mode="json") == event_snapshot


def test_rule_strategy_is_immutable() -> None:
    strategy: RuleImpactStrategy = RuleImpactStrategy(DEFAULT_IMPACT_RULE_CATALOG)

    with pytest.raises(FrozenInstanceError):
        strategy.catalog = DEFAULT_IMPACT_RULE_CATALOG
