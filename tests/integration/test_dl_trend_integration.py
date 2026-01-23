"""Integration tests for DL Trend Entry strategy

Tests the full flow of signal generation with EnsembleFilter and TechnicalCalculator.
"""

from datetime import datetime

import pytest

from domains.futures.strategies.dl_trend import DLTrendConfig, DLTrendEntry
from shared.models.signal import SignalType
from shared.strategy.base import EntryContext


# =============================================================================
# Constants
# =============================================================================

TECHNICAL_WARMUP_PERIODS = 60
CALIBRATOR_MIN_SAMPLES = 60


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def config():
    """Default DL Trend configuration"""
    return DLTrendConfig(
        dl_threshold=0.85,
        max_atr_threshold=1.5,
        zscore_trigger_threshold=1.0,
        zscore_long_confirm_threshold=0.5,
        zscore_short_confirm_threshold=0.0,
        ma_fast_period=20,
        ma_slow_period=60,
        use_multi_horizon=False,
    )


@pytest.fixture
def strategy(config):
    """DL Trend Entry strategy instance"""
    return DLTrendEntry(config)


@pytest.fixture
def multi_horizon_config():
    """Multi-horizon configuration"""
    return DLTrendConfig(
        dl_threshold=0.85,
        max_atr_threshold=1.5,
        zscore_trigger_threshold=1.0,
        zscore_long_confirm_threshold=0.5,
        zscore_short_confirm_threshold=0.0,
        ma_fast_period=20,
        ma_slow_period=60,
        use_multi_horizon=True,
        horizons=[1, 3, 5, 10],
    )


@pytest.fixture
def multi_horizon_strategy(multi_horizon_config):
    """Multi-horizon strategy instance"""
    return DLTrendEntry(multi_horizon_config)


def create_bar_data(high: float, low: float, close: float) -> dict:
    """Helper to create bar data"""
    return {
        "symbol": "KR101",
        "name": "KOSPI200 Futures",
        "high": high,
        "low": low,
        "close": close,
    }


def create_prediction(up_prob: float, down_prob: float = None) -> dict:
    """Helper to create prediction data"""
    if down_prob is None:
        down_prob = 1.0 - up_prob
    return {
        "up_prob": up_prob,
        "down_prob": down_prob,
        "hold_prob": max(0.0, 1.0 - up_prob - down_prob),
    }


def warmup_technical(strategy: DLTrendEntry, periods: int = TECHNICAL_WARMUP_PERIODS):
    """Warm up technical indicators with dummy data"""
    for i in range(periods):
        base = 100.0
        price = base + i * 0.1  # Slight uptrend
        strategy.tech_calc.update(
            high=price + 0.5,
            low=price - 0.5,
            close=price,
        )


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_entry_signal_flow(strategy):
    """Test complete entry signal generation with bullish conditions"""
    # Warm up technical indicators with strong uptrend
    # This creates MA crossover (fast > slow) and price above cloud
    for i in range(TECHNICAL_WARMUP_PERIODS):
        base = 100.0
        price = base + i * 0.2  # Strong uptrend
        strategy.tech_calc.update(
            high=price + 0.5,
            low=price - 0.5,
            close=price,
        )

    # Bullish market conditions - continue uptrend
    market_data = create_bar_data(high=112.5, low=111.5, close=112.0)
    indicators = {
        "prediction": create_prediction(up_prob=0.90),
    }

    context = EntryContext(
        market_data=market_data,
        indicators=indicators,
        current_positions=[],
        timestamp=datetime.now(),
    )

    # Generate signal
    signal = await strategy.generate(context)

    # Verify signal
    assert signal is not None
    assert signal.signal_type == SignalType.ENTRY
    assert signal.code == "KR101"
    assert signal.name == "KOSPI200 Futures"
    assert signal.strategy == "futures_dl_trend"
    assert signal.price == 112.0
    assert signal.confidence == 0.90
    # Direction is stored in metadata
    assert signal.metadata["direction"] == "LONG"
    assert "trigger_horizon" in signal.metadata
    assert "ma_fast" in signal.metadata
    assert "ma_slow" in signal.metadata
    assert "atr" in signal.metadata


@pytest.mark.integration
@pytest.mark.asyncio
async def test_weak_prediction_no_signal(strategy):
    """Test that weak predictions don't generate signals"""
    # Warm up technical indicators
    warmup_technical(strategy)

    # Weak prediction (close to 0.5)
    market_data = create_bar_data(high=105.5, low=104.5, close=105.0)
    indicators = {
        "prediction": create_prediction(up_prob=0.52),
    }

    context = EntryContext(
        market_data=market_data,
        indicators=indicators,
        current_positions=[],
        timestamp=datetime.now(),
    )

    # Generate signal
    signal = await strategy.generate(context)

    # Should NOT generate signal due to weak prediction
    assert signal is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_calibrator_warmup_period(multi_horizon_strategy):
    """Test behavior during calibrator warmup"""
    # Warm up technical indicators first
    warmup_technical(multi_horizon_strategy)

    # Generate predictions during warmup (not enough for calibrator)
    for i in range(10):
        market_data = create_bar_data(
            high=100.0 + i,
            low=99.0 + i,
            close=99.5 + i,
        )
        indicators = {
            "prediction": {
                "up_prob_h1": 0.6,
                "up_prob_h3": 0.65,
                "up_prob_h5": 0.7,
                "up_prob_h10": 0.75,
            }
        }

        context = EntryContext(
            market_data=market_data,
            indicators=indicators,
            current_positions=[],
            timestamp=datetime.now(),
        )

        # Update calibrator
        horizon_probs = {
            1: 0.6,
            3: 0.65,
            5: 0.7,
            10: 0.75,
        }
        multi_horizon_strategy.filter.update_calibrator(horizon_probs)

        # Should not crash during warmup
        signal = await multi_horizon_strategy.generate(context)

        # No signal during calibrator warmup
        assert signal is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_horizon_confirmation(multi_horizon_strategy):
    """Test multi-horizon mode when horizons disagree"""
    # Warm up technical indicators
    warmup_technical(multi_horizon_strategy)

    # Conflicting horizon predictions (h10 bullish, h1 bearish)
    market_data = create_bar_data(high=105.5, low=104.5, close=105.0)
    indicators = {
        "prediction": {
            "up_prob_h1": 0.3,  # Bearish short-term
            "up_prob_h3": 0.35,  # Bearish short-term
            "up_prob_h5": 0.6,
            "up_prob_h10": 0.9,  # Bullish long-term
        }
    }

    # Update calibrator with samples to pass warmup
    for _ in range(CALIBRATOR_MIN_SAMPLES):
        multi_horizon_strategy.filter.update_calibrator(
            {1: 0.5, 3: 0.5, 5: 0.5, 10: 0.5}
        )

    context = EntryContext(
        market_data=market_data,
        indicators=indicators,
        current_positions=[],
        timestamp=datetime.now(),
    )

    # Generate signal
    signal = await multi_horizon_strategy.generate(context)

    # Should NOT generate signal when horizons disagree
    # (h10 triggers but h1/h3 don't confirm)
    assert signal is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_technical_warmup_blocks_entry(strategy):
    """Test that entry is blocked during technical indicator warmup"""
    # No warmup - technical indicators not ready

    market_data = create_bar_data(high=105.5, low=104.5, close=105.0)
    indicators = {
        "prediction": create_prediction(up_prob=0.95),  # Strong prediction
    }

    context = EntryContext(
        market_data=market_data,
        indicators=indicators,
        current_positions=[],
        timestamp=datetime.now(),
    )

    # Generate signal
    signal = await strategy.generate(context)

    # Should be None because technical indicators not ready
    assert signal is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bearish_signal_generation(strategy):
    """Test bearish signal generation"""
    # Warm up technical indicators with strong downtrend
    # This creates MA crossover (fast < slow) and price below cloud
    for i in range(TECHNICAL_WARMUP_PERIODS):
        base = 100.0
        price = base - i * 0.2  # Strong downtrend
        strategy.tech_calc.update(
            high=price + 0.5,
            low=price - 0.5,
            close=price,
        )

    # Bearish market conditions - continue downtrend
    market_data = create_bar_data(high=89.5, low=88.5, close=88.0)
    indicators = {
        "prediction": create_prediction(up_prob=0.05, down_prob=0.90),
    }

    context = EntryContext(
        market_data=market_data,
        indicators=indicators,
        current_positions=[],
        timestamp=datetime.now(),
    )

    # Generate signal
    signal = await strategy.generate(context)

    # Verify SHORT signal
    assert signal is not None
    assert signal.signal_type == SignalType.ENTRY
    assert signal.confidence == 0.90
    # Direction is stored in metadata
    assert signal.metadata["direction"] == "SHORT"
    assert "ma_fast" in signal.metadata
    assert "ma_slow" in signal.metadata
    assert "atr" in signal.metadata


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ma_filter_blocks_entry(strategy):
    """Test that MA filter blocks entry when trend disagrees"""
    # Warm up with downtrend (ma_fast < ma_slow)
    for i in range(TECHNICAL_WARMUP_PERIODS):
        base = 100.0
        price = base - i * 0.1  # Downtrend
        strategy.tech_calc.update(
            high=price + 0.5,
            low=price - 0.5,
            close=price,
        )

    # Strong bullish prediction BUT MA says downtrend
    market_data = create_bar_data(high=95.5, low=94.5, close=95.0)
    indicators = {
        "prediction": create_prediction(up_prob=0.95),
    }

    context = EntryContext(
        market_data=market_data,
        indicators=indicators,
        current_positions=[],
        timestamp=datetime.now(),
    )

    # Generate signal
    signal = await strategy.generate(context)

    # Should be blocked by MA filter
    assert signal is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ichimoku_filter_blocks_entry(strategy):
    """Test that Ichimoku filter blocks entry when price below cloud

    Creates a clear downtrend with price firmly below cloud,
    then provides a bullish prediction that should be blocked.
    """
    # Warm up with consistent downtrend - price will be below cloud
    # Decreasing prices create senkou spans that form cloud above price
    for i in range(TECHNICAL_WARMUP_PERIODS):
        base = 110.0
        price = base - i * 0.3  # Strong downtrend
        strategy.tech_calc.update(
            high=price + 0.5,
            low=price - 0.5,
            close=price,
        )

    # Current price is now around 92.0 (110 - 60*0.3)
    # Cloud formed from past highs will be above this price
    # Strong bullish prediction, but price is below cloud
    market_data = create_bar_data(high=93.0, low=91.0, close=92.0)
    indicators = {
        "prediction": create_prediction(up_prob=0.95),
    }

    context = EntryContext(
        market_data=market_data,
        indicators=indicators,
        current_positions=[],
        timestamp=datetime.now(),
    )

    # Generate signal
    signal = await strategy.generate(context)

    # Should be blocked - price below cloud in downtrend
    # Even with strong bullish prediction
    assert signal is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_strategy_stats(strategy):
    """Test that strategy tracks statistics"""
    # Warm up
    warmup_technical(strategy)

    # Generate several checks
    for up_prob in [0.95, 0.55, 0.45, 0.92]:
        market_data = create_bar_data(high=105.5, low=104.5, close=105.0)
        indicators = {
            "prediction": create_prediction(up_prob=up_prob),
        }

        context = EntryContext(
            market_data=market_data,
            indicators=indicators,
            current_positions=[],
            timestamp=datetime.now(),
        )

        await strategy.generate(context)

    # Check stats
    stats = strategy.get_stats()
    assert stats["total_checks"] > 0
    assert "long_signals" in stats
    assert "rejected_dl" in stats
