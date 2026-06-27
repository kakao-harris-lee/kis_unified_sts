"""Alert models."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class AlertLevel(StrEnum):
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
    metadata: dict | None = None
    sent: bool = False


@dataclass
class AlertConfig:
    """Alert service configuration.

    Credentials should be loaded from environment variables for security.
    Use AlertConfig.from_env() to automatically load credentials.
    """
    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    email_smtp_host: str | None = None
    email_smtp_port: int = 587
    email_username: str | None = None
    email_password: str | None = None
    email_recipients: list[str] = field(default_factory=list)
    min_level: AlertLevel = AlertLevel.WARNING
    rate_limit_seconds: int = 60

    @classmethod
    def from_env(
        cls, *, domain: str | None = None, **overrides
    ) -> "AlertConfig":
        """Create config loading credentials from environment variables.

        Args:
            domain: ``"stock"`` / ``"futures"`` / ``"briefing"`` to read
                domain-specific Telegram credentials (TELEGRAM_<DOMAIN>_*).
                Strict — no legacy fallback to TELEGRAM_BOT_TOKEN, since
                this repo's ``.env`` aliases the legacy keys to the stock
                channel and that would silently leak futures/briefing
                messages.  Pass ``None`` only for legacy single-domain
                deployments.
            **overrides: Override any field (e.g., rate_limit_seconds=30)

        Returns:
            AlertConfig with credentials loaded from environment.
        """
        from shared.config.secrets import SecretsManager
        from shared.notification.telegram import resolve_domain_credentials

        if domain is not None:
            tok, chat = resolve_domain_credentials(domain)
        else:
            tok = SecretsManager.telegram_token()
            chat = SecretsManager.telegram_chat_id()

        return cls(
            telegram_token=overrides.get("telegram_token", tok),
            telegram_chat_id=overrides.get("telegram_chat_id", chat),
            email_smtp_host=overrides.get("email_smtp_host"),
            email_smtp_port=overrides.get("email_smtp_port", 587),
            email_username=overrides.get("email_username"),
            email_password=overrides.get("email_password", SecretsManager.email_password()),
            email_recipients=overrides.get("email_recipients", []),
            min_level=overrides.get("min_level", AlertLevel.WARNING),
            rate_limit_seconds=overrides.get("rate_limit_seconds", 60),
        )
