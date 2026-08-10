from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from app.config import load_optional_kis_config
from app.models import PriceSnapshotStatus


@pytest.mark.anyio
async def test_live_kis_price_for_samsung_electronics_is_available_when_opted_in() -> None:
    """Call the external KIS contract only after an explicit local opt-in."""
    if os.getenv("RUN_LIVE_MARKET_DATA_TESTS") != "1":
        pytest.skip("set RUN_LIVE_MARKET_DATA_TESTS=1 to call KIS")
    config = load_optional_kis_config()
    if config is None:
        pytest.skip("KIS credentials are not configured")

    from app.market_prices import KisRealtimePriceClient

    observation = await KisRealtimePriceClient(config).fetch(
        "005930",
        datetime.now(timezone.utc),
    )

    assert observation.status is PriceSnapshotStatus.AVAILABLE
    assert observation.price is not None
    assert observation.price > 0
