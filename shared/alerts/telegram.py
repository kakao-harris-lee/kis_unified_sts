"""Telegram alert service."""
import logging
from datetime import datetime
from typing import Optional

import aiohttp

from .models import Alert, AlertLevel, AlertConfig

logger = logging.getLogger(__name__)


class TelegramAlertService:
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
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def is_enabled(self) -> bool:
        """Check if service is enabled."""
        return self._enabled

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create persistent HTTP session.

        Reuses existing session for connection pooling and better performance.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the HTTP session.

        Should be called when the service is being shut down
        to properly release resources.
        """
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _format_message(self, alert: Alert) -> str:
        """Format alert for Telegram."""
        level_text = self.LEVEL_EMOJIS.get(alert.level, "Alert")
        timestamp = alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")

        return (
            f"[{level_text}] *{alert.title}*\n\n"
            f"{alert.message}\n\n"
            f"_{timestamp}_ | `{alert.source}`"
        )

    def _should_send(self, alert: Alert) -> bool:
        """Check if alert should be sent (rate limiting)."""
        # Check rate limit
        if self._last_sent:
            elapsed = (datetime.now() - self._last_sent).total_seconds()
            if elapsed < self.config.rate_limit_seconds:
                # Allow critical alerts to bypass rate limit
                if alert.level != AlertLevel.CRITICAL:
                    return False

        return True

    async def send(self, alert: Alert) -> bool:
        """Send alert via Telegram.

        Returns:
            True if sent successfully, False otherwise
        """
        if not self._enabled:
            logger.debug("Telegram alerts disabled")
            return False

        if not self._should_send(alert):
            logger.debug(f"Alert skipped (rate limit or level): {alert.title}")
            return False

        url = f"https://api.telegram.org/bot{self.config.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.config.telegram_chat_id,
            "text": self._format_message(alert),
            "parse_mode": "Markdown",
        }

        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    self._last_sent = datetime.now()
                    alert.sent = True
                    logger.info(f"Alert sent: {alert.title}")
                    return True
                else:
                    logger.error(f"Telegram API error: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False
