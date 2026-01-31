import asyncio
from datetime import datetime

import pytest

from shared.strategy.base import EntryContext
from shared.strategy.entry.opening_volume_surge import (
    OpeningVolumeSurgeConfig,
    OpeningVolumeSurgeEntry,
)


@pytest.mark.asyncio
async def test_opening_volume_surge_triggers_when_volume_exceeds_prev_day_total():
    entry = OpeningVolumeSurgeEntry(
        OpeningVolumeSurgeConfig(
            only_first_minutes=30,
            market_open_hour=9,
            market_open_minute=0,
            min_change_pct=1.0,
            require_above_open=True,
            min_range_position=0.7,
            stop_loss_pct=5.0,
        )
    )

    ts = datetime(2026, 1, 2, 9, 10, 0)
    ctx = EntryContext(
        market_data={
            "code": "123456",
            "name": "TEST",
            "open": 100.0,
            "high": 110.0,
            "low": 95.0,
            "close": 108.0,
            "volume": 1_000_000,
            "prev_day_volume": 900_000,
            "change": 0.08,
        },
        timestamp=ts,
    )

    sig = await entry.generate(ctx)
    assert sig is not None
    assert sig.code == "123456"
    assert sig.metadata["stop_loss_pct"] == 5.0


@pytest.mark.asyncio
async def test_opening_volume_surge_does_not_trigger_after_window():
    entry = OpeningVolumeSurgeEntry(OpeningVolumeSurgeConfig(only_first_minutes=30))

    ts = datetime(2026, 1, 2, 10, 0, 0)  # after first 30 minutes
    ctx = EntryContext(
        market_data={
            "code": "123456",
            "name": "TEST",
            "open": 100.0,
            "high": 110.0,
            "low": 95.0,
            "close": 108.0,
            "volume": 1_000_000,
            "prev_day_volume": 900_000,
            "change": 0.08,
        },
        timestamp=ts,
    )

    sig = await entry.generate(ctx)
    assert sig is None

