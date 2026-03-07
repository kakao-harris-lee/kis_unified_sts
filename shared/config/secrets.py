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

    @classmethod
    def _domain_fallback(
        cls,
        domain: Optional[Domain],
        domain_key_map: dict[str, str],
        legacy_key: str,
    ) -> Optional[str]:
        """Return domain-specific secret with legacy fallback."""
        if domain and domain in domain_key_map:
            return cls.get(domain_key_map[domain]) or cls.get(legacy_key)
        return cls.get(legacy_key)

    @classmethod
    def _domain_value(
        cls,
        domain: Optional[Domain],
        domain_key_map: dict[str, str],
        legacy_key: str,
        default: str,
    ) -> str:
        """Return domain-specific value with default."""
        if domain and domain in domain_key_map:
            return cls.get(domain_key_map[domain], default)
        return cls.get(legacy_key, default)

    # =========================================================================
    # Telegram
    # =========================================================================

    @classmethod
    def telegram_token(cls, domain: Optional[Domain] = None) -> Optional[str]:
        """Get Telegram bot token.

        Args:
            domain: "stock", "futures", "briefing", or None for legacy
        """
        return cls._domain_fallback(
            domain,
            {
                "stock": "TELEGRAM_STOCK_BOT_TOKEN",
                "futures": "TELEGRAM_FUTURES_BOT_TOKEN",
                "briefing": "TELEGRAM_BRIEFING_BOT_TOKEN",
            },
            "TELEGRAM_BOT_TOKEN",
        )

    @classmethod
    def telegram_chat_id(cls, domain: Optional[Domain] = None) -> Optional[str]:
        """Get Telegram chat ID.

        Args:
            domain: "stock", "futures", "briefing", or None for legacy
        """
        return cls._domain_fallback(
            domain,
            {
                "stock": "TELEGRAM_STOCK_CHAT_ID",
                "futures": "TELEGRAM_FUTURES_CHAT_ID",
                "briefing": "TELEGRAM_BRIEFING_CHAT_ID",
            },
            "TELEGRAM_CHAT_ID",
        )

    # =========================================================================
    # KIS API
    # =========================================================================

    @classmethod
    def kis_app_key(cls, domain: Optional[Domain] = None) -> Optional[str]:
        """Get KIS API app key.

        Args:
            domain: "stock", "futures", or None for legacy
        """
        return cls._domain_fallback(
            domain,
            {
                "stock": "KIS_STOCK_APP_KEY",
                "futures": "KIS_FUTURES_APP_KEY",
            },
            "KIS_APP_KEY",
        )

    @classmethod
    def kis_app_secret(cls, domain: Optional[Domain] = None) -> Optional[str]:
        """Get KIS API app secret.

        Args:
            domain: "stock", "futures", or None for legacy
        """
        return cls._domain_fallback(
            domain,
            {
                "stock": "KIS_STOCK_APP_SECRET",
                "futures": "KIS_FUTURES_APP_SECRET",
            },
            "KIS_APP_SECRET",
        )

    @classmethod
    def kis_account_no(cls, domain: Optional[Domain] = None) -> Optional[str]:
        """Get KIS account number.

        Args:
            domain: "stock", "futures", or None for legacy
        """
        return cls._domain_fallback(
            domain,
            {
                "stock": "KIS_STOCK_ACCOUNT_NO",
                "futures": "KIS_FUTURES_ACCOUNT_NO",
            },
            "KIS_ACCOUNT_NO",
        )

    @classmethod
    def kis_market(cls, domain: Optional[Domain] = None) -> str:
        """Get KIS market type (real/mock).

        Args:
            domain: "stock", "futures", or None for legacy
        """
        return cls._domain_value(
            domain,
            {
                "stock": "KIS_STOCK_MARKET",
                "futures": "KIS_FUTURES_MARKET",
            },
            "KIS_MARKET",
            "mock",
        )

    # =========================================================================
    # Database
    # =========================================================================

    @classmethod
    def redis_url(cls, domain: Optional[Domain] = None) -> str:
        """Get Redis URL.

        Args:
            domain: "stock", "futures", or None for system/default

        Returns:
            Redis URL with rediss:// scheme if TLS enabled, redis:// otherwise
        """
        host = cls.get("REDIS_HOST", "localhost")
        port = cls.get("REDIS_PORT", "6379")
        password = cls.get("REDIS_PASSWORD", "")
        tls_enabled = cls.get("REDIS_TLS_ENABLED", "false").lower() == "true"

        if domain == "stock":
            db = cls.get("REDIS_STOCK_DB", "1")
        elif domain == "futures":
            db = cls.get("REDIS_FUTURES_DB", "2")
        else:
            db = cls.get("REDIS_SYSTEM_DB", "1")

        # Use rediss:// scheme for TLS, redis:// for non-TLS
        scheme = "rediss" if tls_enabled else "redis"

        if password:
            return f"{scheme}://:{password}@{host}:{port}/{db}"
        return f"{scheme}://{host}:{port}/{db}"

    @classmethod
    def clickhouse_database(cls, domain: Optional[Domain] = None) -> str:
        """Get ClickHouse database name.

        Args:
            domain: "stock", "futures", or None for default
        """
        return cls._domain_value(
            domain,
            {
                "stock": "CLICKHOUSE_STOCK_DATABASE",
                "futures": "CLICKHOUSE_FUTURES_DATABASE",
            },
            "CLICKHOUSE_DATABASE",
            "default",
        )

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
