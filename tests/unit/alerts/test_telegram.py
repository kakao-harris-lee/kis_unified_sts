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

    # Should contain emoji for warning level
    assert "\u26a0" in formatted  # Warning emoji
    assert "Test Alert" in formatted
    assert "This is a test" in formatted


@pytest.mark.asyncio
async def test_telegram_emoji_mapping():
    """Test that all alert levels have correct emoji mappings."""
    from shared.alerts.telegram import TelegramAlertService
    from shared.alerts.models import AlertLevel

    # Verify all levels are mapped
    assert AlertLevel.INFO in TelegramAlertService.LEVEL_EMOJIS
    assert AlertLevel.WARNING in TelegramAlertService.LEVEL_EMOJIS
    assert AlertLevel.CRITICAL in TelegramAlertService.LEVEL_EMOJIS

    # Verify emojis are actual Unicode characters, not text
    info_emoji = TelegramAlertService.LEVEL_EMOJIS[AlertLevel.INFO]
    warning_emoji = TelegramAlertService.LEVEL_EMOJIS[AlertLevel.WARNING]
    critical_emoji = TelegramAlertService.LEVEL_EMOJIS[AlertLevel.CRITICAL]

    # Should be short Unicode sequences, not words
    assert len(info_emoji) <= 3  # emoji + variation selector
    assert len(warning_emoji) <= 3
    assert len(critical_emoji) <= 3

    # Should not be plain text words
    assert info_emoji.lower() != "info"
    assert warning_emoji.lower() != "warning"
    assert critical_emoji.lower() != "critical"


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
