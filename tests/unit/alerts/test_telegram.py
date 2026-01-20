"""Test TelegramAlertService."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_telegram_format_message():
    """Test message formatting."""
    from shared.alerts.telegram import TelegramAlertService
    from shared.alerts.models import Alert, AlertLevel, AlertConfig

    config = AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="123456",
    )
    service = TelegramAlertService(config)

    alert = Alert(
        level=AlertLevel.WARNING,
        title="Test Alert",
        message="This is a test",
        timestamp=datetime.now(),
    )

    formatted = service._format_message(alert)

    assert "Warning" in formatted or "warning" in formatted.lower()
    assert "Test Alert" in formatted
    assert "This is a test" in formatted


@pytest.mark.asyncio
async def test_telegram_send_disabled():
    """Test sending when disabled."""
    from shared.alerts.telegram import TelegramAlertService
    from shared.alerts.models import Alert, AlertLevel, AlertConfig

    config = AlertConfig()  # No token = disabled
    service = TelegramAlertService(config)

    alert = Alert(
        level=AlertLevel.WARNING,
        title="Test",
        message="Test",
        timestamp=datetime.now(),
    )

    result = await service.send(alert)
    assert result is False
