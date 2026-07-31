from __future__ import annotations

from app.aggregators import ImpactObservationAdapter
from app.models import (
    CompanyRelation, EventFact, ImpactDirection, ImpactObservation,
    ImpactReasonCode, ImpactScope, ImpactUncertainty, ResolvedCompany,
    ResolvedTicker,
)


def test_adapter_creates_one_legacy_evidence_for_each_observation() -> None:
    company: ResolvedCompany = ResolvedCompany(name="Company", relation=CompanyRelation.DIRECT, ticker=ResolvedTicker(ticker="005930", exchange="KRX"))
    observations: tuple[ImpactObservation, ...] = (
        ImpactObservation(scope=ImpactScope.COMPANY, company=company, event_fact=EventFact.FACTORY_EXPANSION, direction=ImpactDirection.POSITIVE, uncertainty=ImpactUncertainty.HIGH, reason_code=ImpactReasonCode.FACTORY_EXPANSION_POSITIVE),
        ImpactObservation(scope=ImpactScope.COMPANY, company=company, event_fact=EventFact.MASS_LAYOFF, direction=ImpactDirection.NEGATIVE, uncertainty=ImpactUncertainty.HIGH, reason_code=ImpactReasonCode.MASS_LAYOFF_NEGATIVE),
    )

    impacts = tuple(ImpactObservationAdapter().to_company_impact(item) for item in observations)

    assert [impact.direction for impact in impacts] == [ImpactDirection.POSITIVE, ImpactDirection.NEGATIVE]
    assert all(impact.company is company for impact in impacts)
