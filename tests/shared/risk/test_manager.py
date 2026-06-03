"""Unit tests for RiskManager core logic

Tests portfolio-level risk management including:
- Position tracking and limits
- Daily loss limits
- Drawdown monitoring
- Blocking/unblocking
- State persistence
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.models.position import Position, PositionSide
from shared.risk.config import RedisConfig, RiskConfig
from shared.risk.manager import RiskManager
from shared.risk.models import (
    BlockReason,
    DrawdownLevel,
    PortfolioMetrics,
    RiskState,
)


@pytest.fixture
def basic_config():
    """Create basic risk config for testing"""
    return RiskConfig(
        daily_loss_limit_pct=5.0,
        max_total_positions=20,
        initial_capital=10_000_000,
    )


@pytest.fixture
def manager(basic_config):
    """Create RiskManager instance for testing"""
    return RiskManager(basic_config)


@pytest.fixture
def sample_positions():
    """Create sample positions for testing"""
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


class TestRiskManagerInitialization:
    """Test RiskManager initialization"""

    def test_initialization(self, basic_config):
        """Test manager initializes with correct defaults"""
        manager = RiskManager(basic_config)

        assert manager.config == basic_config
        assert isinstance(manager.state, RiskState)
        assert isinstance(manager.metrics, PortfolioMetrics)
        assert manager.state.peak_portfolio_value == basic_config.initial_capital
        assert manager.state.current_portfolio_value == basic_config.initial_capital

    def test_initialization_with_validation_error(self):
        """Test initialization fails with invalid config"""
        with pytest.raises(ValueError):
            RiskConfig(daily_loss_limit_pct=100.0)  # Exceeds max


class TestCanOpenPosition:
    """Test can_open_position() logic"""

    def test_can_open_position_when_clear(self, manager):
        """Test position can be opened when all limits are clear"""
        assert manager.can_open_position("stock") is True
        assert manager.can_open_position("futures") is True

    def test_cannot_open_when_blocked(self, manager):
        """Test position blocked when trading is manually blocked"""
        manager.block_trading(BlockReason.MANUAL)
        assert manager.can_open_position("stock") is False
        assert manager.state.is_blocked is True

    def test_cannot_open_when_daily_loss_limit_breached(self, manager):
        """Test position blocked when daily loss limit exceeded"""
        # Set daily P&L to breach limit
        manager._daily_pnl = -600_000  # -6% of 10M
        manager._initial_capital = 10_000_000

        result = manager.can_open_position("stock")

        assert result is False
        assert manager.state.is_blocked is True
        assert manager.state.block_reason == BlockReason.DAILY_LOSS_LIMIT

    def test_cannot_open_when_max_total_positions_reached(
        self, manager, sample_positions
    ):
        """Test position blocked when max total positions reached"""
        # Set max to current count
        manager.config.max_total_positions = 3
        manager.update_positions(sample_positions)

        assert manager.can_open_position("stock") is False

    def test_cannot_open_when_asset_limit_reached(self, manager, sample_positions):
        """Test position blocked when per-asset limit reached"""
        # Set stock limit to current count
        manager.config.asset_limits["stock"].max_positions = 2
        manager.update_positions(sample_positions)

        assert manager.can_open_position("stock") is False
        assert manager.can_open_position("futures") is True  # Futures still OK

    def test_cannot_open_when_critical_drawdown(self, manager):
        """Test position blocked when critical drawdown reached"""
        manager.state.drawdown_level = DrawdownLevel.CRITICAL

        assert manager.can_open_position("stock") is False

    def test_can_open_with_warning_drawdown(self, manager):
        """Test position allowed with warning level drawdown"""
        manager.state.drawdown_level = DrawdownLevel.WARNING

        assert manager.can_open_position("stock") is True

    def test_asset_limits_not_configured(self, manager):
        """Test fail-open behavior when asset limits not configured"""
        # Remove asset limits
        manager.config.asset_limits.clear()

        # Should still allow position (fail-open)
        assert manager.can_open_position("crypto") is True


class TestUpdatePositions:
    """Test update_positions() position tracking"""

    def test_update_positions_from_empty(self, manager, sample_positions):
        """Test updating positions from empty state"""
        manager.update_positions(sample_positions)

        assert manager.metrics.total_positions == 3
        assert manager.metrics.exposure_by_asset["stock"].position_count == 2
        assert manager.metrics.exposure_by_asset["futures"].position_count == 1

    def test_update_positions_calculates_unrealized_pnl(
        self, manager, sample_positions
    ):
        """Test unrealized P&L calculation"""
        manager.update_positions(sample_positions)

        # Stock P&L: (71000-70000)*10 + (122000-120000)*5 = 10000 + 10000 = 20000
        # Futures P&L: (355000-350000)*1 = 5000
        # Total: 25000
        assert manager.metrics.total_unrealized_pnl == 25000

    def test_update_positions_calculates_portfolio_value(
        self, manager, sample_positions
    ):
        """Test portfolio value calculation"""
        manager.update_positions(sample_positions)

        expected_value = 10_000_000 + 25000  # Initial + unrealized P&L
        assert manager.metrics.portfolio_value == expected_value

    def test_update_positions_updates_state(self, manager, sample_positions):
        """Test state is updated with position changes"""
        manager.update_positions(sample_positions)

        assert manager.state.daily_pnl == 25000  # Unrealized P&L
        assert manager.state.current_portfolio_value == 10_025_000

    def test_update_positions_empty_dict(self, manager):
        """Test updating with empty position dict"""
        manager.update_positions({})

        assert manager.metrics.total_positions == 0
        assert manager.metrics.total_unrealized_pnl == 0.0

    def test_realized_pnl_persists_after_positions_close(self, manager):
        """Closed losses remain in risk P&L after open positions disappear."""
        manager.record_realized_pnl(-600_000)
        manager.update_positions({})

        assert manager.metrics.total_positions == 0
        assert manager.metrics.total_realized_pnl == -600_000
        assert manager.metrics.total_unrealized_pnl == 0.0
        assert manager.metrics.portfolio_value == 9_400_000
        assert manager.state.daily_realized_pnl == -600_000
        assert manager.state.daily_pnl == -600_000
        assert manager.state.daily_pnl_pct == -6.0

        assert manager.can_open_position("stock") is False
        assert manager.state.block_reason == BlockReason.DAILY_LOSS_LIMIT

    def test_realized_pnl_updates_drawdown_without_open_positions(self):
        """Realized losses alone can trip the drawdown entry gate."""
        config = RiskConfig(
            daily_loss_limit_pct=20.0,
            max_total_positions=20,
            initial_capital=10_000_000,
        )
        manager = RiskManager(config)

        manager.record_realized_pnl(-700_000)
        manager.update_positions({})

        assert manager.state.drawdown_pct == pytest.approx(7.0)
        assert manager.state.drawdown_level == DrawdownLevel.CRITICAL
        assert manager.can_open_position("stock") is False


class TestDailyLossLimit:
    """Test daily loss limit checking"""

    def test_check_daily_loss_limit_within_limit(self, manager):
        """Test daily loss within limit"""
        manager._daily_pnl = -400_000  # -4%
        manager._initial_capital = 10_000_000

        assert manager.check_daily_loss_limit() is True

    def test_check_daily_loss_limit_at_limit(self, manager):
        """Test daily loss exactly at limit"""
        manager._daily_pnl = -500_000  # -5%
        manager._initial_capital = 10_000_000

        assert manager.check_daily_loss_limit() is True

    def test_check_daily_loss_limit_breached(self, manager):
        """Test daily loss exceeds limit"""
        manager._daily_pnl = -600_000  # -6%
        manager._initial_capital = 10_000_000

        assert manager.check_daily_loss_limit() is False

    def test_check_daily_loss_limit_positive_pnl(self, manager):
        """Test positive daily P&L"""
        manager._daily_pnl = 500_000  # +5%
        manager._initial_capital = 10_000_000

        assert manager.check_daily_loss_limit() is True

    def test_check_daily_loss_limit_zero_capital(self, manager):
        """Test with zero initial capital (edge case)"""
        manager._daily_pnl = -100_000
        manager._initial_capital = 0

        # Should return True (safe default with 0 capital)
        assert manager.check_daily_loss_limit() is True


class TestDrawdownCalculation:
    """Test drawdown calculation and monitoring"""

    def test_calculate_drawdown_from_peak(self, manager):
        """Test drawdown calculation from peak"""
        manager._peak_portfolio_value = 11_000_000
        manager._current_portfolio_value = 10_000_000

        drawdown = manager.calculate_drawdown()

        # (11M - 10M) / 11M * 100 = 9.09%
        assert pytest.approx(drawdown, rel=0.01) == 9.09

    def test_calculate_drawdown_at_peak(self, manager):
        """Test drawdown when at peak"""
        manager._peak_portfolio_value = 10_000_000
        manager._current_portfolio_value = 10_000_000

        drawdown = manager.calculate_drawdown()

        assert drawdown == 0.0

    def test_calculate_drawdown_above_peak(self, manager):
        """Test drawdown when above peak (new peak)"""
        manager._peak_portfolio_value = 10_000_000
        manager._current_portfolio_value = 11_000_000

        drawdown = manager.calculate_drawdown()

        # Should be 0 since we're at new peak
        assert drawdown == 0.0

    def test_calculate_drawdown_updates_state(self, manager):
        """Test drawdown calculation updates state"""
        manager._peak_portfolio_value = 10_000_000
        manager._current_portfolio_value = 9_500_000

        manager.calculate_drawdown()

        assert manager.state.drawdown_pct == 5.0

    def test_calculate_drawdown_updates_level_warning(self, manager):
        """Test drawdown level updated to WARNING"""
        manager._peak_portfolio_value = 10_000_000
        manager._current_portfolio_value = 9_700_000  # 3% drawdown

        manager.calculate_drawdown()

        assert manager.state.drawdown_level == DrawdownLevel.WARNING

    def test_calculate_drawdown_updates_level_danger(self, manager):
        """Test drawdown level updated to DANGER"""
        manager._peak_portfolio_value = 10_000_000
        manager._current_portfolio_value = 9_500_000  # 5% drawdown

        manager.calculate_drawdown()

        assert manager.state.drawdown_level == DrawdownLevel.DANGER

    def test_calculate_drawdown_updates_level_critical(self, manager):
        """Test drawdown level updated to CRITICAL"""
        manager._peak_portfolio_value = 10_000_000
        manager._current_portfolio_value = 9_300_000  # 7% drawdown

        manager.calculate_drawdown()

        assert manager.state.drawdown_level == DrawdownLevel.CRITICAL

    def test_calculate_drawdown_zero_peak(self, manager):
        """Test drawdown with zero peak (edge case)"""
        manager._peak_portfolio_value = 0
        manager._current_portfolio_value = 0

        drawdown = manager.calculate_drawdown()

        assert drawdown == 0.0


class TestBlockingUnblocking:
    """Test manual blocking/unblocking"""

    def test_block_trading(self, manager):
        """Test manual blocking"""
        manager.block_trading(BlockReason.MANUAL)

        assert manager.state.is_blocked is True
        assert manager.state.block_reason == BlockReason.MANUAL

    def test_unblock_trading(self, manager):
        """Test unblocking"""
        manager.block_trading(BlockReason.MANUAL)
        manager.unblock_trading()

        assert manager.state.is_blocked is False
        assert manager.state.block_reason is None

    def test_block_with_different_reasons(self, manager):
        """Test blocking with various reasons"""
        reasons = [
            BlockReason.DAILY_LOSS_LIMIT,
            BlockReason.MAX_POSITIONS,
            BlockReason.DRAWDOWN_CRITICAL,
            BlockReason.MANUAL,
        ]

        for reason in reasons:
            manager.block_trading(reason)
            assert manager.state.block_reason == reason
            manager.unblock_trading()


class TestDailyReset:
    """Test daily reset functionality"""

    def test_reset_daily(self, manager):
        """Test daily reset clears daily metrics"""
        # Set some state
        manager.state.daily_pnl = 100_000
        manager.state.daily_realized_pnl = 75_000
        manager.state.daily_pnl_pct = 1.0
        manager.state.alerts_sent.add("test_alert")
        manager.state.peak_portfolio_value = 10_500_000
        manager.state.current_portfolio_value = 10_000_000
        manager.state.drawdown_pct = 4.76
        manager.metrics.portfolio_value = 9_900_000

        manager.reset_daily()

        assert manager.state.daily_pnl == 0.0
        assert manager.state.daily_realized_pnl == 0.0
        assert manager.state.daily_pnl_pct == 0.0
        assert len(manager.state.alerts_sent) == 0
        assert manager.state.peak_portfolio_value == 9_900_000
        assert manager.state.current_portfolio_value == 9_900_000
        assert manager.state.drawdown_pct == 0.0
        assert manager.state.drawdown_level == DrawdownLevel.SAFE

    def test_reset_daily_auto_unblock(self, manager):
        """Test auto-unblock on daily reset"""
        manager.config.monitoring.auto_unblock_on_reset = True
        manager.block_trading(BlockReason.DAILY_LOSS_LIMIT)

        manager.reset_daily()

        assert manager.state.is_blocked is False

    def test_reset_daily_no_auto_unblock_manual_block(self, manager):
        """Test manual block not auto-unblocked"""
        manager.config.monitoring.auto_unblock_on_reset = True
        manager.block_trading(BlockReason.MANUAL)

        manager.reset_daily()

        # Manual block should NOT be auto-unblocked
        assert manager.state.is_blocked is True

    def test_reset_daily_disabled_auto_unblock(self, manager):
        """Test no auto-unblock when disabled"""
        manager.config.monitoring.auto_unblock_on_reset = False
        manager.block_trading(BlockReason.DAILY_LOSS_LIMIT)

        manager.reset_daily()

        assert manager.state.is_blocked is True

    def test_check_and_reset_daily_on_date_change(self, manager):
        """Test automatic daily reset on date transition"""
        from datetime import timedelta

        # Set last reset to yesterday
        manager._last_reset_date = date.today() - timedelta(days=1)
        manager._daily_pnl = 100_000

        manager._check_and_reset_daily()

        assert manager._last_reset_date == date.today()
        assert manager._daily_pnl == 0.0

    def test_check_and_reset_daily_same_day(self, manager):
        """Test no reset when still same day"""
        manager._last_reset_date = date.today()
        manager._daily_pnl = 100_000

        manager._check_and_reset_daily()

        # Should not reset
        assert manager._daily_pnl == 100_000


class TestSerialization:
    """Test state serialization/deserialization"""

    def test_to_dict(self, manager, sample_positions):
        """Test serialization to dict"""
        manager.update_positions(sample_positions)

        data = manager.to_dict()

        assert "state" in data
        assert "metrics" in data
        assert data["state"]["daily_pnl"] == 25000

    def test_from_dict(self, basic_config, sample_positions):
        """Test deserialization from dict"""
        # Create manager and set state
        manager1 = RiskManager(basic_config)
        manager1.update_positions(sample_positions)
        manager1.block_trading(BlockReason.MANUAL)

        # Serialize
        data = manager1.to_dict()

        # Deserialize to new manager
        manager2 = RiskManager.from_dict(basic_config, data)

        assert manager2.state.is_blocked is True
        assert manager2.state.block_reason == BlockReason.MANUAL
        assert manager2.metrics.total_positions == 3

    def test_serialize_state_internal(self, manager, sample_positions):
        """Test internal _serialize_state method"""
        manager.update_positions(sample_positions)

        data = manager._serialize_state()

        assert "state" in data
        assert "metrics" in data
        assert isinstance(data["state"], dict)
        assert isinstance(data["metrics"], dict)

    def test_deserialize_state_internal(self, manager):
        """Test internal _deserialize_state method"""
        data = {
            "state": {
                "daily_pnl": 50000,
                "is_blocked": True,
                "block_reason": "manual",
                "drawdown_level": "warning",
                "last_reset_date": date.today().isoformat(),
                "last_updated": datetime.now().isoformat(),
            },
            "metrics": {
                "total_positions": 5,
                "total_exposure": 1000000,
                "portfolio_value": 10500000,
            },
        }

        manager._deserialize_state(data)

        assert manager.state.daily_pnl == 50000
        assert manager.state.is_blocked is True
        assert manager.metrics.total_positions == 5
        assert manager._last_reset_date == date.today()


class TestRedisPersistence:
    """Test Redis save/load functionality"""

    @pytest.mark.asyncio
    async def test_save_to_redis(self, manager, sample_positions):
        """Test saving state to Redis"""
        manager.update_positions(sample_positions)

        # Mock Redis client
        with patch("shared.streaming.client.RedisClient") as mock_redis_class:
            mock_client = MagicMock()
            mock_redis_class.get_client.return_value = mock_client

            await manager.save_to_redis()

            # Verify Redis set was called
            mock_client.set.assert_called_once()
            call_args = mock_client.set.call_args
            key = call_args[0][0]
            assert key == "risk:portfolio:state"
            assert call_args[1]["ex"] == 86400

    @pytest.mark.asyncio
    async def test_save_to_redis_uses_configured_key_prefix_and_ttl(self):
        """Test saving state uses configured Redis namespace and TTL"""
        manager = RiskManager(
            RiskConfig(
                redis=RedisConfig(
                    key_prefix="test:risk:portfolio",
                    state_ttl=123,
                )
            )
        )

        with patch("shared.streaming.client.RedisClient") as mock_redis_class:
            mock_client = MagicMock()
            mock_redis_class.get_client.return_value = mock_client

            await manager.save_to_redis()

            call_args = mock_client.set.call_args
            assert call_args[0][0] == "test:risk:portfolio:state"
            assert call_args[1]["ex"] == 123

    @pytest.mark.asyncio
    async def test_save_to_redis_error_handling(self, manager):
        """Test save error handling doesn't raise"""
        with patch("shared.streaming.client.RedisClient") as mock_redis_class:
            mock_redis_class.get_client.side_effect = Exception("Redis error")

            # Should not raise
            await manager.save_to_redis()

    @pytest.mark.asyncio
    async def test_load_from_redis(self, manager):
        """Test loading state from Redis"""
        import json

        state_data = {
            "state": {
                "daily_pnl": 75000,
                "is_blocked": False,
                "drawdown_level": "safe",
                "last_reset_date": date.today().isoformat(),
                "last_updated": datetime.now().isoformat(),
            },
            "metrics": {
                "total_positions": 2,
                "portfolio_value": 10075000,
            },
        }

        with patch("shared.streaming.client.RedisClient") as mock_redis_class:
            mock_client = MagicMock()
            mock_client.get.return_value = json.dumps(state_data)
            mock_redis_class.get_client.return_value = mock_client

            result = await manager.load_from_redis()

            assert result is True
            assert manager.state.daily_pnl == 75000
            assert manager.metrics.total_positions == 2

    @pytest.mark.asyncio
    async def test_load_from_redis_uses_configured_key_prefix(self):
        """Test loading state uses configured Redis namespace"""
        import json

        manager = RiskManager(
            RiskConfig(redis=RedisConfig(key_prefix="test:risk:portfolio"))
        )
        state_data = {
            "state": {
                "daily_pnl": 75000,
                "is_blocked": False,
                "drawdown_level": "safe",
                "last_reset_date": date.today().isoformat(),
                "last_updated": datetime.now().isoformat(),
            },
            "metrics": {
                "total_positions": 2,
                "portfolio_value": 10075000,
            },
        }

        with patch("shared.streaming.client.RedisClient") as mock_redis_class:
            mock_client = MagicMock()
            mock_client.get.return_value = json.dumps(state_data)
            mock_redis_class.get_client.return_value = mock_client

            result = await manager.load_from_redis()

            assert result is True
            mock_client.get.assert_called_once_with("test:risk:portfolio:state")

    @pytest.mark.asyncio
    async def test_load_from_redis_no_data(self, manager):
        """Test load when no data exists in Redis"""
        with patch("shared.streaming.client.RedisClient") as mock_redis_class:
            mock_client = MagicMock()
            mock_client.get.return_value = None
            mock_redis_class.get_client.return_value = mock_client

            result = await manager.load_from_redis()

            assert result is False

    @pytest.mark.asyncio
    async def test_load_from_redis_error_handling(self, manager):
        """Test load error handling doesn't raise"""
        with patch("shared.streaming.client.RedisClient") as mock_redis_class:
            mock_redis_class.get_client.side_effect = Exception("Redis error")

            result = await manager.load_from_redis()

            assert result is False


class TestTelegramAlerts:
    """Test Telegram alert functionality"""

    @pytest.mark.asyncio
    async def test_send_alert_success(self, manager):
        """Test sending alert via Telegram"""
        mock_notifier = AsyncMock()

        await manager.send_alert(
            mock_notifier, "DAILY_LOSS_LIMIT", "Test alert message", is_critical=True
        )

        mock_notifier.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_no_notifier(self, manager):
        """Test alert with no notifier configured"""
        # Should not raise
        await manager.send_alert(None, "TEST_ALERT", "Test message")

    @pytest.mark.asyncio
    async def test_send_alert_error_handling(self, manager):
        """Test alert error handling"""
        mock_notifier = AsyncMock()
        mock_notifier.send_message.side_effect = Exception("Telegram error")

        # Should not raise
        await manager.send_alert(mock_notifier, "TEST_ALERT", "Test message")


class TestGetters:
    """Test getter methods"""

    def test_get_portfolio_metrics(self, manager, sample_positions):
        """Test getting portfolio metrics"""
        manager.update_positions(sample_positions)

        metrics = manager.get_portfolio_metrics()

        assert isinstance(metrics, PortfolioMetrics)
        assert metrics.total_positions == 3

    def test_get_risk_state(self, manager):
        """Test getting risk state"""
        manager.block_trading(BlockReason.MANUAL)

        state = manager.get_risk_state()

        assert isinstance(state, RiskState)
        assert state.is_blocked is True


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_positions_with_zero_quantity(self, manager):
        """Test handling positions with zero quantity"""
        positions = {
            "stock": [
                Position(
                    id="POS-001",
                    code="005930",
                    name="삼성전자",
                    side=PositionSide.LONG,
                    quantity=0,  # Zero quantity
                    entry_price=70000,
                    current_price=71000,
                ),
            ],
        }

        manager.update_positions(positions)

        # Should handle gracefully
        assert manager.metrics.total_positions == 1
        assert manager.metrics.total_unrealized_pnl == 0.0

    def test_positions_with_short_side(self, manager):
        """Test handling short positions"""
        positions = {
            "futures": [
                Position(
                    id="POS-001",
                    code="101S6000",
                    name="KOSPI200 선물",
                    side=PositionSide.SHORT,
                    quantity=1,
                    entry_price=350000,
                    current_price=345000,  # Profitable short
                ),
            ],
        }

        manager.update_positions(positions)

        # Short profit: (350000 - 345000) * 1 = 5000
        assert manager.metrics.total_unrealized_pnl == 5000

    def test_very_large_position_count(self, manager):
        """Test with many positions"""
        positions = {
            "stock": [
                Position(
                    id=f"POS-{i:03d}",
                    code=f"{i:06d}",
                    name=f"Stock {i}",
                    side=PositionSide.LONG,
                    quantity=1,
                    entry_price=10000,
                    current_price=10100,
                )
                for i in range(50)
            ],
        }

        manager.update_positions(positions)

        assert manager.metrics.total_positions == 50

    def test_negative_unrealized_pnl(self, manager):
        """Test with losing positions"""
        positions = {
            "stock": [
                Position(
                    id="POS-001",
                    code="005930",
                    name="삼성전자",
                    side=PositionSide.LONG,
                    quantity=10,
                    entry_price=70000,
                    current_price=65000,  # Loss
                ),
            ],
        }

        manager.update_positions(positions)

        # Loss: (65000 - 70000) * 10 = -50000
        assert manager.metrics.total_unrealized_pnl == -50000
        assert manager.state.daily_pnl == -50000
