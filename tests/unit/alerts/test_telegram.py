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


@pytest.mark.asyncio
async def test_telegram_session_lifecycle():
    """Test session creation and closure."""
    from shared.alerts.telegram import TelegramAlertService
    from shared.alerts.models import AlertConfig

    config = AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="123456",
    )
    service = TelegramAlertService(config)

    # Initially no session
    assert service._session is None

    # Get session creates one
    session = await service._get_session()
    assert session is not None
    assert service._session is session

    # Getting again returns same session
    session2 = await service._get_session()
    assert session2 is session

    # Close cleans up
    await service.close()
    assert service._session is None


@pytest.mark.asyncio
async def test_telegram_session_reuse():
    """Test that session is reused across multiple sends."""
    from shared.alerts.telegram import TelegramAlertService
    from shared.alerts.models import Alert, AlertLevel, AlertConfig
    from unittest.mock import MagicMock

    config = AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="123456",
    )
    service = TelegramAlertService(config)

    # Create mock session
    mock_response = MagicMock()
    mock_response.status = 200

    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__.return_value = mock_response

    mock_session = MagicMock()
    mock_session.post.return_value = mock_post_cm
    mock_session.closed = False

    # Inject mock session
    service._session = mock_session

    # Send multiple alerts
    for i in range(3):
        alert = Alert(
            level=AlertLevel.CRITICAL,  # Bypass rate limit
            title=f"Alert {i}",
            message="Test",
            timestamp=datetime.now(),
        )
        await service.send(alert)

    # Same session should have been used for all
    assert mock_session.post.call_count == 3


@pytest.mark.asyncio
async def test_telegram_close_already_closed():
    """Test closing an already closed session is safe."""
    from shared.alerts.telegram import TelegramAlertService
    from shared.alerts.models import AlertConfig

    config = AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="123456",
    )
    service = TelegramAlertService(config)

    # Close without ever creating session
    await service.close()
    assert service._session is None

    # Close again should be safe
    await service.close()
    assert service._session is None
