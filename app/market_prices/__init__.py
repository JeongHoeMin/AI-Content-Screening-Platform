"""Bounded market-price lookup adapters and fallback orchestration."""

from app.market_prices.contracts import PriceLookupClient, PriceLookupObservation
from app.market_prices.kis import KisRealtimePriceClient
from app.market_prices.krx import KrxClosingPriceClient
from app.market_prices.service import MarketPriceService
from app.market_prices.performance import (
    RecommendationPerformanceItem,
    RecommendationPerformancePolicy,
    RecommendationPerformanceResponse,
    RecommendationPerformanceSummary,
)

__all__ = [
    "KisRealtimePriceClient",
    "KrxClosingPriceClient",
    "MarketPriceService",
    "PriceLookupClient",
    "PriceLookupObservation",
    "RecommendationPerformanceItem",
    "RecommendationPerformancePolicy",
    "RecommendationPerformanceResponse",
    "RecommendationPerformanceSummary",
]
