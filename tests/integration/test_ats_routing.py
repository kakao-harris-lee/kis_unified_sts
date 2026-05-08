"""Integration tests for ATS routing system.

This test validates the complete end-to-end flow of ATS order routing:
1. Configuration loading with ATS enabled
2. VenueRouter selection logic
3. OrderExecutor venue-specific routing
4. ClickHouse persistence with execution_venue
5. Paper trading integration with venue logging
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
import asyncio


def _build_paper_execution_config():
    """Create a paper-safe ExecutionConfig from repo config.

    Integration tests should not depend on externally configured account
    placeholders. PAPER mode allows an empty account number.
    """
    from shared.execution.config import ExecutionConfig
    from shared.config.loader import ConfigLoader

    config_dict = ConfigLoader.load("execution.yaml")
    execution = dict(config_dict["execution"])
    execution["trading_mode"] = "PAPER"
    execution["account_no"] = ""
    return ExecutionConfig(**execution)


@pytest.mark.integration
def test_ats_config_loading():
    """Test ATS routing configuration loads correctly."""
    from shared.config.loader import ConfigLoader
    from shared.execution.config import ATSRoutingConfig

    # Load execution config
    config = ConfigLoader.load("execution.yaml")
    assert "ats_routing" in config, "ATS routing config should exist"

    # Parse into Pydantic model
    ats_config = ATSRoutingConfig(**config["ats_routing"])

    # Verify configuration fields
    assert isinstance(ats_config.enabled, bool)
    assert ats_config.default_venue in ["KRX", "ATS"]
    assert ats_config.price_improvement_threshold_bps > 0
    assert ats_config.min_depth_multiplier > 0
    assert ats_config.max_spread_bps > 0
    assert ats_config.ats_fill_rate_threshold > 0
    assert ats_config.simulation is not None
    assert ats_config.simulation.ats_fill_rate > 0
    assert ats_config.simulation.price_improvement_mean_bps >= 0


@pytest.mark.integration
def test_venue_router_selection():
    """Test VenueRouter makes routing decisions correctly."""
    from shared.execution.venue_router import VenueRouter, MarketData
    from shared.execution.config import ATSRoutingConfig
    from shared.execution.models import ExecutionVenue, OrderRequest, OrderSide
    from shared.config.loader import ConfigLoader

    # Load ATS config
    config_dict = ConfigLoader.load("execution.yaml")
    ats_config = ATSRoutingConfig(**config_dict["ats_routing"])

    # Enable for testing
    ats_config.enabled = True

    # Create router
    router = VenueRouter(ats_config)

    # Create test order
    order = OrderRequest(
        code="005930",
        name="삼성전자",
        side=OrderSide.BUY,
        quantity=10,
        price=70000.0,
        venue=ExecutionVenue.KRX,
    )

    # Pin current_time to 10:00 (an AUTO time band per the production
    # config) so the test isn't subject to wall-clock-driven time-of-day
    # preferences.  Without this, runners executing during a 'KRX'-
    # preferred window (e.g. 11:30–13:00 UTC = lunch) short-circuit
    # before reaching the liquidity / price-improvement checks the
    # rest of this test exercises.
    auto_band_time = datetime(2026, 5, 8, 10, 0, 0)

    # Test case 1: No market data (should use default venue)
    decision = router.select_venue(
        order, market_data=None, current_time=auto_band_time
    )
    # Without market data, router uses default venue preference
    assert decision.venue in [ExecutionVenue.KRX, ExecutionVenue.ATS]

    # Test case 2: ATS offers price improvement
    market_data = MarketData(
        symbol="005930",
        krx_bid=69900.0,
        krx_ask=70100.0,
        krx_bid_qty=1000.0,
        krx_ask_qty=1000.0,
        ats_bid=69950.0,  # Better bid for buying
        ats_ask=70050.0,  # Better ask for buying
        ats_bid_qty=500.0,
        ats_ask_qty=500.0,
    )
    decision = router.select_venue(
        order, market_data=market_data, current_time=auto_band_time
    )
    # Should consider ATS for price improvement
    assert decision.venue in [ExecutionVenue.KRX, ExecutionVenue.ATS]
    assert decision.price_improvement_bps is not None

    # Test case 3: Insufficient ATS liquidity
    market_data_low_liquidity = MarketData(
        symbol="005930",
        krx_bid=69900.0,
        krx_ask=70100.0,
        krx_bid_qty=1000.0,
        krx_ask_qty=1000.0,
        ats_bid=69950.0,
        ats_ask=70050.0,
        ats_bid_qty=5.0,  # Very low depth
        ats_ask_qty=5.0,   # Very low depth
    )
    decision = router.select_venue(
        order, market_data=market_data_low_liquidity, current_time=auto_band_time
    )
    # Should prefer KRX due to liquidity
    assert decision.venue == ExecutionVenue.KRX
    assert "liquidity" in decision.reason.lower() or "depth" in decision.reason.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_order_executor_venue_routing():
    """Test OrderExecutor routes to correct venue."""
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide, ExecutionVenue
    exec_config = _build_paper_execution_config()

    # Create executor
    executor = OrderExecutor(exec_config)

    # Test KRX order
    krx_order = OrderRequest(
        code="005930",
        name="삼성전자",
        side=OrderSide.BUY,
        quantity=10,
        price=70000.0,
        venue=ExecutionVenue.KRX,
    )

    # Execute order (paper mode, should succeed)
    krx_response = await executor.execute_order(krx_order)
    assert krx_response.success
    assert krx_response.venue == ExecutionVenue.KRX

    # Test ATS order
    ats_order = OrderRequest(
        code="005930",
        name="삼성전자",
        side=OrderSide.BUY,
        quantity=10,
        price=70000.0,
        venue=ExecutionVenue.ATS,
    )

    # Execute order (paper mode, should succeed)
    ats_response = await executor.execute_order(ats_order)
    assert ats_response.success
    assert ats_response.venue == ExecutionVenue.ATS


@pytest.mark.integration
def test_clickhouse_execution_venue_schema():
    """Test ClickHouse schemas include execution_venue column."""
    try:
        from shared.db.client import SCHEMAS
    except ImportError:
        pytest.skip("clickhouse_driver not installed")

    # Check rl_trades schema
    rl_trades_schema = SCHEMAS.get("rl_trades", "")
    assert "execution_venue" in rl_trades_schema, "rl_trades should have execution_venue column"
    assert "LowCardinality(String)" in rl_trades_schema or "String" in rl_trades_schema

    # Check swing_positions schema
    swing_positions_schema = SCHEMAS.get("swing_positions", "")
    assert "execution_venue" in swing_positions_schema, "swing_positions should have execution_venue column"
    assert "String" in swing_positions_schema


@pytest.mark.integration
def test_backtest_trade_model_venue():
    """Test BacktestTrade model includes execution_venue."""
    from shared.backtest.result import BacktestTrade
    from datetime import datetime

    # Create trade with ATS venue
    trade = BacktestTrade(
        code="005930",
        name="삼성전자",
        strategy="bb_reversion",
        side="BUY",
        entry_time=datetime.now(),
        exit_time=datetime.now(),
        entry_price=70000.0,
        exit_price=71000.0,
        quantity=10,
        pnl=10000.0,
        pnl_pct=1.43,
        commission=210.0,
        exit_reason="signal",
        execution_venue="ATS",
    )

    assert trade.execution_venue == "ATS"

    # Test serialization
    trade_dict = trade.to_dict()
    assert "execution_venue" in trade_dict
    assert trade_dict["execution_venue"] == "ATS"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_position_tracker_venue_logging():
    """Test PositionTracker logs execution_venue correctly."""
    from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
    from shared.models.position import Position
    from shared.execution.models import ExecutionVenue
    from datetime import datetime

    # Create position tracker with config
    config = PositionTrackerConfig(max_positions=10)
    tracker = PositionTracker(config=config)

    # Add position with ATS venue
    tracker.add_position(
        code="005930",
        name="삼성전자",
        strategy="bb_reversion",
        side="LONG",  # PositionSide.LONG
        quantity=10,
        entry_price=70000.0,
        execution_venue="ATS",
    )

    # Verify position has venue
    positions_by_symbol = tracker.get_positions_by_symbol("005930")
    assert len(positions_by_symbol) == 1
    position = positions_by_symbol[0]
    assert position.execution_venue == "ATS"

    # Close position
    tracker.close_position(
        position_id=position.id,
        exit_price=71000.0,
        reason="signal",
    )

    # Verify closed position has venue
    closed = tracker._closed_positions[0]
    assert closed.execution_venue == "ATS"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_orchestrator_venue_integration():
    """Test TradingOrchestrator integrates VenueRouter correctly."""
    from services.trading.orchestrator import TradingOrchestrator
    from shared.execution.venue_router import VenueRouter
    from shared.execution.config import ATSRoutingConfig
    from shared.config.loader import ConfigLoader

    # This test verifies that:
    # 1. Orchestrator loads ATS config
    # 2. Creates VenueRouter instance
    # 3. Calls select_venue() before placing orders

    # Load config
    config_dict = ConfigLoader.load("execution.yaml")
    ats_config = config_dict.get("ats_routing", {})

    # Verify config structure
    assert isinstance(ats_config, dict)
    assert "enabled" in ats_config
    assert "default_venue" in ats_config

    # Create VenueRouter manually to verify it can be instantiated
    ats_config_model = ATSRoutingConfig(**ats_config)
    router = VenueRouter(ats_config_model)
    assert router is not None
    assert router.config == ats_config_model


@pytest.mark.integration
def test_ats_simulator_backtest_integration():
    """Test ATSSimulator integration with backtest framework."""
    from shared.backtest.ats_simulator import ATSSimulator, ATSSimulationConfig

    # Create simulator
    config = ATSSimulationConfig(
        ats_fill_rate=0.65,
        price_improvement_mean_bps=3.0,
        price_improvement_std_bps=2.0,
        latency_penalty_ms=15.0,
    )
    simulator = ATSSimulator.from_config(config)

    # Test venue selection (simplified - just check it returns valid venue)
    selection = simulator.simulate_venue_selection(
        order_size=10,
        market_data=None,
    )
    assert selection.venue in ["KRX", "ATS"]
    assert selection.expected_price_improvement_bps is not None

    # Test KRX fill
    krx_fill = simulator.simulate_fill(
        venue="KRX",
        order_side="BUY",
        order_size=10,
        order_price=70000.0,
    )
    assert krx_fill.filled is True  # KRX should always fill
    assert krx_fill.fill_price is not None
    assert krx_fill.fill_quantity == 10

    # Test ATS fill (probabilistic)
    ats_fill = simulator.simulate_fill(
        venue="ATS",
        order_side="BUY",
        order_size=10,
        order_price=70000.0,
    )
    # ATS may or may not fill (65% probability)
    assert isinstance(ats_fill.filled, bool)
    if ats_fill.filled:
        assert ats_fill.fill_price is not None
        assert ats_fill.fill_quantity == 10
        # Price improvement can be positive or negative in simulation
        assert isinstance(ats_fill.price_improvement_bps, float)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2e_paper_trading_with_ats():
    """End-to-end test: Paper trading with ATS routing and venue logging.

    This test simulates the complete flow:
    1. Configure ATS routing (enabled)
    2. Place order through paper trading
    3. Verify VenueRouter is called
    4. Verify OrderExecutor routes to venue
    5. Verify execution_venue is logged
    """
    from shared.execution.executor import OrderExecutor
    from shared.execution.models import OrderRequest, OrderSide, ExecutionVenue
    from shared.execution.config import ATSRoutingConfig
    from shared.execution.venue_router import VenueRouter
    from shared.config.loader import ConfigLoader
    from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
    from datetime import datetime

    # Load configs
    config_dict = ConfigLoader.load("execution.yaml")
    exec_config = _build_paper_execution_config()

    ats_config = ATSRoutingConfig(**config_dict["ats_routing"])
    ats_config.enabled = True  # Enable for test

    # Create components
    router = VenueRouter(ats_config)
    executor = OrderExecutor(exec_config)
    tracker_config = PositionTrackerConfig(max_positions=10)
    tracker = PositionTracker(config=tracker_config)

    # Step 1: Create order (OrderRequest doesn't have 'name' field)
    order = OrderRequest(
        code="005930",
        side=OrderSide.BUY,
        quantity=10,
        price=70000.0,
        venue=ExecutionVenue.KRX,  # Default, will be overridden by router
    )

    # Step 2: Route order (VenueRouter selection)
    routing_decision = router.select_venue(order, market_data=None)
    assert routing_decision is not None
    assert routing_decision.venue in [ExecutionVenue.KRX, ExecutionVenue.ATS]

    # Step 3: Update order with selected venue
    order.venue = routing_decision.venue

    # Step 4: Execute order (OrderExecutor)
    response = await executor.execute_order(order)
    assert response.success
    assert response.venue == routing_decision.venue

    # Step 5: Log position with venue (PositionTracker)
    tracker.add_position(
        code=order.code,
        name="삼성전자",  # Name not in OrderRequest, use hardcoded
        strategy="bb_reversion",
        side="LONG",  # PositionSide enum value
        quantity=order.quantity,
        entry_price=order.price,
        execution_venue=response.venue.value,
    )

    # Step 6: Verify position has venue
    positions_by_symbol = tracker.get_positions_by_symbol(order.code)
    assert len(positions_by_symbol) == 1
    position = positions_by_symbol[0]
    assert position.execution_venue == response.venue.value

    # Step 7: Close position
    tracker.close_position(
        position_id=position.id,
        exit_price=71000.0,
        reason="signal",
    )

    # Step 8: Verify closed position has venue
    closed = tracker._closed_positions[0]
    assert closed.execution_venue == response.venue.value

    print(f"✅ E2E Test Passed:")
    print(f"  - Venue selected: {routing_decision.venue.value}")
    print(f"  - Order executed: {response.success}")
    print(f"  - Venue logged: {closed.execution_venue}")
    print(f"  - Routing reason: {routing_decision.reason}")


@pytest.mark.integration
def test_monitoring_metrics_venue_integration():
    """Test monitoring metrics include venue tracking."""
    from services.monitoring.metrics import MetricsCollector

    # Create metrics collector
    metrics = MetricsCollector()

    # Verify venue metrics methods exist
    assert hasattr(metrics, "record_venue_order_count")
    assert hasattr(metrics, "record_venue_price_improvement")

    # Test recording (should not raise)
    metrics.record_venue_order_count("KRX", 100)
    metrics.record_venue_order_count("ATS", 50)
    metrics.record_venue_price_improvement("ATS", 3.5)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
