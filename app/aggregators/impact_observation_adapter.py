from __future__ import annotations

from app.models.impact_analysis import CompanyImpact, ImpactObservation, ImpactScope


class ImpactObservationAdapter:
    """Converts one eligible COMPANY observation into one legacy evidence item."""

    def to_company_impact(self, observation: ImpactObservation) -> CompanyImpact:
        """Preserve the observation direction without merging or cancellation."""
        if observation.scope is not ImpactScope.COMPANY or observation.company is None:
            raise ValueError("Only COMPANY observations with a company are adaptable")
        return CompanyImpact(company=observation.company, direction=observation.direction)
