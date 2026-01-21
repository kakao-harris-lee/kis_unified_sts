"""Alert models."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List


class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Alert:
    """Alert message."""
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime
    source: str = "system"
    metadata: Optional[Dict] = None
    sent: bool = False


@dataclass
class AlertConfig:
    """Alert service configuration.

    Credentials should be loaded from environment variables for security.
    Use AlertConfig.from_env() to automatically load credentials.
    """
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    email_smtp_host: Optional[str] = None
    email_smtp_port: int = 587
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_recipients: List[str] = field(default_factory=list)
    min_level: AlertLevel = AlertLevel.WARNING
    rate_limit_seconds: int = 60

    @classmethod
    def from_env(cls, **overrides) -> "AlertConfig":
        """Create config loading credentials from environment variables.

        This is the recommended way to create AlertConfig for production.
        Credentials are loaded from:
        - TELEGRAM_BOT_TOKEN
        - TELEGRAM_CHAT_ID
        - EMAIL_PASSWORD

        Args:
            **overrides: Override any field (e.g., rate_limit_seconds=30)

        Returns:
            AlertConfig with credentials loaded from environment
        """
        from shared.config.secrets import SecretsManager

        return cls(
            telegram_token=overrides.get("telegram_token", SecretsManager.telegram_token()),
            telegram_chat_id=overrides.get("telegram_chat_id", SecretsManager.telegram_chat_id()),
            email_smtp_host=overrides.get("email_smtp_host"),
            email_smtp_port=overrides.get("email_smtp_port", 587),
            email_username=overrides.get("email_username"),
            email_password=overrides.get("email_password", SecretsManager.email_password()),
            email_recipients=overrides.get("email_recipients", []),
            min_level=overrides.get("min_level", AlertLevel.WARNING),
            rate_limit_seconds=overrides.get("rate_limit_seconds", 60),
        )
