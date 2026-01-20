"""Test ClickHouse client."""
import pytest
from unittest.mock import Mock, patch


def test_client_singleton():
    """Test ClickHouseClient is singleton."""
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig()

    # Reset singleton for test
    ClickHouseClient._instance = None

    client1 = ClickHouseClient(config)
    client2 = ClickHouseClient(config)

    assert client1 is client2


def test_client_ping_mock():
    """Test ping with mocked connection."""
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig()
    ClickHouseClient._instance = None

    client = ClickHouseClient(config)

    with patch.object(client, '_sync_client') as mock_sync:
        mock_sync.execute.return_value = [(1,)]

        result = client.ping()

        assert result is True


def test_get_clickhouse_client_factory():
    """Test factory function."""
    from shared.db.client import get_clickhouse_client, ClickHouseClient

    # Reset singleton
    ClickHouseClient._instance = None

    # Should not raise
    client = get_clickhouse_client()
    assert client is not None
