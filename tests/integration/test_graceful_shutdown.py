"""Integration tests for graceful shutdown and position recovery.

Tests the complete shutdown flow:
1. SIGTERM during active trading
2. Redis flush on state transitions
3. Position recovery after restart
4. Edge cases (Redis failure, concurrent signals, etc.)
"""
import asyncio
import json
import signal
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from shared.models.position import Position, PositionSide, PositionState
from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
from shared.streaming.trading_state import TradingStateWriter, TradingStateReader


# -- Fixtures --


@pytest.fixture
def tracker_config():
    """Create tracker configuration for testing."""
    return PositionTrackerConfig(
        max_positions=20,
        max_positions_per_symbol=5,
        default_breakeven_threshold_pct=0.02,  # 2%
        default_maximize_threshold_pct=0.05,  # 5%
    )


@pytest.fixture
def position_tracker(tracker_config):
    """Create a clean position tracker instance."""
    return PositionTracker(tracker_config)


@pytest.fixture
def state_writer():
    """Create TradingStateWriter for stock."""
    return TradingStateWriter(asset="stock")


@pytest.fixture
def state_reader():
    """Create TradingStateReader for stock."""
    return TradingStateReader(asset="stock")


@pytest.fixture(autouse=True)
def cleanup_redis(state_reader):
    """Clean up Redis before and after each test."""
    # Clean up before test
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=1, decode_responses=True)
        r.delete("trading:stock:positions")
    except Exception:
        pass

    yield

    # Clean up after test
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=1, decode_responses=True)
        r.delete("trading:stock:positions")
    except Exception:
        pass


def create_test_position(
    pos_id="test-001",
    code="005930",
    name="Samsung Electronics",
    side=PositionSide.LONG,
    entry_price=70000.0,
    quantity=10,
    strategy="bb_reversion",
    state=PositionState.SURVIVAL,
) -> Position:
    """Helper to create test positions."""
    return Position(
        id=pos_id,
        code=code,
        name=name,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        entry_time=datetime.now(),
        current_price=entry_price,
        highest_price=entry_price,
        lowest_price=entry_price,
        state=state,
        strategy=strategy,
    )


# -- Test: SIGTERM during active trading --


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sigterm_during_trading():
    """Test SIGTERM during active trading with position recovery.

    Flow:
    1. Start orchestrator with active positions
    2. Simulate state transitions (SURVIVAL -> BREAKEVEN -> MAXIMIZE)
    3. Send SIGTERM (call orchestrator.stop())
    4. Verify positions flushed to Redis with correct state
    5. Simulate restart and verify 100% position recovery
    """
    from services.trading.orchestrator import (
        TradingOrchestrator,
        TradingConfig,
        TradingState,
    )

    # Step 1: Setup orchestrator with positions
    config = TradingConfig.stock(
        strategy_name="bb_reversion",
        symbols=["005930", "000660", "035720"],
        initial_capital=10_000_000,
    )

    # Mock WebSocket and market data provider to avoid actual connections
    with patch("services.trading.orchestrator.MarketDataProvider") as MockProvider:
        mock_provider = AsyncMock()
        MockProvider.return_value = mock_provider

        orchestrator = TradingOrchestrator(config)

        # Initialize tracker
        await orchestrator._initialize_tracker()

        # Add test positions manually
        positions = [
            create_test_position(
                pos_id="pos-001",
                code="005930",
                name="Samsung",
                entry_price=70000.0,
                quantity=10,
                state=PositionState.SURVIVAL,
            ),
            create_test_position(
                pos_id="pos-002",
                code="000660",
                name="SK Hynix",
                entry_price=120000.0,
                quantity=5,
                state=PositionState.BREAKEVEN,
            ),
            create_test_position(
                pos_id="pos-003",
                code="035720",
                name="Kakao",
                entry_price=50000.0,
                quantity=20,
                state=PositionState.MAXIMIZE,
            ),
        ]

        # Add positions to tracker
        for pos in positions:
            orchestrator._position_tracker.add_recovered_position(pos)

        assert orchestrator._position_tracker.position_count == 3

        # Step 2: Simulate state transitions
        # Update prices to trigger state transitions
        orchestrator._position_tracker.update_price("005930", 71500.0)  # +2.14% -> BREAKEVEN
        orchestrator._position_tracker.update_price("000660", 126500.0)  # +5.42% -> MAXIMIZE

        # Force state update
        transitions = orchestrator._position_tracker.update_states()

        # Verify states changed
        pos1 = orchestrator._position_tracker.get_position("pos-001")
        pos2 = orchestrator._position_tracker.get_position("pos-002")
        assert pos1.state == PositionState.BREAKEVEN
        assert pos2.state == PositionState.MAXIMIZE

        # Step 3: Flush positions to Redis (simulate immediate flush on state transition)
        if orchestrator._state_publisher:
            orchestrator._state_publisher.publish_positions_update(
                list(orchestrator._position_tracker.positions),
                throttle=0,  # Immediate flush
            )

        # Step 4: Verify positions in Redis
        reader = TradingStateReader(asset="stock")
        redis_positions = reader.get_positions()

        assert len(redis_positions) == 3, f"Expected 3 positions in Redis, got {len(redis_positions)}"

        # Verify all position IDs are present
        redis_ids = {p["id"] for p in redis_positions}
        expected_ids = {"pos-001", "pos-002", "pos-003"}
        assert redis_ids == expected_ids, f"Position IDs mismatch: {redis_ids} vs {expected_ids}"

        # Verify state preservation
        redis_pos_map = {p["id"]: p for p in redis_positions}
        assert redis_pos_map["pos-001"]["state"] == "breakeven"
        assert redis_pos_map["pos-002"]["state"] == "maximize"
        assert redis_pos_map["pos-003"]["state"] == "maximize"

        # Verify all critical fields are preserved
        for pos_id, orig_pos in zip(["pos-001", "pos-002", "pos-003"], positions):
            redis_pos = redis_pos_map[pos_id]
            assert redis_pos["code"] == orig_pos.code
            assert redis_pos["name"] == orig_pos.name
            assert redis_pos["side"] == orig_pos.side.value
            assert redis_pos["quantity"] == orig_pos.quantity
            assert redis_pos["entry_price"] == orig_pos.entry_price
            assert redis_pos["strategy"] == orig_pos.strategy

        # Step 5: Simulate graceful shutdown
        await orchestrator.stop(timeout=10.0)
        assert orchestrator.state == TradingState.STOPPED

        # Step 6: Simulate restart - create new orchestrator and recover positions
        orchestrator2 = TradingOrchestrator(config)
        await orchestrator2._initialize_tracker()

        # Recovery happens in _recover_positions_from_redis (called during start)
        # We'll call it directly here for testing
        recovered_count = await orchestrator2._recover_positions_from_redis()

        assert recovered_count == 3, f"Expected to recover 3 positions, got {recovered_count}"
        assert orchestrator2._position_tracker.position_count == 3

        # Verify recovered positions maintain state
        recovered_pos1 = orchestrator2._position_tracker.get_position("pos-001")
        recovered_pos2 = orchestrator2._position_tracker.get_position("pos-002")
        recovered_pos3 = orchestrator2._position_tracker.get_position("pos-003")

        assert recovered_pos1 is not None
        assert recovered_pos1.state == PositionState.BREAKEVEN
        assert recovered_pos1.code == "005930"

        assert recovered_pos2 is not None
        assert recovered_pos2.state == PositionState.MAXIMIZE
        assert recovered_pos2.code == "000660"

        assert recovered_pos3 is not None
        assert recovered_pos3.state == PositionState.MAXIMIZE
        assert recovered_pos3.code == "035720"

        # Verify indices were rebuilt correctly
        assert len(orchestrator2._position_tracker.get_positions_by_symbol("005930")) == 1
        assert len(orchestrator2._position_tracker.get_positions_by_symbol("000660")) == 1
        assert len(orchestrator2._position_tracker.get_positions_by_symbol("035720")) == 1
        assert len(orchestrator2._position_tracker.get_positions_by_strategy("bb_reversion")) == 3


# -- Test: State transition during shutdown --


@pytest.mark.integration
@pytest.mark.asyncio
async def test_state_transition_during_shutdown():
    """Test position state transition during shutdown window.

    Edge case: Position transitions from SURVIVAL to BREAKEVEN while
    shutdown is in progress. Verify immediate flush happens and state
    is preserved in Redis.
    """
    from services.trading.orchestrator import TradingOrchestrator, TradingConfig

    config = TradingConfig.stock(
        strategy_name="bb_reversion",
        symbols=["005930"],
    )

    with patch("services.trading.orchestrator.MarketDataProvider") as MockProvider:
        mock_provider = AsyncMock()
        MockProvider.return_value = mock_provider

        orchestrator = TradingOrchestrator(config)
        await orchestrator._initialize_tracker()

        # Add position in SURVIVAL state
        pos = create_test_position(
            pos_id="edge-001",
            code="005930",
            entry_price=70000.0,
            state=PositionState.SURVIVAL,
        )
        orchestrator._position_tracker.add_recovered_position(pos)

        # Trigger state transition (SURVIVAL -> BREAKEVEN)
        orchestrator._position_tracker.update_price("005930", 71500.0)  # +2.14%
        transitions = orchestrator._position_tracker.update_states()

        # Immediate flush on state transition
        if orchestrator._state_publisher and transitions:
            orchestrator._state_publisher.publish_positions_update(
                list(orchestrator._position_tracker.positions),
                throttle=0,
            )

        # Verify state in Redis
        reader = TradingStateReader(asset="stock")
        redis_positions = reader.get_positions()

        assert len(redis_positions) == 1
        assert redis_positions[0]["id"] == "edge-001"
        assert redis_positions[0]["state"] == "breakeven"

        # Shutdown
        await orchestrator.stop(timeout=10.0)

        # Verify state persisted after shutdown
        redis_positions_after = reader.get_positions()
        assert len(redis_positions_after) == 1
        assert redis_positions_after[0]["state"] == "breakeven"


# -- Test: Redis connection failure during shutdown --


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_failure_during_shutdown():
    """Test orchestrator handles Redis connection failure gracefully during shutdown.

    Verify:
    1. orchestrator.stop() doesn't hang on Redis failures
    2. Timeout mechanism works correctly
    3. No exceptions propagate to caller
    """
    from services.trading.orchestrator import TradingOrchestrator, TradingConfig

    config = TradingConfig.stock(strategy_name="bb_reversion", symbols=["005930"])

    with patch("services.trading.orchestrator.MarketDataProvider") as MockProvider:
        mock_provider = AsyncMock()
        MockProvider.return_value = mock_provider

        orchestrator = TradingOrchestrator(config)
        await orchestrator._initialize_tracker()

        # Add test position
        pos = create_test_position(pos_id="redis-fail-001", code="005930")
        orchestrator._position_tracker.add_recovered_position(pos)

        # Mock Redis to raise exception on publish
        if orchestrator._state_publisher:
            original_publish = orchestrator._state_publisher.publish_positions_update

            def failing_publish(*args, **kwargs):
                raise ConnectionError("Simulated Redis connection failure")

            orchestrator._state_publisher.publish_positions_update = failing_publish

        # Stop should complete without hanging (within timeout)
        # This should not raise an exception
        start_time = asyncio.get_event_loop().time()
        await orchestrator.stop(timeout=2.0)
        elapsed = asyncio.get_event_loop().time() - start_time

        # Verify shutdown completed quickly (not waiting full timeout)
        assert elapsed < 3.0, f"Shutdown took {elapsed}s, expected < 3s"
        assert orchestrator.state.name == "STOPPED"


# -- Test: 100% position recovery accuracy --


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_position_recovery():
    """Test 100% position recovery with all field types.

    Test with:
    - Stock long positions
    - Futures short positions
    - Different states (SURVIVAL, BREAKEVEN, MAXIMIZE)
    - All fields: id, code, side, quantity, entry_price, state,
      highest_price, lowest_price, stop_price, fee_rate
    """
    from services.trading.orchestrator import TradingOrchestrator, TradingConfig

    config = TradingConfig.futures(strategy_name="rl_mppo")

    with patch("services.trading.orchestrator.MarketDataProvider") as MockProvider:
        mock_provider = AsyncMock()
        MockProvider.return_value = mock_provider

        orchestrator = TradingOrchestrator(config)
        await orchestrator._initialize_tracker()

        # Create diverse position set
        positions = [
            # Stock long in SURVIVAL
            Position(
                id="recovery-001",
                code="005930",
                name="Samsung",
                side=PositionSide.LONG,
                quantity=100,
                entry_price=70000.0,
                entry_time=datetime.now(),
                current_price=69500.0,
                highest_price=70500.0,
                lowest_price=69000.0,
                state=PositionState.SURVIVAL,
                strategy="bb_reversion",
                fee_rate=0.003,
            ),
            # Futures short in BREAKEVEN
            Position(
                id="recovery-002",
                code="A01603",
                name="KOSPI200 Future",
                side=PositionSide.SHORT,
                quantity=1,
                entry_price=837.0,
                entry_time=datetime.now(),
                current_price=835.0,
                highest_price=840.0,
                lowest_price=834.0,
                state=PositionState.BREAKEVEN,
                strategy="rl_mppo",
                fee_rate=0.00015,
                stop_price=842.0,
            ),
            # Stock long in MAXIMIZE
            Position(
                id="recovery-003",
                code="000660",
                name="SK Hynix",
                side=PositionSide.LONG,
                quantity=50,
                entry_price=120000.0,
                entry_time=datetime.now(),
                current_price=128000.0,
                highest_price=129000.0,
                lowest_price=119500.0,
                state=PositionState.MAXIMIZE,
                strategy="bb_reversion",
                fee_rate=0.003,
                stop_price=115000.0,
            ),
        ]

        # Add positions
        for pos in positions:
            orchestrator._position_tracker.add_recovered_position(pos)

        assert orchestrator._position_tracker.position_count == 3

        # Flush to Redis
        if orchestrator._state_publisher:
            orchestrator._state_publisher.publish_positions_update(
                list(orchestrator._position_tracker.positions),
                throttle=0,
            )

        # Shutdown
        await orchestrator.stop(timeout=10.0)

        # Create new orchestrator and recover
        orchestrator2 = TradingOrchestrator(config)
        await orchestrator2._initialize_tracker()
        recovered_count = await orchestrator2._recover_positions_from_redis()

        assert recovered_count == 3

        # Verify all fields for each position
        for orig_pos in positions:
            recovered = orchestrator2._position_tracker.get_position(orig_pos.id)
            assert recovered is not None, f"Position {orig_pos.id} not recovered"

            # Critical fields
            assert recovered.id == orig_pos.id
            assert recovered.code == orig_pos.code
            assert recovered.name == orig_pos.name
            assert recovered.side == orig_pos.side
            assert recovered.quantity == orig_pos.quantity
            assert recovered.entry_price == orig_pos.entry_price
            assert recovered.state == orig_pos.state
            assert recovered.strategy == orig_pos.strategy

            # Price tracking fields
            assert recovered.current_price == orig_pos.current_price
            assert recovered.highest_price == orig_pos.highest_price
            assert recovered.lowest_price == orig_pos.lowest_price

            # Optional fields
            if orig_pos.fee_rate is not None:
                assert recovered.fee_rate == orig_pos.fee_rate

            if orig_pos.stop_price is not None:
                assert recovered.stop_price == orig_pos.stop_price
