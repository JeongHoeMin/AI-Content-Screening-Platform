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
        for company_name, ticker in tickers.items():
            normalized_name: str = self._normalize_company_name(company_name)
            if normalized_name in normalized_tickers:
                raise ValueError(
                    "Ticker mapping contains duplicate normalized company names"
                )
            normalized_tickers[normalized_name] = ticker
        immutable_tickers: Mapping[str, ResolvedTicker] = MappingProxyType(
            normalized_tickers
        )
        object.__setattr__(self, "_tickers", immutable_tickers)

    def resolve(self, company_name: str) -> Optional[ResolvedTicker]:
        normalized_name: str = self._normalize_company_name(company_name)
        return self._tickers.get(normalized_name)

    @staticmethod
    def _normalize_company_name(company_name: str) -> str:
        return " ".join(company_name.lower().split())
