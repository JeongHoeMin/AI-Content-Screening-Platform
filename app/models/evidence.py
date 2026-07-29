from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from app.models.impact_analysis import CompanyImpact
from app.models.resolved_news_event import ResolvedCompany


@dataclass(frozen=True)
class CompanyEvidence:
    """Immutable evidence collected for one canonical resolved company."""

    company: ResolvedCompany
    impacts: Tuple[CompanyImpact, ...]


@dataclass(frozen=True)
class EvidenceAggregation:
    """Immutable snapshot aggregating all company evidence."""

    companies: Tuple[CompanyEvidence, ...]
