"""Test order execution configuration."""
import pytest


def test_execution_config_creation():
    """Test ExecutionConfig creation."""
    from shared.execution.config import ExecutionConfig

    config = ExecutionConfig(
        trading_mode="MOCK",
        max_retries=3,
        retry_delay=1.0,
    )

    assert config.trading_mode == "MOCK"
    assert config.max_retries == 3


def test_execution_config_modes():
    """Test valid trading modes."""
    from shared.execution.config import ExecutionConfig, TradingMode

    assert TradingMode.PAPER.value == "PAPER"
    assert TradingMode.MOCK.value == "MOCK"
    assert TradingMode.REAL.value == "REAL"


def test_execution_config_defaults():
    """Test default configuration."""
    from shared.execution.config import ExecutionConfig

    config = ExecutionConfig()

    assert config.trading_mode == "PAPER"
    assert config.max_retries == 3
