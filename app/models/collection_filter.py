from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, field_validator


class InvestmentTheme(str, Enum):
    """Supported investment-theme groups selected before article analysis."""

    SEMICONDUCTOR = "semiconductor"
    ARTIFICIAL_INTELLIGENCE = "artificial_intelligence"
    RENEWABLE_ENERGY = "renewable_energy"


class NewsTopic(str, Enum):
    """Deterministic news topics selectable with an investment theme."""

    EARNINGS = "earnings"
    POLICY = "policy"
    SUPPLY_CHAIN = "supply_chain"
    TECHNOLOGY = "technology"


class FilterRejectionReason(str, Enum):
    """Safe reason a document does not satisfy a selected filter dimension."""

    THEME_MISMATCH = "theme_mismatch"
    TOPIC_MISMATCH = "topic_mismatch"


class CollectionFilter(BaseModel):
    """Immutable theme and topic constraints for one collection execution."""

    model_config = ConfigDict(frozen=True)

    themes: Tuple[InvestmentTheme, ...] = ()
    topics: Tuple[NewsTopic, ...] = ()

    @field_validator("themes", "topics")
    @classmethod
    def _deduplicate_values(cls, values: Tuple[Enum, ...]) -> Tuple[Enum, ...]:
        return tuple(dict.fromkeys(values))


class ThemeMatch(BaseModel):
    """Deterministic catalog observation without an LLM or policy decision."""

    model_config = ConfigDict(frozen=True)

    accepted: bool
    rejection_reason: Optional[FilterRejectionReason] = None
    matched_themes: Tuple[InvestmentTheme, ...] = ()
    matched_topics: Tuple[NewsTopic, ...] = ()
    catalog_version: str
