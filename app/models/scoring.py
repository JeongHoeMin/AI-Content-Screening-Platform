from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from app.models.impact_analysis import CompanyImpact
from app.models.resolved_news_event import ResolvedCompany


@dataclass(frozen=True)
class CompanyScore:
    """Immutable quantitative score with its original explanatory evidence."""

    company: ResolvedCompany
    score: float
    evidences: Tuple[CompanyImpact, ...]


@dataclass(frozen=True)
class ScoringResult:
    """Immutable scoring snapshot consumed by the recommendation stage."""

    companies: Tuple[CompanyScore, ...]
