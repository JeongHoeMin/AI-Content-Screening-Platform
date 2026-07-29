from __future__ import annotations

from typing import Iterable, Tuple

from app.models.company_resolution import (
    CanonicalCompany,
    CompanyResolutionObservation,
    CompanyResolutionStatus,
)


class CompanyResolutionPolicy:
    """Converts directory facts into one conservative resolution observation."""

    def resolve(
        self,
        candidates: Iterable[CanonicalCompany],
        *,
        directory_version: str,
    ) -> CompanyResolutionObservation:
        distinct: dict[str, CanonicalCompany] = {
            candidate.company_id: candidate for candidate in candidates
        }
        ordered_candidates: Tuple[CanonicalCompany, ...] = tuple(
            distinct[company_id] for company_id in sorted(distinct)
        )
        candidate_count: int = len(ordered_candidates)
        if candidate_count == 0:
            return CompanyResolutionObservation(
                status=CompanyResolutionStatus.UNRESOLVED,
                candidate_count=0,
                directory_version=directory_version,
            )
        if candidate_count == 1:
            return CompanyResolutionObservation(
                status=CompanyResolutionStatus.RESOLVED,
                candidate_count=1,
                canonical_company=ordered_candidates[0],
                directory_version=directory_version,
            )
        return CompanyResolutionObservation(
            status=CompanyResolutionStatus.AMBIGUOUS,
            candidate_count=candidate_count,
            directory_version=directory_version,
        )
