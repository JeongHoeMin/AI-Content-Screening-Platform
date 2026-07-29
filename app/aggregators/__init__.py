"""Company evidence aggregation contracts and implementations."""

from app.aggregators.base import EvidenceAggregator
from app.aggregators.default import DefaultEvidenceAggregator
from app.aggregators.default_strategy import DefaultAggregationStrategy
from app.aggregators.strategy import AggregationStrategy

__all__ = [
    "AggregationStrategy",
    "DefaultAggregationStrategy",
    "DefaultEvidenceAggregator",
    "EvidenceAggregator",
]
