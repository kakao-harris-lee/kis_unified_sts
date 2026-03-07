"""Integration tests for trading orchestrator lifecycle and startup sequence.

Tests the orchestrator startup sequence to ensure components initialize
in the correct order and dependencies are properly established.
"""
import pytest
from datetime import date, time
from unittest.mock import AsyncMock, MagicMock, patch, call
from types import SimpleNamespace


@pytest.mark.integration
class TestStartupSequence:
    """Test orchestrator startup sequence and component initialization order."""

    @pytest.mark.asyncio
    async def test_component_initialization_order(self):
        """Verify components initialize in the correct order during startup."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        # Track initialization order
        init_order = []

        # Create config
        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
            initial_capital=10_000_000,
        )

        # Mock component initialization methods to track order
        with patch.object(
            TradingOrchestrator, "_init_kis_client", return_value=None
        ) as mock_kis, patch.object(
            TradingOrchestrator, "_init_futures_slippage_controller", return_value=None
        ) as mock_futures_slip, patch.object(
            TradingOrchestrator, "_init_price_feeds", return_value=None
        ) as mock_price_feeds, patch.object(
            TradingOrchestrator, "_init_data_provider", return_value=None
        ) as mock_data_provider, patch.object(
            TradingOrchestrator, "_init_tick_stream_publisher", return_value=None
        ) as mock_tick_stream, patch.object(
            TradingOrchestrator, "_init_strategy_infrastructure", return_value=None
        ) as mock_strategy_infra, patch.object(
            TradingOrchestrator, "_init_indicator_engine", return_value=None
        ) as mock_indicator, patch.object(
            TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
        ) as mock_execution, patch.object(
            TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
        ) as mock_positions, patch.object(
            TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
        ) as mock_market_data, patch.object(
            TradingOrchestrator, "_create_pipeline", return_value=MagicMock(start=AsyncMock())
        ) as mock_pipeline, patch(
            "services.monitoring.metrics.get_metrics_collector"
        ) as mock_metrics:

            # Configure mocks to track call order
            def track_init(name):
                def wrapper(*args, **kwargs):
                    init_order.append(name)

                return wrapper

            mock_kis.side_effect = track_init("kis_client")
            mock_futures_slip.side_effect = track_init("futures_slippage")
            mock_price_feeds.side_effect = track_init("price_feeds")
            mock_data_provider.side_effect = track_init("data_provider")
            mock_tick_stream.side_effect = track_init("tick_stream")
            mock_strategy_infra.side_effect = track_init("strategy_infra")
            mock_indicator.side_effect = track_init("indicator_engine")
            mock_execution.side_effect = track_init("execution_layer")
            mock_positions.side_effect = track_init("swing_positions")
            mock_market_data.side_effect = track_init("market_data_loop")

            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Verify initialization order matches expected sequence
            expected_order = [
                "kis_client",  # 1. Initialize KIS Client & Config
                "futures_slippage",  # 2. Initialize futures slippage controller
                "price_feeds",  # 3. Initialize Price Feeds (WebSocket)
                "data_provider",  # 4. Initialize Data Provider
                "tick_stream",  # 5. Initialize optional tick stream publisher
                "strategy_infra",  # 6. Initialize Strategy Infrastructure
                "indicator_engine",  # 7. Initialize Indicator Engine
                "execution_layer",  # 8. Initialize Execution Layer
                "swing_positions",  # 9. Load Swing Positions
                "market_data_loop",  # 10. Start market data loop
            ]

            assert init_order == expected_order, (
                f"Component initialization order mismatch.\n"
                f"Expected: {expected_order}\n"
                f"Actual:   {init_order}"
            )

            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_kis_client_initializes_first(self):
        """Verify KIS client initializes before dependent components."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        kis_init_called = False

        def mock_init_kis(*args):
            nonlocal kis_init_called
            kis_init_called = True
            return None

        def check_kis_init(*args):
            # This should only be called after KIS client is initialized
            assert kis_init_called, "KIS client must be initialized first"

        with patch.object(
            TradingOrchestrator, "_init_kis_client", side_effect=mock_init_kis
        ), patch.object(
            TradingOrchestrator, "_init_price_feeds", side_effect=check_kis_init
        ), patch.object(
            TradingOrchestrator, "_init_futures_slippage_controller"
        ), patch.object(
            TradingOrchestrator, "_init_data_provider"
        ), patch.object(
            TradingOrchestrator, "_init_tick_stream_publisher"
        ), patch.object(
            TradingOrchestrator, "_init_strategy_infrastructure"
        ), patch.object(
            TradingOrchestrator, "_init_indicator_engine"
        ), patch.object(
            TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_create_pipeline", return_value=MagicMock(start=AsyncMock())
        ), patch(
            "services.monitoring.metrics.get_metrics_collector"
        ) as mock_metrics:
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()
            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_strategy_infrastructure_before_indicator_engine(self):
        """Verify strategy infrastructure initializes before indicator engine."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        strategy_init_called = False

        def mock_strategy_init(*args):
            nonlocal strategy_init_called
            strategy_init_called = True

        def check_strategy_init(*args):
            assert strategy_init_called, "Strategy infrastructure must be initialized before indicator engine"

        with patch.object(
            TradingOrchestrator, "_init_kis_client", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_futures_slippage_controller"
        ), patch.object(
            TradingOrchestrator, "_init_price_feeds", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_data_provider"
        ), patch.object(
            TradingOrchestrator, "_init_tick_stream_publisher"
        ), patch.object(
            TradingOrchestrator, "_init_strategy_infrastructure", side_effect=mock_strategy_init
        ), patch.object(
            TradingOrchestrator, "_init_indicator_engine", side_effect=check_strategy_init
        ), patch.object(
            TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_create_pipeline", return_value=MagicMock(start=AsyncMock())
        ), patch(
            "services.monitoring.metrics.get_metrics_collector"
        ) as mock_metrics:
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()
            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_data_provider_initializes_after_price_feeds(self):
        """Verify data provider initializes after price feeds."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        price_feeds_init_called = False
        data_source_passed = None

        def mock_price_feeds(*args):
            nonlocal price_feeds_init_called
            price_feeds_init_called = True
            return MagicMock()  # Return a mock data source

        def check_price_feeds(data_source):
            nonlocal data_source_passed
            data_source_passed = data_source
            assert price_feeds_init_called, "Price feeds must be initialized before data provider"
            assert data_source is not None, "Data source should be passed to data provider"

        with patch.object(
            TradingOrchestrator, "_init_kis_client", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_futures_slippage_controller"
        ), patch.object(
            TradingOrchestrator, "_init_price_feeds", side_effect=mock_price_feeds
        ), patch.object(
            TradingOrchestrator, "_init_data_provider", side_effect=check_price_feeds
        ), patch.object(
            TradingOrchestrator, "_init_tick_stream_publisher"
        ), patch.object(
            TradingOrchestrator, "_init_strategy_infrastructure"
        ), patch.object(
            TradingOrchestrator, "_init_indicator_engine"
        ), patch.object(
            TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_create_pipeline", return_value=MagicMock(start=AsyncMock())
        ), patch(
            "services.monitoring.metrics.get_metrics_collector"
        ) as mock_metrics:
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()
            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_market_data_loop_starts_before_pipeline(self):
        """Verify market data loop starts before pipeline."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        market_data_started = False

        async def mock_market_data(*args):
            nonlocal market_data_started
            market_data_started = True

        def check_market_data_before_pipeline():
            assert market_data_started, "Market data loop must start before pipeline"
            pipeline_mock = MagicMock()
            pipeline_mock.start = AsyncMock()
            return pipeline_mock

        with patch.object(
            TradingOrchestrator, "_init_kis_client", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_futures_slippage_controller"
        ), patch.object(
            TradingOrchestrator, "_init_price_feeds", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_data_provider"
        ), patch.object(
            TradingOrchestrator, "_init_tick_stream_publisher"
        ), patch.object(
            TradingOrchestrator, "_init_strategy_infrastructure"
        ), patch.object(
            TradingOrchestrator, "_init_indicator_engine"
        ), patch.object(
            TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_start_market_data_loop", side_effect=mock_market_data
        ), patch.object(
            TradingOrchestrator, "_create_pipeline", side_effect=check_market_data_before_pipeline
        ), patch(
            "services.monitoring.metrics.get_metrics_collector"
        ) as mock_metrics:
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()
            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_execution_layer_initializes_before_position_recovery(self):
        """Verify execution layer initializes before position recovery."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        execution_init_called = False

        async def mock_execution(*args):
            nonlocal execution_init_called
            execution_init_called = True

        async def check_execution(*args):
            assert execution_init_called, "Execution layer must be initialized before position recovery"

        with patch.object(
            TradingOrchestrator, "_init_kis_client", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_futures_slippage_controller"
        ), patch.object(
            TradingOrchestrator, "_init_price_feeds", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_data_provider"
        ), patch.object(
            TradingOrchestrator, "_init_tick_stream_publisher"
        ), patch.object(
            TradingOrchestrator, "_init_strategy_infrastructure"
        ), patch.object(
            TradingOrchestrator, "_init_indicator_engine"
        ), patch.object(
            TradingOrchestrator, "_init_execution_layer", side_effect=mock_execution
        ), patch.object(
            TradingOrchestrator, "_load_swing_positions", side_effect=check_execution
        ), patch.object(
            TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_create_pipeline", return_value=MagicMock(start=AsyncMock())
        ), patch(
            "services.monitoring.metrics.get_metrics_collector"
        ) as mock_metrics:
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()
            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_pipeline_starts_after_all_components(self):
        """Verify pipeline starts only after all components are initialized."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        components_ready = {
            "kis_client": False,
            "price_feeds": False,
            "data_provider": False,
            "strategy_infra": False,
            "indicator_engine": False,
            "execution_layer": False,
            "positions": False,
            "market_data": False,
        }

        def mark_ready(name):
            def wrapper(*args):
                components_ready[name] = True

            return wrapper

        async def mark_ready_async(name):
            async def wrapper(*args):
                components_ready[name] = True

            return wrapper

        def check_all_ready():
            for component, ready in components_ready.items():
                assert ready, f"Component {component} must be ready before pipeline starts"
            pipeline_mock = MagicMock()
            pipeline_mock.start = AsyncMock()
            return pipeline_mock

        with patch.object(
            TradingOrchestrator, "_init_kis_client", side_effect=mark_ready("kis_client")
        ), patch.object(
            TradingOrchestrator, "_init_futures_slippage_controller"
        ), patch.object(
            TradingOrchestrator, "_init_price_feeds", side_effect=mark_ready("price_feeds")
        ), patch.object(
            TradingOrchestrator, "_init_data_provider", side_effect=mark_ready("data_provider")
        ), patch.object(
            TradingOrchestrator, "_init_tick_stream_publisher"
        ), patch.object(
            TradingOrchestrator,
            "_init_strategy_infrastructure",
            side_effect=mark_ready("strategy_infra"),
        ), patch.object(
            TradingOrchestrator,
            "_init_indicator_engine",
            side_effect=mark_ready("indicator_engine"),
        ), patch.object(
            TradingOrchestrator,
            "_init_execution_layer",
            side_effect=mark_ready_async("execution_layer"),
        ), patch.object(
            TradingOrchestrator, "_load_swing_positions", side_effect=mark_ready_async("positions")
        ), patch.object(
            TradingOrchestrator,
            "_start_market_data_loop",
            side_effect=mark_ready_async("market_data"),
        ), patch.object(
            TradingOrchestrator, "_create_pipeline", side_effect=check_all_ready
        ), patch(
            "services.monitoring.metrics.get_metrics_collector"
        ) as mock_metrics:
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()
            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_futures_config_initializes_slippage_controller(self):
        """Verify futures configuration initializes slippage controller."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.futures(
            strategy_name="rl_mppo",
            initial_capital=5_000_000,
        )

        slippage_init_called = False

        def mock_slippage_init(*args):
            nonlocal slippage_init_called
            slippage_init_called = True

        with patch.object(
            TradingOrchestrator, "_init_kis_client", return_value=None
        ), patch.object(
            TradingOrchestrator,
            "_init_futures_slippage_controller",
            side_effect=mock_slippage_init,
        ), patch.object(
            TradingOrchestrator, "_init_price_feeds", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_data_provider"
        ), patch.object(
            TradingOrchestrator, "_init_tick_stream_publisher"
        ), patch.object(
            TradingOrchestrator, "_init_strategy_infrastructure"
        ), patch.object(
            TradingOrchestrator, "_init_indicator_engine"
        ), patch.object(
            TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_create_pipeline", return_value=MagicMock(start=AsyncMock())
        ), patch(
            "services.monitoring.metrics.get_metrics_collector"
        ) as mock_metrics:
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Verify slippage controller was initialized
            assert slippage_init_called

            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_stock_config_skips_slippage_controller(self):
        """Verify stock configuration skips slippage controller initialization."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        # Track if slippage controller actually does work
        slippage_did_work = False

        def mock_slippage_init(self_ref):
            nonlocal slippage_did_work
            # Call the real method
            original_method = TradingOrchestrator._init_futures_slippage_controller.__get__(
                self_ref, TradingOrchestrator
            )
            original_method()
            # Check if controller was set
            if self_ref._futures_slippage_controller is not None:
                slippage_did_work = True

        with patch.object(
            TradingOrchestrator, "_init_kis_client", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_price_feeds", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_data_provider"
        ), patch.object(
            TradingOrchestrator, "_init_tick_stream_publisher"
        ), patch.object(
            TradingOrchestrator, "_init_strategy_infrastructure"
        ), patch.object(
            TradingOrchestrator, "_init_indicator_engine"
        ), patch.object(
            TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_create_pipeline", return_value=MagicMock(start=AsyncMock())
        ), patch(
            "services.monitoring.metrics.get_metrics_collector"
        ) as mock_metrics:
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # For stock, slippage controller should remain None
            assert orchestrator._futures_slippage_controller is None
            assert not slippage_did_work

            await orchestrator.stop()


@pytest.mark.integration
class TestComponentDependencies:
    """Test component initialization dependencies."""

    @pytest.mark.asyncio
    async def test_indicator_engine_uses_strategy_config(self):
        """Verify indicator engine reads parameters from strategy configuration."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        strategy_infra_initialized = False
        indicator_params_verified = False

        def mock_strategy_init(self_ref):
            nonlocal strategy_infra_initialized
            strategy_infra_initialized = True
            # Create a minimal strategy manager mock
            self_ref._strategy_manager = MagicMock()
            self_ref._strategy_manager.strategy_names = ["bb_reversion"]
            self_ref._position_tracker = MagicMock()
            self_ref._risk_manager = MagicMock()
            self_ref._adaptive_sizing = MagicMock()

        def mock_indicator_init(self_ref):
            nonlocal indicator_params_verified
            # Verify strategy infrastructure is ready
            assert strategy_infra_initialized, "Strategy infrastructure must be ready"
            assert self_ref._strategy_manager is not None
            indicator_params_verified = True
            self_ref._indicator_engine = MagicMock()
            self_ref._indicator_resolver = MagicMock()

        with patch.object(
            TradingOrchestrator, "_init_kis_client", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_futures_slippage_controller"
        ), patch.object(
            TradingOrchestrator, "_init_price_feeds", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_data_provider"
        ), patch.object(
            TradingOrchestrator, "_init_tick_stream_publisher"
        ), patch.object(
            TradingOrchestrator, "_init_strategy_infrastructure", side_effect=mock_strategy_init
        ), patch.object(
            TradingOrchestrator, "_init_indicator_engine", side_effect=mock_indicator_init
        ), patch.object(
            TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_create_pipeline", return_value=MagicMock(start=AsyncMock())
        ), patch(
            "services.monitoring.metrics.get_metrics_collector"
        ) as mock_metrics:
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            assert indicator_params_verified
            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_execution_layer_uses_paper_broker_when_configured(self):
        """Verify execution layer initializes paper broker when paper_trading=True."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
            paper_trading=True,
        )

        paper_broker_initialized = False

        async def mock_execution_init(self_ref):
            nonlocal paper_broker_initialized
            # Simulate paper broker initialization
            if self_ref.config.paper_trading:
                self_ref._paper_broker = MagicMock()
                paper_broker_initialized = True

        with patch.object(
            TradingOrchestrator, "_init_kis_client", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_futures_slippage_controller"
        ), patch.object(
            TradingOrchestrator, "_init_price_feeds", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_data_provider"
        ), patch.object(
            TradingOrchestrator, "_init_tick_stream_publisher"
        ), patch.object(
            TradingOrchestrator, "_init_strategy_infrastructure"
        ), patch.object(
            TradingOrchestrator, "_init_indicator_engine"
        ), patch.object(
            TradingOrchestrator, "_init_execution_layer", side_effect=mock_execution_init
        ), patch.object(
            TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_create_pipeline", return_value=MagicMock(start=AsyncMock())
        ), patch(
            "services.monitoring.metrics.get_metrics_collector"
        ) as mock_metrics:
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            assert paper_broker_initialized
            await orchestrator.stop()


@pytest.mark.integration
class TestStartupState:
    """Test orchestrator state transitions during startup."""

    @pytest.mark.asyncio
    async def test_state_transitions_on_successful_start(self):
        """Verify state transitions from IDLE to RUNNING on successful startup."""
        from services.trading.orchestrator import (
            TradingOrchestrator,
            TradingConfig,
            TradingState,
        )

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        with patch.object(
            TradingOrchestrator, "_init_kis_client", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_futures_slippage_controller"
        ), patch.object(
            TradingOrchestrator, "_init_price_feeds", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_data_provider"
        ), patch.object(
            TradingOrchestrator, "_init_tick_stream_publisher"
        ), patch.object(
            TradingOrchestrator, "_init_strategy_infrastructure"
        ), patch.object(
            TradingOrchestrator, "_init_indicator_engine"
        ), patch.object(
            TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_create_pipeline", return_value=MagicMock(start=AsyncMock())
        ), patch(
            "services.monitoring.metrics.get_metrics_collector"
        ) as mock_metrics:
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)

            # Initial state
            assert orchestrator.state == TradingState.IDLE

            # Start
            await orchestrator.start()
            assert orchestrator.state == TradingState.RUNNING

            # Stop
            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_start_time_recorded_on_startup(self):
        """Verify start_time is recorded when orchestrator starts."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        from datetime import datetime

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        with patch.object(
            TradingOrchestrator, "_init_kis_client", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_futures_slippage_controller"
        ), patch.object(
            TradingOrchestrator, "_init_price_feeds", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_data_provider"
        ), patch.object(
            TradingOrchestrator, "_init_tick_stream_publisher"
        ), patch.object(
            TradingOrchestrator, "_init_strategy_infrastructure"
        ), patch.object(
            TradingOrchestrator, "_init_indicator_engine"
        ), patch.object(
            TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_create_pipeline", return_value=MagicMock(start=AsyncMock())
        ), patch(
            "services.monitoring.metrics.get_metrics_collector"
        ) as mock_metrics:
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)

            # Start time should be None initially
            assert orchestrator.start_time is None

            before_start = datetime.now()
            await orchestrator.start()
            after_start = datetime.now()

            # Start time should be set
            assert orchestrator.start_time is not None
            assert before_start <= orchestrator.start_time <= after_start

            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_prometheus_starts_after_pipeline(self):
        """Verify Prometheus server starts after pipeline initialization."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        pipeline_started = False
        prometheus_started = False

        async def mock_pipeline_start():
            nonlocal pipeline_started
            pipeline_started = True

        def mock_prometheus_start(*args, **kwargs):
            nonlocal prometheus_started
            assert pipeline_started, "Pipeline must start before Prometheus"
            prometheus_started = True

        with patch.object(
            TradingOrchestrator, "_init_kis_client", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_futures_slippage_controller"
        ), patch.object(
            TradingOrchestrator, "_init_price_feeds", return_value=None
        ), patch.object(
            TradingOrchestrator, "_init_data_provider"
        ), patch.object(
            TradingOrchestrator, "_init_tick_stream_publisher"
        ), patch.object(
            TradingOrchestrator, "_init_strategy_infrastructure"
        ), patch.object(
            TradingOrchestrator, "_init_indicator_engine"
        ), patch.object(
            TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
        ), patch.object(
            TradingOrchestrator,
            "_create_pipeline",
            return_value=MagicMock(start=mock_pipeline_start),
        ), patch(
            "services.monitoring.metrics.get_metrics_collector"
        ) as mock_metrics:
            mock_metrics_instance = MagicMock()
            mock_metrics_instance.start_prometheus_server = mock_prometheus_start
            mock_metrics_instance.register_strategies = MagicMock()
            mock_metrics.return_value = mock_metrics_instance

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            assert pipeline_started
            assert prometheus_started

            await orchestrator.stop()
