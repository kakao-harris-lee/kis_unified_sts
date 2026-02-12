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
    from shared.execution.config import TradingMode

    assert TradingMode.PAPER.value == "PAPER"
    assert TradingMode.MOCK.value == "MOCK"
    assert TradingMode.REAL.value == "REAL"


def test_execution_config_defaults():
    """Test default configuration."""
    from shared.execution.config import ExecutionConfig

    config = ExecutionConfig()

    assert config.trading_mode == "PAPER"
    assert config.max_retries == 3


def test_account_no_validation_valid():
    """Test valid account number passes validation."""
    from shared.execution.config import ExecutionConfig

    config = ExecutionConfig(account_no="1234567890")
    assert config.account_no == "1234567890"


def test_account_no_validation_empty():
    """Test empty account number is allowed (for PAPER mode)."""
    from shared.execution.config import ExecutionConfig

    config = ExecutionConfig(account_no="")
    assert config.account_no == ""


def test_account_no_validation_invalid_length():
    """Test invalid account number (wrong length) raises error."""
    from shared.execution.config import ExecutionConfig
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        ExecutionConfig(account_no="12345")

    assert "10 digits" in str(exc_info.value)


def test_account_no_validation_invalid_characters():
    """Test invalid account number (non-digits) raises error."""
    from shared.execution.config import ExecutionConfig
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        ExecutionConfig(account_no="123456789a")

    assert "10 digits" in str(exc_info.value)


def test_rate_limit_config_fields():
    """Test rate limit configuration fields."""
    from shared.execution.config import ExecutionConfig

    config = ExecutionConfig(
        redis_url="redis://localhost:6379",
        rate_limit_key="stock",
        requests_per_second=20.0,
        rate_limit_timeout=5.0,
        rate_limit_initial_delay=0.05,
        rate_limit_max_delay=0.2,
        rate_limit_backoff_multiplier=1.5,
        metrics_cache_ttl=1.0,
    )

    assert config.redis_url == "redis://localhost:6379"
    assert config.rate_limit_key == "stock"
    assert config.requests_per_second == 20.0
    assert config.rate_limit_initial_delay == 0.05
    assert config.metrics_cache_ttl == 1.0


def test_kis_api_config_fields():
    """Test KIS API configuration fields."""
    from shared.execution.config import ExecutionConfig

    config = ExecutionConfig()

    # Check default values
    assert "openapivts.koreainvestment.com" in config.kis_mock_base_url
    assert "openapi.koreainvestment.com" in config.kis_real_base_url
    assert config.tr_code_buy_mock == "VTTC0802U"
    assert config.tr_code_buy_real == "TTTC0802U"
    assert config.tr_code_sell_mock == "VTTC0801U"
    assert config.tr_code_sell_real == "TTTC0801U"
