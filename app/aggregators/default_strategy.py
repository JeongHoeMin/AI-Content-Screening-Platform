from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.aggregators.strategy import AggregationStrategy
from app.models.evidence import CompanyEvidence
from app.models.impact_analysis import CompanyImpact, ImpactAnalysis
from app.models.resolved_news_event import ResolvedCompany, ResolvedTicker


@dataclass(frozen=True)
class DefaultAggregationStrategy(AggregationStrategy):
    """Groups resolved impacts by ticker and preserves unresolved impacts.

    ResolvedTicker equality, rather than object identity, determines resolved
    company grouping. Each unresolved impact remains in an independent group.
    """

    def aggregate(
        self,
        analyses: List[ImpactAnalysis],
    ) -> Tuple[CompanyEvidence, ...]:
        resolved_group_indices: Dict[ResolvedTicker, int] = {}
        canonical_companies: List[ResolvedCompany] = []
        grouped_impacts: List[List[CompanyImpact]] = []

        for analysis in analyses:
            for impact in analysis.impacts:
                ticker: Optional[ResolvedTicker] = impact.company.ticker
                if ticker is None:
                    canonical_companies.append(impact.company)
                    grouped_impacts.append([impact])
                    continue

                group_index: Optional[int] = resolved_group_indices.get(ticker)
                if group_index is None:
                    group_index = len(canonical_companies)
                    resolved_group_indices[ticker] = group_index
                    canonical_companies.append(impact.company)
                    grouped_impacts.append([impact])
                    continue

                grouped_impacts[group_index].append(impact)

        return tuple(
            CompanyEvidence(
                company=canonical_companies[index],
                impacts=tuple(impacts),
            )
            for index, impacts in enumerate(grouped_impacts)
        )
