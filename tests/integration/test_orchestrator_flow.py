"""Integration tests for trading orchestrator flow.

Tests the orchestrator lifecycle and component integration.
"""
import pytest
from datetime import date, time


@pytest.mark.integration
class TestOrchestratorFlow:
    """Test orchestrator integration."""

    def test_config_stock_creation(self):
        """Test stock configuration creation."""
        from services.trading.orchestrator import TradingConfig

        config = TradingConfig.stock(
            strategy_name="bb_reversion",
            symbols=["005930", "000660"],
            initial_capital=10_000_000,
        )

        assert config.asset_class == "stock"
        assert config.strategy_name == "bb_reversion"
        assert config.symbols == ["005930", "000660"]
        assert config.initial_capital == 10_000_000
        assert config.schedule.stock_open == time(9, 0)
        assert config.schedule.stock_close == time(15, 30)

    def test_config_futures_creation(self):
        """Test futures configuration creation."""
        from services.trading.orchestrator import TradingConfig

        config = TradingConfig.futures(
            strategy_name="pure_micro",
            initial_capital=5_000_000,
        )

        assert config.asset_class == "futures"
        assert config.strategy_name == "pure_micro"
        assert config.initial_capital == 5_000_000
        assert config.schedule.futures_close == time(15, 45)

    @pytest.mark.asyncio
    async def test_orchestrator_lifecycle(self):
        """Test orchestrator start/pause/resume/stop lifecycle."""
        from services.trading.orchestrator import (
            TradingOrchestrator,
            TradingConfig,
            TradingState,
        )

        config = TradingConfig.stock()
        orchestrator = TradingOrchestrator(config)

        # Initial state
        assert orchestrator.state == TradingState.IDLE
        assert orchestrator.is_running is False

        # Start
        await orchestrator.start()
        assert orchestrator.state == TradingState.RUNNING

        # Pause
        await orchestrator.pause()
        assert orchestrator.state == TradingState.PAUSED

        # Resume
        await orchestrator.resume()
        assert orchestrator.state == TradingState.RUNNING

        # Stop
        await orchestrator.stop()
        assert orchestrator.state == TradingState.STOPPED

    def test_is_trading_day(self):
        """Test trading day detection."""
        from services.trading.orchestrator import is_trading_day

        # Monday is trading day
        monday = date(2024, 1, 15)
        assert is_trading_day(monday, holidays=set()) is True

        # Saturday is not trading day
        saturday = date(2024, 1, 13)
        assert is_trading_day(saturday, holidays=set()) is False

        # Holiday is not trading day
        new_year = date(2024, 1, 1)
        assert is_trading_day(new_year, holidays={new_year}) is False

    def test_get_status(self):
        """Test orchestrator status retrieval."""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock(
            strategy_name="test_strategy",
            initial_capital=10_000_000,
        )
        orchestrator = TradingOrchestrator(config)

        status = orchestrator.get_status()

        assert "state" in status
        assert "config" in status
        assert "stats" in status
        assert status["config"]["asset_class"] == "stock"
        assert status["config"]["strategy"] == "test_strategy"
        assert status["config"]["capital"] == 10_000_000


@pytest.mark.integration
class TestPipelineFlow:
    """Test trading pipeline integration."""

    @pytest.mark.asyncio
    async def test_pipeline_lifecycle(self):
        """Test pipeline start/stop lifecycle."""
        from services.trading.pipeline import TradingPipeline

        # Create pipeline with dummy handlers
        async def dummy_handler():
            return None

        pipeline = TradingPipeline(
            regime_handler=dummy_handler,
            entry_handler=dummy_handler,
            monitoring_handler=dummy_handler,
            exit_handler=dummy_handler,
        )

        # Initial state
        assert pipeline.is_running is False

        # Start
        await pipeline.start()
        assert pipeline.is_running is True

        # Stop
        await pipeline.stop()
        assert pipeline.is_running is False

    def test_pipeline_metrics(self):
        """Test pipeline metrics tracking."""
        from services.trading.pipeline import TradingPipeline, PipelineMetrics

        async def dummy_handler():
            return None

        pipeline = TradingPipeline(
            regime_handler=dummy_handler,
            entry_handler=dummy_handler,
            monitoring_handler=dummy_handler,
            exit_handler=dummy_handler,
        )

        metrics = pipeline.metrics
        assert isinstance(metrics, PipelineMetrics)

        metrics_dict = metrics.to_dict()
        assert "stages" in metrics_dict
        assert "total_signals" in metrics_dict
        assert "total_orders" in metrics_dict
        assert "total_errors" in metrics_dict
