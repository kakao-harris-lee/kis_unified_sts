"""Test Breakout entry strategy."""
import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_breakout_long_signal():
    """Test breakout LONG signal when price breaks N-period high."""
    from shared.strategy.entry.breakout import BreakoutEntry, BreakoutConfig
    from shared.strategy.base import EntryContext

    config = BreakoutConfig(
        lookback_period=20,
        volume_confirm=True,
        volume_threshold=1.5,
    )

    strategy = BreakoutEntry(config)

    context = EntryContext(
        market_data={
            "code": "101W06",
            "name": "코스피200선물",
            "close": 375.0,
            "high_20": 374.0,  # Price breaks above 20-period high
            "low_20": 365.0,
            "volume": 15000,
            "volume_ma": 10000,  # Volume 1.5x average
        },
        timestamp=datetime.now(),
    )

    signal = await strategy.generate(context)

    assert signal is not None
    assert signal.code == "101W06"
    assert signal.strategy == "breakout"
    assert signal.metadata.get("signal_direction") == "long"


@pytest.mark.asyncio
async def test_breakout_short_signal():
    """Test breakout SHORT signal when price breaks N-period low."""
    from shared.strategy.entry.breakout import BreakoutEntry, BreakoutConfig
    from shared.strategy.base import EntryContext

    config = BreakoutConfig()
    strategy = BreakoutEntry(config)

    context = EntryContext(
        market_data={
            "code": "101W06",
            "close": 364.0,
            "high_20": 374.0,
            "low_20": 365.0,  # Price breaks below 20-period low
            "volume": 15000,
            "volume_ma": 10000,
        },
        timestamp=datetime.now(),
    )

    signal = await strategy.generate(context)

    assert signal is not None
    assert signal.metadata.get("signal_direction") == "short"


@pytest.mark.asyncio
async def test_breakout_no_signal_in_range():
    """Test breakout returns None when price is within range."""
    from shared.strategy.entry.breakout import BreakoutEntry, BreakoutConfig
    from shared.strategy.base import EntryContext

    config = BreakoutConfig()
    strategy = BreakoutEntry(config)

    context = EntryContext(
        market_data={
            "code": "101W06",
            "close": 370.0,  # Within range
            "high_20": 374.0,
            "low_20": 365.0,
            "volume": 15000,
            "volume_ma": 10000,
        },
        timestamp=datetime.now(),
    )

    signal = await strategy.generate(context)
    assert signal is None


@pytest.mark.asyncio
async def test_breakout_no_signal_low_volume():
    """Test breakout returns None when volume is low."""
    from shared.strategy.entry.breakout import BreakoutEntry, BreakoutConfig
    from shared.strategy.base import EntryContext

    config = BreakoutConfig(volume_confirm=True, volume_threshold=1.5)
    strategy = BreakoutEntry(config)

    context = EntryContext(
        market_data={
            "code": "101W06",
            "close": 375.0,
            "high_20": 374.0,  # Price breaks high
            "low_20": 365.0,
            "volume": 8000,  # Volume below threshold (1.5x)
            "volume_ma": 10000,
        },
        timestamp=datetime.now(),
    )

    signal = await strategy.generate(context)
    assert signal is None


def test_breakout_required_indicators():
    """Test breakout reports required indicators."""
    from shared.strategy.entry.breakout import BreakoutEntry, BreakoutConfig

    config = BreakoutConfig()
    strategy = BreakoutEntry(config)

    indicators = strategy.required_indicators
    assert "high_20" in indicators
    assert "low_20" in indicators
