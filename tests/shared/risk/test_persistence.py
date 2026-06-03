"""Integration tests for RiskManager Redis persistence.

These tests require a running Redis instance.
Run with: pytest tests/shared/risk/test_persistence.py -v

To skip these tests when Redis is unavailable:
    pytest -m "not integration"
"""

import asyncio
import json
import os
from datetime import date, datetime

import pytest

# Skip all tests in this module if Redis is not available
pytestmark = [pytest.mark.integration]

_TEST_RISK_KEY_PREFIX = "test:risk:portfolio"
_TEST_RISK_STATE_KEY = f"{_TEST_RISK_KEY_PREFIX}:state"
_LIVE_INFRA_ENV = "KIS_RUN_LIVE_INFRA_TESTS"


def live_infra_enabled():
    """Return whether live Redis/ClickHouse tests may touch infrastructure."""
    return os.getenv(_LIVE_INFRA_ENV, "").lower() in {"1", "true", "yes"}


def redis_available():
    """Check if Redis is available."""
    if not live_infra_enabled():
        return False

    try:
        import redis

        r = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/1"),
            socket_timeout=1,
        )
        r.ping()
        return True
    except Exception:
        return False


@pytest.fixture
def redis_url():
    """Get Redis URL from environment or use default."""
    return os.getenv("REDIS_URL", "redis://localhost:6379/1")


@pytest.fixture
async def redis_cleanup(redis_url):
    """Clean up Redis test data before and after tests."""
    import redis

    r = redis.Redis.from_url(redis_url, decode_responses=True)

    # Clean up before test
    r.delete(_TEST_RISK_STATE_KEY)

    yield

    # Clean up after test
    r.delete(_TEST_RISK_STATE_KEY)
    r.close()


@pytest.fixture
def basic_config():
    """Create basic risk config for testing."""
    from shared.risk.config import RedisConfig, RiskConfig

    return RiskConfig(
        daily_loss_limit_pct=5.0,
        max_total_positions=20,
        initial_capital=10_000_000,
        redis=RedisConfig(
            key_prefix=_TEST_RISK_KEY_PREFIX,
            state_ttl=86400,
        ),
    )


@pytest.fixture
def sample_positions():
    """Create sample positions for testing."""
    from shared.models.position import Position, PositionSide

    return {
        "stock": [
            Position(
                id="POS-001",
                code="005930",
                name="삼성전자",
                side=PositionSide.LONG,
                quantity=10,
                entry_price=70000,
                current_price=71000,
            ),
            Position(
                id="POS-002",
                code="000660",
                name="SK하이닉스",
                side=PositionSide.LONG,
                quantity=5,
                entry_price=120000,
                current_price=122000,
            ),
        ],
        "futures": [
            Position(
                id="POS-003",
                code="101S6000",
                name="KOSPI200 선물",
                side=PositionSide.LONG,
                quantity=1,
                entry_price=350000,
                current_price=355000,
            ),
        ],
    }


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_save_and_load_basic_state(basic_config, redis_cleanup):
    """Test saving and loading basic risk state from Redis."""
    from shared.risk.manager import RiskManager

    # Create manager and update some state
    manager = RiskManager(basic_config)
    manager._daily_pnl = 150_000  # +1.5% profit
    manager._initial_capital = 10_000_000

    # Save to Redis
    await manager.save_to_redis()

    # Create new manager and load state
    manager2 = RiskManager(basic_config)
    result = await manager2.load_from_redis()

    assert result is True
    # Note: _daily_pnl is not serialized, but state.daily_pnl is
    # After save, state should be updated


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_save_and_load_with_positions(
    basic_config, sample_positions, redis_cleanup
):
    """Test saving and loading risk state with position data."""
    from shared.risk.manager import RiskManager

    # Create manager with positions
    manager = RiskManager(basic_config)
    manager.update_positions(sample_positions)

    # Verify initial state
    assert manager.metrics.total_positions == 3
    assert manager.metrics.total_unrealized_pnl == 25000
    initial_portfolio_value = manager.metrics.portfolio_value

    # Save to Redis
    await manager.save_to_redis()

    # Create new manager and load state
    manager2 = RiskManager(basic_config)
    result = await manager2.load_from_redis()

    assert result is True
    assert manager2.metrics.total_positions == 3
    assert manager2.metrics.portfolio_value == initial_portfolio_value
    assert manager2.state.daily_pnl == 25000


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_save_blocked_state(basic_config, redis_cleanup):
    """Test saving and loading blocked trading state."""
    from shared.risk.manager import RiskManager
    from shared.risk.models import BlockReason

    # Create manager and block trading
    manager = RiskManager(basic_config)
    manager.block_trading(BlockReason.DAILY_LOSS_LIMIT)

    assert manager.state.is_blocked is True
    assert manager.state.block_reason == BlockReason.DAILY_LOSS_LIMIT

    # Save to Redis
    await manager.save_to_redis()

    # Create new manager and load state
    manager2 = RiskManager(basic_config)
    result = await manager2.load_from_redis()

    assert result is True
    assert manager2.state.is_blocked is True
    assert manager2.state.block_reason == BlockReason.DAILY_LOSS_LIMIT


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_save_drawdown_state(basic_config, redis_cleanup):
    """Test saving and loading drawdown state."""
    from shared.risk.manager import RiskManager
    from shared.risk.models import DrawdownLevel

    # Create manager and set drawdown
    manager = RiskManager(basic_config)
    manager._peak_portfolio_value = 11_000_000
    manager._current_portfolio_value = 10_000_000
    drawdown = manager.calculate_drawdown()

    # Drawdown should be ~9.09%
    assert drawdown > 9.0
    assert manager.state.drawdown_level == DrawdownLevel.CRITICAL  # > 7%

    # Save to Redis
    await manager.save_to_redis()

    # Create new manager and load state
    manager2 = RiskManager(basic_config)
    result = await manager2.load_from_redis()

    assert result is True
    assert manager2.state.drawdown_pct > 9.0
    assert manager2.state.drawdown_level == DrawdownLevel.CRITICAL


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_load_nonexistent_state(basic_config, redis_cleanup):
    """Test loading when no state exists in Redis."""
    from shared.risk.manager import RiskManager

    manager = RiskManager(basic_config)
    result = await manager.load_from_redis()

    # Should return False when no state exists
    assert result is False
    # Manager should still be in valid initial state
    assert manager.state.daily_pnl == 0.0
    assert manager.metrics.total_positions == 0


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_multiple_save_load_cycles(basic_config, sample_positions, redis_cleanup):
    """Test multiple save/load cycles preserve state correctly."""
    from shared.risk.manager import RiskManager

    # Cycle 1: Save with positions
    manager1 = RiskManager(basic_config)
    manager1.update_positions(sample_positions)
    await manager1.save_to_redis()

    # Cycle 2: Load and update
    manager2 = RiskManager(basic_config)
    await manager2.load_from_redis()
    assert manager2.metrics.total_positions == 3

    # Add more positions (simulate)
    manager2.metrics.total_positions = 5
    await manager2.save_to_redis()

    # Cycle 3: Load updated state
    manager3 = RiskManager(basic_config)
    await manager3.load_from_redis()
    assert manager3.metrics.total_positions == 5


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_concurrent_save_operations(basic_config, redis_cleanup):
    """Test concurrent save operations don't corrupt state."""
    from shared.risk.manager import RiskManager

    managers = [RiskManager(basic_config) for _ in range(5)]

    # Set different daily P&L for each
    for i, mgr in enumerate(managers):
        mgr.state.daily_pnl = (i + 1) * 10000

    # Save concurrently
    await asyncio.gather(*[mgr.save_to_redis() for mgr in managers])

    # Load and verify we got one of the valid states
    final_manager = RiskManager(basic_config)
    result = await final_manager.load_from_redis()

    assert result is True
    # Should be one of the saved values
    assert final_manager.state.daily_pnl in [10000, 20000, 30000, 40000, 50000]


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_asset_exposure_persistence(
    basic_config, sample_positions, redis_cleanup
):
    """Test per-asset exposure metrics are persisted correctly."""
    from shared.risk.manager import RiskManager

    # Create manager with positions
    manager = RiskManager(basic_config)
    manager.update_positions(sample_positions)

    # Verify asset exposure
    assert "stock" in manager.metrics.exposure_by_asset
    assert "futures" in manager.metrics.exposure_by_asset
    assert manager.metrics.exposure_by_asset["stock"].position_count == 2
    assert manager.metrics.exposure_by_asset["futures"].position_count == 1

    # Save to Redis
    await manager.save_to_redis()

    # Load and verify
    manager2 = RiskManager(basic_config)
    await manager2.load_from_redis()

    assert "stock" in manager2.metrics.exposure_by_asset
    assert "futures" in manager2.metrics.exposure_by_asset
    assert manager2.metrics.exposure_by_asset["stock"].position_count == 2
    assert manager2.metrics.exposure_by_asset["futures"].position_count == 1


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_alerts_sent_persistence(basic_config, redis_cleanup):
    """Test alerts_sent tracking is persisted correctly."""
    from shared.risk.manager import RiskManager

    # Create manager and track alerts
    manager = RiskManager(basic_config)
    manager.state.alerts_sent.add("DRAWDOWN_WARNING")
    manager.state.alerts_sent.add("POSITION_LIMIT")

    # Save to Redis
    await manager.save_to_redis()

    # Load and verify
    manager2 = RiskManager(basic_config)
    await manager2.load_from_redis()

    assert "DRAWDOWN_WARNING" in manager2.state.alerts_sent
    assert "POSITION_LIMIT" in manager2.state.alerts_sent
    assert len(manager2.state.alerts_sent) == 2


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_redis_key_format(basic_config, redis_cleanup, redis_url):
    """Test that correct Redis key format is used."""
    import redis

    from shared.risk.manager import RiskManager

    manager = RiskManager(basic_config)
    manager.state.daily_pnl = 100_000
    await manager.save_to_redis()

    # Directly check Redis
    r = redis.Redis.from_url(redis_url, decode_responses=True)
    raw_data = r.get(_TEST_RISK_STATE_KEY)

    assert raw_data is not None
    data = json.loads(raw_data)
    assert "state" in data
    assert "metrics" in data
    ttl = r.ttl(_TEST_RISK_STATE_KEY)
    assert 0 < ttl <= 86400

    r.close()


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_state_recovery_after_restart(
    basic_config, sample_positions, redis_cleanup
):
    """Test simulating process restart and state recovery."""
    from shared.risk.manager import RiskManager
    from shared.risk.models import BlockReason

    # Initial process: Create manager, set complex state
    manager1 = RiskManager(basic_config)
    manager1.update_positions(sample_positions)
    manager1.block_trading(BlockReason.MANUAL)
    manager1.state.alerts_sent.add("TEST_ALERT")

    initial_daily_pnl = manager1.state.daily_pnl
    initial_positions = manager1.metrics.total_positions

    # Save state
    await manager1.save_to_redis()

    # Simulate restart: Create new manager (as if process restarted)
    manager2 = RiskManager(basic_config)

    # Before load, state should be fresh
    assert manager2.state.daily_pnl == 0.0
    assert manager2.metrics.total_positions == 0

    # Load from Redis
    result = await manager2.load_from_redis()

    # After load, state should be recovered
    assert result is True
    assert manager2.state.daily_pnl == initial_daily_pnl
    assert manager2.metrics.total_positions == initial_positions
    assert manager2.state.is_blocked is True
    assert manager2.state.block_reason == BlockReason.MANUAL
    assert "TEST_ALERT" in manager2.state.alerts_sent


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_date_serialization(basic_config, redis_cleanup):
    """Test that stale persisted reset dates are normalized on load."""
    from shared.risk.manager import RiskManager

    # Create manager with specific dates
    manager = RiskManager(basic_config)
    test_date = date(2024, 3, 15)
    manager.state.last_reset_date = test_date

    # Save and load
    await manager.save_to_redis()

    manager2 = RiskManager(basic_config)
    await manager2.load_from_redis()

    assert manager2.state.last_reset_date == date.today()
    assert isinstance(manager2.state.last_updated, datetime)


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_error_recovery_corrupted_data(basic_config, redis_cleanup, redis_url):
    """Test that corrupted Redis data doesn't crash the manager."""
    import redis

    from shared.risk.manager import RiskManager

    # Write corrupted data to Redis
    r = redis.Redis.from_url(redis_url, decode_responses=True)
    r.set(_TEST_RISK_STATE_KEY, "invalid json data {{{")
    r.close()

    # Try to load - should handle gracefully
    manager = RiskManager(basic_config)
    result = await manager.load_from_redis()

    # Should return False and not crash
    assert result is False
    # Manager should still be in valid initial state
    assert manager.state.daily_pnl == 0.0
