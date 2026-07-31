from __future__ import annotations

from enum import Enum
from typing import Annotated, List, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    MAJOR_SUPPLY_CONTRACT = "major_supply_contract"


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
