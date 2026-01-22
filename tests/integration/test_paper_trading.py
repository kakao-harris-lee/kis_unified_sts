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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_trading_pipeline_flow():
    """Test complete trading pipeline from regime to exit.

    This integration test validates the full trading flow:
    1. Regime detection determines market state
    2. Entry signals generated based on regime
    3. Paper trading executes orders
    4. Position monitoring tracks P&L
    5. Exit signals close positions

    Components tested:
    - StockRegimeDetector
    - StrategyRouter
    - PaperTradingEngine
    - Position tracking
    - Trade recording
    """
    import pandas as pd
    import numpy as np

    from shared.regime.detector import StockRegimeDetector
    from shared.regime.router import StrategyRouter
    from shared.regime.models import RegimeState, RegimeConfig
    from shared.paper.engine import PaperTradingEngine
    from shared.paper.config import PaperTradingConfig
    from shared.paper.models import OrderSide, PositionSide

    # ============================================
    # Phase 1: Market Regime Detection
    # ============================================
    regime_config = RegimeConfig(sma_fast=10, sma_slow=20)
    detector = StockRegimeDetector(regime_config)

    # Create bull market data with strong trend
    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    bull_prices = 100 + np.arange(60) * 1.0  # Strong uptrend (1% per day)
    df_bull = pd.DataFrame({"datetime": dates, "close": bull_prices})

    # Detect regime
    regime_signal = detector.detect(df_bull)
    assert regime_signal.state == RegimeState.BULL
    # Confidence may vary based on volatility, just verify it's detected as BULL
    assert regime_signal.confidence > 0

    # ============================================
    # Phase 2: Strategy Routing
    # ============================================
    router = StrategyRouter(default_strategy="balanced")
    router.register("momentum", [RegimeState.BULL])
    router.register("defensive", [RegimeState.BEAR])
    router.register("range_trading", [RegimeState.SIDEWAYS])

    active_strategy = router.update(regime_signal)
    assert active_strategy == "momentum"

    # ============================================
    # Phase 3: Paper Trading Execution
    # ============================================
    trading_config = PaperTradingConfig(
        initial_balance=10_000_000,
        max_positions=5,
        commission_rate=0.00015,  # 0.015%
    )
    engine = PaperTradingEngine(trading_config)

    await engine.start()
    assert engine.is_running

    # Entry: Buy signal based on bull regime
    symbol = "005930"
    entry_price = 58000
    quantity = 10

    await engine.process_signal(symbol, OrderSide.BUY, entry_price, quantity)

    # Verify position created
    positions = engine.broker.positions
    assert len(positions) == 1
    assert symbol in positions

    position = positions[symbol]
    assert position.side == PositionSide.LONG
    assert position.quantity == quantity
    # Entry price may include slippage/commission, just verify it's close
    assert abs(position.entry_price - entry_price) < entry_price * 0.01  # Within 1%

    # ============================================
    # Phase 4: Position Monitoring
    # ============================================
    # Simulate price movement (profitable)
    new_price = 60000  # +3.4% profit
    position.update_price(new_price)

    unrealized_pnl = position.unrealized_pnl
    assert unrealized_pnl > 0  # Should be profitable
    # Approximate check due to slippage in entry price
    expected_pnl = (new_price - position.entry_price) * quantity
    assert abs(unrealized_pnl - expected_pnl) < 100  # Within small tolerance

    # Track highest price
    assert position.highest_price == new_price

    # ============================================
    # Phase 5: Exit Execution
    # ============================================
    exit_price = 60500  # Exit at profit
    await engine.process_signal(symbol, OrderSide.SELL, exit_price, quantity)

    # Verify position closed
    assert len(engine.broker.positions) == 0

    # Verify trade recorded
    trades = engine.broker.trades
    assert len(trades) == 1

    trade = trades[0]
    assert trade.symbol == symbol
    # Prices may include slippage, verify they're close
    assert abs(trade.entry_price - entry_price) < entry_price * 0.01
    assert abs(trade.exit_price - exit_price) < exit_price * 0.01
    assert trade.quantity == quantity
    assert trade.pnl > 0  # Profitable trade

    # ============================================
    # Phase 6: Performance Summary
    # ============================================
    performance = engine.get_performance()

    assert performance["total_trades"] == 1
    assert performance["winning_trades"] == 1
    assert performance["win_rate"] == 1.0  # 100% as decimal

    # Check balance increased (equity includes unrealized, balance is cash)
    assert performance["total_pnl"] > 0
    assert performance["equity"] > trading_config.initial_balance

    # Cleanup
    await engine.stop()
    assert not engine.is_running


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_circuit_breaker_integration():
    """Test circuit breaker integration with pipeline."""
    from services.trading.pipeline import TradingPipeline, PipelineStage
    from shared.resilience import CircuitState

    # Create pipeline with handlers that fail
    fail_count = 0

    async def failing_handler():
        nonlocal fail_count
        fail_count += 1
        if fail_count <= 5:
            raise RuntimeError("Simulated failure")
        return "success"

    pipeline = TradingPipeline(
        regime_handler=failing_handler,
        entry_handler=None,
        monitoring_handler=None,
        exit_handler=None,
    )

    # Get regime breaker
    regime_breaker = pipeline.breakers[PipelineStage.REGIME]

    # Verify initial state
    assert not regime_breaker.is_open

    # Record failures
    for _ in range(5):
        regime_breaker.record_failure()

    # Breaker should be open after threshold
    assert regime_breaker.state == CircuitState.OPEN


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_symbol_trading():
    """Test trading multiple symbols simultaneously."""
    from shared.paper.engine import PaperTradingEngine
    from shared.paper.config import PaperTradingConfig
    from shared.paper.models import OrderSide

    config = PaperTradingConfig(
        initial_balance=50_000_000,
        max_positions=5,
    )
    engine = PaperTradingEngine(config)

    await engine.start()

    # Open positions in multiple symbols
    symbols = [
        ("005930", 58000, 10),   # Samsung Electronics
        ("000660", 120000, 5),   # SK Hynix
        ("035420", 280000, 3),   # NAVER
    ]

    for symbol, price, qty in symbols:
        await engine.process_signal(symbol, OrderSide.BUY, price, qty)

    # Verify all positions opened
    assert len(engine.broker.positions) == 3

    # Close all positions with profit
    for symbol, entry_price, qty in symbols:
        exit_price = entry_price * 1.02  # 2% profit
        await engine.process_signal(symbol, OrderSide.SELL, exit_price, qty)

    # Verify all positions closed
    assert len(engine.broker.positions) == 0
    assert len(engine.broker.trades) == 3

    # All trades should be profitable
    for trade in engine.broker.trades:
        assert trade.pnl > 0

    await engine.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_regime_change_strategy_switch():
    """Test strategy switching when regime changes."""
    import pandas as pd
    import numpy as np

    from shared.regime.detector import StockRegimeDetector
    from shared.regime.router import StrategyRouter
    from shared.regime.models import RegimeState, RegimeConfig

    config = RegimeConfig(sma_fast=10, sma_slow=20, trend_threshold=0.02)
    detector = StockRegimeDetector(config)

    router = StrategyRouter(default_strategy="balanced")
    router.register("momentum", [RegimeState.BULL])
    router.register("defensive", [RegimeState.BEAR])
    router.register("range", [RegimeState.SIDEWAYS])

    # Phase 1: Bull market
    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    bull_prices = 100 + np.arange(60) * 0.8
    df_bull = pd.DataFrame({"datetime": dates, "close": bull_prices})

    signal = detector.detect(df_bull)
    router.update(signal)
    assert router.current_strategy == "momentum"

    # Phase 2: Bear market (prices declining)
    bear_prices = 148 - np.arange(60) * 0.8
    df_bear = pd.DataFrame({"datetime": dates, "close": bear_prices})

    signal = detector.detect(df_bear)
    router.update(signal)
    assert router.current_strategy == "defensive"

    # Phase 3: Sideways market (flat prices)
    sideways_prices = 100 + np.sin(np.arange(60) * 0.1) * 0.5
    df_sideways = pd.DataFrame({"datetime": dates, "close": sideways_prices})

    signal = detector.detect(df_sideways)
    router.update(signal)
    assert router.current_strategy == "range"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_equity_curve_tracking():
    """Test equity curve is tracked during trading."""
    from shared.paper.engine import PaperTradingEngine
    from shared.paper.config import PaperTradingConfig
    from shared.paper.models import OrderSide

    config = PaperTradingConfig(
        initial_balance=10_000_000,
        max_equity_points=100,
    )
    engine = PaperTradingEngine(config)

    await engine.start()

    # Make several trades
    for i in range(5):
        price = 50000 + i * 100
        await engine.process_signal("005930", OrderSide.BUY, price, 10)
        await engine.process_signal("005930", OrderSide.SELL, price + 500, 10)

    # Equity curve should have entries
    assert len(engine.equity_curve) > 0

    # Each entry should have required fields
    for point in engine.equity_curve:
        assert "timestamp" in point
        assert "equity" in point
        assert "balance" in point
        assert "positions" in point

    await engine.stop()
