from __future__ import annotations

from typing import List, Optional

import pytest

from app.models import EvidenceAggregation, ScoringResult
from app.scorers import DefaultScoringEngine, ScoringEngine, ScoringStrategy


class FakeScoringStrategy(ScoringStrategy):
    def __init__(self, result: ScoringResult, error: Optional[Exception] = None) -> None:
        self.result: ScoringResult = result
        self.error: Optional[Exception] = error
        self.calls: List[EvidenceAggregation] = []

    def score(self, aggregation: EvidenceAggregation) -> ScoringResult:
        self.calls.append(aggregation)
        if self.error is not None:
            raise self.error
        return self.result


def test_engine_returns_the_exact_strategy_result_without_reassembly() -> None:
    aggregation: EvidenceAggregation = EvidenceAggregation(companies=())
    strategy_result: ScoringResult = ScoringResult(policy_version="test-v1", companies=())
    strategy: FakeScoringStrategy = FakeScoringStrategy(strategy_result)
    engine: ScoringEngine = DefaultScoringEngine(strategy)

    assert engine.score(aggregation) is strategy_result
    assert strategy.calls == [aggregation]


def test_engine_propagates_strategy_error_without_wrapping() -> None:
    aggregation: EvidenceAggregation = EvidenceAggregation(companies=())
    expected_error: RuntimeError = RuntimeError("scoring failed")
    strategy: FakeScoringStrategy = FakeScoringStrategy(ScoringResult(policy_version="test-v1", companies=()), expected_error)

    with pytest.raises(RuntimeError) as error_info:
        DefaultScoringEngine(strategy).score(aggregation)

    assert error_info.value is expected_error
    assert strategy.calls == [aggregation]
