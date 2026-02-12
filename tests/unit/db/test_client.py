"""Test ClickHouse client."""
from unittest.mock import Mock, patch


def test_client_singleton():
    """Test ClickHouseClient is singleton."""
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig()

    # Reset singleton for test
    ClickHouseClient.reset_singleton()

    client1 = ClickHouseClient(config)
    client2 = ClickHouseClient(config)

    assert client1 is client2


def test_client_ping_mock():
    """Test get_sync_client with mocked connection."""
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig()
    ClickHouseClient.reset_singleton()

    client = ClickHouseClient(config)

    # Test that get_sync_client creates connection when called
    with patch('shared.db.client.SyncClient') as MockSyncClient:
        mock_conn = Mock()
        MockSyncClient.return_value = mock_conn

        result = client.get_sync_client()

        assert result is mock_conn
        MockSyncClient.assert_called_once()


def test_get_clickhouse_client_factory():
    """Test factory function with config."""
    from shared.db.client import get_clickhouse_client, ClickHouseClient
    from shared.db.config import ClickHouseConfig

    # Reset singleton
    ClickHouseClient.reset_singleton()

    # Factory should accept config
    config = ClickHouseConfig()
    client = get_clickhouse_client(config)
    assert client is not None
