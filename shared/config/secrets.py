"""Secrets management - load from environment variables."""
import os
import logging
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class SecretsManager:
    """Load secrets from environment variables only.

    Security best practice: credentials should never be hardcoded
    or stored in configuration files. This class provides a clean
    interface for loading secrets from environment variables.

    Usage:
        token = SecretsManager.telegram_token()
        # or
        value = SecretsManager.get("MY_SECRET_KEY")
    """

    @staticmethod
    @lru_cache
    def get(key: str, default: Optional[str] = None) -> Optional[str]:
        """Get secret from environment.

        Args:
            key: Environment variable name
            default: Default value if not set

        Returns:
            Secret value or default
        """
        value = os.environ.get(key, default)
        if value is None:
            logger.warning(f"Secret {key} not found in environment")
        return value

    @classmethod
    def telegram_token(cls) -> Optional[str]:
        """Get Telegram bot token."""
        return cls.get("TELEGRAM_BOT_TOKEN")

    @classmethod
    def telegram_chat_id(cls) -> Optional[str]:
        """Get Telegram chat ID."""
        return cls.get("TELEGRAM_CHAT_ID")

    @classmethod
    def email_password(cls) -> Optional[str]:
        """Get email password."""
        return cls.get("EMAIL_PASSWORD")

    @classmethod
    def kis_app_key(cls) -> Optional[str]:
        """Get KIS API app key."""
        return cls.get("KIS_APP_KEY")

    @classmethod
    def kis_app_secret(cls) -> Optional[str]:
        """Get KIS API app secret."""
        return cls.get("KIS_APP_SECRET")

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the cached secrets (for testing)."""
        cls.get.cache_clear()


def require_secret(key: str) -> str:
    """Get secret or raise error if not set.

    Args:
        key: Environment variable name

    Returns:
        Secret value

    Raises:
        EnvironmentError: If secret is not set
    """
    value = SecretsManager.get(key)
    if value is None:
        raise EnvironmentError(f"Required secret {key} not set in environment")
    return value
