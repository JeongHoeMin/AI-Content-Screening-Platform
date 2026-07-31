from __future__ import annotations

from typing import List

from app.models import (
    CanonicalCompany,
    CompanyDirectoryEntry,
    CompanyRelation,
    CompanyResolutionStatus,
    EventType,
    ExtractedCompany,
    KRXExchange,
    NewsEvent,
)
from app.resolvers import (
    CompanyDirectory,
    CompanyResolutionPolicy,
    DefaultCompanyResolver,
    StaticCompanyDirectory,
)


def build_company(
    company_id: str,
    name: str,
    ticker: str,
) -> CanonicalCompany:
    return CanonicalCompany(
        company_id=company_id,
        canonical_name=name,
        ticker=ticker,
        exchange=KRXExchange.KOSPI,
        directory_version="2026-07-30",
    )


def build_event(companies: List[ExtractedCompany]) -> NewsEvent:
    return NewsEvent(
        title="Company event",
        summary="A company event",
        event_type=EventType.CORPORATE_EVENT,
        companies=companies,
        industries=["Semiconductors"],
        keywords=["HBM"],
        reasons=["Article evidence"],
    )


def test_policy_deduplicates_candidates_by_company_id_and_sorts_them() -> None:
    first: CanonicalCompany = build_company("KRX-COMPANY-000002", "B", "000002")
    second: CanonicalCompany = build_company("KRX-COMPANY-000001", "A", "000001")
    policy: CompanyResolutionPolicy = CompanyResolutionPolicy()

    observation = policy.resolve(
        (first, second, first),
        directory_version="2026-07-30",
    )

    assert observation.status is CompanyResolutionStatus.AMBIGUOUS
    assert observation.candidate_count == 2
    assert observation.canonical_company is None


def test_resolver_preserves_identity_order_and_resolution_outcomes() -> None:
    samsung: CanonicalCompany = build_company(
        "KRX-COMPANY-000001",
        "Samsung Electronics",
        "005930",
    )
    sdi: CanonicalCompany = build_company(
        "KRX-COMPANY-000002",
        "Samsung SDI",
        "006400",
    )
    directory = StaticCompanyDirectory(
        [
            CompanyDirectoryEntry(company=samsung, aliases=("Samsung",)),
            CompanyDirectoryEntry(company=sdi, aliases=("Samsung",)),
        ],
        version="2026-07-30",
    )
    event: NewsEvent = build_event(
        [
            ExtractedCompany(name="Samsung Electronics", relation=CompanyRelation.DIRECT),
            ExtractedCompany(name="Samsung", relation=CompanyRelation.INDIRECT),
            ExtractedCompany(name="Unknown", relation=CompanyRelation.DIRECT),
        ]
    )
    resolver = DefaultCompanyResolver(directory, CompanyResolutionPolicy())

    result = resolver.resolve([event])

    assert result[0].event is event
    assert [company.name for company in result[0].companies] == [
        "Samsung Electronics",
        "Samsung",
        "Unknown",
    ]
    assert result[0].companies[0].resolution_status is CompanyResolutionStatus.RESOLVED
    assert result[0].companies[0].company_id == "KRX-COMPANY-000001"
    assert result[0].companies[0].ticker is not None
    assert result[0].companies[1].resolution_status is CompanyResolutionStatus.AMBIGUOUS
    assert result[0].companies[1].company_id is None
    assert result[0].companies[1].ticker is None
    assert result[0].companies[2].resolution_status is CompanyResolutionStatus.UNRESOLVED
    assert result[0].companies[2].directory_version == "2026-07-30"


def test_resolver_is_deterministic_when_candidate_order_changes() -> None:
    first: CanonicalCompany = build_company("KRX-COMPANY-000002", "B", "000002")
    second: CanonicalCompany = build_company("KRX-COMPANY-000001", "A", "000001")

    class ReversingDirectory(CompanyDirectory):
        @property
        def version(self) -> str:
            return "2026-07-30"

        def find_candidates(self, company_name: str) -> tuple[CanonicalCompany, ...]:
            return (second, first) if company_name == "forward" else (first, second)

    resolver = DefaultCompanyResolver(ReversingDirectory(), CompanyResolutionPolicy())
    first_event: NewsEvent = build_event(
        [ExtractedCompany(name="forward", relation=CompanyRelation.DIRECT)]
    )
    second_event: NewsEvent = build_event(
        [ExtractedCompany(name="reverse", relation=CompanyRelation.DIRECT)]
    )

    first_result = resolver.resolve([first_event])[0].companies[0]
    second_result = resolver.resolve([second_event])[0].companies[0]

    assert first_result.resolution_status is second_result.resolution_status
    assert first_result.company_id is second_result.company_id is None
    assert first_result.directory_version == second_result.directory_version


def test_resolver_is_deterministic_across_repeated_runs() -> None:
    company: CanonicalCompany = build_company(
        "KRX-COMPANY-000001",
        "Samsung Electronics",
        "005930",
    )
    directory = StaticCompanyDirectory(
        [CompanyDirectoryEntry(company=company, aliases=("Samsung",))],
        version="2026-07-30",
    )
    resolver = DefaultCompanyResolver(directory, CompanyResolutionPolicy())
    event: NewsEvent = build_event(
        [ExtractedCompany(name="Samsung", relation=CompanyRelation.DIRECT)]
    )

    outcomes = tuple(
        resolver.resolve([event])[0].companies[0]
        for _ in range(100)
    )

    assert all(outcome == outcomes[0] for outcome in outcomes)
    assert outcomes[0].company_id == "KRX-COMPANY-000001"
