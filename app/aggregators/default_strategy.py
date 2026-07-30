from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.aggregators.strategy import AggregationStrategy
from app.aggregators.impact_observation_adapter import ImpactObservationAdapter
from app.models.evidence import CompanyEvidence
from app.models.impact_analysis import CompanyImpact, ImpactAnalysis
from app.models.company_resolution import CompanyResolutionStatus
from app.models.resolved_news_event import ResolvedCompany


@dataclass(frozen=True)
class DefaultAggregationStrategy(AggregationStrategy):
    """Groups only canonical resolved impacts by stable company identity."""

    adapter: ImpactObservationAdapter = ImpactObservationAdapter()

    def aggregate(
        self,
        analyses: List[ImpactAnalysis],
    ) -> Tuple[CompanyEvidence, ...]:
        resolved_group_indices: Dict[str, int] = {}
        canonical_companies: List[ResolvedCompany] = []
        grouped_impacts: List[List[CompanyImpact]] = []

        for analysis in analyses:
            for observation, filter_result in zip(
                analysis.observations,
                analysis.filters,
            ):
                if not filter_result.eligible:
                    continue
                impact: CompanyImpact = self.adapter.to_company_impact(observation)
                company_id: Optional[str] = impact.company.company_id
                if (
                    impact.company.resolution_status
                    is not CompanyResolutionStatus.RESOLVED
                    or company_id is None
                ):
                    continue

                group_index: Optional[int] = resolved_group_indices.get(company_id)
                if group_index is None:
                    group_index = len(canonical_companies)
                    resolved_group_indices[company_id] = group_index
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
