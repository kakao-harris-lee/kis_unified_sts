"""Secrets management - load from environment variables.

환경변수 구조:
- 공통: CLICKHOUSE_*, REDIS_*, MLFLOW_*
- 주식: KIS_STOCK_*, TELEGRAM_STOCK_*
- 선물: KIS_FUTURES_*, TELEGRAM_FUTURES_*
- LLM: OPENAI_*, KRX_*, TELEGRAM_BRIEFING_*
"""
import os
import logging
from typing import Literal, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

Domain = Literal["stock", "futures", "briefing"]


class SecretsManager:
    """Load secrets from environment variables only.

    Security best practice: credentials should never be hardcoded
    or stored in configuration files. This class provides a clean
    interface for loading secrets from environment variables.

    Supports domain-specific secrets (stock, futures, briefing).

    Usage:
        # Legacy (단일 계좌)
        token = SecretsManager.telegram_token()

        # Domain-specific (권장)
        stock_key = SecretsManager.kis_app_key("stock")
        futures_key = SecretsManager.kis_app_key("futures")
        briefing_token = SecretsManager.telegram_token("briefing")
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
            logger.debug(f"Secret {key} not found in environment")
        return value

    # =========================================================================
    # Telegram
    # =========================================================================

    @classmethod
    def telegram_token(cls, domain: Optional[Domain] = None) -> Optional[str]:
        """Get Telegram bot token.

        Args:
            domain: "stock", "futures", "briefing", or None for legacy
        """
        if domain == "stock":
            return cls.get("TELEGRAM_STOCK_BOT_TOKEN") or cls.get("TELEGRAM_BOT_TOKEN")
        elif domain == "futures":
            return cls.get("TELEGRAM_FUTURES_BOT_TOKEN") or cls.get("TELEGRAM_BOT_TOKEN")
        elif domain == "briefing":
            return cls.get("TELEGRAM_BRIEFING_BOT_TOKEN") or cls.get("TELEGRAM_BOT_TOKEN")
        return cls.get("TELEGRAM_BOT_TOKEN")

    @classmethod
    def telegram_chat_id(cls, domain: Optional[Domain] = None) -> Optional[str]:
        """Get Telegram chat ID.

        Args:
            domain: "stock", "futures", "briefing", or None for legacy
        """
        if domain == "stock":
            return cls.get("TELEGRAM_STOCK_CHAT_ID") or cls.get("TELEGRAM_CHAT_ID")
        elif domain == "futures":
            return cls.get("TELEGRAM_FUTURES_CHAT_ID") or cls.get("TELEGRAM_CHAT_ID")
        elif domain == "briefing":
            return cls.get("TELEGRAM_BRIEFING_CHAT_ID") or cls.get("TELEGRAM_CHAT_ID")
        return cls.get("TELEGRAM_CHAT_ID")

    # =========================================================================
    # KIS API
    # =========================================================================

    @classmethod
    def kis_app_key(cls, domain: Optional[Domain] = None) -> Optional[str]:
        """Get KIS API app key.

        Args:
            domain: "stock", "futures", or None for legacy
        """
        if domain == "stock":
            return cls.get("KIS_STOCK_APP_KEY") or cls.get("KIS_APP_KEY")
        elif domain == "futures":
            return cls.get("KIS_FUTURES_APP_KEY") or cls.get("KIS_APP_KEY")
        return cls.get("KIS_APP_KEY")

    @classmethod
    def kis_app_secret(cls, domain: Optional[Domain] = None) -> Optional[str]:
        """Get KIS API app secret.

        Args:
            domain: "stock", "futures", or None for legacy
        """
        if domain == "stock":
            return cls.get("KIS_STOCK_APP_SECRET") or cls.get("KIS_APP_SECRET")
        elif domain == "futures":
            return cls.get("KIS_FUTURES_APP_SECRET") or cls.get("KIS_APP_SECRET")
        return cls.get("KIS_APP_SECRET")

    @classmethod
    def kis_account_no(cls, domain: Optional[Domain] = None) -> Optional[str]:
        """Get KIS account number.

        Args:
            domain: "stock", "futures", or None for legacy
        """
        if domain == "stock":
            return cls.get("KIS_STOCK_ACCOUNT_NO") or cls.get("KIS_ACCOUNT_NO")
        elif domain == "futures":
            return cls.get("KIS_FUTURES_ACCOUNT_NO") or cls.get("KIS_ACCOUNT_NO")
        return cls.get("KIS_ACCOUNT_NO")

    @classmethod
    def kis_market(cls, domain: Optional[Domain] = None) -> str:
        """Get KIS market type (real/mock).

        Args:
            domain: "stock", "futures", or None for legacy
        """
        if domain == "stock":
            return cls.get("KIS_STOCK_MARKET", "mock")
        elif domain == "futures":
            return cls.get("KIS_FUTURES_MARKET", "mock")
        return cls.get("KIS_MARKET", "mock")

    # =========================================================================
    # Database
    # =========================================================================

    @classmethod
    def redis_url(cls, domain: Optional[Domain] = None) -> str:
        """Get Redis URL.

        Args:
            domain: "stock", "futures", or None for system/default
        """
        host = cls.get("REDIS_HOST", "localhost")
        port = cls.get("REDIS_PORT", "6379")
        password = cls.get("REDIS_PASSWORD", "")

        if domain == "stock":
            db = cls.get("REDIS_STOCK_DB", "1")
        elif domain == "futures":
            db = cls.get("REDIS_FUTURES_DB", "2")
        else:
            db = cls.get("REDIS_SYSTEM_DB", "0")

        if password:
            return f"redis://:{password}@{host}:{port}/{db}"
        return f"redis://{host}:{port}/{db}"

    @classmethod
    def clickhouse_database(cls, domain: Optional[Domain] = None) -> str:
        """Get ClickHouse database name.

        Args:
            domain: "stock", "futures", or None for default
        """
        if domain == "stock":
            return cls.get("CLICKHOUSE_STOCK_DATABASE", "market")
        elif domain == "futures":
            return cls.get("CLICKHOUSE_FUTURES_DATABASE", "kospi")
        return cls.get("CLICKHOUSE_DATABASE", "default")

    # =========================================================================
    # LLM
    # =========================================================================

    @classmethod
    def openai_api_key(cls) -> Optional[str]:
        """Get OpenAI API key."""
        return cls.get("OPENAI_API_KEY")

    @classmethod
    def krx_api_key(cls) -> Optional[str]:
        """Get KRX Open API key."""
        return cls.get("KRX_API_KEY")

    @classmethod
    def dart_api_key(cls) -> Optional[str]:
        """Get DART API key."""
        return cls.get("DART_API_KEY")

    @classmethod
    def llm_model(cls) -> str:
        """Get LLM model name."""
        return cls.get("LLM_MODEL", "gpt-4o-mini")

    @classmethod
    def llm_enabled(cls) -> bool:
        """Check if LLM analysis is enabled."""
        return cls.get("LLM_ANALYSIS_ENABLED", "true").lower() == "true"

    # =========================================================================
    # Legacy
    # =========================================================================

    @classmethod
    def email_password(cls) -> Optional[str]:
        """Get email password."""
        return cls.get("EMAIL_PASSWORD")

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
