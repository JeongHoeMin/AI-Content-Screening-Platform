from __future__ import annotations

from enum import Enum
from typing import Annotated, ClassVar, Dict, List, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EventType(str, Enum):
    """Stable top-level domain category for one extracted event."""

    CORPORATE_EVENT = "corporate_event"
    LEGAL_EVENT = "legal_event"
    FINANCIAL_EVENT = "financial_event"
    PRODUCT_EVENT = "product_event"
    MACRO_EVENT = "macro_event"


class EventFact(str, Enum):
    """Independent, concrete fact extracted from one event."""

    FACTORY_EXPANSION = "factory_expansion"
    MASS_LAYOFF = "mass_layoff"
    BANKRUPTCY = "bankruptcy"
    PRODUCT_RELEASE = "product_release"
    CEO_INTERVIEW = "ceo_interview"

    _COMPATIBLE_EVENT_TYPES: ClassVar[Dict["EventFact", EventType]]

    def is_compatible_with(self, event_type: EventType) -> bool:
        """Return whether this fact belongs to the supplied event category."""
        return self._COMPATIBLE_EVENT_TYPES[self] is event_type


EventFact._COMPATIBLE_EVENT_TYPES = {
    EventFact.FACTORY_EXPANSION: EventType.CORPORATE_EVENT,
    EventFact.MASS_LAYOFF: EventType.CORPORATE_EVENT,
    EventFact.BANKRUPTCY: EventType.FINANCIAL_EVENT,
    EventFact.PRODUCT_RELEASE: EventType.PRODUCT_EVENT,
    EventFact.CEO_INTERVIEW: EventType.CORPORATE_EVENT,
}


class CompanyRelation(str, Enum):
    """Fact-based relationship between a company and a news event."""

    DIRECT = "direct"
    INDIRECT = "indirect"


class ExtractedCompany(BaseModel):
    """Company explicitly connected to a news event."""

    name: str = Field(min_length=1)
    relation: CompanyRelation


class NewsEvent(BaseModel):
    """Non-persistent value object extracted from an evaluated article."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    event_type: EventType
    event_facts: Tuple[EventFact, ...] = ()
    companies: List[ExtractedCompany]
    industries: List[Annotated[str, Field(min_length=1)]]
    keywords: List[Annotated[str, Field(min_length=1)]]
    reasons: List[Annotated[str, Field(min_length=1)]]

    @field_validator("event_facts")
    @classmethod
    def deduplicate_event_facts(
        cls,
        event_facts: Tuple[EventFact, ...],
    ) -> Tuple[EventFact, ...]:
        """Retain independent facts in extraction order without duplicates."""
        return tuple(dict.fromkeys(event_facts))

    @model_validator(mode="after")
    def validate_fact_compatibility(self) -> "NewsEvent":
        """Reject facts that do not belong to the event's primary category."""
        incompatible_facts: Tuple[EventFact, ...] = tuple(
            fact
            for fact in self.event_facts
            if not fact.is_compatible_with(self.event_type)
        )
        if incompatible_facts:
            raise ValueError(
                "Event facts must be compatible with the primary event type."
            )
        return self
