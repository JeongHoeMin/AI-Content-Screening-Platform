from __future__ import annotations

from enum import Enum


class DartEventCategory(str, Enum):
    """Investment-relevant DART disclosure categories allowed into discovery."""

    SUPPLY_CONTRACT = "supply_contract"
    EARNINGS_GUIDANCE = "earnings_guidance"
    CAPACITY_INVESTMENT = "capacity_investment"
    MERGER_ACQUISITION = "merger_acquisition"
    CAPITAL_EVENT = "capital_event"
    REGULATORY_LEGAL = "regulatory_legal"
