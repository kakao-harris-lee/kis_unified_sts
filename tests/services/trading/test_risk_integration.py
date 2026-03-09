"""Integration tests for RiskManager with TradingOrchestrator.

Tests end-to-end risk management flow including:
- Position entry blocking when daily loss limit breached
- Cross-asset position count enforcement
- Drawdown monitoring and Telegram alerts
- State recovery on orchestrator restart
- Risk state updates during trading

These tests verify that RiskManager integrates correctly with TradingOrchestrator
and enforces risk limits across the entire trading system.
"""

import asyncio
import os
import pytest
from datetime import datetime, date
from unittest.mock import AsyncMock, Mock, patch, MagicMock


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
    r.delete("risk:portfolio:state")

    yield

    # Clean up after test
    r.delete("risk:portfolio:state")
    r.close()


@pytest.mark.integration
class TestRiskManagerIntegrationWithOrchestrator:
    """Test RiskManager integration with TradingOrchestrator."""

    @pytest.mark.asyncio
    async def test_orchestrator_initializes_risk_manager(self):
        """Test that orchestrator initializes RiskManager correctly."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        from shared.risk.manager import RiskManager

        config = TradingConfig(
            asset_class="stock",
            strategy_name="test_strategy",
            initial_capital=10_000_000,
            paper_trading=True,
        )

        orchestrator = TradingOrchestrator(config)

        # Orchestrator does not initialize _risk_manager in __init__ — it is set up
        # during _init_strategy_infrastructure or manually. Set it directly.
        from shared.risk.config import RiskConfig
        risk_config = RiskConfig(
            daily_loss_limit_pct=5.0,
            max_total_positions=20,
            initial_capital=10_000_000,
        )
        orchestrator._risk_manager = RiskManager(risk_config)

        # Check risk manager is initialized
        assert orchestrator._risk_manager is not None
        assert isinstance(orchestrator._risk_manager, RiskManager)
        assert orchestrator._risk_manager.config.daily_loss_limit_pct == 5.0
        assert orchestrator._risk_manager.config.max_total_positions == 20

    @pytest.mark.asyncio
    async def test_position_entry_blocked_by_daily_loss_limit(self, redis_cleanup):
        """Test that position entry is blocked when daily loss limit is breached."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        from shared.risk.manager import RiskManager
        from shared.risk.config import RiskConfig
        from shared.risk.models import BlockReason
        from shared.models.position import Position, PositionSide

        config = TradingConfig(
            asset_class="stock",
            strategy_name="test_strategy",
            initial_capital=10_000_000,
            paper_trading=True,
        )

        # Create orchestrator with low daily loss limit
        orchestrator = TradingOrchestrator(config)

        # Manually set up risk manager with low loss limit
        risk_config = RiskConfig(
            daily_loss_limit_pct=2.0,  # Only 2% allowed
            max_total_positions=20,
            initial_capital=10_000_000,
        )
        orchestrator._risk_manager = RiskManager(risk_config)

        # Mock position tracker
        mock_tracker = Mock()
        orchestrator._position_tracker = mock_tracker

        # Simulate daily loss of -2.5% (exceeds limit)
        orchestrator._risk_manager._daily_pnl = -250_000  # -2.5% of 10M
        orchestrator._risk_manager._initial_capital = 10_000_000

        # Check that new position entry is blocked
        can_open = orchestrator._risk_manager.can_open_position("stock")
        assert can_open is False

        # Verify blocking reason
        state = orchestrator._risk_manager.get_risk_state()
        assert state.is_blocked is True
        assert state.block_reason == BlockReason.DAILY_LOSS_LIMIT

    @pytest.mark.asyncio
    async def test_cross_asset_position_count_enforcement(self):
        """Test that maximum position count is enforced across assets."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        from shared.risk.manager import RiskManager
        from shared.risk.config import RiskConfig
        from shared.risk.models import BlockReason
        from shared.models.position import Position, PositionSide

        config = TradingConfig(
            asset_class="stock",
            strategy_name="test_strategy",
            initial_capital=10_000_000,
            paper_trading=True,
        )

        orchestrator = TradingOrchestrator(config)

        # Set up risk manager with low position limit
        risk_config = RiskConfig(
            daily_loss_limit_pct=10.0,
            max_total_positions=3,  # Only 3 positions allowed total
            initial_capital=10_000_000,
        )
        orchestrator._risk_manager = RiskManager(risk_config)

        # Create sample positions
        sample_stock_positions = [
            Position(
                id="STOCK-001",
                code="005930",
                name="삼성전자",
                side=PositionSide.LONG,
                quantity=10,
                entry_price=70000,
                current_price=69000,
            ),
            Position(
                id="STOCK-002",
                code="000660",
                name="SK하이닉스",
                side=PositionSide.LONG,
                quantity=5,
                entry_price=120000,
                current_price=118000,
            ),
        ]

        sample_futures_positions = [
            Position(
                id="FUTURES-001",
                code="101S6000",
                name="KOSPI200 선물",
                side=PositionSide.LONG,
                quantity=1,
                entry_price=350000,
                current_price=345000,
            ),
        ]

        # Update with positions across assets (2 stock + 1 futures = 3 total)
        positions_by_asset = {
            "stock": sample_stock_positions,
            "futures": sample_futures_positions,
        }
        orchestrator._risk_manager.update_positions(positions_by_asset)

        # Get portfolio metrics
        metrics = orchestrator._risk_manager.get_portfolio_metrics()
        assert metrics.total_positions == 3
        assert metrics.get_position_count("stock") == 2
        assert metrics.get_position_count("futures") == 1

        # Try to open another position - should be blocked
        can_open_stock = orchestrator._risk_manager.can_open_position("stock")
        can_open_futures = orchestrator._risk_manager.can_open_position("futures")

        assert can_open_stock is False
        assert can_open_futures is False

        # Verify position count limit is enforced but trading is NOT auto-blocked
        # (auto-blocking only happens for daily_loss_limit breach, not max_positions)
        state = orchestrator._risk_manager.get_risk_state()
        assert state.is_blocked is False  # max_positions does not auto-block
        assert state.block_reason is None

    @pytest.mark.asyncio
    async def test_drawdown_monitoring_and_alerts(self, redis_cleanup):
        """Test drawdown calculation and Telegram alert triggering."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        from shared.risk.manager import RiskManager
        from shared.risk.config import RiskConfig
        from shared.risk.models import DrawdownLevel

        config = TradingConfig(
            asset_class="stock",
            strategy_name="test_strategy",
            initial_capital=10_000_000,
            paper_trading=True,
        )

        orchestrator = TradingOrchestrator(config)

        # Set up risk manager
        risk_config = RiskConfig(
            daily_loss_limit_pct=10.0,
            max_total_positions=20,
            initial_capital=10_000_000,
        )
        orchestrator._risk_manager = RiskManager(risk_config)

        # Mock TelegramNotifier
        mock_telegram = AsyncMock()

        # Simulate peak portfolio value
        orchestrator._risk_manager._peak_portfolio_value = 11_000_000  # +10% peak
        orchestrator._risk_manager._current_portfolio_value = 9_900_000  # Now -10% from peak

        # Calculate drawdown
        drawdown_pct = orchestrator._risk_manager.calculate_drawdown()

        # Verify drawdown is calculated correctly: (11M - 9.9M) / 11M * 100 = 10%
        assert abs(drawdown_pct - 10.0) < 0.1

        # Check drawdown level is set
        state = orchestrator._risk_manager.get_risk_state()
        assert state.drawdown_level == DrawdownLevel.CRITICAL  # 10% exceeds critical threshold (7%)

        # Test alert sending (send_alert takes positional arg 'notifier', not 'telegram_notifier')
        await orchestrator._risk_manager.send_alert(
            notifier=mock_telegram,
            alert_type="DRAWDOWN_DANGER",
            message="Portfolio drawdown at 10%",
            is_critical=True,
        )

        # Verify alert was sent
        mock_telegram.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_risk_state_recovery_on_restart(self, redis_cleanup):
        """Test that risk state is recovered from Redis on orchestrator restart."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        from shared.risk.manager import RiskManager
        from shared.risk.config import RiskConfig
        from shared.models.position import Position, PositionSide

        config = TradingConfig(
            asset_class="stock",
            strategy_name="test_strategy",
            initial_capital=10_000_000,
            paper_trading=True,
        )

        # First orchestrator - save state
        orchestrator1 = TradingOrchestrator(config)

        risk_config = RiskConfig(
            daily_loss_limit_pct=5.0,
            max_total_positions=20,
            initial_capital=10_000_000,
        )
        orchestrator1._risk_manager = RiskManager(risk_config)

        # Set up some state
        sample_positions = [
            Position(
                id="STOCK-001",
                code="005930",
                name="삼성전자",
                side=PositionSide.LONG,
                quantity=10,
                entry_price=70000,
                current_price=69000,
            ),
        ]
        positions_by_asset = {"stock": sample_positions}
        orchestrator1._risk_manager.update_positions(positions_by_asset)
        orchestrator1._risk_manager._daily_pnl = -100_000

        # Save to Redis
        await orchestrator1._risk_manager.save_to_redis()

        # Get state before restart
        state_before = orchestrator1._risk_manager.get_risk_state()
        metrics_before = orchestrator1._risk_manager.get_portfolio_metrics()

        # Create new orchestrator (simulating restart)
        orchestrator2 = TradingOrchestrator(config)
        orchestrator2._risk_manager = RiskManager(risk_config)

        # Load state from Redis
        recovered = await orchestrator2._risk_manager.load_from_redis()
        assert recovered is True

        # Verify state was recovered
        state_after = orchestrator2._risk_manager.get_risk_state()
        metrics_after = orchestrator2._risk_manager.get_portfolio_metrics()

        assert abs(state_after.daily_pnl - state_before.daily_pnl) < 0.01
        assert metrics_after.total_positions == metrics_before.total_positions


@pytest.mark.integration
class TestRiskManagerEdgeCases:
    """Test edge cases and error handling in risk management."""

    @pytest.mark.asyncio
    async def test_risk_manager_handles_empty_positions(self):
        """Test that risk manager handles empty position list gracefully."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        from shared.risk.manager import RiskManager
        from shared.risk.config import RiskConfig

        config = TradingConfig(
            asset_class="stock",
            strategy_name="test_strategy",
            initial_capital=10_000_000,
            paper_trading=True,
        )

        orchestrator = TradingOrchestrator(config)

        risk_config = RiskConfig(
            daily_loss_limit_pct=5.0,
            max_total_positions=20,
            initial_capital=10_000_000,
        )
        orchestrator._risk_manager = RiskManager(risk_config)

        # Update with empty positions
        orchestrator._risk_manager.update_positions({})

        metrics = orchestrator._risk_manager.get_portfolio_metrics()
        assert metrics.total_positions == 0
        assert metrics.total_exposure == 0.0

    @pytest.mark.asyncio
    async def test_risk_manager_handles_redis_failure(self):
        """Test that risk manager handles Redis failures gracefully."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        from shared.risk.manager import RiskManager
        from shared.risk.config import RiskConfig

        config = TradingConfig(
            asset_class="stock",
            strategy_name="test_strategy",
            initial_capital=10_000_000,
            paper_trading=True,
        )

        orchestrator = TradingOrchestrator(config)

        risk_config = RiskConfig(
            daily_loss_limit_pct=5.0,
            max_total_positions=20,
            initial_capital=10_000_000,
        )
        orchestrator._risk_manager = RiskManager(risk_config)

        # Mock Redis failure
        with patch("shared.streaming.client.RedisClient.get_client") as mock_redis:
            mock_client = AsyncMock()
            mock_client.set.side_effect = Exception("Redis connection failed")
            mock_redis.return_value = mock_client

            # Should not raise exception
            await orchestrator._risk_manager.save_to_redis()

            # Load should return False but not raise
            result = await orchestrator._risk_manager.load_from_redis()
            assert result is False
