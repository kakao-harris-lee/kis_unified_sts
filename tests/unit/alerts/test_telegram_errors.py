"""Test error handling in TelegramAlertService."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
import aiohttp

from shared.alerts.telegram import TelegramAlertService
from shared.alerts.models import Alert, AlertLevel, AlertConfig


@pytest.fixture
def alert_config():
    """Create test alert config."""
    return AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="123456",
    )


@pytest.fixture
def test_alert():
    """Create test alert."""
    return Alert(
        level=AlertLevel.WARNING,
        title="Test Alert",
        message="This is a test message",
        timestamp=datetime.now(),
        source="test",
    )


@pytest.mark.asyncio
async def test_telegram_http_500_error(alert_config, test_alert):
    """Test handling of HTTP 500 server errors."""
    service = TelegramAlertService(alert_config)

    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 500

        mock_session.post.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await service.send(test_alert)

        assert result is False


@pytest.mark.asyncio
async def test_telegram_http_401_unauthorized(alert_config, test_alert):
    """Test handling of unauthorized API errors."""
    service = TelegramAlertService(alert_config)

    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 401  # Unauthorized

        mock_session.post.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await service.send(test_alert)

        assert result is False


@pytest.mark.asyncio
async def test_telegram_http_429_rate_limited(alert_config, test_alert):
    """Test handling of rate limit errors from Telegram API."""
    service = TelegramAlertService(alert_config)

    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 429  # Too Many Requests

        mock_session.post.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await service.send(test_alert)

        assert result is False


@pytest.mark.asyncio
async def test_telegram_network_timeout(alert_config, test_alert):
    """Test handling of network timeouts."""
    service = TelegramAlertService(alert_config)

    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.side_effect = aiohttp.ClientTimeout()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await service.send(test_alert)

        assert result is False


@pytest.mark.asyncio
async def test_telegram_connection_error(alert_config, test_alert):
    """Test handling of connection errors."""
    service = TelegramAlertService(alert_config)

    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.side_effect = aiohttp.ClientConnectorError(
            connection_key=MagicMock(),
            os_error=OSError("Connection refused"),
        )
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await service.send(test_alert)

        assert result is False


@pytest.mark.asyncio
async def test_telegram_disabled_service(test_alert):
    """Test that disabled service returns False immediately."""
    # No token or chat_id
    config = AlertConfig()
    service = TelegramAlertService(config)

    assert service.is_enabled is False

    result = await service.send(test_alert)

    assert result is False


@pytest.mark.asyncio
async def test_telegram_empty_token(test_alert):
    """Test handling of empty token."""
    config = AlertConfig(
        telegram_token="",
        telegram_chat_id="123456",
    )
    service = TelegramAlertService(config)

    assert service.is_enabled is False


@pytest.mark.asyncio
async def test_telegram_empty_chat_id(test_alert):
    """Test handling of empty chat_id."""
    config = AlertConfig(
        telegram_token="test_token",
        telegram_chat_id="",
    )
    service = TelegramAlertService(config)

    assert service.is_enabled is False


@pytest.mark.asyncio
async def test_telegram_successful_send(alert_config, test_alert):
    """Test successful message sending."""
    service = TelegramAlertService(alert_config)

    # Create a proper async context manager mock
    mock_response = MagicMock()
    mock_response.status = 200

    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__.return_value = mock_response

    mock_session = MagicMock()
    mock_session.post.return_value = mock_post_cm

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session

    with patch("aiohttp.ClientSession", return_value=mock_session_cm):
        result = await service.send(test_alert)

        assert result is True
        assert test_alert.sent is True


@pytest.mark.asyncio
async def test_telegram_format_message(alert_config):
    """Test message formatting."""
    service = TelegramAlertService(alert_config)

    alert = Alert(
        level=AlertLevel.CRITICAL,
        title="Critical Error",
        message="Something went wrong",
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        source="system",
    )

    formatted = service._format_message(alert)

    assert "Critical Error" in formatted
    assert "Something went wrong" in formatted
    assert "2024-01-15" in formatted


@pytest.mark.asyncio
async def test_telegram_generic_exception(alert_config, test_alert):
    """Test handling of generic exceptions."""
    service = TelegramAlertService(alert_config)

    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.side_effect = Exception("Unexpected error")
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await service.send(test_alert)

        assert result is False
