"""Test CLI commands."""

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


class TestCLIHelp:
    """Test CLI help commands."""

    def test_main_help(self, runner):
        """Test main help command."""
        from cli.main import cli

        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "KIS Unified Trading System CLI" in result.output

    def test_backtest_help(self, runner):
        """Test backtest help command."""
        from cli.main import cli

        result = runner.invoke(cli, ["backtest", "--help"])
        assert result.exit_code == 0
        assert "backtest" in result.output.lower()

    def test_collect_help(self, runner):
        """Test collect help command."""
        from cli.main import cli

        result = runner.invoke(cli, ["collect", "--help"])
        assert result.exit_code == 0
        assert "collect" in result.output.lower()

    def test_trade_help(self, runner):
        """Test trade help command."""
        from cli.main import cli

        result = runner.invoke(cli, ["trade", "--help"])
        assert result.exit_code == 0
        assert "trade" in result.output.lower()

    def test_mlflow_help(self, runner):
        """Test mlflow help command."""
        from cli.main import cli

        result = runner.invoke(cli, ["mlflow", "--help"])
        assert result.exit_code == 0
        assert "mlflow" in result.output.lower()

    def test_data_help(self, runner):
        """Test data command help."""
        from cli.main import cli

        result = runner.invoke(cli, ["data", "--help"])
        assert result.exit_code == 0
        assert "validate-parquet" in result.output
        assert "export-clickhouse" not in result.output
        assert "validate-parquet" in result.output


class TestBacktestCommands:
    """Test backtest commands."""

    def test_backtest_list(self, runner):
        """Test backtest list command."""
        from cli.main import cli

        result = runner.invoke(cli, ["backtest", "list"])
        # May succeed or fail depending on config directory
        assert result.exit_code in (0, 1)

    @pytest.mark.parametrize(
        ("timeframe", "is_daily"),
        [("minute", False), ("daily", True)],
    )
    def test_tier_backtest_uses_configured_market_data_store(
        self,
        monkeypatch,
        timeframe,
        is_daily,
        capsys,
    ):
        """Tier backtests should use StorageConfig market-data source, not CH loaders."""
        import pandas as pd

        import shared.backtest as backtest_module
        import shared.backtest.adapter as adapter_module
        import shared.backtest.daily_adapter as daily_adapter_module
        import shared.storage as storage_module
        import shared.strategy.registry as registry_module
        from cli.main import _run_tier_backtest
        from shared.collector.historical import stock as stock_module
        from shared.config.loader import ConfigLoader
        from shared.storage import StorageConfig

        monkeypatch.setattr(
            stock_module,
            "STOCK_UNIVERSE",
            [{"code": "005930", "name": "Samsung", "tier": "top"}],
        )
        monkeypatch.setattr(
            ConfigLoader,
            "load_strategy",
            staticmethod(
                lambda _asset, _strategy: {
                    "strategy": {
                        "name": "test_strategy",
                        "timeframe": timeframe,
                        "position": {"params": {"max_positions": 1}},
                    }
                }
            ),
        )
        monkeypatch.setattr(
            registry_module, "register_builtin_components", lambda: None
        )
        monkeypatch.setattr(
            registry_module.StrategyFactory,
            "create",
            staticmethod(lambda _config: object()),
        )

        captured: dict[str, object] = {}

        def fake_load_market_bars_for_backtest(**kwargs):
            captured.update(kwargs)
            return pd.DataFrame(
                {
                    "code": ["005930", "005930"],
                    "datetime": [
                        pd.Timestamp("2026-06-03 09:00:00"),
                        pd.Timestamp("2026-06-03 09:01:00"),
                    ],
                    "open": [100.0, 101.0],
                    "high": [101.0, 102.0],
                    "low": [99.0, 100.0],
                    "close": [101.0, 102.0],
                    "volume": [1000, 1200],
                }
            )

        def fail_clickhouse_loader(*_args, **_kwargs):
            raise AssertionError("legacy ClickHouse loader should not be called")

        monkeypatch.setattr(
            storage_module,
            "load_market_bars_for_backtest",
            fake_load_market_bars_for_backtest,
        )
        monkeypatch.setattr(
            stock_module,
            "load_stock_minute_from_parquet",
            fail_clickhouse_loader,
        )
        monkeypatch.setattr(
            daily_adapter_module,
            "load_stock_daily_from_parquet",
            fail_clickhouse_loader,
        )

        class FakeResult:
            total_trades = 1
            total_return_pct = 1.2
            win_rate = 100.0
            sharpe_ratio = 1.5
            max_drawdown_pct = -0.2

        class FakeBacktestEngine:
            def __init__(self, _strategy, _config):
                pass

            def run(self, df):
                captured["rows"] = len(df)
                return FakeResult()

        monkeypatch.setattr(backtest_module, "BacktestEngine", FakeBacktestEngine)
        monkeypatch.setattr(
            adapter_module,
            "BacktestStrategyAdapter",
            lambda _strategy, _config: object(),
        )
        monkeypatch.setattr(
            daily_adapter_module,
            "DailyBacktestAdapter",
            lambda _strategy, _config: object(),
        )
        monkeypatch.setattr(
            StorageConfig,
            "load_or_default",
            classmethod(lambda cls: cls()),
        )

        _run_tier_backtest(
            strategy="test_strategy",
            asset="stock",
            tier="top",
            start=None,
            end=None,
            capital=10_000_000,
            track=False,
            experiment=None,
            is_daily=is_daily,
        )

        assert captured["symbol"] == "005930"
        assert captured["asset_class"] == "stock"
        assert captured["timeframe"] == timeframe
        assert captured["rows"] == 2
        assert "Market data source: parquet" in capsys.readouterr().out


class TestCollectCommands:
    """Test collect commands."""

    def test_collect_status(self, runner):
        """Test collect status command."""
        from cli.main import cli

        result = runner.invoke(cli, ["collect", "status"])
        assert result.exit_code == 0
        assert "Status" in result.output


class TestDataCommands:
    """Test research data commands."""

    def test_validate_parquet_allows_empty_dataset(self, runner, tmp_path):
        """Empty dataset validation can be used as a smoke check."""
        from cli.main import cli

        result = runner.invoke(
            cli,
            [
                "data",
                "validate-parquet",
                "--root",
                str(tmp_path / "market"),
                "--allow-empty",
            ],
        )

        assert result.exit_code == 0
        assert "Files: 0" in result.output

    def test_data_help_excludes_clickhouse_export(self, runner):
        from cli.main import cli

        result = runner.invoke(cli, ["data", "--help"])

        assert result.exit_code == 0
        assert "validate-parquet" in result.output
        assert "export-clickhouse" not in result.output


class TestBackfillCommands:
    """Test historical backfill command routing."""

    def test_futures_backfill_defaults_to_parquet(self, runner, monkeypatch):
        """Default futures backfill should route to the Parquet sink."""
        from cli.main import cli
        from shared.collector.historical import parquet_backfill

        captured = {}

        async def fake_backfill_futures_parquet(**kwargs):
            captured.update(kwargs)
            return parquet_backfill.ParquetBackfillResult(tasks=2, rows=3)

        monkeypatch.setattr(
            parquet_backfill,
            "backfill_futures_parquet",
            fake_backfill_futures_parquet,
        )

        result = runner.invoke(
            cli, ["backfill", "run", "--days", "2", "--no-mini", "--index"]
        )

        assert result.exit_code == 0
        assert captured["days"] == 2
        assert captured["mini"] is False
        assert captured["index"] is True
        assert "rows=3" in result.output

    def test_stock_backfill_defaults_to_parquet(self, runner, monkeypatch):
        """Default stock backfill should route to the Parquet sink."""
        from cli.main import cli
        from shared.collector.historical import parquet_backfill

        captured = {}

        async def fake_backfill_stock_minute_parquet(**kwargs):
            captured.update(kwargs)
            return parquet_backfill.ParquetBackfillResult(tasks=1, rows=1)

        monkeypatch.setattr(
            parquet_backfill,
            "backfill_stock_minute_parquet",
            fake_backfill_stock_minute_parquet,
        )

        result = runner.invoke(
            cli,
            ["stock-backfill", "run", "--days", "1", "-c", "005930"],
        )

        assert result.exit_code == 0
        assert captured["days"] == 1
        assert captured["codes"] == ["005930"]
        assert "rows=1" in result.output

    def test_backfill_rejects_clickhouse_sink(self, runner):
        """Market-data collection should no longer expose a ClickHouse sink."""
        from cli.main import cli

        result = runner.invoke(cli, ["backfill", "run", "--sink", "clickhouse"])

        assert result.exit_code != 0
        assert "Invalid value for '--sink'" in result.output


class TestTradeCommands:
    """Test trade commands."""

    @pytest.mark.parametrize("asset", ["stock", "futures"])
    def test_trade_start_paper_single_enters_orchestrator(
        self,
        runner,
        monkeypatch,
        asset,
    ):
        """Paper start should route to the orchestrator without live confirmation."""
        from cli.main import cli
        from services.trading import orchestrator as orchestrator_module

        seen_configs = []

        class FakeOrchestrator:
            def __init__(self, config):
                self.config = config
                seen_configs.append(config)

            async def run(self):
                raise AssertionError("single-session smoke should not run daemon mode")

            async def run_session(self):
                return None

            async def stop(self):
                return None

        monkeypatch.setattr(
            orchestrator_module.TradingConfig,
            "_get_futures_default_symbols",
            staticmethod(lambda: ["101V6000"]),
        )
        monkeypatch.setattr(
            orchestrator_module,
            "TradingOrchestrator",
            FakeOrchestrator,
        )

        result = runner.invoke(
            cli,
            [
                "trade",
                "start",
                "--asset",
                asset,
                "--paper",
                "--single",
                "--capital",
                "10000000",
            ],
        )

        assert result.exit_code == 0, result.output
        assert len(seen_configs) == 1
        assert seen_configs[0].asset_class == asset
        assert seen_configs[0].paper_trading is True
        assert "Starting Paper Trading" in result.output

    def test_trade_status(self, runner, mocker):
        """Test trade status command shows 'not running' when no server."""
        from cli.main import cli

        mocker.patch("httpx.get", side_effect=ConnectionError("no server"))
        result = runner.invoke(cli, ["trade", "status"])
        assert result.exit_code == 0
        assert "Status" in result.output

    def test_live_noninteractive_confirm_requires_live_env(self, runner, monkeypatch):
        """--yes-live is reserved for explicit live environments."""
        from cli.main import cli

        monkeypatch.delenv("KIS_REAL_TRADING", raising=False)

        result = runner.invoke(
            cli,
            ["trade", "start", "--asset", "stock", "--live", "--yes-live"],
        )

        assert result.exit_code == 1
        assert "--yes-live requires KIS_REAL_TRADING=true" in result.output


class TestHealthCommand:
    """Test health command."""

    def test_health_no_server(self, runner):
        """Test health command when server not running."""
        from cli.main import cli

        result = runner.invoke(cli, ["health"])
        # Should show connection error or not installed
        assert result.exit_code in (0, 1)
