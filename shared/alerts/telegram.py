"""Telegram alert service."""
import logging
import re
from datetime import UTC, datetime
from typing import Optional

from shared.http import AsyncSessionMixin

from .models import Alert, AlertConfig, AlertLevel

logger = logging.getLogger(__name__)

# Telegram API base URL (token appended at runtime)
_TELEGRAM_API_BASE = "https://api.telegram.org/bot"


class TelegramAlertService(AsyncSessionMixin):
    """Send alerts via Telegram.

    Features:
    - Formatted messages with emojis
    - Rate limiting
    - Async sending
    - Persistent HTTP session for connection reuse
    """

    LEVEL_EMOJIS = {
        AlertLevel.INFO: "\u2139\ufe0f",      # ℹ️
        AlertLevel.WARNING: "\u26a0\ufe0f",   # ⚠️
        AlertLevel.CRITICAL: "\U0001f6a8",    # 🚨
    }

    def __init__(self, config: AlertConfig):
        self.config = config
        self._last_sent: Optional[datetime] = None
        self._enabled = bool(config.telegram_token and config.telegram_chat_id)

    @property
    def is_enabled(self) -> bool:
        """Check if service is enabled."""
        return self._enabled

    @staticmethod
    def _escape_markdown(text: str) -> str:
        """Escape Markdown special characters to prevent injection.

        Args:
            text: Raw text that may contain Markdown special chars

        Returns:
            Escaped text safe for Telegram Markdown
        """
        # Telegram Markdown v1 special characters: _ * ` [
        escape_chars = r"_*`["
        return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

    async def close(self) -> None:
        """Close the HTTP session."""
        await self._close_session()

    def _format_message(self, alert: Alert) -> str:
        """Format alert for Telegram.

        Note: User input (title, message, source) is escaped to prevent
        Markdown injection attacks.
        """
        level_text = self.LEVEL_EMOJIS.get(alert.level, "Alert")
        timestamp = alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # Escape user-controlled content to prevent Markdown injection
        safe_title = self._escape_markdown(alert.title)
        safe_message = self._escape_markdown(alert.message)
        safe_source = self._escape_markdown(alert.source)

        return (
            f"[{level_text}] *{safe_title}*\n\n"
            f"{safe_message}\n\n"
            f"_{timestamp}_ | `{safe_source}`"
        )

    def _should_send(self, alert: Alert) -> bool:
        """Check if alert should be sent (rate limiting)."""
        # Check rate limit
        if self._last_sent:
            now = datetime.now(UTC)
            elapsed = (now - self._last_sent).total_seconds()
            if elapsed < self.config.rate_limit_seconds:
                # Allow critical alerts to bypass rate limit
                if alert.level != AlertLevel.CRITICAL:
                    return False

        return True

    async def send(self, alert: Alert) -> bool:
        """Send alert via Telegram.

        Returns:
            True if sent successfully, False otherwise

        Note:
            Token is never logged to prevent exposure in log files.
        """
        if not self._enabled:
            logger.debug("Telegram alerts disabled")
            return False

        if not self._should_send(alert):
            logger.debug(f"Alert skipped (rate limit or level): {alert.title}")
            return False

        # Build URL with token (never log this URL)
        url = f"{_TELEGRAM_API_BASE}{self.config.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.config.telegram_chat_id,
            "text": self._format_message(alert),
            "parse_mode": "Markdown",
        }

        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    self._last_sent = datetime.now(UTC)
                    alert.sent = True
                    logger.info(f"Alert sent: {alert.title}")
                    return True
                else:
                    # Log status without URL to prevent token exposure
                    logger.error(f"Telegram API error: status={resp.status}")
                    return False
        except Exception as e:
            # Sanitize error message to prevent token leak
            error_msg = str(e)
            if self.config.telegram_token and self.config.telegram_token in error_msg:
                error_msg = error_msg.replace(
                    self.config.telegram_token, "[REDACTED]"
                )
            logger.error(f"Failed to send alert: {error_msg}")
            return False
