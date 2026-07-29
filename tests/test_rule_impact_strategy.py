from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import List, Tuple

import pytest

from app.analyzers import ImpactStrategy, RuleImpactStrategy
from app.models import (
    CompanyImpact,
    CompanyRelation,
    ExtractedCompany,
    ImpactDirection,
    NewsEvent,
    ResolvedCompany,
    ResolvedNewsEvent,
    ResolvedTicker,
)


def build_resolved_event(
    title: str,
    summary: str,
    company_count: int = 1,
) -> ResolvedNewsEvent:
    companies: List[ResolvedCompany] = [
        ResolvedCompany(
            name=f"Company {index}",
            relation=CompanyRelation.DIRECT,
            ticker=ResolvedTicker(ticker=f"0000{index}", exchange="KRX"),
        )
        for index in range(company_count)
    ]
    event: NewsEvent = NewsEvent(
        title=title,
        summary=summary,
        companies=[
            ExtractedCompany(
                name=company.name,
                relation=company.relation,
            )
            for company in companies
        ],
        industries=["Semiconductors"],
        keywords=["HBM"],
        reasons=["Fact is stated in the article"],
    )
    return ResolvedNewsEvent(event=event, companies=tuple(companies))


@pytest.mark.parametrize(
    ("title", "summary", "expected_direction"),
    [
        ("공장 증설 발표", "생산 능력을 확대한다.", ImpactDirection.POSITIVE),
        ("새 설비 투자", "생산 라인 투자 계획", ImpactDirection.POSITIVE),
        ("사업 계획", "투자 확대를 결정했다.", ImpactDirection.POSITIVE),
        ("소송 제기", "법적 분쟁이 시작됐다.", ImpactDirection.NEGATIVE),
        ("제품 리콜", "자발적 리콜을 발표했다.", ImpactDirection.NEGATIVE),
        ("계약 종료", "공급 계약이 종료된다.", ImpactDirection.NEGATIVE),
        ("계약 체결", "새 공급 계약을 맺었다.", ImpactDirection.UNKNOWN),
        ("일반 기사", "특별한 방향 판단 근거가 없다.", ImpactDirection.UNKNOWN),
        ("공장 증설", "소송 가능성도 제기됐다.", ImpactDirection.UNKNOWN),
    ],
)
def test_rule_strategy_applies_current_default_policy(
    title: str,
    summary: str,
    expected_direction: ImpactDirection,
) -> None:
    strategy: ImpactStrategy = RuleImpactStrategy()
    event: ResolvedNewsEvent = build_resolved_event(title, summary)

    impacts: Tuple[CompanyImpact, ...] = strategy.analyze(event)

    assert impacts[0].direction is expected_direction


def test_rule_strategy_combines_title_and_summary_before_matching() -> None:
    strategy: RuleImpactStrategy = RuleImpactStrategy()
    event: ResolvedNewsEvent = build_resolved_event(
        title="일반 기사",
        summary="설비 투자 계획을 발표했다.",
    )

    impacts: Tuple[CompanyImpact, ...] = strategy.analyze(event)

    assert impacts[0].direction is ImpactDirection.POSITIVE


def test_rule_strategy_preserves_each_company_identity_and_current_direction_policy() -> None:
    strategy: RuleImpactStrategy = RuleImpactStrategy()
    event: ResolvedNewsEvent = build_resolved_event(
        title="공장 증설",
        summary="생산 능력을 확대한다.",
        company_count=3,
    )

    impacts: Tuple[CompanyImpact, ...] = strategy.analyze(event)

    assert len(impacts) == 3
    assert [impact.company for impact in impacts] == list(event.companies)
    assert all(
        impact.company is event.companies[index]
        for index, impact in enumerate(impacts)
    )
    assert all(impact.direction is ImpactDirection.POSITIVE for impact in impacts)


def test_rule_strategy_is_deterministic_and_does_not_mutate_input() -> None:
    strategy: RuleImpactStrategy = RuleImpactStrategy()
    event: ResolvedNewsEvent = build_resolved_event(
        title="리콜 발표",
        summary="제품 리콜을 실시한다.",
    )
    event_snapshot: dict[str, object] = event.event.model_dump(mode="json")
    companies_snapshot: Tuple[ResolvedCompany, ...] = event.companies

    first_impacts: Tuple[CompanyImpact, ...] = strategy.analyze(event)
    second_impacts: Tuple[CompanyImpact, ...] = strategy.analyze(event)

    assert first_impacts == second_impacts
    assert event.event.model_dump(mode="json") == event_snapshot
    assert event.companies is companies_snapshot


def test_rule_strategy_is_immutable() -> None:
    strategy: RuleImpactStrategy = RuleImpactStrategy()

    with pytest.raises(FrozenInstanceError):
        strategy._policy = "changed"
