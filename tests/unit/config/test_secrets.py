"""Tests for secrets management module."""

import os

import pytest
from pydantic import BaseModel


class _TelegramCredentialsConfig(BaseModel):
    """Local stand-in for the removed ``shared.alerts.models.AlertConfig``.

    Only exists to exercise ``SecretsManager`` credential loading through a
    ``from_env``-style entry point; it is not a production model.
    """

    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    rate_limit_seconds: int = 60

    @classmethod
    def from_env(cls, **overrides: object) -> "_TelegramCredentialsConfig":
        from shared.config.secrets import SecretsManager

        return cls(
            telegram_token=overrides.get(
                "telegram_token", SecretsManager.telegram_token()
            ),
            telegram_chat_id=overrides.get(
                "telegram_chat_id", SecretsManager.telegram_chat_id()
            ),
            rate_limit_seconds=overrides.get("rate_limit_seconds", 60),
        )


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
    """Test a from_env()-style config loads credentials from environment."""
    from shared.config.secrets import SecretsManager

    SecretsManager.clear_cache()
    os.environ["TELEGRAM_BOT_TOKEN"] = "test_token"
    os.environ["TELEGRAM_CHAT_ID"] = "123456"

    try:
        config = _TelegramCredentialsConfig.from_env()
        assert config.telegram_token == "test_token"
        assert config.telegram_chat_id == "123456"
    finally:
        del os.environ["TELEGRAM_BOT_TOKEN"]
        del os.environ["TELEGRAM_CHAT_ID"]
        SecretsManager.clear_cache()


def test_alert_config_from_env_with_overrides():
    """Test a from_env()-style config accepts overrides."""
    from shared.config.secrets import SecretsManager

    SecretsManager.clear_cache()
    os.environ["TELEGRAM_BOT_TOKEN"] = "env_token"

    try:
        config = _TelegramCredentialsConfig.from_env(
            telegram_token="override_token",
            rate_limit_seconds=30,
        )
        assert config.telegram_token == "override_token"
        assert config.rate_limit_seconds == 30
    finally:
        del os.environ["TELEGRAM_BOT_TOKEN"]
        SecretsManager.clear_cache()
