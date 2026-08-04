from __future__ import annotations

from datetime import datetime, timezone

from app.models.collection_filter import InvestmentTheme, NewsTopic
from app.models.collection_filter_result import CollectionFilterSnapshot


def test_filter_snapshot_keeps_only_safe_reproducibility_data() -> None:
    snapshot = CollectionFilterSnapshot(
        run_id="run-1",
        themes=(InvestmentTheme.SEMICONDUCTOR,),
        topics=(NewsTopic.SUPPLY_CHAIN,),
        catalog_version="investment-theme-v1",
        collected_count=25,
        accepted_count=8,
        excluded_count=17,
        rejection_counts={"theme_mismatch": 17},
        created_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )

    assert snapshot.run_id == "run-1"
    assert snapshot.collected_count == snapshot.accepted_count + snapshot.excluded_count
