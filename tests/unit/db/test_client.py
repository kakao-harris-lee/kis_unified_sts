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


def test_build_connection_params_includes_tcp_keepalive():
    """When keepalive is enabled, params carry the (idle, interval, count) tuple.

    clickhouse_driver maps a 3-tuple to SO_KEEPALIVE + TCP_KEEPIDLE/INTVL/CNT.
    """
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig()
    ClickHouseClient.reset_singleton()
    client = ClickHouseClient(config)

    params = client._build_connection_params()

    assert params["tcp_keepalive"] == (
        config.tcp_keepalive_idle,
        config.tcp_keepalive_interval,
        config.tcp_keepalive_count,
    )


def test_build_connection_params_omits_keepalive_when_disabled():
    """When keepalive is disabled, the param is absent (driver default applies)."""
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig(tcp_keepalive=False)
    ClickHouseClient.reset_singleton()
    client = ClickHouseClient(config)

    params = client._build_connection_params()

    assert "tcp_keepalive" not in params
