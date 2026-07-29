from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Dict, Mapping, Optional

from app.models.resolved_news_event import ResolvedTicker
from app.resolvers.lookup import TickerLookup


@dataclass(frozen=True, init=False)
class StaticTickerLookup(TickerLookup):
    """Immutable static ticker lookup using the current normalization policy.

    Construction normalizes mapping keys, rejects normalized-key collisions,
    and stores a read-only table. Resolve calls never modify internal state.
    """

    _tickers: Mapping[str, ResolvedTicker]

    def __init__(self, tickers: Mapping[str, ResolvedTicker]) -> None:
        normalized_tickers: Dict[str, ResolvedTicker] = {}
        original_keys: Dict[str, str] = {}
        for company_name, ticker in tickers.items():
            normalized_name: str = self._normalize_company_name(company_name)
            if normalized_name in normalized_tickers:
                existing_key: str = original_keys[normalized_name]
                raise ValueError(
                    "Duplicate normalized company name: "
                    f"{normalized_name!r}; original keys: "
                    f"{existing_key!r}, {company_name!r}"
                )
            normalized_tickers[normalized_name] = ticker
            original_keys[normalized_name] = company_name
        immutable_tickers: Mapping[str, ResolvedTicker] = MappingProxyType(
            normalized_tickers
        )
        object.__setattr__(self, "_tickers", immutable_tickers)

    def resolve(self, company_name: str) -> Optional[ResolvedTicker]:
        """Return the matching static ticker with average O(1) lookup time."""
        normalized_name: str = self._normalize_company_name(company_name)
        return self._tickers.get(normalized_name)

    @staticmethod
    def _normalize_company_name(company_name: str) -> str:
        """Apply the current company-name normalization policy.

        The policy trims leading and trailing whitespace, converts to lowercase,
        and collapses consecutive whitespace. It intentionally does not perform
        Unicode normalization, alias resolution, fuzzy matching, or semantic
        matching.
        """
        return " ".join(company_name.lower().split())
