from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

from app.harness.entry_price_backfill import (
    DailyEntryPriceBackfill,
    HistoricalClosingPriceCapture,
    RecommendationEntryPriceBackfill,
)
from app.market_prices.contracts import PriceLookupObservation
from app.models.market_price import (
    PriceBasis,
    PriceErrorKind,
    PriceProvider,
    PriceSnapshotStatus,
    RecommendationPriceSnapshot,
)
from app.models.recommendation import RecommendationAction
from app.persistence.price_repository import RecommendationPriceEntry, SnapshotKind


def _unavailable_entry() -> RecommendationPriceEntry:
    return RecommendationPriceEntry(
        snapshot=RecommendationPriceSnapshot(
            run_id="run-1",
            recommendation_index=0,
            ticker="005930",
            action=RecommendationAction.BUY,
            status=PriceSnapshotStatus.UNAVAILABLE,
            observed_at=datetime(2026, 8, 4, 15, tzinfo=timezone.utc),
            error_kind=PriceErrorKind.TRANSPORT,
        ),
        snapshot_kind=SnapshotKind.ENTRY,
        company_id="005930",
        company_name="삼성전자",
    )


def test_entry_backfill_uses_the_original_recommendation_time_and_only_updates_unavailable_entries() -> None:
    entry = _unavailable_entry()

    class ClosingClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, datetime]] = []

        async def fetch(self, ticker: str, observed_at: datetime) -> PriceLookupObservation:
            self.calls.append((ticker, observed_at))
            return PriceLookupObservation(
                status=PriceSnapshotStatus.AVAILABLE,
                price=Decimal("71000"),
                basis=PriceBasis.CLOSE,
                provider=PriceProvider.KRX,
                observed_at=observed_at,
                trading_date=date(2026, 8, 4),
            )

    class Persistence:
        def __init__(self) -> None:
            self.updated: tuple[RecommendationPriceEntry, ...] = ()

        async def list_snapshots(self) -> tuple[RecommendationPriceEntry, ...]:
            return (entry,)

        async def backfill_entries(
            self, snapshots: tuple[RecommendationPriceEntry, ...]
        ) -> int:
            self.updated = snapshots
            return len(snapshots)

    client = ClosingClient()
    persistence = Persistence()
    recovered = asyncio.run(
        RecommendationEntryPriceBackfill(
            HistoricalClosingPriceCapture(client), persistence
        ).backfill("run-1", 0)
    )

    assert recovered == 1
    assert client.calls == [("005930", entry.snapshot.observed_at)]
    assert persistence.updated[0].snapshot.price == Decimal("71000")
    assert persistence.updated[0].snapshot.basis is PriceBasis.CLOSE


def test_daily_entry_backfill_runs_once_per_kst_day() -> None:
    class Backfill:
        def __init__(self) -> None:
            self.calls = 0

        async def backfill(self) -> int:
            self.calls += 1
            return 2

    backfill = Backfill()
    daily = DailyEntryPriceBackfill(backfill)  # type: ignore[arg-type]

    assert asyncio.run(daily.run_if_due(datetime(2026, 8, 4, 15, tzinfo=timezone.utc))) == 2
    assert asyncio.run(daily.run_if_due(datetime(2026, 8, 5, 14, tzinfo=timezone.utc))) is None
    assert asyncio.run(daily.run_if_due(datetime(2026, 8, 5, 15, tzinfo=timezone.utc))) == 2
    assert backfill.calls == 2
