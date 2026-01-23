"""Integration test for AsyncClickHouseClient context manager.

These tests verify the actual implementation (not mocked) when dependencies are available.
"""
import pytest

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
def config():
    """Create a test ClickHouse config."""
    return ClickHouseConfig(
        host="localhost",
        port=9000,
        http_port=8123,
        user="default",
        password="",
        database="test_db",
    )


@pytest.mark.asyncio
async def test_context_manager_basic(config):
    """Test that context manager properly initializes and cleans up."""
    async with AsyncClickHouseClient(config) as client:
        # Should be connected inside context
        assert client._session is not None
        assert client._client is not None
        assert client._initialized is True

    # Should be closed outside context
    assert client._session is None
    assert client._client is None
    assert client._initialized is False


@pytest.mark.asyncio
async def test_double_close_safe(config):
    """Test that calling close() multiple times is safe."""
    client = AsyncClickHouseClient(config)
    await client.connect()

    # First close
    await client.close()
    assert client._session is None
    assert client._initialized is False

    # Second close should not raise
    await client.close()
    assert client._session is None
    assert client._initialized is False


@pytest.mark.asyncio
async def test_manual_connect_and_close(config):
    """Test manual connect and close (non-context manager)."""
    client = AsyncClickHouseClient(config)

    # Initially not connected
    assert client._session is None
    assert client._initialized is False

    # Connect
    await client.connect()
    assert client._session is not None
    assert client._initialized is True

    # Close
    await client.close()
    assert client._session is None
    assert client._initialized is False
