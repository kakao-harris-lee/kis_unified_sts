"""Test StochRSI trend entry strategy."""
from datetime import datetime

import pytest


@pytest.mark.asyncio
async def test_stochrsi_entry_signal_buy():
    """Test StochRSI entry signal generation for BUY (oversold)."""
    from shared.strategy.base import EntryContext
    from shared.strategy.entry.stochrsi_trend import StochRSIConfig, StochRSITrendEntry

    config = StochRSIConfig(
        rsi_period=14,
        stoch_period=14,
        k_period=3,
        d_period=3,
        oversold=20,
        overbought=80,
    )

    strategy = StochRSITrendEntry(config)

    # Create test data with oversold StochRSI crossing up
    context = EntryContext(
        market_data={
            "code": "005930",
            "name": "삼성전자",
            "close": 58000,
            "stochrsi_k": 25,  # K line
            "stochrsi_d": 15,  # D line - K crossing above D (bullish)
            "stochrsi_k_prev": 12,  # Previous K was below current
        },
        indicators={},
        current_positions=[],
        timestamp=datetime.now(),
    )

    signal = await strategy.generate(context)

    assert signal is not None
    assert signal.code == "005930"
    assert signal.strategy == "stochrsi_trend"


@pytest.mark.asyncio
async def test_stochrsi_entry_signal_sell():
    """Test StochRSI entry signal generation for SELL (overbought)."""
    from shared.strategy.base import EntryContext
    from shared.strategy.entry.stochrsi_trend import StochRSIConfig, StochRSITrendEntry

    config = StochRSIConfig()
    strategy = StochRSITrendEntry(config)

    # Create test data with overbought StochRSI crossing down
    context = EntryContext(
        market_data={
            "code": "005930",
            "close": 62000,
            "stochrsi_k": 75,  # K line
            "stochrsi_d": 85,  # D line - K crossing below D (bearish)
            "stochrsi_k_prev": 88,  # Previous K was higher (crossing down)
        },
        timestamp=datetime.now(),
    )

    signal = await strategy.generate(context)

    # Short signal in overbought zone
    assert signal is not None
    assert signal.strategy == "stochrsi_trend"


@pytest.mark.asyncio
async def test_stochrsi_no_signal_in_neutral_zone():
    """Test StochRSI returns None in neutral zone."""
    from shared.strategy.base import EntryContext
    from shared.strategy.entry.stochrsi_trend import StochRSIConfig, StochRSITrendEntry

    config = StochRSIConfig()
    strategy = StochRSITrendEntry(config)

    context = EntryContext(
        market_data={
            "code": "005930",
            "close": 60000,
            "stochrsi_k": 50,  # Neutral zone
            "stochrsi_d": 50,
            "stochrsi_k_prev": 48,
        },
        timestamp=datetime.now(),
    )

    signal = await strategy.generate(context)
    assert signal is None


def test_stochrsi_required_indicators():
    """Test StochRSI reports required indicators."""
    from shared.strategy.entry.stochrsi_trend import StochRSIConfig, StochRSITrendEntry

    config = StochRSIConfig()
    strategy = StochRSITrendEntry(config)

    indicators = strategy.required_indicators
    assert "stochrsi_k" in indicators
    assert "stochrsi_d" in indicators
