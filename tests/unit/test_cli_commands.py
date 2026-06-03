"""Test CLI commands."""

from datetime import date, datetime

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
        assert "export-clickhouse" in result.output
        assert "validate-parquet" in result.output


class TestBacktestCommands:
    """Test backtest commands."""

    def test_backtest_list(self, runner):
        """Test backtest list command."""
        from cli.main import cli

        result = runner.invoke(cli, ["backtest", "list"])
        # May succeed or fail depending on config directory
        assert result.exit_code in (0, 1)


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

    def test_export_clickhouse_minute_end_date_is_exclusive_next_day(
        self, runner, monkeypatch, tmp_path
    ):
        """Minute export should include the full --end date."""
        import clickhouse_driver

        from cli.main import cli

        captured = {}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def execute(self, query, params):
                captured["query"] = query
                captured["params"] = params
                return [
                    (
                        "005930",
                        datetime(2026, 6, 3, 9, 0),
                        71000.0,
                        71100.0,
                        70900.0,
                        71050.0,
                        1000,
                    )
                ]

        monkeypatch.setattr(clickhouse_driver, "Client", FakeClient)

        result = runner.invoke(
            cli,
            [
                "data",
                "export-clickhouse",
                "--asset",
                "stock",
                "--database",
                "market",
                "--timeframe",
                "minute",
                "--start",
                "2026-06-03",
                "--end",
                "2026-06-03",
                "--out",
                str(tmp_path / "market"),
            ],
        )

        assert result.exit_code == 0
        assert "datetime < %(end_exclusive)s" in captured["query"]
        assert captured["params"]["start"] == datetime(2026, 6, 3)
        assert captured["params"]["end_exclusive"] == datetime(2026, 6, 4)
        assert "end" not in captured["params"]

    def test_export_clickhouse_daily_end_date_stays_inclusive(
        self, runner, monkeypatch, tmp_path
    ):
        """Daily export keeps inclusive date filtering."""
        import clickhouse_driver

        from cli.main import cli

        captured = {}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def execute(self, query, params):
                captured["query"] = query
                captured["params"] = params
                return [
                    (
                        "005930",
                        date(2026, 6, 3),
                        71000.0,
                        71100.0,
                        70900.0,
                        71050.0,
                        1000,
                    )
                ]

        monkeypatch.setattr(clickhouse_driver, "Client", FakeClient)

        result = runner.invoke(
            cli,
            [
                "data",
                "export-clickhouse",
                "--asset",
                "stock",
                "--database",
                "market",
                "--timeframe",
                "daily",
                "--start",
                "2026-06-03",
                "--end",
                "2026-06-03",
                "--out",
                str(tmp_path / "market"),
            ],
        )

        assert result.exit_code == 0
        assert "date <= %(end)s" in captured["query"]
        assert captured["params"]["start"] == date(2026, 6, 3)
        assert captured["params"]["end"] == date(2026, 6, 3)
        assert "end_exclusive" not in captured["params"]


class TestTradeCommands:
    """Test trade commands."""

    def test_trade_status(self, runner, mocker):
        """Test trade status command shows 'not running' when no server."""
        from cli.main import cli

        mocker.patch("httpx.get", side_effect=ConnectionError("no server"))
        result = runner.invoke(cli, ["trade", "status"])
        assert result.exit_code == 0
        assert "Status" in result.output


class TestHealthCommand:
    """Test health command."""

    def test_health_no_server(self, runner):
        """Test health command when server not running."""
        from cli.main import cli

        result = runner.invoke(cli, ["health"])
        # Should show connection error or not installed
        assert result.exit_code in (0, 1)
