"""Tests for secrets management module."""
import os

import pytest


def test_secrets_manager_get_from_env():
    """Test getting secret from environment variable."""
    from shared.config.secrets import SecretsManager

    # Clear cache before test
    SecretsManager.clear_cache()

    # Set test env var
    os.environ["TEST_SECRET_KEY"] = "test_value"

    try:
        value = SecretsManager.get("TEST_SECRET_KEY")
        assert value == "test_value"
    finally:
        del os.environ["TEST_SECRET_KEY"]
        SecretsManager.clear_cache()


def test_secrets_manager_get_default():
    """Test getting default when env var not set."""
    from shared.config.secrets import SecretsManager

    SecretsManager.clear_cache()

    value = SecretsManager.get("NONEXISTENT_KEY", "default_value")
    assert value == "default_value"
    SecretsManager.clear_cache()


def test_secrets_manager_get_none():
    """Test getting None when env var not set and no default."""
    from shared.config.secrets import SecretsManager

    SecretsManager.clear_cache()

    value = SecretsManager.get("NONEXISTENT_KEY_NO_DEFAULT")
    assert value is None
    SecretsManager.clear_cache()


def test_require_secret_raises():
    """Test require_secret raises when env var not set."""
    from shared.config.secrets import SecretsManager, require_secret

    SecretsManager.clear_cache()

    with pytest.raises(EnvironmentError) as exc_info:
        require_secret("REQUIRED_BUT_MISSING")

    assert "REQUIRED_BUT_MISSING" in str(exc_info.value)
    SecretsManager.clear_cache()


def test_require_secret_returns_value():
    """Test require_secret returns value when set."""
    from shared.config.secrets import SecretsManager, require_secret

    SecretsManager.clear_cache()
    os.environ["REQUIRED_SECRET"] = "secret_value"

    try:
        value = require_secret("REQUIRED_SECRET")
        assert value == "secret_value"
    finally:
        del os.environ["REQUIRED_SECRET"]
        SecretsManager.clear_cache()


def test_telegram_token_helper():
    """Test telegram token helper method."""
    from shared.config.secrets import SecretsManager

    SecretsManager.clear_cache()
    os.environ["TELEGRAM_BOT_TOKEN"] = "bot12345:ABC"

    try:
        token = SecretsManager.telegram_token()
        assert token == "bot12345:ABC"
    finally:
        del os.environ["TELEGRAM_BOT_TOKEN"]
        SecretsManager.clear_cache()


def test_alert_config_from_env():
    """Test AlertConfig.from_env() loads credentials from environment."""
    from shared.alerts.models import AlertConfig
    from shared.config.secrets import SecretsManager

    SecretsManager.clear_cache()
    os.environ["TELEGRAM_BOT_TOKEN"] = "test_token"
    os.environ["TELEGRAM_CHAT_ID"] = "123456"

    try:
        config = AlertConfig.from_env()
        assert config.telegram_token == "test_token"
        assert config.telegram_chat_id == "123456"
    finally:
        del os.environ["TELEGRAM_BOT_TOKEN"]
        del os.environ["TELEGRAM_CHAT_ID"]
        SecretsManager.clear_cache()


def test_alert_config_from_env_with_overrides():
    """Test AlertConfig.from_env() accepts overrides."""
    from shared.alerts.models import AlertConfig
    from shared.config.secrets import SecretsManager

    SecretsManager.clear_cache()
    os.environ["TELEGRAM_BOT_TOKEN"] = "env_token"

    try:
        config = AlertConfig.from_env(
            telegram_token="override_token",
            rate_limit_seconds=30,
        )
        assert config.telegram_token == "override_token"
        assert config.rate_limit_seconds == 30
    finally:
        del os.environ["TELEGRAM_BOT_TOKEN"]
        SecretsManager.clear_cache()
