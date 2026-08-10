from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import (
    PriceBasis,
    PriceErrorKind,
    PriceProvider,
    PriceSnapshotStatus,
    RecommendationAction,
    RecommendationPriceSnapshot,
)


def build_available_snapshot() -> RecommendationPriceSnapshot:
    return RecommendationPriceSnapshot(
        run_id="run-20260805",
        recommendation_index=0,
        ticker="005930",
        action=RecommendationAction.BUY,
        status=PriceSnapshotStatus.AVAILABLE,
        price=Decimal("72000"),
        basis=PriceBasis.REALTIME,
        provider=PriceProvider.KIS,
        observed_at=datetime(2026, 8, 5, 0, 15, tzinfo=timezone.utc),
        trading_date=date(2026, 8, 5),
    )


def test_available_snapshot_requires_a_positive_price() -> None:
    with pytest.raises(ValidationError, match="AVAILABLE requires a positive price"):
        RecommendationPriceSnapshot(
            run_id="run-20260805",
            recommendation_index=0,
            ticker="005930",
            action=RecommendationAction.BUY,
            status=PriceSnapshotStatus.AVAILABLE,
            price=None,
            basis=PriceBasis.REALTIME,
            provider=PriceProvider.KIS,
            observed_at=datetime(2026, 8, 5, 0, 15, tzinfo=timezone.utc),
            trading_date=date(2026, 8, 5),
        )


def test_available_snapshot_preserves_validated_price_observation() -> None:
    snapshot: RecommendationPriceSnapshot = build_available_snapshot()

    assert snapshot.price == Decimal("72000")
    assert snapshot.basis is PriceBasis.REALTIME
    assert snapshot.provider is PriceProvider.KIS
    assert snapshot.trading_date == date(2026, 8, 5)


def test_unavailable_snapshot_requires_only_a_bounded_error_kind() -> None:
    snapshot: RecommendationPriceSnapshot = RecommendationPriceSnapshot(
        run_id="run-20260805",
        recommendation_index=1,
        ticker="005930",
        action=RecommendationAction.SELL,
        status=PriceSnapshotStatus.UNAVAILABLE,
        price=None,
        basis=None,
        provider=None,
        observed_at=datetime(2026, 8, 5, 0, 15, tzinfo=timezone.utc),
        trading_date=None,
        error_kind=PriceErrorKind.NOT_CONFIGURED,
    )

    assert snapshot.error_kind is PriceErrorKind.NOT_CONFIGURED
    with pytest.raises(ValidationError, match="UNAVAILABLE requires price, basis, provider"):
        snapshot.model_copy(update={"price": Decimal("72000")}).__class__(
            **snapshot.model_copy(update={"price": Decimal("72000")}).model_dump()
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    (("recommendation_index", -1), ("ticker", "5930"), ("action", RecommendationAction.HOLD)),
)
def test_snapshot_rejects_invalid_recommendation_identity(
    field_name: str,
    value: object,
) -> None:
    payload: dict[str, object] = build_available_snapshot().model_dump()
    payload[field_name] = value

    with pytest.raises(ValidationError):
        RecommendationPriceSnapshot(**payload)


def test_snapshot_requires_utc_observed_at() -> None:
    payload: dict[str, object] = build_available_snapshot().model_dump()
    payload["observed_at"] = datetime(2026, 8, 5, 9, 15)

    with pytest.raises(ValidationError, match="UTC"):
        RecommendationPriceSnapshot(**payload)
