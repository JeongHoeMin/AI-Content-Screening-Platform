from __future__ import annotations

from typing import List, Protocol, Tuple

from app.models.evidence import CompanyEvidence
from app.models.impact_analysis import ImpactAnalysis


class AggregationStrategy(Protocol):
    """Groups every CompanyImpact into exactly one CompanyEvidence.

    Implementations are deterministic and side-effect free. They do not mutate
    input analyses, create companies or impacts, modify directions, or wrap
    exceptions.
    """

    def aggregate(
        self,
        analyses: List[ImpactAnalysis],
    ) -> Tuple[CompanyEvidence, ...]:
        """Return immutable company evidence in the strategy-defined order."""
        ...
