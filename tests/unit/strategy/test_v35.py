"""Test V35 optimized entry strategy."""
import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_v35_entry_signal_buy():
    """Test V35 entry signal generation for BUY."""
    from shared.strategy.entry.v35_optimized import V35OptimizedEntry, V35Config
    from shared.strategy.base import EntryContext

    config = V35Config(
        bb_period=20,
        bb_std=2.0,
        rsi_period=14,
        rsi_oversold=30,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
    )

    strategy = V35OptimizedEntry(config)

    # Create test data with oversold conditions
    context = EntryContext(
        market_data={
            "code": "005930",
            "name": "삼성전자",
            "close": 58000,
            "bb_lower": 58500,  # Price below BB lower
            "rsi": 25,  # Oversold
            "macd_hist": 0.5,  # Positive momentum
        },
        indicators={},
        current_positions=[],
        timestamp=datetime.now(),
    )

    signal = await strategy.generate(context)

    assert signal is not None
    assert signal.code == "005930"
    assert signal.signal_type.value == "entry"
    assert signal.strategy == "v35_optimized"


@pytest.mark.asyncio
async def test_v35_no_signal_when_rsi_not_oversold():
    """Test V35 returns None when RSI is not oversold."""
    from shared.strategy.entry.v35_optimized import V35OptimizedEntry, V35Config
    from shared.strategy.base import EntryContext

    config = V35Config()
    strategy = V35OptimizedEntry(config)

    context = EntryContext(
        market_data={
            "code": "005930",
            "close": 58000,
            "bb_lower": 58500,
            "rsi": 50,  # Not oversold
            "macd_hist": 0.5,
        },
        timestamp=datetime.now(),
    )

    signal = await strategy.generate(context)
    assert signal is None


@pytest.mark.asyncio
async def test_v35_no_signal_when_price_above_bb():
    """Test V35 returns None when price is above BB lower."""
    from shared.strategy.entry.v35_optimized import V35OptimizedEntry, V35Config
    from shared.strategy.base import EntryContext

    config = V35Config()
    strategy = V35OptimizedEntry(config)

    context = EntryContext(
        market_data={
            "code": "005930",
            "close": 59000,  # Above BB lower
            "bb_lower": 58500,
            "rsi": 25,
            "macd_hist": 0.5,
        },
        timestamp=datetime.now(),
    )

    signal = await strategy.generate(context)
    assert signal is None


def test_v35_required_indicators():
    """Test V35 reports required indicators."""
    from shared.strategy.entry.v35_optimized import V35OptimizedEntry, V35Config

    config = V35Config()
    strategy = V35OptimizedEntry(config)

    indicators = strategy.required_indicators
    assert "bb_lower" in indicators
    assert "rsi" in indicators
    assert "macd_hist" in indicators
