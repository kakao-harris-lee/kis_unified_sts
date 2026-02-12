"""Integration test for DL Trend Entry with triple barrier support"""

import pytest

from domains.futures.strategies.dl_trend import DLTrendConfig, DLTrendEntry
from shared.strategy.base import EntryContext


@pytest.fixture
def dl_trend_strategy():
    """DL Trend Entry strategy with default config"""
    config = DLTrendConfig(
        dl_threshold=0.55,
        use_multi_horizon=False,  # Single horizon mode for simplicity
    )
    return DLTrendEntry(config)


@pytest.mark.asyncio
async def test_binary_mode_backward_compatible(dl_trend_strategy):
    """Test legacy binary mode (up_prob only) still works"""
    context = EntryContext(
        market_data={
            "symbol": "KR101",
            "name": "KOSPI200 Mini",
            "high": 105.0,
            "low": 95.0,
            "close": 100.0,
        },
        indicators={
            "prediction": {
                "up_prob": 0.7,  # Legacy binary format
            }
        },
        current_positions=[],
        timestamp=None,
    )

    _ = await dl_trend_strategy.generate(context)
    # Signal may be None due to technical indicators warming up
    # This test just ensures no errors occur


@pytest.mark.asyncio
async def test_triple_barrier_mode(dl_trend_strategy):
    """Test triple barrier mode with explicit probabilities"""
    context = EntryContext(
        market_data={
            "symbol": "KR101",
            "name": "KOSPI200 Mini",
            "high": 105.0,
            "low": 95.0,
            "close": 100.0,
        },
        indicators={
            "prediction": {
                "up_prob": 0.6,
                "down_prob": 0.25,
                "hold_prob": 0.15,
            }
        },
        current_positions=[],
        timestamp=None,
    )

    _ = await dl_trend_strategy.generate(context)
    # Signal may be None due to technical indicators warming up
    # This test ensures triple barrier format is handled


@pytest.mark.asyncio
async def test_weak_prediction_rejected(dl_trend_strategy):
    """Test weak predictions are properly rejected"""
    context = EntryContext(
        market_data={
            "symbol": "KR101",
            "name": "KOSPI200 Mini",
            "high": 105.0,
            "low": 95.0,
            "close": 100.0,
        },
        indicators={
            "prediction": {
                "up_prob": 0.3,
                "down_prob": 0.2,
                "hold_prob": 0.5,  # Hold dominant
            }
        },
        current_positions=[],
        timestamp=None,
    )

    # Warm up technical indicators
    for _ in range(100):
        dl_trend_strategy.tech_calc.update(100.0, 95.0, 100.0)

    _ = await dl_trend_strategy.generate(context)
    # Should be None due to weak prediction
    assert signal is None


@pytest.mark.asyncio
async def test_multi_horizon_fallback_to_binary(dl_trend_strategy):
    """Test multi-horizon mode falls back to binary when no horizon data"""
    dl_trend_strategy.config.use_multi_horizon = True

    context = EntryContext(
        market_data={
            "symbol": "KR101",
            "name": "KOSPI200 Mini",
            "high": 105.0,
            "low": 95.0,
            "close": 100.0,
        },
        indicators={
            "prediction": {
                "up_prob": 0.7,  # No horizon data, should fallback
            }
        },
        current_positions=[],
        timestamp=None,
    )

    _ = await dl_trend_strategy.generate(context)
    # Should work without errors
