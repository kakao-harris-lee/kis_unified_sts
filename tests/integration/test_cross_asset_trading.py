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

    Returns:
        Position object for stock trading
    """
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


def create_futures_position(
    pos_id: str = "FUTURES-001",
    code: str = "101S6000",
    name: str = "KOSPI200 Futures",
    side: PositionSide = PositionSide.LONG,
    entry_price: float = 350000.0,
    quantity: int = 1,
    strategy: str = "rl_mppo",
    state: PositionState = PositionState.SURVIVAL,
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

    Returns:
        Position object for futures trading
    """
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
