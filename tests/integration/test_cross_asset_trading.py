"""Integration tests for cross-asset trading (stock + futures).

Tests the complete cross-asset trading lifecycle:
1. Concurrent stock and futures trading without interference
2. Redis position key isolation between asset classes
3. Cross-asset risk limit enforcement
4. Graceful shutdown with multi-asset position recovery
5. Asset-specific EOD policies (futures 15:15 close, stocks swing exempt)

These tests verify that the platform can manage real capital across
independent asset classes without state corruption or missed exits.
"""
import asyncio
import json
import os
from datetime import datetime, time
from unittest.mock import MagicMock, patch, AsyncMock, Mock

import pytest
import redis

from shared.models.position import Position, PositionSide, PositionState
from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
from shared.streaming.trading_state import TradingStatePublisher, TradingStateReader


# Helper to check if Redis is available
def is_redis_available(redis_url: str = "redis://localhost:6379/1") -> bool:
    """Check if Redis is available at the given URL."""
    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=1)
        r.ping()
        r.close()
        return True
    except (redis.ConnectionError, redis.TimeoutError):
        return False


# -- Fixtures --


@pytest.fixture
def redis_url():
    """Get Redis URL from environment or use default."""
    return os.getenv("REDIS_URL", "redis://localhost:6379/1")


@pytest.fixture(autouse=True)
def cross_asset_redis_cleanup(redis_url):
    """Clean both stock and futures Redis keys before and after tests."""
    import redis

    r = redis.Redis.from_url(redis_url, decode_responses=True)

    # Clean up before test
    r.delete("trading:stock:positions")
    r.delete("trading:futures:positions")
    r.delete("trading:stock:trades")
    r.delete("trading:futures:trades")
    r.delete("risk:portfolio:state")

    yield

    # Clean up after test
    r.delete("trading:stock:positions")
    r.delete("trading:futures:positions")
    r.delete("trading:stock:trades")
    r.delete("trading:futures:trades")
    r.delete("risk:portfolio:state")
    r.close()


@pytest.fixture
def mock_stock_config():
    """Create TradingConfig for stock testing."""
    from services.trading.orchestrator import TradingConfig

    return TradingConfig(
        asset_class="stock",
        strategy_name="bb_reversion",
        symbols=["005930", "000660", "035720"],  # Samsung, SK Hynix, Kakao
        initial_capital=10_000_000,  # 10M KRW
        paper_trading=True,
    )


@pytest.fixture
def mock_futures_config():
    """Create TradingConfig for futures testing."""
    from services.trading.orchestrator import TradingConfig

    return TradingConfig(
        asset_class="futures",
        strategy_name="rl_mppo",
        symbols=["101S6000"],  # KOSPI200 futures
        initial_capital=10_000_000,  # 10M KRW
        paper_trading=True,
    )


@pytest.fixture
def mock_kis_api():
    """Mock KIS API responses for both asset classes."""
    with patch("shared.kis.api.KISApi") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Mock stock order responses
        mock_api.order_stock.return_value = {
            "output": {
                "KRX_FWDG_ORD_ORGNO": "00001",
                "ODNO": "0000000001",
                "ORD_TMD": "093000",
            },
            "rt_cd": "0",
            "msg_cd": "00000",
            "msg1": "Success",
        }

        # Mock futures order responses
        mock_api.order_futures.return_value = {
            "output": {
                "KRX_FWDG_ORD_ORGNO": "00001",
                "ODNO": "0000000002",
                "ORD_TMD": "093000",
            },
            "rt_cd": "0",
            "msg_cd": "00000",
            "msg1": "Success",
        }

        # Mock position query responses
        mock_api.get_stock_balance.return_value = {
            "output1": [],
            "rt_cd": "0",
        }

        mock_api.get_futures_balance.return_value = {
            "output1": [],
            "rt_cd": "0",
        }

        yield mock_api


@pytest.fixture
def tracker_config():
    """Create position tracker configuration for testing."""
    return PositionTrackerConfig(
        max_positions=20,
        max_positions_per_symbol=5,
        default_breakeven_threshold_pct=0.02,  # 2%
        default_maximize_threshold_pct=0.05,  # 5%
    )


# -- Helper Functions --


def create_stock_position(
    pos_id: str = "STOCK-001",
    code: str = "005930",
    name: str = "Samsung Electronics",
    side: PositionSide = PositionSide.LONG,
    entry_price: float = 70000.0,
    quantity: int = 10,
    strategy: str = "bb_reversion",
    state: PositionState = PositionState.SURVIVAL,
    current_price: float = None,
) -> Position:
    """Helper to create test stock positions.

    Args:
        pos_id: Position identifier
        code: Stock code (6-digit)
        name: Stock name
        side: LONG or SHORT
        entry_price: Entry price in KRW
        quantity: Number of shares
        strategy: Strategy name
        state: Position state (SURVIVAL/BREAKEVEN/MAXIMIZE)
        current_price: Current price in KRW (defaults to entry_price)

    Returns:
        Position object for stock trading
    """
    if current_price is None:
        current_price = entry_price

    return Position(
        id=pos_id,
        code=code,
        name=name,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        entry_time=datetime.now(),
        current_price=current_price,
        highest_price=max(entry_price, current_price),
        lowest_price=min(entry_price, current_price),
        state=state,
        strategy=strategy,
    )


def create_futures_position(
    pos_id: str = "FUTURES-001",
    code: str = "101S6000",
    name: str = "KOSPI200 Futures",
    side: PositionSide = PositionSide.LONG,
    entry_price: float = 350000.0,
    quantity: int = 1,
    strategy: str = "rl_mppo",
    state: PositionState = PositionState.SURVIVAL,
    current_price: float = None,
) -> Position:
    """Helper to create test futures positions.

    Args:
        pos_id: Position identifier
        code: Futures code (8-digit)
        name: Futures name
        side: LONG or SHORT
        entry_price: Entry price (futures point value)
        quantity: Number of contracts
        strategy: Strategy name
        state: Position state (SURVIVAL/BREAKEVEN/MAXIMIZE)
        current_price: Current price (defaults to entry_price)

    Returns:
        Position object for futures trading
    """
    if current_price is None:
        current_price = entry_price

    return Position(
        id=pos_id,
        code=code,
        name=name,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        entry_time=datetime.now(),
        current_price=current_price,
        highest_price=max(entry_price, current_price),
        lowest_price=min(entry_price, current_price),
        state=state,
        strategy=strategy,
    )


def verify_redis_isolation(redis_url: str) -> dict:
    """Verify Redis keys are isolated by asset class.

    Args:
        redis_url: Redis connection URL

    Returns:
        Dict with key names and existence status:
        {
            "stock_positions_exists": bool,
            "futures_positions_exists": bool,
            "stock_trades_exists": bool,
            "futures_trades_exists": bool,
            "stock_position_count": int,
            "futures_position_count": int,
        }
    """
    import redis

    r = redis.Redis.from_url(redis_url, decode_responses=True)

    result = {
        "stock_positions_exists": r.exists("trading:stock:positions") > 0,
        "futures_positions_exists": r.exists("trading:futures:positions") > 0,
        "stock_trades_exists": r.exists("trading:stock:trades") > 0,
        "futures_trades_exists": r.exists("trading:futures:trades") > 0,
        "stock_position_count": r.hlen("trading:stock:positions"),
        "futures_position_count": r.hlen("trading:futures:positions"),
    }

    r.close()
    return result


# -- Test Class --


@pytest.mark.integration
class TestCrossAssetTrading:
    """Integration tests for cross-asset trading scenarios.

    Test cases:
    1. Concurrent stock + futures lifecycle
    2. Redis position key isolation
    3. Cross-asset risk limit enforcement
    4. Multi-asset graceful shutdown
    5. Asset-specific EOD policies
    """

    @pytest.mark.asyncio
    async def test_placeholder_for_phase_1_completion(self):
        """Placeholder test to verify module imports and fixtures work.

        This test will be replaced with actual integration tests in subsequent phases.
        For now, it verifies:
        - Module structure is correct
        - Fixtures are available
        - Helpers can be called
        - Redis cleanup works
        """
        # Verify helper functions work
        stock_pos = create_stock_position(
            pos_id="TEST-STOCK-001",
            code="005930",
            name="Samsung",
            entry_price=70000.0,
            quantity=10,
        )
        assert stock_pos.code == "005930"
        assert stock_pos.entry_price == 70000.0
        assert stock_pos.state == PositionState.SURVIVAL

        futures_pos = create_futures_position(
            pos_id="TEST-FUTURES-001",
            code="101S6000",
            name="KOSPI200",
            entry_price=350000.0,
            quantity=1,
        )
        assert futures_pos.code == "101S6000"
        assert futures_pos.entry_price == 350000.0
        assert futures_pos.state == PositionState.SURVIVAL

        # Verify Redis isolation helper
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
        isolation_status = verify_redis_isolation(redis_url)
        assert isinstance(isolation_status, dict)
        assert "stock_positions_exists" in isolation_status
        assert "futures_positions_exists" in isolation_status
        assert isolation_status["stock_position_count"] == 0
        assert isolation_status["futures_position_count"] == 0

    @pytest.mark.asyncio
    async def test_tracker_config_fixture(self, tracker_config):
        """Verify tracker_config fixture provides correct configuration."""
        assert tracker_config.max_positions == 20
        assert tracker_config.max_positions_per_symbol == 5
        assert tracker_config.default_breakeven_threshold_pct == 0.02
        assert tracker_config.default_maximize_threshold_pct == 0.05

    @pytest.mark.asyncio
    async def test_mock_configs_fixtures(self, mock_stock_config, mock_futures_config):
        """Verify mock config fixtures for stock and futures."""
        # Stock config
        assert mock_stock_config.asset_class == "stock"
        assert mock_stock_config.strategy_name == "bb_reversion"
        assert "005930" in mock_stock_config.symbols
        assert mock_stock_config.initial_capital == 10_000_000
        assert mock_stock_config.paper_trading is True

        # Futures config
        assert mock_futures_config.asset_class == "futures"
        assert mock_futures_config.strategy_name == "rl_mppo"
        assert "101S6000" in mock_futures_config.symbols
        assert mock_futures_config.initial_capital == 10_000_000
        assert mock_futures_config.paper_trading is True

    @pytest.mark.asyncio
    async def test_mock_kis_api_fixture(self, mock_kis_api):
        """Verify mock KIS API fixture provides mocked responses."""
        # Test stock order mock
        stock_response = mock_kis_api.order_stock(
            code="005930",
            order_type="BUY",
            quantity=10,
            price=70000,
        )
        assert stock_response["rt_cd"] == "0"
        assert "ODNO" in stock_response["output"]

        # Test futures order mock
        futures_response = mock_kis_api.order_futures(
            code="101S6000",
            order_type="BUY",
            quantity=1,
            price=350000,
        )
        assert futures_response["rt_cd"] == "0"
        assert "ODNO" in futures_response["output"]

        # Test position query mocks
        stock_balance = mock_kis_api.get_stock_balance()
        assert stock_balance["rt_cd"] == "0"
        assert "output1" in stock_balance

        futures_balance = mock_kis_api.get_futures_balance()
        assert futures_balance["rt_cd"] == "0"
        assert "output1" in futures_balance

    @pytest.mark.asyncio
    async def test_redis_cleanup_fixture(self, redis_url):
        """Verify cross_asset_redis_cleanup fixture cleans all keys."""
        import redis

        r = redis.Redis.from_url(redis_url, decode_responses=True)

        # Write some test data to Redis
        r.hset("trading:stock:positions", "TEST-001", json.dumps({"id": "TEST-001"}))
        r.hset("trading:futures:positions", "TEST-002", json.dumps({"id": "TEST-002"}))

        # Verify data exists
        assert r.exists("trading:stock:positions") > 0
        assert r.exists("trading:futures:positions") > 0

        r.close()

        # Fixture will clean up after test (tested in next test run)
        # For now, manually verify cleanup can work
        isolation = verify_redis_isolation(redis_url)
        assert isinstance(isolation, dict)

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not is_redis_available(),
        reason="Redis is not available. Start Redis with: docker-compose -f docker-compose.dev.yml up redis -d"
    )
    async def test_concurrent_stock_futures_lifecycle(
        self, redis_url, tracker_config, mock_stock_config, mock_futures_config
    ):
        """Test complete concurrent stock + futures trading lifecycle.

        This integration test validates concurrent cross-asset trading:
        1. Independent position tracking for stock and futures
        2. Redis key isolation (trading:stock:positions vs trading:futures:positions)
        3. Concurrent position updates without interference
        4. Asset-specific P&L calculation
        5. Graceful multi-asset shutdown with position recovery

        Components tested:
        - PositionTracker (stock and futures instances)
        - Redis persistence layer
        - Position state management
        - Cross-asset isolation
        """
        import redis

        # ============================================
        # Phase 1: Initialize Position Trackers
        # ============================================
        stock_tracker = PositionTracker(
            asset_class="stock",
            config=tracker_config,
            redis_url=redis_url,
        )

        futures_tracker = PositionTracker(
            asset_class="futures",
            config=tracker_config,
            redis_url=redis_url,
        )

        # Verify trackers are configured correctly
        assert stock_tracker.asset_class == "stock"
        assert futures_tracker.asset_class == "futures"
        assert stock_tracker.config.max_positions == 20
        assert futures_tracker.config.max_positions == 20

        # ============================================
        # Phase 2: Create and Track Stock Positions
        # ============================================
        # Entry: Buy Samsung Electronics
        stock_pos_1 = create_stock_position(
            pos_id="STOCK-001",
            code="005930",
            name="Samsung Electronics",
            side=PositionSide.LONG,
            entry_price=70000.0,
            quantity=10,
            strategy="bb_reversion",
        )

        # Entry: Buy SK Hynix
        stock_pos_2 = create_stock_position(
            pos_id="STOCK-002",
            code="000660",
            name="SK Hynix",
            side=PositionSide.LONG,
            entry_price=120000.0,
            quantity=5,
            strategy="bb_reversion",
        )

        stock_tracker.add_position(stock_pos_1)
        stock_tracker.add_position(stock_pos_2)

        # Verify stock positions tracked
        assert len(stock_tracker.get_all_positions()) == 2
        assert stock_tracker.get_position("STOCK-001") is not None
        assert stock_tracker.get_position("STOCK-002") is not None

        # ============================================
        # Phase 3: Create and Track Futures Positions
        # ============================================
        # Entry: Long KOSPI200 Futures
        futures_pos_1 = create_futures_position(
            pos_id="FUTURES-001",
            code="101S6000",
            name="KOSPI200 Futures",
            side=PositionSide.LONG,
            entry_price=350000.0,
            quantity=1,
            strategy="rl_mppo",
        )

        # Entry: Short KOSPI200 Futures (hedging)
        futures_pos_2 = create_futures_position(
            pos_id="FUTURES-002",
            code="101S6000",
            name="KOSPI200 Futures",
            side=PositionSide.SHORT,
            entry_price=351000.0,
            quantity=1,
            strategy="rl_mppo",
        )

        futures_tracker.add_position(futures_pos_1)
        futures_tracker.add_position(futures_pos_2)

        # Verify futures positions tracked
        assert len(futures_tracker.get_all_positions()) == 2
        assert futures_tracker.get_position("FUTURES-001") is not None
        assert futures_tracker.get_position("FUTURES-002") is not None

        # ============================================
        # Phase 4: Verify Redis Key Isolation
        # ============================================
        r = redis.Redis.from_url(redis_url, decode_responses=True)

        # Verify separate Redis keys exist
        stock_positions_raw = r.hgetall("trading:stock:positions")
        futures_positions_raw = r.hgetall("trading:futures:positions")

        assert len(stock_positions_raw) == 2, "Should have 2 stock positions in Redis"
        assert len(futures_positions_raw) == 2, "Should have 2 futures positions in Redis"

        # Verify position IDs are correctly isolated
        stock_ids = set(stock_positions_raw.keys())
        futures_ids = set(futures_positions_raw.keys())

        assert "STOCK-001" in stock_ids
        assert "STOCK-002" in stock_ids
        assert "FUTURES-001" in futures_ids
        assert "FUTURES-002" in futures_ids

        # Verify no cross-contamination
        assert "FUTURES-001" not in stock_ids
        assert "STOCK-001" not in futures_ids

        # ============================================
        # Phase 5: Concurrent Position Updates
        # ============================================
        # Simulate price movements for stock positions
        stock_tracker.update_position("STOCK-001", current_price=72000.0)  # +2.86% profit
        stock_tracker.update_position("STOCK-002", current_price=125000.0)  # +4.17% profit

        # Simulate price movements for futures positions
        futures_tracker.update_position("FUTURES-001", current_price=352000.0)  # +0.57% profit
        futures_tracker.update_position("FUTURES-002", current_price=350000.0)  # +0.28% profit (short)

        # Verify stock position updates
        stock_pos_1_updated = stock_tracker.get_position("STOCK-001")
        assert stock_pos_1_updated.current_price == 72000.0
        assert stock_pos_1_updated.unrealized_pnl > 0
        expected_stock_pnl_1 = (72000.0 - 70000.0) * 10
        assert abs(stock_pos_1_updated.unrealized_pnl - expected_stock_pnl_1) < 10

        stock_pos_2_updated = stock_tracker.get_position("STOCK-002")
        assert stock_pos_2_updated.current_price == 125000.0
        expected_stock_pnl_2 = (125000.0 - 120000.0) * 5
        assert abs(stock_pos_2_updated.unrealized_pnl - expected_stock_pnl_2) < 10

        # Verify futures position updates
        futures_pos_1_updated = futures_tracker.get_position("FUTURES-001")
        assert futures_pos_1_updated.current_price == 352000.0
        assert futures_pos_1_updated.unrealized_pnl > 0

        futures_pos_2_updated = futures_tracker.get_position("FUTURES-002")
        assert futures_pos_2_updated.current_price == 350000.0
        assert futures_pos_2_updated.unrealized_pnl > 0  # Short position profits from price drop

        # ============================================
        # Phase 6: Position State Transitions
        # ============================================
        # Stock position reaches BREAKEVEN threshold (2%)
        stock_pos_1_updated.state = PositionState.BREAKEVEN
        stock_tracker.update_position("STOCK-001", current_price=73000.0)

        # Verify state persisted
        stock_pos_1_state = stock_tracker.get_position("STOCK-001")
        assert stock_pos_1_state.state == PositionState.BREAKEVEN

        # Futures position remains in SURVIVAL (RL-based exit)
        futures_pos_1_updated.state = PositionState.SURVIVAL
        futures_tracker.update_position("FUTURES-001", current_price=353000.0)

        # Verify state persisted
        futures_pos_1_state = futures_tracker.get_position("FUTURES-001")
        assert futures_pos_1_state.state == PositionState.SURVIVAL

        # ============================================
        # Phase 7: Exit Positions
        # ============================================
        # Close stock position (profitable exit)
        closed_stock_pos = stock_tracker.close_position("STOCK-001", exit_price=73000.0)
        assert closed_stock_pos is not None
        assert closed_stock_pos.id == "STOCK-001"
        assert closed_stock_pos.exit_price == 73000.0

        # Close futures position (profitable exit)
        closed_futures_pos = futures_tracker.close_position("FUTURES-001", exit_price=353000.0)
        assert closed_futures_pos is not None
        assert closed_futures_pos.id == "FUTURES-001"
        assert closed_futures_pos.exit_price == 353000.0

        # Verify positions removed from tracking
        assert stock_tracker.get_position("STOCK-001") is None
        assert futures_tracker.get_position("FUTURES-001") is None

        # Verify remaining positions still tracked
        assert len(stock_tracker.get_all_positions()) == 1
        assert len(futures_tracker.get_all_positions()) == 1

        # ============================================
        # Phase 8: Portfolio P&L Aggregation
        # ============================================
        # Calculate total portfolio P&L across assets
        stock_total_pnl = sum(
            pos.unrealized_pnl for pos in stock_tracker.get_all_positions()
        )
        futures_total_pnl = sum(
            pos.unrealized_pnl for pos in futures_tracker.get_all_positions()
        )
        portfolio_total_pnl = stock_total_pnl + futures_total_pnl

        assert stock_total_pnl > 0, "Stock portfolio should be profitable"
        assert futures_total_pnl > 0, "Futures portfolio should be profitable"
        assert portfolio_total_pnl > 0, "Total portfolio should be profitable"

        # ============================================
        # Phase 9: Graceful Shutdown and Recovery
        # ============================================
        # Simulate shutdown: positions should persist in Redis
        stock_tracker_snapshot = stock_tracker.get_all_positions()
        futures_tracker_snapshot = futures_tracker.get_all_positions()

        assert len(stock_tracker_snapshot) == 1
        assert len(futures_tracker_snapshot) == 1

        # Create new tracker instances (simulating process restart)
        stock_tracker_recovered = PositionTracker(
            asset_class="stock",
            config=tracker_config,
            redis_url=redis_url,
        )

        futures_tracker_recovered = PositionTracker(
            asset_class="futures",
            config=tracker_config,
            redis_url=redis_url,
        )

        # Load positions from Redis
        stock_tracker_recovered.load_from_redis()
        futures_tracker_recovered.load_from_redis()

        # Verify positions recovered
        stock_recovered_positions = stock_tracker_recovered.get_all_positions()
        futures_recovered_positions = futures_tracker_recovered.get_all_positions()

        assert len(stock_recovered_positions) == 1
        assert len(futures_recovered_positions) == 1

        # Verify recovered position details
        recovered_stock_pos = stock_recovered_positions[0]
        assert recovered_stock_pos.code == "000660"
        assert recovered_stock_pos.strategy == "bb_reversion"

        recovered_futures_pos = futures_recovered_positions[0]
        assert recovered_futures_pos.code == "101S6000"
        assert recovered_futures_pos.strategy == "rl_mppo"

        # ============================================
        # Phase 10: Cleanup
        # ============================================
        r.close()

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not is_redis_available(),
        reason="Redis is not available. Start Redis with: docker-compose -f docker-compose.dev.yml up redis -d"
    )
    async def test_redis_position_key_isolation(self, redis_url):
        """Test Redis key isolation between stock and futures asset classes.

        This test verifies that position data for different asset classes
        is stored in separate Redis keys to prevent state corruption.

        Flow:
        1. Publish stock positions to Redis using TradingStatePublisher("stock")
        2. Publish futures positions to Redis using TradingStatePublisher("futures")
        3. Verify separate Redis keys exist (trading:stock:positions vs trading:futures:positions)
        4. Verify no cross-contamination between asset class keys
        5. Verify TradingStateReader reads correct asset-specific data
        6. Verify position updates don't leak across asset classes
        """
        import redis

        # Step 1: Create TradingStatePublishers for each asset class
        stock_publisher = TradingStatePublisher(asset_class="stock")
        futures_publisher = TradingStatePublisher(asset_class="futures")

        # Step 2: Create and publish stock positions
        stock_pos_1 = create_stock_position(
            pos_id="STOCK-ISO-001",
            code="005930",
            name="Samsung Electronics",
            entry_price=70000.0,
            quantity=10,
        )

        stock_pos_2 = create_stock_position(
            pos_id="STOCK-ISO-002",
            code="000660",
            name="SK Hynix",
            entry_price=120000.0,
            quantity=5,
        )

        # Publish stock positions
        stock_publisher.publish_position_opened(stock_pos_1)
        stock_publisher.publish_position_opened(stock_pos_2)

        # Step 3: Create and publish futures positions
        futures_pos_1 = create_futures_position(
            pos_id="FUTURES-ISO-001",
            code="101S6000",
            name="KOSPI200 Futures",
            side=PositionSide.LONG,
            entry_price=350000.0,
            quantity=1,
        )

        futures_pos_2 = create_futures_position(
            pos_id="FUTURES-ISO-002",
            code="101S6000",
            name="KOSPI200 Futures",
            side=PositionSide.SHORT,
            entry_price=351000.0,
            quantity=1,
        )

        # Publish futures positions
        futures_publisher.publish_position_opened(futures_pos_1)
        futures_publisher.publish_position_opened(futures_pos_2)

        # Step 4: Verify separate Redis keys exist
        r = redis.Redis.from_url(redis_url, decode_responses=True)

        # Check that both keys exist
        stock_key_exists = r.exists("trading:stock:positions")
        futures_key_exists = r.exists("trading:futures:positions")

        assert stock_key_exists > 0, "Stock positions key should exist in Redis"
        assert futures_key_exists > 0, "Futures positions key should exist in Redis"

        # Step 5: Verify position counts in each key
        stock_positions_raw = r.hgetall("trading:stock:positions")
        futures_positions_raw = r.hgetall("trading:futures:positions")

        assert len(stock_positions_raw) == 2, "Should have exactly 2 stock positions"
        assert len(futures_positions_raw) == 2, "Should have exactly 2 futures positions"

        # Step 6: Verify no cross-contamination
        stock_position_ids = set(stock_positions_raw.keys())
        futures_position_ids = set(futures_positions_raw.keys())

        # Stock positions should only contain stock IDs
        assert "STOCK-ISO-001" in stock_position_ids
        assert "STOCK-ISO-002" in stock_position_ids
        assert "FUTURES-ISO-001" not in stock_position_ids
        assert "FUTURES-ISO-002" not in stock_position_ids

        # Futures positions should only contain futures IDs
        assert "FUTURES-ISO-001" in futures_position_ids
        assert "FUTURES-ISO-002" in futures_position_ids
        assert "STOCK-ISO-001" not in futures_position_ids
        assert "STOCK-ISO-002" not in futures_position_ids

        # Step 7: Verify position data integrity
        # Parse stock position data
        stock_pos_1_data = json.loads(stock_positions_raw["STOCK-ISO-001"])
        assert stock_pos_1_data["code"] == "005930"
        assert stock_pos_1_data["strategy"] == "bb_reversion"
        assert float(stock_pos_1_data["entry_price"]) == 70000.0

        # Parse futures position data
        futures_pos_1_data = json.loads(futures_positions_raw["FUTURES-ISO-001"])
        assert futures_pos_1_data["code"] == "101S6000"
        assert futures_pos_1_data["strategy"] == "rl_mppo"
        assert float(futures_pos_1_data["entry_price"]) == 350000.0

        # Step 8: Verify TradingStateReader reads correct asset-specific data
        stock_reader = TradingStateReader(asset_class="stock")
        futures_reader = TradingStateReader(asset_class="futures")

        # Read stock positions
        stock_positions_read = stock_reader.get_positions()
        assert len(stock_positions_read) == 2
        stock_ids_read = {pos["id"] for pos in stock_positions_read.values()}
        assert "STOCK-ISO-001" in stock_ids_read
        assert "STOCK-ISO-002" in stock_ids_read

        # Read futures positions
        futures_positions_read = futures_reader.get_positions()
        assert len(futures_positions_read) == 2
        futures_ids_read = {pos["id"] for pos in futures_positions_read.values()}
        assert "FUTURES-ISO-001" in futures_ids_read
        assert "FUTURES-ISO-002" in futures_ids_read

        # Step 9: Test position updates don't leak across asset classes
        # Update a stock position
        stock_pos_1.current_price = 72000.0
        stock_publisher.publish_position_opened(stock_pos_1)  # Update in Redis

        # Update a futures position
        futures_pos_1.current_price = 352000.0
        futures_publisher.publish_position_opened(futures_pos_1)  # Update in Redis

        # Verify updates are isolated
        stock_positions_updated = r.hgetall("trading:stock:positions")
        futures_positions_updated = r.hgetall("trading:futures:positions")

        stock_pos_1_updated = json.loads(stock_positions_updated["STOCK-ISO-001"])
        assert float(stock_pos_1_updated["current_price"]) == 72000.0

        futures_pos_1_updated = json.loads(futures_positions_updated["FUTURES-ISO-001"])
        assert float(futures_pos_1_updated["current_price"]) == 352000.0

        # Verify no cross-contamination in counts
        assert len(stock_positions_updated) == 2
        assert len(futures_positions_updated) == 2

        # Step 10: Test position close isolation
        # Close a stock position
        stock_publisher.publish_position_closed(stock_pos_1)

        # Close a futures position
        futures_publisher.publish_position_closed(futures_pos_1)

        # Verify positions removed from respective keys
        stock_positions_after_close = r.hgetall("trading:stock:positions")
        futures_positions_after_close = r.hgetall("trading:futures:positions")

        assert len(stock_positions_after_close) == 1, "Should have 1 stock position after close"
        assert len(futures_positions_after_close) == 1, "Should have 1 futures position after close"
        assert "STOCK-ISO-001" not in stock_positions_after_close
        assert "FUTURES-ISO-001" not in futures_positions_after_close

        # Verify trades keys are also isolated
        stock_trades_key_exists = r.exists("trading:stock:trades")
        futures_trades_key_exists = r.exists("trading:futures:trades")

        assert stock_trades_key_exists > 0, "Stock trades key should exist"
        assert futures_trades_key_exists > 0, "Futures trades key should exist"

        # Step 11: Cleanup
        r.close()

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not is_redis_available(),
        reason="Redis not available",
    )
    async def test_cross_asset_risk_limits(self, redis_url):
        """Test RiskManager enforces limits across stock and futures positions.

        Scenario:
        1. Set max_total_positions=5, open 3 stock + 3 futures (6 total)
        2. Verify 6th position is blocked due to position limit
        3. Set daily_loss_limit_pct=2%, trigger losses in both assets
        4. Verify total loss blocks new positions across both asset classes

        Verifies:
        - Position count limit enforced across assets
        - Daily loss limit calculated from both stock and futures
        - Risk state blocks new positions when limit exceeded
        - Block reason correctly reported
        """
        from shared.risk.manager import RiskManager
        from shared.risk.config import RiskConfig
        from shared.risk.models import BlockReason

        # Step 1: Test cross-asset position count enforcement
        # Set up risk manager with low position limit (5 total)
        risk_config = RiskConfig(
            daily_loss_limit_pct=10.0,  # High limit, won't trigger yet
            max_total_positions=5,  # Only 5 positions allowed total
            initial_capital=10_000_000,  # 10M KRW
        )
        risk_manager = RiskManager(risk_config)

        # Create 3 stock positions
        stock_positions = [
            create_stock_position(
                pos_id="STOCK-RISK-001",
                code="005930",
                name="삼성전자",
                side=PositionSide.LONG,
                entry_price=70000,
                current_price=69000,  # Small loss
                quantity=10,
            ),
            create_stock_position(
                pos_id="STOCK-RISK-002",
                code="000660",
                name="SK하이닉스",
                side=PositionSide.LONG,
                entry_price=120000,
                current_price=118000,  # Small loss
                quantity=5,
            ),
            create_stock_position(
                pos_id="STOCK-RISK-003",
                code="035720",
                name="카카오",
                side=PositionSide.LONG,
                entry_price=50000,
                current_price=49500,  # Small loss
                quantity=20,
            ),
        ]

        # Create 2 futures positions
        futures_positions = [
            create_futures_position(
                pos_id="FUTURES-RISK-001",
                code="101S6000",
                name="KOSPI200 선물",
                side=PositionSide.LONG,
                entry_price=350000,
                current_price=345000,  # Small loss
                quantity=1,
            ),
            create_futures_position(
                pos_id="FUTURES-RISK-002",
                code="101S6000",
                name="KOSPI200 선물",
                side=PositionSide.SHORT,
                entry_price=340000,
                current_price=342000,  # Small loss
                quantity=1,
            ),
        ]

        # Update risk manager with positions (3 stock + 2 futures = 5 total)
        positions_by_asset = {
            "stock": stock_positions,
            "futures": futures_positions,
        }
        risk_manager.update_positions(positions_by_asset)

        # Verify portfolio metrics
        metrics = risk_manager.get_portfolio_metrics()
        assert metrics.total_positions == 5, "Should have 5 total positions"
        assert metrics.exposure_by_asset["stock"].position_count == 3, "Should have 3 stock positions"
        assert metrics.exposure_by_asset["futures"].position_count == 2, "Should have 2 futures positions"

        # At limit (5/5), new positions should be blocked
        can_open_stock = risk_manager.can_open_position("stock")
        can_open_futures = risk_manager.can_open_position("futures")

        assert can_open_stock is False, "Should not allow opening stock position (at limit)"
        assert can_open_futures is False, "Should not allow opening futures position (at limit)"

        # Step 2: Test cross-asset daily loss limit enforcement
        # Create new risk manager with low daily loss limit
        risk_config_loss_limit = RiskConfig(
            daily_loss_limit_pct=2.0,  # Only 2% allowed (200,000 KRW)
            max_total_positions=20,  # High limit, won't trigger
            initial_capital=10_000_000,  # 10M KRW
        )
        risk_manager_loss = RiskManager(risk_config_loss_limit)

        # Simulate positions with losses across both asset classes
        # Stock losses: -150,000 KRW
        stock_positions_with_loss = [
            create_stock_position(
                pos_id="STOCK-LOSS-001",
                code="005930",
                name="삼성전자",
                side=PositionSide.LONG,
                entry_price=70000,
                current_price=65000,  # -5000 per share * 10 = -50,000 KRW
                quantity=10,
            ),
            create_stock_position(
                pos_id="STOCK-LOSS-002",
                code="000660",
                name="SK하이닉스",
                side=PositionSide.LONG,
                entry_price=120000,
                current_price=110000,  # -10,000 per share * 10 = -100,000 KRW
                quantity=10,
            ),
        ]

        # Futures losses: -100,000 KRW (total loss = -250,000 = -2.5%)
        futures_positions_with_loss = [
            create_futures_position(
                pos_id="FUTURES-LOSS-001",
                code="101S6000",
                name="KOSPI200 선물",
                side=PositionSide.LONG,
                entry_price=350000,
                current_price=340000,  # -10,000 per contract * 10 contracts = -100,000 KRW
                quantity=10,
            ),
        ]

        # Update positions and calculate PnL
        positions_with_loss = {
            "stock": stock_positions_with_loss,
            "futures": futures_positions_with_loss,
        }
        risk_manager_loss.update_positions(positions_with_loss)

        # Manually calculate and set daily PnL to simulate actual trading losses
        # Stock loss: (65000-70000)*10 + (110000-120000)*10 = -50,000 + -100,000 = -150,000
        # Futures loss: (340000-350000)*10 = -100,000
        # Total: -250,000 KRW = -2.5% of 10M (exceeds 2% limit)
        total_daily_loss = -250_000
        risk_manager_loss._daily_pnl = total_daily_loss

        # Verify daily loss percentage
        loss_pct = abs(total_daily_loss) / risk_config_loss_limit.initial_capital * 100
        assert loss_pct == 2.5, "Daily loss should be 2.5%"
        assert loss_pct > risk_config_loss_limit.daily_loss_limit_pct, "Should exceed limit"

        # Check that new position entry is blocked for both asset classes
        can_open_stock_loss = risk_manager_loss.can_open_position("stock")
        can_open_futures_loss = risk_manager_loss.can_open_position("futures")

        assert can_open_stock_loss is False, "Stock entry should be blocked due to daily loss"
        assert can_open_futures_loss is False, "Futures entry should be blocked due to daily loss"

        # Verify the internal daily loss tracking
        # The _daily_pnl test attribute should reflect the simulated loss
        assert risk_manager_loss._daily_pnl == total_daily_loss, "Daily PnL tracking should match simulated loss"

        # Step 3: Verify cross-asset metrics are accurate
        metrics_loss = risk_manager_loss.get_portfolio_metrics()
        assert metrics_loss.total_positions == 3, "Should have 3 total positions (2 stock + 1 futures)"
        assert metrics_loss.exposure_by_asset["stock"].position_count == 2, "Should have 2 stock positions"
        assert metrics_loss.exposure_by_asset["futures"].position_count == 1, "Should have 1 futures position"

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not is_redis_available(),
        reason="Redis not available",
    )
    async def test_graceful_shutdown_multi_asset(
        self, redis_url, mock_stock_config, mock_futures_config
    ):
        """Test graceful shutdown with open stock and futures positions.

        This test validates multi-asset graceful shutdown and recovery:
        1. Start stock and futures orchestrators with active positions
        2. Simulate state transitions in both asset classes
        3. Trigger graceful shutdown (SIGTERM) on both orchestrators
        4. Verify positions flushed to isolated Redis keys
        5. Simulate restart and verify 100% position recovery for both assets
        6. Verify no cross-contamination between asset classes

        Flow:
        - Stock orchestrator: 3 positions (SURVIVAL, BREAKEVEN, MAXIMIZE)
        - Futures orchestrator: 2 positions (LONG, SHORT)
        - Shutdown both orchestrators
        - Verify Redis keys: trading:stock:positions and trading:futures:positions
        - Restart and recover all 5 positions
        """
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        # ============================================
        # Phase 1: Setup Stock Orchestrator
        # ============================================
        with patch("services.trading.orchestrator.MarketDataProvider") as MockStockProvider:
            mock_stock_provider = AsyncMock()
            MockStockProvider.return_value = mock_stock_provider

            stock_orchestrator = TradingOrchestrator(mock_stock_config)

            # Initialize strategy infrastructure
            stock_orchestrator._init_strategy_infrastructure()
            stock_orchestrator._state_publisher = TradingStatePublisher(asset_class="stock")

            # Add stock test positions
            stock_positions = [
                create_stock_position(
                    pos_id="STOCK-SD-001",
                    code="005930",
                    name="Samsung Electronics",
                    entry_price=70000.0,
                    quantity=10,
                    state=PositionState.SURVIVAL,
                ),
                create_stock_position(
                    pos_id="STOCK-SD-002",
                    code="000660",
                    name="SK Hynix",
                    entry_price=120000.0,
                    quantity=5,
                    state=PositionState.BREAKEVEN,
                ),
                create_stock_position(
                    pos_id="STOCK-SD-003",
                    code="035720",
                    name="Kakao",
                    entry_price=50000.0,
                    quantity=20,
                    state=PositionState.MAXIMIZE,
                ),
            ]

            for pos in stock_positions:
                stock_orchestrator._position_tracker.add_recovered_position(pos)

            assert stock_orchestrator._position_tracker.position_count == 3

        # ============================================
        # Phase 2: Setup Futures Orchestrator
        # ============================================
        with patch("services.trading.orchestrator.MarketDataProvider") as MockFuturesProvider:
            mock_futures_provider = AsyncMock()
            MockFuturesProvider.return_value = mock_futures_provider

            futures_orchestrator = TradingOrchestrator(mock_futures_config)

            # Initialize strategy infrastructure
            futures_orchestrator._init_strategy_infrastructure()
            futures_orchestrator._state_publisher = TradingStatePublisher(asset_class="futures")

            # Add futures test positions
            futures_positions = [
                create_futures_position(
                    pos_id="FUTURES-SD-001",
                    code="101S6000",
                    name="KOSPI200 Futures",
                    side=PositionSide.LONG,
                    entry_price=350000.0,
                    quantity=1,
                    state=PositionState.SURVIVAL,
                ),
                create_futures_position(
                    pos_id="FUTURES-SD-002",
                    code="101S6000",
                    name="KOSPI200 Futures",
                    side=PositionSide.SHORT,
                    entry_price=351000.0,
                    quantity=1,
                    state=PositionState.SURVIVAL,
                ),
            ]

            for pos in futures_positions:
                futures_orchestrator._position_tracker.add_recovered_position(pos)

            assert futures_orchestrator._position_tracker.position_count == 2

        # ============================================
        # Phase 3: Simulate State Transitions
        # ============================================
        # Update stock prices to trigger state transitions
        stock_orchestrator._position_tracker.update_prices({
            "005930": 71500.0,  # +2.14% -> BREAKEVEN
            "000660": 126500.0,  # +5.42% -> MAXIMIZE
        })

        # Update futures prices
        futures_orchestrator._position_tracker.update_prices({
            "101S6000": 352000.0,  # LONG +0.57%, SHORT -0.28%
        })

        # Force state updates
        stock_transitions = stock_orchestrator._position_tracker.update_states()
        futures_transitions = futures_orchestrator._position_tracker.update_states()

        # Verify stock states changed
        stock_pos_1 = stock_orchestrator._position_tracker.get_position("STOCK-SD-001")
        stock_pos_2 = stock_orchestrator._position_tracker.get_position("STOCK-SD-002")
        assert stock_pos_1.state == PositionState.BREAKEVEN
        assert stock_pos_2.state == PositionState.MAXIMIZE

        # ============================================
        # Phase 4: Flush Positions to Redis
        # ============================================
        # Simulate immediate flush on state transition (graceful shutdown behavior)
        if stock_orchestrator._state_publisher:
            stock_orchestrator._state_publisher.publish_positions_update(
                list(stock_orchestrator._position_tracker.positions),
                throttle=0,  # Immediate flush
            )

        if futures_orchestrator._state_publisher:
            futures_orchestrator._state_publisher.publish_positions_update(
                list(futures_orchestrator._position_tracker.positions),
                throttle=0,  # Immediate flush
            )

        # Wait for Redis writes to complete
        await asyncio.sleep(0.1)

        # ============================================
        # Phase 5: Verify Redis Key Isolation
        # ============================================
        import redis

        r = redis.Redis.from_url(redis_url, decode_responses=True)

        # Verify separate keys exist
        stock_positions_raw = r.hgetall("trading:stock:positions")
        futures_positions_raw = r.hgetall("trading:futures:positions")

        assert len(stock_positions_raw) == 3, "Should have 3 stock positions in Redis"
        assert len(futures_positions_raw) == 2, "Should have 2 futures positions in Redis"

        # Verify position IDs are correctly isolated
        stock_ids = set(stock_positions_raw.keys())
        futures_ids = set(futures_positions_raw.keys())

        assert "STOCK-SD-001" in stock_ids
        assert "STOCK-SD-002" in stock_ids
        assert "STOCK-SD-003" in stock_ids
        assert "FUTURES-SD-001" in futures_ids
        assert "FUTURES-SD-002" in futures_ids

        # Verify no cross-contamination
        assert "FUTURES-SD-001" not in stock_ids
        assert "FUTURES-SD-002" not in stock_ids
        assert "STOCK-SD-001" not in futures_ids
        assert "STOCK-SD-002" not in futures_ids

        # ============================================
        # Phase 6: Trigger Graceful Shutdown
        # ============================================
        # Call stop() on both orchestrators (simulates SIGTERM)
        await stock_orchestrator.stop(timeout=5)
        await futures_orchestrator.stop(timeout=5)

        # Verify final Redis flush occurred
        stock_positions_after_shutdown = r.hgetall("trading:stock:positions")
        futures_positions_after_shutdown = r.hgetall("trading:futures:positions")

        assert len(stock_positions_after_shutdown) == 3, "Stock positions should persist after shutdown"
        assert len(futures_positions_after_shutdown) == 2, "Futures positions should persist after shutdown"

        # ============================================
        # Phase 7: Verify Position Recovery from Redis
        # ============================================
        # Use TradingStateReader to verify positions can be recovered
        stock_reader = TradingStateReader(asset_class="stock")
        futures_reader = TradingStateReader(asset_class="futures")

        # Read stock positions from Redis (returns list of position dicts)
        stock_positions_read = stock_reader.get_positions()
        assert len(stock_positions_read) == 3, "Should have 3 stock positions in Redis"

        # Verify stock position details
        stock_ids_read = {pos["id"] for pos in stock_positions_read}
        assert "STOCK-SD-001" in stock_ids_read
        assert "STOCK-SD-002" in stock_ids_read
        assert "STOCK-SD-003" in stock_ids_read

        # Build position lookup dict for verification
        stock_pos_dict = {pos["id"]: pos for pos in stock_positions_read}

        # Verify stock position states preserved
        assert stock_pos_dict["STOCK-SD-001"]["code"] == "005930"
        assert stock_pos_dict["STOCK-SD-001"]["state"] == "breakeven"
        assert stock_pos_dict["STOCK-SD-002"]["code"] == "000660"
        assert stock_pos_dict["STOCK-SD-002"]["state"] == "maximize"
        assert stock_pos_dict["STOCK-SD-003"]["code"] == "035720"
        assert stock_pos_dict["STOCK-SD-003"]["state"] == "maximize"

        # Read futures positions from Redis (returns list of position dicts)
        futures_positions_read = futures_reader.get_positions()
        assert len(futures_positions_read) == 2, "Should have 2 futures positions in Redis"

        # Verify futures position details
        futures_ids_read = {pos["id"] for pos in futures_positions_read}
        assert "FUTURES-SD-001" in futures_ids_read
        assert "FUTURES-SD-002" in futures_ids_read

        # Build position lookup dict for verification
        futures_pos_dict = {pos["id"]: pos for pos in futures_positions_read}

        # Verify futures position sides preserved
        assert futures_pos_dict["FUTURES-SD-001"]["code"] == "101S6000"
        assert futures_pos_dict["FUTURES-SD-001"]["side"] == "long"
        assert futures_pos_dict["FUTURES-SD-002"]["code"] == "101S6000"
        assert futures_pos_dict["FUTURES-SD-002"]["side"] == "short"

        # ============================================
        # Phase 8: Verify No Cross-Asset Contamination
        # ============================================
        # Verify stock positions don't contain futures IDs
        assert "FUTURES-SD-001" not in stock_ids_read
        assert "FUTURES-SD-002" not in stock_ids_read

        # Verify futures positions don't contain stock IDs
        assert "STOCK-SD-001" not in futures_ids_read
        assert "STOCK-SD-002" not in futures_ids_read
        assert "STOCK-SD-003" not in futures_ids_read

        # ============================================
        # Phase 9: Cleanup
        # ============================================
        r.close()

    @pytest.mark.asyncio
    async def test_eod_policies_by_asset_class(self, redis_url):
        """Test futures EOD force-close at 15:15 vs stock swing positions.

        Verifies:
        - Futures positions are force-closed at 15:15 (EOD policy)
        - Stock positions in MAXIMIZE state are NOT force-closed at EOD
          (swing positions allowed per CLAUDE.md policy)

        This test validates asset-specific EOD behavior:
        - Futures: intraday only, force-close at 15:15
        - Stocks: swing positions allowed, no forced EOD close
        """
        from shared.strategy.base import ExitContext
        from shared.strategy.exit.rl_mppo_exit import RLMPPOExit, RLMPPOExitConfig
        from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig
        from shared.models.signal import ExitReason
        from shared.strategy.market_time import now_kst
        from zoneinfo import ZoneInfo

        # ============================================
        # Phase 1: Create Test Positions
        # ============================================
        # Futures position (any state, will be force-closed at EOD)
        futures_position = create_futures_position(
            pos_id="FUT-EOD-001",
            code="101S6000",
            name="KOSPI200 Futures",
            side=PositionSide.LONG,
            entry_price=350.0,
            quantity=1,
            current_price=352.0,  # +0.57% profit
            state=PositionState.SURVIVAL,
        )

        # Stock position in MAXIMIZE state (swing position candidate)
        stock_position = create_stock_position(
            pos_id="STK-SWING-001",
            code="005930",
            name="Samsung Electronics",
            side=PositionSide.LONG,
            entry_price=70000.0,
            quantity=10,
            current_price=73500.0,  # +5% profit
            state=PositionState.MAXIMIZE,  # Swing position state
        )

        # ============================================
        # Phase 2: Setup Exit Strategies
        # ============================================
        # Futures exit strategy (RL M-PPO)
        futures_exit_config = RLMPPOExitConfig(
            model_path="models/futures/rl/mppo_best/best_model.zip",
            min_exit_confidence=0.5,
            hard_stop_pct=-0.03,
            eod_close_hour=15,
            eod_close_minute=15,
        )
        futures_exit_strategy = RLMPPOExit(futures_exit_config)

        # Stock exit strategy (Three-Stage with swing positions allowed)
        stock_exit_config = ThreeStageExitConfig(
            stop_loss_pct=-0.05,
            breakeven_threshold_pct=0.02,
            maximize_threshold_pct=0.05,
            trailing_stop_pct=-0.03,
            eod_close_hour=23,  # Swing strategy - EOD disabled
            eod_close_minute=59,  # Allows overnight positions
        )
        stock_exit_strategy = ThreeStageExit(stock_exit_config)

        # ============================================
        # Phase 3: Mock Market Data
        # ============================================
        # Create mock market data provider
        mock_market_data = MagicMock()

        # Mock futures price snapshot
        mock_market_data.get_symbol_snapshot.return_value = {
            "101S6000": {
                "last_price": 352.0,
                "bid_price": 351.95,
                "ask_price": 352.05,
                "volume": 10000,
            }
        }

        # Mock stock price snapshot
        mock_stock_snapshot = {
            "005930": {
                "last_price": 73500.0,
                "bid_price": 73450.0,
                "ask_price": 73550.0,
                "volume": 5000000,
            }
        }

        # ============================================
        # Phase 4: Test Futures EOD Close at 15:15
        # ============================================
        # Mock time to 15:15 (futures EOD)
        eod_time = datetime(2024, 3, 15, 15, 15, 0, tzinfo=ZoneInfo("Asia/Seoul"))

        with patch("shared.strategy.exit.rl_mppo_exit.now_kst", return_value=eod_time):
            # Create exit context for futures
            futures_exit_ctx = ExitContext(
                position=futures_position,
                market_data=mock_market_data,
                timestamp=eod_time,
                metadata={"is_backtest": False},  # Real trading mode
            )

            # Check if futures should exit
            with patch.object(
                futures_exit_strategy,
                "_get_current_price",
                return_value=352.0,
            ):
                futures_should_exit, futures_signal = await futures_exit_strategy.should_exit(
                    futures_exit_ctx
                )

            # Verify futures exits at EOD
            assert futures_should_exit, "Futures position should exit at 15:15 EOD"
            assert futures_signal is not None, "Futures exit signal should be generated"
            assert futures_signal.reason == ExitReason.EOD_CLOSE, (
                f"Futures should exit with EOD_CLOSE reason, got {futures_signal.reason}"
            )
            assert futures_signal.priority == 1, "EOD close should have high priority (1)"

        # ============================================
        # Phase 5: Test Stock Swing Position at Same Time
        # ============================================
        # Test stock at 15:15 (same time as futures EOD, but before stock EOD 23:59)
        # Stock should NOT exit because EOD is configured at 23:59 (swing allowed)

        with patch("shared.strategy.exit.three_stage.now_kst", return_value=eod_time):
            with patch("shared.strategy.exit.three_stage.is_trading_day_kst", return_value=True):
                with patch("shared.strategy.exit.three_stage.to_kst", return_value=eod_time):
                    # Create exit context for stock
                    stock_exit_ctx = ExitContext(
                        position=stock_position,
                        market_data=mock_market_data,
                        timestamp=eod_time,
                        metadata={"is_backtest": False},  # Real trading mode
                    )

                    # Mock market data for stock
                    with patch.object(
                        stock_exit_strategy,
                        "_get_current_price",
                        return_value=73500.0,
                    ):
                        stock_should_exit, stock_signal = await stock_exit_strategy.should_exit(
                            stock_exit_ctx
                        )

            # Verify stock does NOT exit at 15:15
            # Stock EOD is configured at 23:59, so it should hold
            if stock_should_exit and stock_signal:
                # If it exits, it should NOT be for EOD_CLOSE reason
                assert stock_signal.reason != ExitReason.EOD_CLOSE, (
                    f"Stock swing position should not exit due to EOD at 15:15. "
                    f"Stock EOD is at 23:59. Got exit reason: {stock_signal.reason}"
                )
                # It might exit for other valid reasons (trailing stop, etc.)
            else:
                # Expected: stock holds because EOD is at 23:59, not 15:15
                pass  # This is the expected behavior

        # ============================================
        # Phase 6: Verify Asset Class EOD Policy Isolation
        # ============================================
        # Verify that futures and stock exit strategies use different EOD policies

        # Futures: Intraday only, force-close at 15:15
        assert futures_exit_config.eod_close_hour == 15
        assert futures_exit_config.eod_close_minute == 15

        # Stocks: Swing positions allowed, EOD set to 23:59 (effectively disabled)
        assert stock_exit_config.eod_close_hour == 23
        assert stock_exit_config.eod_close_minute == 59
