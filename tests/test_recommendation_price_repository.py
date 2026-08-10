from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from app.models.market_price import (
    PriceBasis,
    PriceProvider,
    PriceSnapshotStatus,
    RecommendationPriceSnapshot,
)
from app.models.recommendation import RecommendationAction


def test_price_entry_schema_keeps_one_entry_per_run_recommendation_and_kind() -> None:
    from app.persistence.schema import recommendation_price_snapshots

    unique_columns: set[tuple[str, ...]] = {
        tuple(column.name for column in constraint.columns)
        for constraint in recommendation_price_snapshots.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert set(recommendation_price_snapshots.columns.keys()) == {
        "id",
        "run_id",
        "recommendation_index",
        "snapshot_kind",
        "company_id",
        "company_name",
        "ticker",
        "action",
        "status",
        "price",
        "currency",
        "basis",
        "provider",
        "observed_at",
        "trading_date",
        "error_kind",
        "created_at",
    }
    assert ("run_id", "recommendation_index", "snapshot_kind") in unique_columns


def test_repository_entry_insert_is_idempotent_for_the_same_snapshot_identity() -> None:
    from app.persistence.price_repository import (
        RecommendationPriceEntry,
        SnapshotKind,
        SqlAlchemyRecommendationPriceRepository,
    )

    class RecordingSession:
        def __init__(self) -> None:
            self.statements: list[object] = []

        async def execute(self, statement: object) -> None:
            self.statements.append(statement)

    snapshot = RecommendationPriceSnapshot(
        run_id="run-1",
        recommendation_index=0,
        ticker="005930",
        action=RecommendationAction.BUY,
        status=PriceSnapshotStatus.AVAILABLE,
        price=Decimal("72000"),
        basis=PriceBasis.CLOSE,
        provider=PriceProvider.KRX,
        observed_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        trading_date=date(2026, 8, 4),
    )
    session = RecordingSession()
    repository = SqlAlchemyRecommendationPriceRepository(session)  # type: ignore[arg-type]

    import asyncio

    asyncio.run(
        repository.store_entries(
            (
                RecommendationPriceEntry(
                    snapshot=snapshot,
                    snapshot_kind=SnapshotKind.ENTRY,
                    company_id="company-samsung",
                    company_name="삼성전자",
                ),
            )
        )
    )

    statement = session.statements[0]
    compiled = str(
        statement.compile(dialect=__import__("sqlalchemy").dialects.postgresql.dialect())
    )
    assert "ON CONFLICT (run_id, recommendation_index, snapshot_kind) DO NOTHING" in compiled
