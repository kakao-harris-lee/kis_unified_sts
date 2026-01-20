"""Integration tests for paper trading system."""
import pytest
from datetime import datetime


@pytest.mark.integration
@pytest.mark.asyncio
async def test_paper_trading_full_cycle():
    """Test complete paper trading cycle."""
    from shared.paper.engine import PaperTradingEngine
    from shared.paper.config import PaperTradingConfig
    from shared.paper.models import OrderSide

    config = PaperTradingConfig(
        initial_balance=10_000_000,
        max_positions=3,
    )
    engine = PaperTradingEngine(config)

    # Start engine
    await engine.start()
    assert engine.is_running

    # Execute trades
    await engine.process_signal("005930", OrderSide.BUY, 58000, 10)
    await engine.process_signal("000660", OrderSide.BUY, 120000, 5)

    # Check positions
    assert len(engine.broker.positions) == 2

    # Close one position
    await engine.process_signal("005930", OrderSide.SELL, 59000, 10)

    # Check trade recorded
    assert len(engine.broker.trades) == 1

    # Stop engine
    await engine.stop()
    assert not engine.is_running

    # Check performance
    perf = engine.get_performance()
    assert "total_trades" in perf
    assert perf["total_trades"] == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_regime_detection_pipeline():
    """Test regime detection integration."""
    import pandas as pd
    import numpy as np

    from shared.regime.detector import StockRegimeDetector
    from shared.regime.router import StrategyRouter
    from shared.regime.models import RegimeState

    # Create test data
    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    prices = 100 + np.arange(60) * 0.3 + np.random.randn(60) * 0.5  # Uptrend
    df = pd.DataFrame({"datetime": dates, "close": prices})

    # Setup detector and router
    detector = StockRegimeDetector()
    router = StrategyRouter(default_strategy="balanced")
    router.register("momentum", [RegimeState.BULL])
    router.register("defensive", [RegimeState.BEAR])

    # Detect regime
    signal = detector.detect(df)

    # Route to strategy
    strategy = router.update(signal)

    # Should route to momentum in uptrend
    assert router.current_strategy == "momentum"
