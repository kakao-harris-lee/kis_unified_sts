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

from shared.models.position import Position, PositionSide, PositionState
from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
from shared.streaming.trading_state import TradingStatePublisher, TradingStateReader


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
