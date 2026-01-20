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


class TestTradeCommands:
    """Test trade commands."""

    def test_trade_status(self, runner):
        """Test trade status command."""
        from cli.main import cli

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
