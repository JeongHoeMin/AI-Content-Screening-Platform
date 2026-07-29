from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import List, Optional

import pytest

from app.deduplicators import DuplicateStrategy, RuleDuplicateStrategy
from app.models import CompanyRelation, ExtractedCompany, NewsEvent


def build_event(
    title: str = "Samsung expands HBM production",
    company_names: Optional[List[str]] = None,
    industries: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    relation: CompanyRelation = CompanyRelation.DIRECT,
) -> NewsEvent:
    resolved_company_names: List[str] = (
        ["Samsung Electronics"] if company_names is None else company_names
    )
    resolved_industries: List[str] = (
        ["Semiconductors"] if industries is None else industries
    )
    resolved_keywords: List[str] = (
        ["HBM", "production"] if keywords is None else keywords
    )
    return NewsEvent(
        title=title,
        summary="Event summary",
        companies=[
            ExtractedCompany(name=name, relation=relation)
            for name in resolved_company_names
        ],
        industries=resolved_industries,
        keywords=resolved_keywords,
        reasons=["Fact is stated in the article"],
    )


def test_default_threshold_is_half_and_strategy_is_immutable() -> None:
    strategy: RuleDuplicateStrategy = RuleDuplicateStrategy()

    assert strategy.keyword_similarity_threshold == 0.5
    with pytest.raises(FrozenInstanceError):
        strategy.keyword_similarity_threshold = 0.7


@pytest.mark.parametrize("threshold", [-0.1, 1.5])
def test_invalid_threshold_fails_during_construction(threshold: float) -> None:
    with pytest.raises(ValueError):
        RuleDuplicateStrategy(keyword_similarity_threshold=threshold)


def test_same_event_is_duplicate_and_rule_is_reflexive() -> None:
    strategy: DuplicateStrategy = RuleDuplicateStrategy()
    event: NewsEvent = build_event()

    assert strategy.is_duplicate(event, event) is True


def test_title_normalization_and_company_relation_are_ignored() -> None:
    strategy: RuleDuplicateStrategy = RuleDuplicateStrategy()
    left: NewsEvent = build_event(title="  Samsung   expands HBM production  ")
    right: NewsEvent = build_event(
        title="samsung expands hbm production",
        relation=CompanyRelation.INDIRECT,
    )

    assert strategy.is_duplicate(left, right) is True
    assert strategy.is_duplicate(right, left) is True


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        (" Samsung  AI ", "samsung ai"),
        ("Samsung     AI", "samsung ai"),
    ],
)
def test_normalize_title_applies_default_policy(
    title: str,
    expected: str,
) -> None:
    assert RuleDuplicateStrategy._normalize_title(title) == expected


@pytest.mark.parametrize(
    "right",
    [
        build_event(company_names=["SK hynix"]),
        build_event(industries=["Memory"]),
        build_event(title="Samsung starts a new factory"),
        build_event(keywords=["HBM", "factory"]),
    ],
)
def test_rule_requires_all_default_policy_conditions(right: NewsEvent) -> None:
    strategy: RuleDuplicateStrategy = RuleDuplicateStrategy()
    left: NewsEvent = build_event()

    assert strategy.is_duplicate(left, right) is False


def test_keyword_jaccard_threshold_accepts_half_similarity() -> None:
    strategy: RuleDuplicateStrategy = RuleDuplicateStrategy()
    left: NewsEvent = build_event(keywords=["HBM", "production"])
    right: NewsEvent = build_event(keywords=["HBM"])

    assert strategy.is_duplicate(left, right) is True


def test_empty_keyword_sets_are_duplicate_when_other_conditions_match() -> None:
    strategy: RuleDuplicateStrategy = RuleDuplicateStrategy()
    left: NewsEvent = build_event(keywords=[])
    right: NewsEvent = build_event(keywords=[])

    assert strategy.is_duplicate(left, right) is True


def test_one_empty_keyword_set_is_not_duplicate() -> None:
    strategy: RuleDuplicateStrategy = RuleDuplicateStrategy()
    left: NewsEvent = build_event(keywords=[])
    right: NewsEvent = build_event(keywords=["HBM"])

    assert strategy.is_duplicate(left, right) is False


def test_strategy_is_deterministic_and_does_not_mutate_inputs() -> None:
    strategy: RuleDuplicateStrategy = RuleDuplicateStrategy()
    left: NewsEvent = build_event()
    right: NewsEvent = build_event()
    left_snapshot: dict[str, object] = left.model_dump(mode="json")
    right_snapshot: dict[str, object] = right.model_dump(mode="json")

    first_result: bool = strategy.is_duplicate(left, right)
    second_result: bool = strategy.is_duplicate(left, right)

    assert first_result is True
    assert second_result is first_result
    assert left.model_dump(mode="json") == left_snapshot
    assert right.model_dump(mode="json") == right_snapshot
