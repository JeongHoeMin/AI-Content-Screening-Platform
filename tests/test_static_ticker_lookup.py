from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Dict, Optional

import pytest

from app.models import ResolvedTicker
from app.resolvers import StaticTickerLookup, TickerLookup


def build_ticker(ticker: str = "005930") -> ResolvedTicker:
    return ResolvedTicker(ticker=ticker, exchange="KRX")


def test_lookup_resolves_registered_name_with_default_normalization() -> None:
    expected_ticker: ResolvedTicker = build_ticker()
    lookup: TickerLookup = StaticTickerLookup(
        {"Samsung Electronics": expected_ticker}
    )

    result: Optional[ResolvedTicker] = lookup.resolve(
        "  samsung   electronics  "
    )

    assert result is expected_ticker


def test_lookup_returns_none_for_unknown_company() -> None:
    lookup: StaticTickerLookup = StaticTickerLookup(
        {"Samsung Electronics": build_ticker()}
    )

    assert lookup.resolve("Unknown Company") is None


def test_lookup_is_isolated_from_external_mapping_and_stays_unchanged() -> None:
    samsung_ticker: ResolvedTicker = build_ticker()
    source_mapping: Dict[str, ResolvedTicker] = {
        "Samsung Electronics": samsung_ticker
    }
    lookup: StaticTickerLookup = StaticTickerLookup(source_mapping)
    table_identity: object = lookup._tickers
    table_snapshot: Dict[str, ResolvedTicker] = dict(lookup._tickers)

    source_mapping["LG Electronics"] = build_ticker("066570")
    first_result: Optional[ResolvedTicker] = lookup.resolve("Samsung Electronics")
    second_result: Optional[ResolvedTicker] = lookup.resolve("LG Electronics")
    third_result: Optional[ResolvedTicker] = lookup.resolve("Samsung Electronics")

    assert first_result is samsung_ticker
    assert second_result is None
    assert third_result is samsung_ticker
    assert lookup._tickers is table_identity
    assert dict(lookup._tickers) == table_snapshot
    with pytest.raises(TypeError):
        lookup._tickers["LG Electronics"] = build_ticker("066570")


def test_lookup_is_immutable_after_construction() -> None:
    lookup: StaticTickerLookup = StaticTickerLookup(
        {"Samsung Electronics": build_ticker()}
    )

    with pytest.raises(FrozenInstanceError):
        lookup._tickers = {}


def test_normalized_mapping_key_collision_fails_during_construction() -> None:
    with pytest.raises(ValueError):
        StaticTickerLookup(
            {
                "Samsung Electronics": build_ticker(),
                "  samsung   electronics  ": build_ticker("005931"),
            }
        )
