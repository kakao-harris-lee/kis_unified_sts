"""Test paper trading CLI commands."""
from click.testing import CliRunner


def test_paper_start_command():
    """Test paper start command exists."""
    from cli.main import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["paper", "--help"])

    assert result.exit_code == 0
    assert "start" in result.output
    assert "status" in result.output


def test_paper_status_command():
    """Test paper status command."""
    from cli.main import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["paper", "status"])

    assert result.exit_code == 0
