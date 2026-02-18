"""Test Mean Reversion entry strategy."""
import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_mean_reversion_buy_signal():
    """Test mean reversion BUY signal when price below lower band."""
    from shared.strategy.entry.mean_reversion import MeanReversionEntry, MeanReversionConfig
    from shared.strategy.base import EntryContext

    config = MeanReversionConfig(
        bb_period=20,
        bb_std=2.0,
        rsi_period=14,
        rsi_oversold=30,
        rsi_overbought=70,
    )

    strategy = MeanReversionEntry(config)

    context = EntryContext(
        market_data={
            "code": "101W06",
            "name": "코스피200선물",
            "close": 365.0,
            "bb_lower": 366.0,  # Price below BB lower
            "bb_upper": 374.0,
            "bb_middle": 370.0,
            "rsi": 25,  # Oversold
        },
        timestamp=datetime(2026, 2, 16, 10, 30, 0),
    )

    signal = await strategy.generate(context)

    assert signal is not None
    assert signal.code == "101W06"
    assert signal.strategy == "mean_reversion"
    assert signal.metadata.get("signal_direction") == "long"


@pytest.mark.asyncio
async def test_mean_reversion_sell_signal():
    """Test mean reversion SELL signal when price above upper band."""
    from shared.strategy.entry.mean_reversion import MeanReversionEntry, MeanReversionConfig
    from shared.strategy.base import EntryContext

    config = MeanReversionConfig(allow_short=True)
    strategy = MeanReversionEntry(config)

    context = EntryContext(
        market_data={
            "code": "101W06",
            "close": 376.0,
            "bb_lower": 366.0,
            "bb_upper": 374.0,  # Price above BB upper
            "bb_middle": 370.0,
            "rsi": 75,  # Overbought
        },
        timestamp=datetime(2026, 2, 16, 10, 30, 0),
    )

    signal = await strategy.generate(context)

    assert signal is not None
    assert signal.metadata.get("signal_direction") == "short"


@pytest.mark.asyncio
async def test_mean_reversion_no_signal_in_range():
    """Test mean reversion returns None when price is within bands."""
    from shared.strategy.entry.mean_reversion import MeanReversionEntry, MeanReversionConfig
    from shared.strategy.base import EntryContext

    config = MeanReversionConfig()
    strategy = MeanReversionEntry(config)

    context = EntryContext(
        market_data={
            "code": "101W06",
            "close": 370.0,  # Within range
            "bb_lower": 366.0,
            "bb_upper": 374.0,
            "bb_middle": 370.0,
            "rsi": 50,  # Neutral RSI
        },
        timestamp=datetime(2026, 2, 16, 10, 30, 0),
    )

    signal = await strategy.generate(context)
    assert signal is None


@pytest.mark.asyncio
async def test_mean_reversion_no_signal_rsi_not_extreme():
    """Test mean reversion returns None when RSI not confirming."""
    from shared.strategy.entry.mean_reversion import MeanReversionEntry, MeanReversionConfig
    from shared.strategy.base import EntryContext

    config = MeanReversionConfig()
    strategy = MeanReversionEntry(config)

    context = EntryContext(
        market_data={
            "code": "101W06",
            "close": 365.0,
            "bb_lower": 366.0,  # Below BB lower
            "bb_upper": 374.0,
            "bb_middle": 370.0,
            "rsi": 50,  # RSI not confirming
        },
        timestamp=datetime(2026, 2, 16, 10, 30, 0),
    )

    signal = await strategy.generate(context)
    assert signal is None


def test_mean_reversion_required_indicators():
    """Test mean reversion reports required indicators."""
    from shared.strategy.entry.mean_reversion import MeanReversionEntry, MeanReversionConfig

    config = MeanReversionConfig()
    strategy = MeanReversionEntry(config)

    indicators = strategy.required_indicators
    assert "bb_lower" in indicators
    assert "bb_upper" in indicators
    assert "rsi" in indicators
