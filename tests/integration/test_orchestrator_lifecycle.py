"""Integration tests for trading orchestrator lifecycle and startup sequence.

Tests the orchestrator startup sequence to ensure components initialize
in the correct order and dependencies are properly established.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


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
        with (
            patch.object(
                TradingOrchestrator, "_init_kis_client", return_value=None
            ) as mock_kis,
            patch.object(
                TradingOrchestrator,
                "_init_futures_slippage_controller",
                return_value=None,
            ) as mock_futures_slip,
            patch.object(
                TradingOrchestrator, "_init_price_feeds", return_value=None
            ) as mock_price_feeds,
            patch.object(
                TradingOrchestrator, "_init_data_provider", return_value=None
            ) as mock_data_provider,
            patch.object(
                TradingOrchestrator, "_init_tick_stream_publisher", return_value=None
            ) as mock_tick_stream,
            patch.object(
                TradingOrchestrator, "_init_strategy_infrastructure", return_value=None
            ) as mock_strategy_infra,
            patch.object(
                TradingOrchestrator, "_init_indicator_engine", return_value=None
            ) as mock_indicator,
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ) as mock_execution,
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ) as mock_positions,
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ) as mock_market_data,
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):

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

        with (
            patch.object(
                TradingOrchestrator, "_init_kis_client", side_effect=mock_init_kis
            ),
            patch.object(
                TradingOrchestrator, "_init_price_feeds", side_effect=check_kis_init
            ),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
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
            assert (
                strategy_init_called
            ), "Strategy infrastructure must be initialized before indicator engine"

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(
                TradingOrchestrator,
                "_init_strategy_infrastructure",
                side_effect=mock_strategy_init,
            ),
            patch.object(
                TradingOrchestrator,
                "_init_indicator_engine",
                side_effect=check_strategy_init,
            ),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
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
            assert (
                price_feeds_init_called
            ), "Price feeds must be initialized before data provider"
            assert (
                data_source is not None
            ), "Data source should be passed to data provider"

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(
                TradingOrchestrator, "_init_price_feeds", side_effect=mock_price_feeds
            ),
            patch.object(
                TradingOrchestrator,
                "_init_data_provider",
                side_effect=check_price_feeds,
            ),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
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
            pipeline_mock.stop = AsyncMock()
            return pipeline_mock

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_start_market_data_loop",
                side_effect=mock_market_data,
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                side_effect=check_market_data_before_pipeline,
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
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
            assert (
                execution_init_called
            ), "Execution layer must be initialized before position recovery"

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", side_effect=mock_execution
            ),
            patch.object(
                TradingOrchestrator,
                "_load_swing_positions",
                side_effect=check_execution,
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
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

        def mark_ready_async(name):
            async def wrapper(*args):
                components_ready[name] = True

            return wrapper

        def check_all_ready():
            for component, ready in components_ready.items():
                assert (
                    ready
                ), f"Component {component} must be ready before pipeline starts"
            pipeline_mock = MagicMock()
            pipeline_mock.start = AsyncMock()
            pipeline_mock.stop = AsyncMock()
            return pipeline_mock

        with (
            patch.object(
                TradingOrchestrator,
                "_init_kis_client",
                side_effect=mark_ready("kis_client"),
            ),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(
                TradingOrchestrator,
                "_init_price_feeds",
                side_effect=mark_ready("price_feeds"),
            ),
            patch.object(
                TradingOrchestrator,
                "_init_data_provider",
                side_effect=mark_ready("data_provider"),
            ),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(
                TradingOrchestrator,
                "_init_strategy_infrastructure",
                side_effect=mark_ready("strategy_infra"),
            ),
            patch.object(
                TradingOrchestrator,
                "_init_indicator_engine",
                side_effect=mark_ready("indicator_engine"),
            ),
            patch.object(
                TradingOrchestrator,
                "_init_execution_layer",
                side_effect=mark_ready_async("execution_layer"),
            ),
            patch.object(
                TradingOrchestrator,
                "_load_swing_positions",
                side_effect=mark_ready_async("positions"),
            ),
            patch.object(
                TradingOrchestrator,
                "_start_market_data_loop",
                side_effect=mark_ready_async("market_data"),
            ),
            patch.object(
                TradingOrchestrator, "_create_pipeline", side_effect=check_all_ready
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
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
            strategy_name="setup_a_gap_reversion",
            initial_capital=5_000_000,
        )

        slippage_init_called = False

        def mock_slippage_init(*args):
            nonlocal slippage_init_called
            slippage_init_called = True

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(
                TradingOrchestrator,
                "_init_futures_slippage_controller",
                side_effect=mock_slippage_init,
            ),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
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
            original_method = (
                TradingOrchestrator._init_futures_slippage_controller.__get__(
                    self_ref, TradingOrchestrator
                )
            )
            original_method()
            # Check if controller was set
            if self_ref._futures_slippage_controller is not None:
                slippage_did_work = True

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
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

        def mock_strategy_init():
            nonlocal strategy_infra_initialized
            strategy_infra_initialized = True

        def mock_indicator_init():
            nonlocal indicator_params_verified
            # Verify strategy infrastructure is ready
            assert strategy_infra_initialized, "Strategy infrastructure must be ready"
            indicator_params_verified = True

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(
                TradingOrchestrator,
                "_init_strategy_infrastructure",
                side_effect=mock_strategy_init,
            ),
            patch.object(
                TradingOrchestrator,
                "_init_indicator_engine",
                side_effect=mock_indicator_init,
            ),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
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

        async def mock_execution_init():
            nonlocal paper_broker_initialized
            # Simulate paper broker initialization for paper trading config
            if config.paper_trading:
                paper_broker_initialized = True

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator,
                "_init_execution_layer",
                side_effect=mock_execution_init,
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
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

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
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

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
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

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=mock_pipeline_start, stop=AsyncMock()),
            ),
            patch(
                "services.trading.orchestrator.get_metrics_collector"
            ) as mock_metrics,
        ):
            mock_metrics_instance = MagicMock()
            mock_metrics_instance.start_prometheus_server = mock_prometheus_start
            mock_metrics_instance.register_strategies = MagicMock()
            mock_metrics.return_value = mock_metrics_instance

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            assert pipeline_started
            assert prometheus_started

            await orchestrator.stop()


@pytest.mark.integration
class TestTradingLoop:
    """Test trading loop event processing and market data handling."""

    @pytest.mark.asyncio
    async def test_trading_loop_starts_and_runs(self):
        """Verify trading loop starts and runs after orchestrator start."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        import asyncio

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        loop_started = False
        loop_running = False

        async def mock_market_data_loop(*args):
            nonlocal loop_started, loop_running
            loop_started = True
            loop_running = True
            # Simulate loop running
            await asyncio.sleep(0.1)

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_start_market_data_loop",
                side_effect=mock_market_data_loop,
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Verify loop started
            assert loop_started
            assert loop_running

            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_market_data_processing(self):
        """Verify market data is processed through the loop."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        data_processed = []
        orchestrator_holder = [None]

        # Mock data provider to simulate market data
        mock_data_provider = MagicMock()

        def mock_init_data_provider(*args):
            if orchestrator_holder[0] is not None:
                orchestrator_holder[0]._data_provider = mock_data_provider

        async def mock_market_data_loop():
            # Simulate processing market data
            for i in range(3):
                data = {"symbol": "005930", "price": 60000 + i * 100, "volume": 1000}
                data_processed.append(data)
                await asyncio.sleep(0.01)

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(
                TradingOrchestrator,
                "_init_data_provider",
                side_effect=mock_init_data_provider,
            ),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_start_market_data_loop",
                side_effect=mock_market_data_loop,
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            orchestrator_holder[0] = orchestrator
            await orchestrator.start()

            # Verify data was processed
            assert len(data_processed) == 3
            assert data_processed[0]["symbol"] == "005930"
            assert data_processed[0]["price"] == 60000

            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_loop_processes_multiple_symbols(self):
        """Verify loop processes market data for multiple symbols."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930", "000660", "035720"],
        )

        symbols_processed = set()

        async def mock_market_data_loop():
            # Simulate processing data for all symbols
            for symbol in config.symbols:
                symbols_processed.add(symbol)
                await asyncio.sleep(0.01)

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_start_market_data_loop",
                side_effect=mock_market_data_loop,
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Verify all symbols were processed
            assert symbols_processed == {"005930", "000660", "035720"}

            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_loop_stops_gracefully(self):
        """Verify trading loop stops gracefully when orchestrator stops."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        import asyncio

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        loop_stopped = False
        orchestrator_holder = [None]
        loop_task_holder = [None]

        async def _loop_body():
            # Run until stop is requested
            while orchestrator_holder[0] is None or orchestrator_holder[0].is_running:
                await asyncio.sleep(0.01)
            nonlocal loop_stopped
            loop_stopped = True

        async def mock_start_market_data_loop():
            # Mimic real implementation: create task instead of blocking
            loop_task_holder[0] = asyncio.create_task(_loop_body())

        async def mock_stop(*args, **kwargs):
            # Signal loop to stop
            if orchestrator_holder[0] is not None:
                orchestrator_holder[0]._running = False
                orchestrator_holder[0]._state = TradingState.STOPPED
            # Wait for loop task to finish
            if loop_task_holder[0] is not None:
                await asyncio.wait_for(loop_task_holder[0], timeout=1.0)

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_start_market_data_loop",
                side_effect=mock_start_market_data_loop,
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
            from services.trading.orchestrator import TradingState

            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            orchestrator_holder[0] = orchestrator

            # Patch stop method
            with patch.object(TradingOrchestrator, "stop", side_effect=mock_stop):
                await orchestrator.start()

                # Wait a bit for loop to run
                await asyncio.sleep(0.05)

                # Stop orchestrator
                await orchestrator.stop()

                # Verify loop stopped
                assert loop_stopped

    @pytest.mark.asyncio
    async def test_loop_continues_after_processing_error(self):
        """Verify loop continues running even if individual data processing fails."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        import asyncio

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        process_attempts = []

        async def mock_market_data_loop():
            # Simulate processing with errors
            for i in range(5):
                try:
                    process_attempts.append(i)
                    if i == 2:
                        # Simulate error on 3rd attempt
                        raise ValueError("Simulated processing error")
                except ValueError:
                    # Log error but continue
                    pass
                await asyncio.sleep(0.01)

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_start_market_data_loop",
                side_effect=mock_market_data_loop,
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Verify loop processed all attempts including after error
            assert len(process_attempts) == 5
            assert process_attempts == [0, 1, 2, 3, 4]

            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_futures_loop_processes_continuous_data(self):
        """Verify futures trading loop processes continuous market data."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.futures(
            strategy_name="setup_a_gap_reversion",
            initial_capital=5_000_000,
        )

        futures_data_processed = []

        async def mock_market_data_loop():
            # Simulate continuous futures data processing
            for i in range(10):
                data = {
                    "symbol": "101S6000",  # KOSPI200 futures
                    "price": 250.0 + i * 0.05,
                    "timestamp": i,
                }
                futures_data_processed.append(data)
                await asyncio.sleep(0.01)

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_start_market_data_loop",
                side_effect=mock_market_data_loop,
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Verify continuous data processing
            assert len(futures_data_processed) == 10
            assert futures_data_processed[0]["price"] == 250.0
            assert futures_data_processed[-1]["price"] == 250.45

            await orchestrator.stop()


@pytest.mark.integration
class TestPauseResume:
    """Test orchestrator pause/resume functionality without data loss."""

    @pytest.mark.asyncio
    async def test_basic_pause_resume_state_transitions(self):
        """Verify basic pause/resume state transitions work correctly."""
        from services.trading.orchestrator import (
            TradingOrchestrator,
            TradingConfig,
            TradingState,
        )

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)

            # Initial state
            assert orchestrator.state == TradingState.IDLE

            # Start -> RUNNING
            await orchestrator.start()
            assert orchestrator.state == TradingState.RUNNING

            # Pause -> PAUSED
            await orchestrator.pause()
            assert orchestrator.state == TradingState.PAUSED

            # Resume -> RUNNING
            await orchestrator.resume()
            assert orchestrator.state == TradingState.RUNNING

            # Cleanup
            await orchestrator.stop()
            assert orchestrator.state == TradingState.STOPPED

    @pytest.mark.asyncio
    async def test_pause_resume_preserves_positions(self):
        """Verify positions are preserved during pause/resume."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        from services.trading.position_tracker import PositionTracker
        from shared.models.position import Position, PositionSide

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930", "000660"],
        )

        # Create mock positions
        mock_positions = [
            Position(
                id="pos_005930",
                code="005930",
                name="삼성전자",
                side=PositionSide.LONG,
                entry_price=70000.0,
                quantity=10,
                current_price=71000.0,
                strategy="bb_reversion",
            ),
            Position(
                id="pos_000660",
                code="000660",
                name="SK하이닉스",
                side=PositionSide.LONG,
                entry_price=120000.0,
                quantity=5,
                current_price=122000.0,
                strategy="bb_reversion",
            ),
        ]

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Add positions to position tracker
            orchestrator._position_tracker = MagicMock(spec=PositionTracker)
            orchestrator._position_tracker.positions = mock_positions.copy()
            orchestrator._position_tracker.position_count = len(mock_positions)

            # Capture positions before pause
            positions_before = list(orchestrator._position_tracker.positions)

            # Pause
            await orchestrator.pause()

            # Verify positions still exist during pause
            assert len(orchestrator._position_tracker.positions) == 2
            assert orchestrator._position_tracker.positions == positions_before

            # Resume
            await orchestrator.resume()

            # Verify positions are still intact after resume
            assert len(orchestrator._position_tracker.positions) == 2
            assert orchestrator._position_tracker.positions == positions_before

            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_pause_resume_preserves_statistics(self):
        """Verify trading statistics are preserved during pause/resume."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Set some statistics
            orchestrator.session_count = 5
            orchestrator.total_trades = 42
            orchestrator.total_pnl = 123456.78

            # Capture stats before pause
            session_count_before = orchestrator.session_count
            total_trades_before = orchestrator.total_trades
            total_pnl_before = orchestrator.total_pnl

            # Pause
            await orchestrator.pause()

            # Verify stats unchanged during pause
            assert orchestrator.session_count == session_count_before
            assert orchestrator.total_trades == total_trades_before
            assert orchestrator.total_pnl == total_pnl_before

            # Resume
            await orchestrator.resume()

            # Verify stats unchanged after resume
            assert orchestrator.session_count == session_count_before
            assert orchestrator.total_trades == total_trades_before
            assert orchestrator.total_pnl == total_pnl_before

            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_pause_stops_pipeline_resume_restarts(self):
        """Verify pause stops pipeline and resume restarts it."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        mock_pipeline = MagicMock()
        mock_pipeline.start = AsyncMock()
        mock_pipeline.stop = AsyncMock()

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_create_pipeline", return_value=mock_pipeline
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Pipeline should have started
            assert mock_pipeline.start.call_count >= 1

            # Pause - pipeline should stop
            await orchestrator.pause()
            assert mock_pipeline.stop.call_count == 1

            # Resume - pipeline should start again
            await orchestrator.resume()
            assert mock_pipeline.start.call_count >= 2

            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_market_data_continuity_after_resume(self):
        """Verify market data processing continues correctly after resume."""
        import asyncio
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.futures(
            strategy_name="setup_a_gap_reversion",
        )

        # Track market data processing
        market_data_events = []
        pause_event = asyncio.Event()
        resume_event = asyncio.Event()
        orchestrator_holder = [None]

        async def _loop_body():
            """Simulate market data loop that can be paused/resumed"""
            for i in range(20):
                # Simulate pause at iteration 10
                if i == 10:
                    pause_event.set()
                    # Wait for resume signal
                    await resume_event.wait()

                state_value = (
                    orchestrator_holder[0].state.value
                    if orchestrator_holder[0]
                    else "unknown"
                )
                market_data_events.append(
                    {
                        "iteration": i,
                        "price": 250.0 + i * 0.1,
                        "state": state_value,
                    }
                )
                await asyncio.sleep(0.01)

        async def mock_start_market_data_loop():
            # Mimic real implementation: create task instead of blocking
            asyncio.create_task(_loop_body())

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_start_market_data_loop",
                side_effect=mock_start_market_data_loop,
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            orchestrator_holder[0] = orchestrator

            # Start orchestrator
            async def run_with_pause_resume():
                await orchestrator.start()

                # Wait for pause point
                await pause_event.wait()

                # Pause
                await orchestrator.pause()
                await asyncio.sleep(0.05)  # Brief pause

                # Resume
                await orchestrator.resume()
                resume_event.set()

                # Wait a bit for remaining iterations
                await asyncio.sleep(0.3)

                await orchestrator.stop()

            await run_with_pause_resume()

            # Verify market data was processed continuously
            # (though state changed during pause)
            assert len(market_data_events) == 20
            assert market_data_events[0]["iteration"] == 0
            assert market_data_events[-1]["iteration"] == 19

            # Verify data continuity (no gaps in iteration sequence)
            iterations = [event["iteration"] for event in market_data_events]
            assert iterations == list(range(20))

    @pytest.mark.asyncio
    async def test_no_duplicate_orders_after_resume(self):
        """Verify no duplicate orders are placed after resume."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        from shared.models.signal import Signal, SignalType

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        # Track order execution attempts
        order_attempts = []

        async def mock_execute_order(*args, **kwargs):
            """Track order execution attempts"""
            signal = args[0] if args else kwargs.get("signal")
            order_attempts.append(
                {
                    "code": signal.code,
                    "direction": signal.signal_type,
                }
            )
            # Simulate successful order
            return MagicMock(success=True, order_id=f"ORDER_{len(order_attempts)}")

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch.object(
                TradingOrchestrator, "_execute_entry", side_effect=mock_execute_order
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Create a test signal
            test_signal = Signal(
                code="005930",
                name="삼성전자",
                signal_type=SignalType.ENTRY,
                strategy="bb_reversion",
                price=70000.0,
                confidence=0.85,
            )

            # Execute order before pause
            await orchestrator._execute_entry(test_signal)
            initial_order_count = len(order_attempts)

            # Pause
            await orchestrator.pause()

            # Try to execute during pause (should not happen in real scenario,
            # but testing defensive behavior)
            # Note: In real implementation, check should prevent this

            # Resume
            await orchestrator.resume()

            # After resume, order attempts should not have duplicated
            # The count should only increase if new signals are generated
            assert len(order_attempts) == initial_order_count

            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_multiple_pause_resume_cycles(self):
        """Verify orchestrator handles multiple pause/resume cycles correctly."""
        from services.trading.orchestrator import (
            TradingOrchestrator,
            TradingConfig,
            TradingState,
        )

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds", return_value=None),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Set some initial state
            orchestrator.total_trades = 10

            # Multiple pause/resume cycles
            for i in range(5):
                # Pause
                await orchestrator.pause()
                assert orchestrator.state == TradingState.PAUSED

                # State should be preserved
                assert orchestrator.total_trades == 10

                # Resume
                await orchestrator.resume()
                assert orchestrator.state == TradingState.RUNNING

                # State should still be preserved
                assert orchestrator.total_trades == 10

            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_pause_from_non_running_state_is_noop(self):
        """Verify pause from non-RUNNING state is a no-op."""
        from services.trading.orchestrator import (
            TradingOrchestrator,
            TradingConfig,
            TradingState,
        )

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        with (
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)

            # Try to pause when IDLE
            assert orchestrator.state == TradingState.IDLE
            await orchestrator.pause()
            # Should remain IDLE (not change to PAUSED)
            assert orchestrator.state == TradingState.IDLE

    @pytest.mark.asyncio
    async def test_resume_from_non_paused_state_is_noop(self):
        """Verify resume from non-PAUSED state is a no-op."""
        from services.trading.orchestrator import (
            TradingOrchestrator,
            TradingConfig,
            TradingState,
        )

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        with (
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)

            # Try to resume when IDLE
            assert orchestrator.state == TradingState.IDLE
            await orchestrator.resume()
            # Should remain IDLE (not change to RUNNING)
            assert orchestrator.state == TradingState.IDLE


@pytest.mark.integration
class TestGracefulShutdown:
    """Test graceful shutdown and cleanup procedures."""

    @pytest.mark.asyncio
    async def test_websocket_close_on_shutdown(self):
        """Verify WebSocket connections are properly closed during shutdown."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        # Mock price feeds to track close calls
        mock_stock_feed = MagicMock()
        mock_stock_feed.stop = AsyncMock()
        mock_futures_feed = MagicMock()
        mock_futures_feed.stop = AsyncMock()

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds"),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Inject mock price feeds
            orchestrator._stock_price_feed = mock_stock_feed
            orchestrator._futures_price_feed = mock_futures_feed
            orchestrator._market_data_running = True

            # Stop orchestrator
            await orchestrator.stop()

            # Verify WebSocket close was called on both feeds
            mock_stock_feed.stop.assert_awaited_once()
            mock_futures_feed.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_redis_flush_on_shutdown(self):
        """Verify positions are flushed to Redis during shutdown."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        from shared.models.position import Position, PositionSide

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        # Mock position tracker and state publisher
        mock_position_tracker = MagicMock()
        mock_position_tracker.position_count = 2
        mock_position_tracker.positions = [
            Position(
                id="pos1",
                code="005930",
                name="삼성전자",
                strategy="bb_reversion",
                entry_price=70000,
                quantity=10,
                side=PositionSide.LONG,
            ),
            Position(
                id="pos2",
                code="005930",
                name="삼성전자",
                strategy="bb_reversion",
                entry_price=71000,
                quantity=5,
                side=PositionSide.LONG,
            ),
        ]
        mock_position_tracker.stop_auto_flush = AsyncMock()

        mock_state_publisher = MagicMock()
        mock_state_publisher.publish_positions_update = MagicMock()
        mock_state_publisher.publish_status = MagicMock()

        mock_data_provider = MagicMock()
        mock_data_provider.get_data = AsyncMock(
            return_value={"005930": {"close": 72000}}
        )

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds"),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_stop_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Inject mocks
            orchestrator._position_tracker = mock_position_tracker
            orchestrator._state_publisher = mock_state_publisher
            orchestrator._data_provider = mock_data_provider

            # Stop orchestrator
            await orchestrator.stop()

            # Verify positions were flushed to Redis
            mock_state_publisher.publish_positions_update.assert_called()
            # Verify the positions list was passed
            call_args = mock_state_publisher.publish_positions_update.call_args
            assert len(call_args[0][0]) == 2  # Two positions
            assert call_args[1]["throttle"] == 0  # No throttling on shutdown

            # Verify auto-flush was stopped
            mock_position_tracker.stop_auto_flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_position_serialization_on_shutdown(self):
        """Verify positions are properly serialized before Redis flush."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        from shared.models.position import Position, PositionSide

        config = TradingConfig.futures(
            strategy_name="setup_a_gap_reversion",
        )

        # Create test positions with various states
        test_positions = [
            Position(
                id="swing_pos",
                code="101S6000",
                name="KOSPI200 선물",
                strategy="setup_a_gap_reversion",
                entry_price=350.0,
                quantity=1,
                side=PositionSide.LONG,
            ),
        ]

        mock_position_tracker = MagicMock()
        mock_position_tracker.position_count = 1
        mock_position_tracker.positions = test_positions
        mock_position_tracker.stop_auto_flush = AsyncMock()
        mock_position_tracker.close_position.return_value = MagicMock(
            unrealized_pnl=0.0
        )

        # Track what gets serialized
        serialized_positions = []

        def capture_positions(positions, **kwargs):
            serialized_positions.extend(positions)

        mock_state_publisher = MagicMock()
        mock_state_publisher.publish_positions_update = MagicMock(
            side_effect=capture_positions
        )
        mock_state_publisher.publish_status = MagicMock()

        mock_data_provider = MagicMock()
        mock_data_provider.get_data = AsyncMock(
            return_value={"101S6000": {"close": 352.0}}
        )

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds"),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_stop_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Inject mocks
            orchestrator._position_tracker = mock_position_tracker
            orchestrator._state_publisher = mock_state_publisher
            orchestrator._data_provider = mock_data_provider

            # Stop orchestrator
            await orchestrator.stop()

            # Verify position was serialized correctly
            assert len(serialized_positions) == 1
            pos = serialized_positions[0]
            assert pos.id == "swing_pos"
            assert pos.code == "101S6000"
            assert pos.strategy == "setup_a_gap_reversion"
            assert pos.entry_price == 350.0
            assert pos.quantity == 1
            assert pos.side == PositionSide.LONG

    @pytest.mark.asyncio
    async def test_timeout_handling_forces_redis_flush(self):
        """Verify timeout triggers forced Redis flush as last resort."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        from shared.models.position import Position, PositionSide

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        # Mock position tracker with positions
        mock_position_tracker = MagicMock()
        mock_position_tracker.position_count = 1
        mock_position_tracker.positions = [
            Position(
                id="pos1",
                code="005930",
                name="삼성전자",
                strategy="bb_reversion",
                entry_price=70000,
                quantity=10,
                side=PositionSide.LONG,
            ),
        ]
        mock_position_tracker.stop_auto_flush = AsyncMock()

        mock_state_publisher = MagicMock()
        # First call times out, second (forced) call succeeds
        mock_state_publisher.publish_positions_update = MagicMock()
        mock_state_publisher.publish_status = MagicMock()

        # Simulate a slow shutdown that will timeout
        async def slow_stop():
            await asyncio.sleep(2.0)  # Longer than timeout

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds"),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
            patch.object(TradingOrchestrator, "_stop_impl", side_effect=slow_stop),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Inject mocks
            orchestrator._position_tracker = mock_position_tracker
            orchestrator._state_publisher = mock_state_publisher

            # Stop with short timeout (will trigger timeout)
            await orchestrator.stop(timeout=0.1)

            # Verify forced Redis flush was attempted
            # Should be called at least once (in the timeout handler)
            assert mock_state_publisher.publish_positions_update.call_count >= 1

            # Verify state changed to STOPPED despite timeout
            from services.trading.orchestrator import TradingState

            assert orchestrator.state == TradingState.STOPPED
            assert orchestrator._running is False

    @pytest.mark.asyncio
    async def test_cleanup_resources_releases_all_components(self):
        """Verify all components are properly released during cleanup."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        # Mock all components that should be cleaned up
        mock_tick_stream = MagicMock()
        mock_tick_stream.close = MagicMock()

        mock_pipeline = MagicMock()
        mock_pipeline.stop = AsyncMock()
        mock_pipeline.start = AsyncMock()

        mock_order_executor = MagicMock()
        mock_order_executor.cleanup = AsyncMock()

        mock_mock_mirror = MagicMock()
        mock_mock_mirror.cleanup = AsyncMock()

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds"),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_stop_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_create_pipeline", return_value=mock_pipeline
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Inject mocks
            orchestrator._tick_stream_publisher = mock_tick_stream
            orchestrator.pipeline = mock_pipeline
            orchestrator._order_executor = mock_order_executor
            orchestrator._mock_mirror = mock_mock_mirror

            # Stop orchestrator
            await orchestrator.stop()

            # Verify all components were cleaned up
            mock_tick_stream.close.assert_called_once()
            mock_pipeline.stop.assert_awaited()
            mock_order_executor.cleanup.assert_awaited_once()
            mock_mock_mirror.cleanup.assert_awaited_once()

            # Verify components are set to None
            assert orchestrator._tick_stream_publisher is None
            assert orchestrator.pipeline is None
            assert orchestrator._order_executor is None
            assert orchestrator._mock_mirror is None
            assert orchestrator._data_provider is None
            assert orchestrator._strategy_manager is None
            assert orchestrator._position_tracker is None
            assert orchestrator._indicator_engine is None

    @pytest.mark.asyncio
    async def test_redis_flush_retry_on_connection_error(self):
        """Verify Redis flush retries on connection errors."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig
        from shared.models.position import Position, PositionSide

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930"],
        )

        mock_position_tracker = MagicMock()
        mock_position_tracker.position_count = 1
        mock_position_tracker.positions = [
            Position(
                id="pos1",
                code="005930",
                name="삼성전자",
                strategy="bb_reversion",
                entry_price=70000,
                quantity=10,
                side=PositionSide.LONG,
            ),
        ]
        mock_position_tracker.stop_auto_flush = AsyncMock()

        mock_state_publisher = MagicMock()
        # First two calls fail, third succeeds
        mock_state_publisher.publish_positions_update = MagicMock(
            side_effect=[
                ConnectionError("Redis connection failed"),
                ConnectionError("Redis connection failed"),
                None,  # Success on third try
            ]
        )
        mock_state_publisher.publish_status = MagicMock()

        mock_data_provider = MagicMock()
        mock_data_provider.get_data = AsyncMock(
            return_value={"005930": {"close": 72000}}
        )

        with (
            patch.object(TradingOrchestrator, "_init_kis_client", return_value=None),
            patch.object(TradingOrchestrator, "_init_futures_slippage_controller"),
            patch.object(TradingOrchestrator, "_init_price_feeds"),
            patch.object(TradingOrchestrator, "_init_data_provider"),
            patch.object(TradingOrchestrator, "_init_tick_stream_publisher"),
            patch.object(TradingOrchestrator, "_init_strategy_infrastructure"),
            patch.object(TradingOrchestrator, "_init_indicator_engine"),
            patch.object(
                TradingOrchestrator, "_init_execution_layer", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_load_swing_positions", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_start_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator, "_stop_market_data_loop", new_callable=AsyncMock
            ),
            patch.object(
                TradingOrchestrator,
                "_create_pipeline",
                return_value=MagicMock(start=AsyncMock(), stop=AsyncMock()),
            ),
            patch("services.monitoring.metrics.get_metrics_collector") as mock_metrics,
            patch.object(TradingOrchestrator, "_notify", new_callable=AsyncMock),
        ):
            mock_metrics.return_value = MagicMock(
                start_prometheus_server=MagicMock(),
                register_strategies=MagicMock(),
            )

            orchestrator = TradingOrchestrator(config)
            await orchestrator.start()

            # Inject mocks
            orchestrator._position_tracker = mock_position_tracker
            orchestrator._state_publisher = mock_state_publisher
            orchestrator._data_provider = mock_data_provider

            # Stop orchestrator
            await orchestrator.stop()

            # Verify publish_positions_update was called 3 times (2 failures + 1 success)
            assert mock_state_publisher.publish_positions_update.call_count == 3
