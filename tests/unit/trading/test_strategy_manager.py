"""Tests for services/trading/strategy_manager.py"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestStrategyManagerConfig:
    """StrategyManagerConfig tests"""

    def test_default_values(self):
        """Test default configuration values"""
        from services.trading.strategy_manager import StrategyManagerConfig

        config = StrategyManagerConfig()
        assert config.min_confidence == 0.3
        assert config.dedupe_by_symbol is True
        assert config.dedupe_scope == "direction"
        assert config.dedupe_window_seconds == 60.0
        assert config.parallel_entries is True
        assert config.parallel_exits is True

    def test_validation_passes(self):
        """Test valid configuration passes"""
        from services.trading.strategy_manager import StrategyManagerConfig

        config = StrategyManagerConfig(
            min_confidence=0.5,
            dedupe_window_seconds=120.0,
        )
        assert config.min_confidence == 0.5

    def test_validation_min_confidence_bounds(self):
        """Test min_confidence bounds validation"""
        from services.trading.strategy_manager import StrategyManagerConfig

        with pytest.raises(ValueError, match="min_confidence"):
            StrategyManagerConfig(min_confidence=-0.1)

        with pytest.raises(ValueError, match="min_confidence"):
            StrategyManagerConfig(min_confidence=1.5)

    def test_validation_dedupe_window_bounds(self):
        """Test dedupe_window_seconds bounds validation"""
        from services.trading.strategy_manager import StrategyManagerConfig

        with pytest.raises(ValueError, match="dedupe_window_seconds"):
            StrategyManagerConfig(dedupe_window_seconds=-1.0)

        with pytest.raises(ValueError, match="dedupe_window_seconds"):
            StrategyManagerConfig(dedupe_window_seconds=5000.0)

    def test_from_dict(self):
        """Test from_dict factory method"""
        from services.trading.strategy_manager import StrategyManagerConfig

        config = StrategyManagerConfig.from_dict({
            "min_confidence": 0.5,
            "dedupe_by_symbol": False,
            "dedupe_scope": "strategy",
            "parallel_entries": False,
        })
        assert config.min_confidence == 0.5
        assert config.dedupe_by_symbol is False
        assert config.dedupe_scope == "strategy"
        assert config.parallel_entries is False

    def test_from_dict_type_validation(self):
        """Test from_dict type validation"""
        from services.trading.strategy_manager import StrategyManagerConfig

        with pytest.raises(TypeError, match="min_confidence"):
            StrategyManagerConfig.from_dict({"min_confidence": "invalid"})

    def test_validation_dedupe_scope(self):
        """Test dedupe_scope validation."""
        from services.trading.strategy_manager import StrategyManagerConfig

        with pytest.raises(ValueError, match="dedupe_scope"):
            StrategyManagerConfig(dedupe_scope="invalid")


class TestStrategyManager:
    """StrategyManager tests"""

    @pytest.fixture
    def mock_strategy(self):
        """Create a mock strategy"""
        strategy = MagicMock()
        strategy.name = "test_strategy"
        strategy.required_indicators = ["rsi", "bb_lower"]
        strategy.entry = MagicMock()
        strategy.entry.name = "test_entry"
        strategy.exit = MagicMock()
        strategy.exit.name = "test_exit"
        strategy.check_entry = AsyncMock(return_value=None)
        strategy.check_exit = AsyncMock(return_value=(False, None))
        return strategy

    @pytest.fixture
    def mock_signal(self):
        """Create a mock signal"""
        signal = MagicMock()
        signal.code = "005930"
        signal.name = "Samsung"
        signal.confidence = 0.8
        signal.strategy = "test_strategy"
        signal.metadata = {"signal_direction": "long"}
        return signal

    @pytest.fixture
    def mock_position(self):
        """Create a mock position"""
        position = MagicMock()
        position.id = "pos-123"
        position.code = "005930"
        position.strategy = "test_strategy"
        position.current_price = 100
        position.entry_price = 95
        return position

    def test_init_registers_components(self):
        """Test initialization registers built-in components"""
        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ) as mock_register:
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager

                _ = StrategyManager(asset_class="stock")

                mock_register.assert_called_once()

    def test_add_strategy(self, mock_strategy):
        """Test adding strategy manually"""
        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager

                manager = StrategyManager(asset_class="stock")
                manager.add_strategy(mock_strategy)

                assert "test_strategy" in manager.strategies
                assert manager.strategies["test_strategy"] is mock_strategy

    def test_remove_strategy(self, mock_strategy):
        """Test removing strategy"""
        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager

                manager = StrategyManager(asset_class="stock")
                manager.add_strategy(mock_strategy)
                manager.remove_strategy("test_strategy")

                assert "test_strategy" not in manager.strategies

    def test_strategy_names_property(self, mock_strategy):
        """Test strategy_names property"""
        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager

                manager = StrategyManager(asset_class="stock")
                manager.add_strategy(mock_strategy)

                assert "test_strategy" in manager.strategy_names

    def test_required_indicators_property(self, mock_strategy):
        """Test required_indicators aggregates all strategies"""
        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager

                manager = StrategyManager(asset_class="stock")
                manager.add_strategy(mock_strategy)

                indicators = manager.required_indicators
                assert "rsi" in indicators
                assert "bb_lower" in indicators

    @pytest.mark.asyncio
    async def test_check_entries_empty_strategies(self):
        """Test check_entries with no strategies returns empty"""
        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager
                from shared.strategy.base import EntryContext

                manager = StrategyManager(asset_class="stock")

                context = MagicMock(spec=EntryContext)
                signals = await manager.check_entries(context)

                assert signals == []

    @pytest.mark.asyncio
    async def test_check_entries_returns_signals(self, mock_strategy, mock_signal):
        """Test check_entries returns signals from strategies"""
        mock_strategy.check_entry = AsyncMock(return_value=mock_signal)

        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager
                from shared.strategy.base import EntryContext

                manager = StrategyManager(asset_class="stock")
                manager.add_strategy(mock_strategy)

                context = MagicMock(spec=EntryContext)
                signals = await manager.check_entries(context)

                assert len(signals) == 1
                assert signals[0] is mock_signal

    @pytest.mark.asyncio
    async def test_check_entries_filters_low_confidence(
        self, mock_strategy, mock_signal
    ):
        """Test check_entries filters out low confidence signals"""
        mock_signal.confidence = 0.1  # Below threshold
        mock_strategy.check_entry = AsyncMock(return_value=mock_signal)

        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager
                from shared.strategy.base import EntryContext

                manager = StrategyManager(asset_class="stock")
                manager.add_strategy(mock_strategy)

                context = MagicMock(spec=EntryContext)
                signals = await manager.check_entries(context)

                assert len(signals) == 0

    @pytest.mark.asyncio
    async def test_check_entries_deduplicates(self, mock_strategy, mock_signal):
        """Test check_entries deduplicates signals"""
        mock_strategy.check_entry = AsyncMock(return_value=mock_signal)

        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager
                from shared.strategy.base import EntryContext

                manager = StrategyManager(asset_class="stock")
                manager.add_strategy(mock_strategy)

                context = MagicMock(spec=EntryContext)

                # First call
                signals1 = await manager.check_entries(context)
                assert len(signals1) == 1

                # Second call - should be deduped
                signals2 = await manager.check_entries(context)
                assert len(signals2) == 0

    @pytest.mark.asyncio
    async def test_check_entries_dedupes_by_strategy_scope(self, mock_strategy, mock_signal):
        """Signals from different strategies on same code should both pass."""
        signal2 = MagicMock()
        signal2.code = "005930"
        signal2.name = "Samsung"
        signal2.confidence = 0.8
        signal2.strategy = "other_strategy"
        signal2.metadata = {"signal_direction": "long"}

        strategy2 = MagicMock()
        strategy2.name = "other_strategy"
        strategy2.required_indicators = []
        strategy2.entry = MagicMock()
        strategy2.exit = MagicMock()
        strategy2.check_entry = AsyncMock(return_value=signal2)

        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager, StrategyManagerConfig
                from shared.strategy.base import EntryContext

                manager = StrategyManager(
                    asset_class="stock",
                    config=StrategyManagerConfig(dedupe_scope="strategy"),
                )
                mock_strategy.check_entry = AsyncMock(return_value=mock_signal)
                mock_signal.metadata = {"signal_direction": "long"}
                manager.add_strategy(mock_strategy)
                manager.add_strategy(strategy2)

                context = MagicMock(spec=EntryContext)
                signals = await manager.check_entries(context)

                assert len(signals) == 2

    @pytest.mark.asyncio
    async def test_check_exits_empty_positions(self, mock_strategy):
        """Test check_exits with no positions returns empty"""
        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager

                manager = StrategyManager(asset_class="stock")
                manager.add_strategy(mock_strategy)

                signals = await manager.check_exits(
                    positions=[], market_data={}, market_state=None
                )

                assert signals == []

    @pytest.mark.asyncio
    async def test_check_exits_pre_groups_by_strategy(
        self, mock_strategy, mock_position
    ):
        """Test check_exits pre-groups positions by strategy"""
        mock_exit_signal = MagicMock()
        mock_exit_signal.priority = 1
        mock_strategy.exit.scan_positions = AsyncMock(return_value=[mock_exit_signal])

        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager

                manager = StrategyManager(asset_class="stock")
                manager.add_strategy(mock_strategy)

                _ = await manager.check_exits(
                    positions=[mock_position], market_data={}, market_state=None
                )

                # Should have called scan_positions with the position
                mock_strategy.exit.scan_positions.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_exits_returns_scan_positions_results(
        self, mock_strategy, mock_position
    ):
        """Test that check_exits returns the signals from scan_positions"""
        mock_exit_signal = MagicMock()
        mock_exit_signal.priority = 1
        mock_exit_signal.position_id = "pos-123"
        mock_strategy.exit.scan_positions = AsyncMock(return_value=[mock_exit_signal])

        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager

                manager = StrategyManager(asset_class="stock")
                manager.add_strategy(mock_strategy)

                signals = await manager.check_exits(
                    positions=[mock_position], market_data={}, market_state=None
                )

                # Verify signals are returned
                assert len(signals) == 1
                assert signals[0] is mock_exit_signal

    @pytest.mark.asyncio
    async def test_check_exits_passes_correct_arguments(
        self, mock_strategy, mock_position
    ):
        """Test that check_exits passes correct arguments to scan_positions"""
        mock_strategy.exit.scan_positions = AsyncMock(return_value=[])

        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager

                manager = StrategyManager(asset_class="stock")
                manager.add_strategy(mock_strategy)

                market_data = {"005930": {"close": 100}}
                market_state = "BULL"

                await manager.check_exits(
                    positions=[mock_position],
                    market_data=market_data,
                    market_state=market_state,
                )

                # Verify correct arguments were passed
                mock_strategy.exit.scan_positions.assert_called_once()
                call_args = mock_strategy.exit.scan_positions.call_args
                assert call_args.kwargs["positions"] == [mock_position]
                assert call_args.kwargs["market_data"] == market_data
                assert call_args.kwargs["market_state"] == market_state

    def test_get_strategy_info(self, mock_strategy):
        """Test get_strategy_info returns details"""
        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager

                manager = StrategyManager(asset_class="stock")
                manager.add_strategy(mock_strategy)

                info = manager.get_strategy_info()

                assert len(info) == 1
                assert info[0]["name"] == "test_strategy"
                assert info[0]["entry"] == "test_entry"
                assert info[0]["exit"] == "test_exit"

    def test_get_stats(self, mock_strategy):
        """Test get_stats returns manager statistics"""
        with patch(
            "services.trading.strategy_manager.register_builtin_components"
        ):
            with patch(
                "services.trading.strategy_manager.StrategyFactory"
            ) as mock_factory:
                mock_factory.create_all.return_value = []

                from services.trading.strategy_manager import StrategyManager

                manager = StrategyManager(asset_class="stock")
                manager.add_strategy(mock_strategy)

                stats = manager.get_stats()

                assert stats["asset_class"] == "stock"
                assert stats["strategy_count"] == 1
                assert "test_strategy" in stats["strategies"]
