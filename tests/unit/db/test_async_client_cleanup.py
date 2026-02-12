"""Tests for AsyncClickHouseClient resource cleanup."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys

from shared.db.client import HAS_ASYNC
from shared.db.config import ClickHouseConfig


# Skip all tests if async dependencies not available
pytestmark = pytest.mark.skipif(
    not HAS_ASYNC,
    reason="aiochclient not installed"
)


if HAS_ASYNC:
    from shared.db.client import AsyncClickHouseClient


@pytest.fixture
def mock_config():
    """Create a mock ClickHouse config."""
    return ClickHouseConfig(
        host="localhost",
        port=9000,
        http_port=8123,
        user="default",
        password="",
        database="test_db",
    )


@pytest.mark.asyncio
async def test_close_cleans_all_resources(mock_config):
    """close() should clean both session and client."""
    # Create mocks before importing the module
    mock_session = MagicMock()
    mock_session.close = AsyncMock()

    mock_client = MagicMock()

    # Patch the imports in the client module
    with patch.object(sys.modules['shared.db.client'], 'ClientSession', return_value=mock_session), \
         patch.object(sys.modules['shared.db.client'], 'ChClient', return_value=mock_client):

        client = AsyncClickHouseClient(mock_config)
        await client.connect()

        assert client._session is not None
        assert client._client is not None
        assert client._initialized is True

        await client.close()

        # Verify both were closed
        mock_session.close.assert_called_once()
        assert client._session is None
        assert client._client is None
        assert client._initialized is False


@pytest.mark.asyncio
async def test_close_handles_session_error(mock_config):
    """close() should continue cleaning even if session.close() fails."""
    mock_session = MagicMock()
    mock_session.close = AsyncMock(side_effect=Exception("Session close failed"))

    mock_client = MagicMock()

    with patch.object(sys.modules['shared.db.client'], 'ClientSession', return_value=mock_session), \
         patch.object(sys.modules['shared.db.client'], 'ChClient', return_value=mock_client):

        client = AsyncClickHouseClient(mock_config)
        await client.connect()

        # Should not raise, should log warning instead
        await client.close()

        # Resources should still be cleared
        assert client._session is None
        assert client._client is None
        assert client._initialized is False


@pytest.mark.asyncio
async def test_close_handles_client_with_close_method(mock_config):
    """close() should call ChClient.close() if it exists (sync)."""
    mock_session = MagicMock()
    mock_session.close = AsyncMock()

    # ChClient with sync close method
    mock_client = MagicMock()
    mock_client.close = MagicMock()

    with patch.object(sys.modules['shared.db.client'], 'ClientSession', return_value=mock_session), \
         patch.object(sys.modules['shared.db.client'], 'ChClient', return_value=mock_client):

        client = AsyncClickHouseClient(mock_config)
        await client.connect()
        await client.close()

        # Verify ChClient.close() was called
        mock_client.close.assert_called_once()
        assert client._client is None


@pytest.mark.asyncio
async def test_close_handles_client_with_async_close(mock_config):
    """close() should await async close methods."""
    mock_session = MagicMock()
    mock_session.close = AsyncMock()

    # ChClient with async close method
    mock_client = MagicMock()
    mock_client.close = AsyncMock()

    with patch.object(sys.modules['shared.db.client'], 'ClientSession', return_value=mock_session), \
         patch.object(sys.modules['shared.db.client'], 'ChClient', return_value=mock_client):

        client = AsyncClickHouseClient(mock_config)
        await client.connect()
        await client.close()

        # Verify async close() was awaited
        mock_client.close.assert_awaited_once()
        assert client._client is None


@pytest.mark.asyncio
async def test_context_manager_calls_connect_and_close(mock_config):
    """Context manager should call connect on enter, close on exit."""
    mock_session = MagicMock()
    mock_session.close = AsyncMock()

    mock_client = MagicMock()

    with patch.object(sys.modules['shared.db.client'], 'ClientSession', return_value=mock_session), \
         patch.object(sys.modules['shared.db.client'], 'ChClient', return_value=mock_client):

        client = AsyncClickHouseClient(mock_config)

        async with client as ctx_client:
            # Inside context, should be connected
            assert ctx_client is client
            assert client._session is not None
            assert client._client is not None
            assert client._initialized is True

        # After exit, should be closed
        assert client._session is None
        assert client._client is None
        assert client._initialized is False


@pytest.mark.asyncio
async def test_context_manager_closes_on_exception(mock_config):
    """Context manager should close even when exception occurs."""
    mock_session = MagicMock()
    mock_session.close = AsyncMock()

    mock_client = MagicMock()

    with patch.object(sys.modules['shared.db.client'], 'ClientSession', return_value=mock_session), \
         patch.object(sys.modules['shared.db.client'], 'ChClient', return_value=mock_client):

        client = AsyncClickHouseClient(mock_config)

        with pytest.raises(ValueError):
            async with client:
                raise ValueError("Test exception")

        # Should still be closed after exception
        assert client._session is None
        assert client._client is None
        assert client._initialized is False


@pytest.mark.asyncio
async def test_double_close_is_safe(mock_config):
    """Calling close() twice should not raise."""
    mock_session = MagicMock()
    mock_session.close = AsyncMock()

    mock_client = MagicMock()

    with patch.object(sys.modules['shared.db.client'], 'ClientSession', return_value=mock_session), \
         patch.object(sys.modules['shared.db.client'], 'ChClient', return_value=mock_client):

        client = AsyncClickHouseClient(mock_config)
        await client.connect()

        # First close
        await client.close()
        assert client._session is None

        # Second close should not raise
        await client.close()
        assert client._session is None
        assert client._initialized is False


@pytest.mark.asyncio
async def test_close_handles_client_close_error(mock_config):
    """close() should continue even if ChClient.close() fails."""
    mock_session = MagicMock()
    mock_session.close = AsyncMock()

    # ChClient with failing close
    mock_client = MagicMock()
    mock_client.close = MagicMock(side_effect=Exception("Client close failed"))

    with patch.object(sys.modules['shared.db.client'], 'ClientSession', return_value=mock_session), \
         patch.object(sys.modules['shared.db.client'], 'ChClient', return_value=mock_client):

        client = AsyncClickHouseClient(mock_config)
        await client.connect()

        # Should not raise
        await client.close()

        # Both resources should still be cleared
        assert client._client is None
        assert client._session is None
        assert client._initialized is False


@pytest.mark.asyncio
async def test_connect_cleans_session_on_chclient_failure(mock_config):
    """If ChClient constructor fails, session should be cleaned up."""
    mock_session = MagicMock()
    mock_session.close = AsyncMock()

    with patch.object(sys.modules['shared.db.client'], 'ClientSession', return_value=mock_session), \
         patch.object(sys.modules['shared.db.client'], 'ChClient', side_effect=Exception("Connection failed")):

        client = AsyncClickHouseClient(mock_config)

        with pytest.raises(Exception, match="Connection failed"):
            await client.connect()

        # Session should have been cleaned up
        mock_session.close.assert_awaited_once()
        assert client._session is None
        assert client._client is None
