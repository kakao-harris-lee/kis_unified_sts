"""Test strategy registry integration."""
import pytest
from datetime import datetime


def test_register_builtin_components():
    """Test that builtin components are registered correctly."""
    from shared.strategy.registry import (
        EntryRegistry,
        ExitRegistry,
        register_builtin_components,
    )

    # Clear and re-register
    EntryRegistry.clear()
    ExitRegistry.clear()
    register_builtin_components()

    # Check entry strategies are registered
    entry_strategies = EntryRegistry.list_all()
    assert "v35_optimized" in entry_strategies
    assert "stochrsi_trend" in entry_strategies
    assert "mean_reversion" in entry_strategies
    assert "breakout" in entry_strategies

    # Check exit strategies are registered
    exit_strategies = ExitRegistry.list_all()
    assert "three_stage" in exit_strategies


def test_create_entry_from_registry():
    """Test creating entry strategies from registry."""
    from shared.strategy.registry import EntryRegistry, register_builtin_components

    EntryRegistry.clear()
    register_builtin_components()

    # Create V35 entry
    v35 = EntryRegistry.create("v35_optimized", {"bb_period": 20, "rsi_oversold": 30})
    assert v35 is not None
    assert v35.name == "v35_optimized"

    # Create StochRSI entry
    stochrsi = EntryRegistry.create("stochrsi_trend", {"oversold": 20, "overbought": 80})
    assert stochrsi is not None
    assert stochrsi.name == "stochrsi_trend"

    # Create Mean Reversion entry
    mean_rev = EntryRegistry.create("mean_reversion", {"bb_period": 20, "rsi_oversold": 30})
    assert mean_rev is not None
    assert mean_rev.name == "mean_reversion"

    # Create Breakout entry
    breakout = EntryRegistry.create("breakout", {"lookback_period": 20, "volume_confirm": True})
    assert breakout is not None
    assert breakout.name == "breakout"


@pytest.mark.asyncio
async def test_entry_strategy_generate_signal():
    """Test that created strategies can generate signals."""
    from shared.strategy.registry import EntryRegistry, register_builtin_components
    from shared.strategy.base import EntryContext

    EntryRegistry.clear()
    register_builtin_components()

    # Create V35 entry and generate signal
    v35 = EntryRegistry.create("v35_optimized", {"rsi_oversold": 30})

    context = EntryContext(
        market_data={
            "code": "005930",
            "name": "삼성전자",
            "close": 58000,
            "bb_lower": 58500,
            "rsi": 25,
            "macd_hist": 0.5,
        },
        timestamp=datetime.now(),
    )

    signal = await v35.generate(context)
    assert signal is not None
    assert signal.code == "005930"


def test_import_all_entries_from_module():
    """Test that all entries can be imported from the module."""
    from shared.strategy.entry import (
        V35OptimizedEntry,
        V35Config,
        StochRSITrendEntry,
        StochRSIConfig,
        MeanReversionEntry,
        MeanReversionConfig,
        BreakoutEntry,
        BreakoutConfig,
    )

    # Verify all classes are importable
    assert V35OptimizedEntry is not None
    assert V35Config is not None
    assert StochRSITrendEntry is not None
    assert StochRSIConfig is not None
    assert MeanReversionEntry is not None
    assert MeanReversionConfig is not None
    assert BreakoutEntry is not None
    assert BreakoutConfig is not None
