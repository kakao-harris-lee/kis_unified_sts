"""Test TelegramAlertService."""
from datetime import datetime
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_telegram_format_message():
    """Test message formatting."""
    from shared.alerts.models import Alert, AlertConfig, AlertLevel
    from shared.alerts.telegram import TelegramAlertService

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
    from shared.alerts.models import AlertLevel
    from shared.alerts.telegram import TelegramAlertService

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
    from shared.alerts.models import Alert, AlertConfig, AlertLevel
    from shared.alerts.telegram import TelegramAlertService

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
    from shared.alerts.models import AlertConfig
    from shared.alerts.telegram import TelegramAlertService

    config = AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="123456",
    )
    service = TelegramAlertService(config)

    # Initially no session (attribute doesn't exist yet - use property check)
    assert not service._session_active

    # Get session creates one
    session = await service._get_session()
    assert session is not None
    assert service._session is session

    # Getting again returns same session
    session2 = await service._get_session()
    assert session2 is session

    # Close cleans up
    await service.close()
    assert not service._session_active


@pytest.mark.asyncio
async def test_telegram_session_reuse():
    """Test that session is reused across multiple sends."""
    from unittest.mock import MagicMock

    from shared.alerts.models import Alert, AlertConfig, AlertLevel
    from shared.alerts.telegram import TelegramAlertService

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
    from shared.alerts.models import AlertConfig
    from shared.alerts.telegram import TelegramAlertService

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


@pytest.mark.asyncio
async def test_telegram_rate_limiting_blocks_second_alert():
    """Test that rate limiting blocks alerts within the limit window."""
    from unittest.mock import MagicMock

    from shared.alerts.models import Alert, AlertConfig, AlertLevel
    from shared.alerts.telegram import TelegramAlertService

    config = AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="123456",
        rate_limit_seconds=60,  # 60 second rate limit
    )
    service = TelegramAlertService(config)

    # Create mock session for successful send
    mock_response = MagicMock()
    mock_response.status = 200

    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__.return_value = mock_response

    mock_session = MagicMock()
    mock_session.post.return_value = mock_post_cm
    mock_session.closed = False
    service._session = mock_session

    # First alert (WARNING level) should send
    alert1 = Alert(
        level=AlertLevel.WARNING,
        title="First Alert",
        message="Test",
        timestamp=datetime.now(),
    )
    result1 = await service.send(alert1)
    assert result1 is True
    assert mock_session.post.call_count == 1

    # Second alert (WARNING level) should be blocked by rate limit
    alert2 = Alert(
        level=AlertLevel.WARNING,
        title="Second Alert",
        message="Test",
        timestamp=datetime.now(),
    )
    result2 = await service.send(alert2)
    assert result2 is False
    # Post should not have been called again
    assert mock_session.post.call_count == 1


@pytest.mark.asyncio
async def test_telegram_critical_bypasses_rate_limit():
    """Test that CRITICAL alerts bypass rate limiting."""
    from unittest.mock import MagicMock

    from shared.alerts.models import Alert, AlertConfig, AlertLevel
    from shared.alerts.telegram import TelegramAlertService

    config = AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="123456",
        rate_limit_seconds=60,
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
    service._session = mock_session

    # First alert (WARNING) should send
    alert1 = Alert(
        level=AlertLevel.WARNING,
        title="First Alert",
        message="Test",
        timestamp=datetime.now(),
    )
    result1 = await service.send(alert1)
    assert result1 is True

    # Second alert (CRITICAL) should bypass rate limit
    alert2 = Alert(
        level=AlertLevel.CRITICAL,
        title="Critical Alert",
        message="Emergency!",
        timestamp=datetime.now(),
    )
    result2 = await service.send(alert2)
    assert result2 is True
    # Post should have been called twice
    assert mock_session.post.call_count == 2


@pytest.mark.asyncio
async def test_telegram_info_level_rate_limited():
    """Test that INFO level alerts are subject to rate limiting."""
    from unittest.mock import MagicMock

    from shared.alerts.models import Alert, AlertConfig, AlertLevel
    from shared.alerts.telegram import TelegramAlertService

    config = AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="123456",
        rate_limit_seconds=60,
    )
    service = TelegramAlertService(config)

    mock_response = MagicMock()
    mock_response.status = 200

    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__.return_value = mock_response

    mock_session = MagicMock()
    mock_session.post.return_value = mock_post_cm
    mock_session.closed = False
    service._session = mock_session

    # First INFO alert should send
    alert1 = Alert(
        level=AlertLevel.INFO,
        title="Info 1",
        message="Test",
        timestamp=datetime.now(),
    )
    result1 = await service.send(alert1)
    assert result1 is True

    # Second INFO alert should be blocked
    alert2 = Alert(
        level=AlertLevel.INFO,
        title="Info 2",
        message="Test",
        timestamp=datetime.now(),
    )
    result2 = await service.send(alert2)
    assert result2 is False


@pytest.mark.asyncio
async def test_telegram_should_send_first_alert():
    """Test _should_send allows first alert without rate limit."""
    from shared.alerts.models import Alert, AlertConfig, AlertLevel
    from shared.alerts.telegram import TelegramAlertService

    config = AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="123456",
        rate_limit_seconds=60,
    )
    service = TelegramAlertService(config)

    alert = Alert(
        level=AlertLevel.WARNING,
        title="First Alert",
        message="Test",
        timestamp=datetime.now(),
    )

    # No _last_sent set, should allow
    assert service._should_send(alert) is True


@pytest.mark.asyncio
async def test_telegram_rate_limit_updates_last_sent():
    """Test that successful send updates _last_sent timestamp."""
    from unittest.mock import MagicMock

    from shared.alerts.models import Alert, AlertConfig, AlertLevel
    from shared.alerts.telegram import TelegramAlertService

    config = AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="123456",
    )
    service = TelegramAlertService(config)

    assert service._last_sent is None

    mock_response = MagicMock()
    mock_response.status = 200

    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__.return_value = mock_response

    mock_session = MagicMock()
    mock_session.post.return_value = mock_post_cm
    mock_session.closed = False
    service._session = mock_session

    alert = Alert(
        level=AlertLevel.WARNING,
        title="Test",
        message="Test",
        timestamp=datetime.now(),
    )

    await service.send(alert)

    # _last_sent should now be set
    assert service._last_sent is not None
    assert isinstance(service._last_sent, datetime)


@pytest.mark.asyncio
async def test_telegram_custom_rate_limit_seconds():
    """Test custom rate limit configuration."""
    from unittest.mock import MagicMock

    from shared.alerts.models import Alert, AlertConfig, AlertLevel
    from shared.alerts.telegram import TelegramAlertService

    # Very short rate limit
    config = AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="123456",
        rate_limit_seconds=1,  # 1 second rate limit
    )
    service = TelegramAlertService(config)

    mock_response = MagicMock()
    mock_response.status = 200

    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__.return_value = mock_response

    mock_session = MagicMock()
    mock_session.post.return_value = mock_post_cm
    mock_session.closed = False
    service._session = mock_session

    alert1 = Alert(
        level=AlertLevel.WARNING,
        title="Alert 1",
        message="Test",
        timestamp=datetime.now(),
    )
    result1 = await service.send(alert1)
    assert result1 is True

    # Immediately send second alert - should be blocked
    alert2 = Alert(
        level=AlertLevel.WARNING,
        title="Alert 2",
        message="Test",
        timestamp=datetime.now(),
    )
    result2 = await service.send(alert2)
    assert result2 is False


@pytest.mark.asyncio
async def test_telegram_failed_send_does_not_update_last_sent():
    """Test that failed sends do not update _last_sent timestamp."""
    from unittest.mock import MagicMock

    from shared.alerts.models import Alert, AlertConfig, AlertLevel
    from shared.alerts.telegram import TelegramAlertService

    config = AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="123456",
    )
    service = TelegramAlertService(config)

    mock_response = MagicMock()
    mock_response.status = 500  # Server error

    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__.return_value = mock_response

    mock_session = MagicMock()
    mock_session.post.return_value = mock_post_cm
    mock_session.closed = False
    service._session = mock_session

    alert = Alert(
        level=AlertLevel.WARNING,
        title="Test",
        message="Test",
        timestamp=datetime.now(),
    )

    result = await service.send(alert)

    assert result is False
    # _last_sent should NOT be updated on failure
    assert service._last_sent is None
