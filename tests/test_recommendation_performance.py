from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import asyncio

from app.models.market_price import (
    PriceBasis,
    PriceErrorKind,
    PriceProvider,
    PriceSnapshotStatus,
    RecommendationPriceSnapshot,
)
from app.models.recommendation import RecommendationAction


def _snapshot(
    *,
    action: RecommendationAction = RecommendationAction.BUY,
    ticker: str = "005930",
    price: Decimal | None = Decimal("100"),
    currency: str = "KRW",
    run_id: str = "run-1",
    recommendation_index: int = 0,
) -> RecommendationPriceSnapshot:
    if price is None:
        return RecommendationPriceSnapshot(
            run_id=run_id,
            recommendation_index=recommendation_index,
            ticker=ticker,
            action=action,
            status=PriceSnapshotStatus.UNAVAILABLE,
            observed_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            error_kind=PriceErrorKind.NOT_FOUND,
        )
    return RecommendationPriceSnapshot(
        run_id=run_id,
        recommendation_index=recommendation_index,
        ticker=ticker,
        action=action,
        status=PriceSnapshotStatus.AVAILABLE,
        price=price,
        currency=currency,
        basis=PriceBasis.CLOSE,
        provider=PriceProvider.KRX,
        observed_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        trading_date=date(2026, 8, 4),
    )


def test_policy_calculates_positive_sell_return_rounded_half_up() -> None:
    from app.market_prices.performance import RecommendationPerformancePolicy

    performance = RecommendationPerformancePolicy().evaluate(
        _snapshot(action=RecommendationAction.SELL, price=Decimal("100")),
        _snapshot(action=RecommendationAction.SELL, price=Decimal("90")),
    )

    assert performance.return_percent == Decimal("10.0")


def test_policy_keeps_return_unknown_when_a_price_is_unavailable_or_mismatched() -> None:
    from app.market_prices.performance import RecommendationPerformancePolicy

    policy = RecommendationPerformancePolicy()
    unavailable = policy.evaluate(_snapshot(), _snapshot(price=None))
    mismatched_ticker = policy.evaluate(_snapshot(), _snapshot(ticker="000660"))

    assert unavailable.return_percent is None
    assert mismatched_ticker.return_percent is None


def test_policy_uses_half_up_and_rejects_missing_or_currency_mismatch_latest() -> None:
    from app.market_prices.performance import RecommendationPerformancePolicy

    policy = RecommendationPerformancePolicy()
    entry = _snapshot(price=Decimal("1000"))
    half_up_latest = _snapshot(price=Decimal("1000.5"))
    mismatched_currency = half_up_latest.model_copy(update={"currency": "USD"})

    assert policy.evaluate(entry, half_up_latest).return_percent == Decimal("0.1")
    assert policy.evaluate(entry, None).return_percent is None
    assert policy.evaluate(entry, mismatched_currency).return_percent is None


def test_policy_summarizes_buy_sell_win_rate_and_median() -> None:
    from app.market_prices.performance import RecommendationPerformancePolicy

    policy = RecommendationPerformancePolicy()
    performances = (
        policy.evaluate(_snapshot(price=Decimal("100")), _snapshot(price=Decimal("110"))),
        policy.evaluate(_snapshot(price=Decimal("100")), _snapshot(price=Decimal("90"))),
        policy.evaluate(
            _snapshot(action=RecommendationAction.SELL, price=Decimal("100")),
            _snapshot(action=RecommendationAction.SELL, price=Decimal("90")),
        ),
    )

    summary = policy.summarize(performances)

    assert summary.confirmed_count == 3
    assert summary.buy_count == 2
    assert summary.sell_count == 1
    assert summary.positive_win_rate == 66.7
    assert summary.mean_return_percent == 3.3
    assert summary.median_return_percent == 10.0


def test_service_upserts_latest_without_replacing_the_entry_snapshot() -> None:
    from app.harness.recommendation_prices import RecommendationPerformanceService
    from app.market_prices.contracts import PriceLookupObservation
    from app.persistence.price_repository import RecommendationPriceEntry, SnapshotKind

    entry = RecommendationPriceEntry(
        snapshot=_snapshot(price=Decimal("100")),
        snapshot_kind=SnapshotKind.ENTRY,
        company_id="company-samsung",
        company_name="삼성전자",
    )

    class _Capture:
        async def capture(
            self,
            ticker: str,
            observed_at: datetime,
        ) -> PriceLookupObservation:
            return PriceLookupObservation(
                status=PriceSnapshotStatus.AVAILABLE,
                price=Decimal("110"),
                basis=PriceBasis.REALTIME,
                provider=PriceProvider.KIS,
                observed_at=observed_at,
                trading_date=observed_at.date(),
            )

    class _Persistence:
        def __init__(self) -> None:
            self.entries: tuple[RecommendationPriceEntry, ...] = (entry,)
            self.latest: tuple[RecommendationPriceEntry, ...] = ()

        async def list_snapshots(self) -> tuple[RecommendationPriceEntry, ...]:
            return self.entries + self.latest

        async def upsert_latest(
            self,
            snapshots: tuple[RecommendationPriceEntry, ...],
        ) -> None:
            self.latest = snapshots

    persistence = _Persistence()
    response = asyncio.run(
        RecommendationPerformanceService(_Capture(), persistence).refresh_and_query()  # type: ignore[arg-type]
    )

    assert persistence.entries == (entry,)
    assert persistence.latest[0].snapshot_kind is SnapshotKind.LATEST
    assert persistence.latest[0].snapshot.price == Decimal("110")
    assert response.items[0].return_percent == 10.0


def test_service_scopes_two_same_ticker_runs_and_summary_to_requested_run() -> None:
    from app.harness.recommendation_prices import RecommendationPerformanceService
    from app.market_prices.contracts import PriceLookupObservation
    from app.persistence.price_repository import RecommendationPriceEntry, SnapshotKind

    old_entry = RecommendationPriceEntry(
        snapshot=_snapshot(run_id="run-old", price=Decimal("100")),
        snapshot_kind=SnapshotKind.ENTRY,
        company_id="company-samsung",
        company_name="삼성전자",
    )
    current_entry = RecommendationPriceEntry(
        snapshot=_snapshot(run_id="run-current", price=Decimal("200")),
        snapshot_kind=SnapshotKind.ENTRY,
        company_id="company-samsung",
        company_name="삼성전자",
    )

    class _Capture:
        def __init__(self) -> None:
            self.tickers: list[str] = []

        async def capture(
            self,
            ticker: str,
            observed_at: datetime,
        ) -> PriceLookupObservation:
            self.tickers.append(ticker)
            return PriceLookupObservation(
                status=PriceSnapshotStatus.AVAILABLE,
                price=Decimal("110"),
                basis=PriceBasis.REALTIME,
                provider=PriceProvider.KIS,
                observed_at=observed_at,
                trading_date=observed_at.date(),
            )

    class _Persistence:
        async def list_snapshots(self) -> tuple[RecommendationPriceEntry, ...]:
            return (old_entry, current_entry)

        async def upsert_latest(
            self,
            snapshots: tuple[RecommendationPriceEntry, ...],
        ) -> None:
            return None

    capture = _Capture()
    response = asyncio.run(
        RecommendationPerformanceService(capture, _Persistence()).refresh_and_query(  # type: ignore[arg-type]
            "run-current"
        )
    )

    assert capture.tickers == ["005930"]
    assert tuple(item.run_id for item in response.items) == ("run-current",)
    assert response.items[0].return_percent == -45.0
    assert response.summary.confirmed_count == 1
    assert response.summary.mean_return_percent == -45.0
