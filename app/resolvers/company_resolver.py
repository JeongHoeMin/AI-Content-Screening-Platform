from __future__ import annotations

from typing import List, Tuple

from app.models.company_resolution import (
    CanonicalCompany,
    CompanyResolutionObservation,
    CompanyResolutionStatus,
)
from app.models.news_event import ExtractedCompany, NewsEvent
from app.models.resolved_news_event import ResolvedCompany, ResolvedTicker, TickerResolvedEvent
from app.resolvers.base import TickerResolver
from app.resolvers.company_policy import CompanyResolutionPolicy
from app.resolvers.directory import CompanyDirectory


class DefaultCompanyResolver(TickerResolver):
    """Builds immutable company snapshots from directory facts and policy output."""

    def __init__(
        self,
        directory: CompanyDirectory,
        policy: CompanyResolutionPolicy,
    ) -> None:
        self._directory: CompanyDirectory = directory
        self._policy: CompanyResolutionPolicy = policy

    def resolve(self, events: List[NewsEvent]) -> List[TickerResolvedEvent]:
        return [
            TickerResolvedEvent(
                event=event,
                companies=self._resolve_companies(event.companies),
            )
            for event in events
        ]

    def _resolve_companies(
        self,
        companies: List[ExtractedCompany],
    ) -> Tuple[ResolvedCompany, ...]:
        return tuple(self._resolve_company(company) for company in companies)

    def _resolve_company(self, company: ExtractedCompany) -> ResolvedCompany:
        observation: CompanyResolutionObservation = self._policy.resolve(
            self._directory.find_candidates(company.name),
            directory_version=self._directory.version,
        )
        canonical_company: CanonicalCompany | None = observation.canonical_company
        ticker: ResolvedTicker | None = None
        company_id: str | None = None
        if canonical_company is not None:
            ticker = ResolvedTicker(
                ticker=canonical_company.ticker,
                exchange=canonical_company.exchange,
            )
            company_id = canonical_company.company_id
        return ResolvedCompany(
            name=company.name,
            relation=company.relation,
            ticker=ticker,
            company_id=company_id,
            resolution_status=observation.status,
            directory_version=observation.directory_version,
        )
