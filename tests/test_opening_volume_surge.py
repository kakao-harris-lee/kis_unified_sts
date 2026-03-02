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


@pytest.mark.asyncio
async def test_opening_volume_surge_allows_intraday_when_window_disabled():
    entry = OpeningVolumeSurgeEntry(OpeningVolumeSurgeConfig(only_first_minutes=0))

    ts = datetime(2026, 1, 2, 13, 0, 0)  # intraday, long after open
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


@pytest.mark.asyncio
async def test_opening_volume_surge_triggers_on_rvol_burst():
    entry = OpeningVolumeSurgeEntry(
        OpeningVolumeSurgeConfig(
            only_first_minutes=0,
            volume_multiplier=1.0,
            volume_gate_mode="either",
            min_rvol=1.8,
        )
    )

    ts = datetime(2026, 1, 2, 13, 0, 0)
    ctx = EntryContext(
        market_data={
            "code": "123456",
            "name": "TEST",
            "open": 100.0,
            "high": 111.0,
            "low": 95.0,
            "close": 109.0,
            "volume": 200_000,         # below cumulative requirement (1_000_000)
            "prev_day_volume": 1_000_000,
            "rvol": 2.2,               # burst gate passes
            "change": 0.08,
        },
        timestamp=ts,
    )

    sig = await entry.generate(ctx)
    assert sig is not None
    assert sig.metadata["volume_gate_pass_cumulative"] is False
    assert sig.metadata["volume_gate_pass_rvol"] is True


@pytest.mark.asyncio
async def test_opening_volume_surge_rvol_mode_works_without_prev_day_volume():
    entry = OpeningVolumeSurgeEntry(
        OpeningVolumeSurgeConfig(
            only_first_minutes=0,
            volume_gate_mode="rvol",
            min_rvol=2.0,
        )
    )

    ts = datetime(2026, 1, 2, 14, 20, 0)
    ctx = EntryContext(
        market_data={
            "code": "123456",
            "name": "TEST",
            "open": 100.0,
            "high": 110.0,
            "low": 95.0,
            "close": 108.0,
            "volume": 150_000,
            "prev_day_volume": 0,      # baseline unavailable
            "rvol": 2.5,
            "change": 0.06,
        },
        timestamp=ts,
    )

    sig = await entry.generate(ctx)
    assert sig is not None


@pytest.mark.asyncio
async def test_opening_volume_surge_blocks_when_score_below_threshold():
    entry = OpeningVolumeSurgeEntry(
        OpeningVolumeSurgeConfig(
            only_first_minutes=0,
            min_change_pct=0.1,
            volume_gate_mode="either",
            min_rvol=1.0,
            min_signal_score=1.5,
        )
    )

    ts = datetime(2026, 1, 2, 13, 10, 0)
    ctx = EntryContext(
        market_data={
            "code": "123456",
            "name": "TEST",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.6,
            "volume": 360_000,
            "prev_day_volume": 300_000,
            "rvol": 1.2,
            "change": 0.005,  # +0.5%
        },
        timestamp=ts,
    )

    sig = await entry.generate(ctx)
    assert sig is None


@pytest.mark.asyncio
async def test_opening_volume_surge_allows_when_score_above_threshold():
    entry = OpeningVolumeSurgeEntry(
        OpeningVolumeSurgeConfig(
            only_first_minutes=0,
            min_change_pct=0.1,
            volume_gate_mode="either",
            min_rvol=1.0,
            min_signal_score=1.5,
        )
    )

    ts = datetime(2026, 1, 2, 13, 11, 0)
    ctx = EntryContext(
        market_data={
            "code": "123456",
            "name": "TEST",
            "open": 100.0,
            "high": 110.0,
            "low": 99.0,
            "close": 108.0,
            "volume": 2_400_000,
            "prev_day_volume": 1_000_000,
            "rvol": 2.8,
            "change": 0.08,  # +8%
        },
        timestamp=ts,
    )

    sig = await entry.generate(ctx)
    assert sig is not None
    assert sig.metadata["signal_score"] >= 1.5


@pytest.mark.asyncio
async def test_opening_volume_surge_spike_and_1m_return_filters():
    entry = OpeningVolumeSurgeEntry(
        OpeningVolumeSurgeConfig(
            only_first_minutes=0,
            min_change_pct=0.0,
            min_range_position=0.5,
            min_day_range_pct=0.0,
            volume_gate_mode="either",
            min_rvol=1.0,
            min_return_1m_pct=0.1,
            rvol_spike_threshold=2.0,
            spike_lookback_minutes=5,
            min_spike_hits=2,
        )
    )

    # First minute: no previous minute close => ret_1m=0.0, should be blocked
    first = EntryContext(
        market_data={
            "code": "123456",
            "name": "TEST",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 400_000,
            "prev_day_volume": 300_000,
            "rvol": 2.2,
            "change": 0.01,
        },
        timestamp=datetime(2026, 1, 2, 9, 10, 0),
    )
    sig1 = await entry.generate(first)
    assert sig1 is None

    # Next minute: positive 1m return + second spike hit => allowed
    second = EntryContext(
        market_data={
            "code": "123456",
            "name": "TEST",
            "open": 100.0,
            "high": 101.5,
            "low": 99.0,
            "close": 100.3,
            "volume": 500_000,
            "prev_day_volume": 300_000,
            "rvol": 2.3,
            "change": 0.012,
        },
        timestamp=datetime(2026, 1, 2, 9, 11, 0),
    )
    sig2 = await entry.generate(second)
    assert sig2 is not None
    assert sig2.metadata["ret_1m_pct"] >= 0.1
    assert sig2.metadata["spike_hits_window"] >= 2
