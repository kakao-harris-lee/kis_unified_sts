"""Test ClickHouse configuration."""


def test_clickhouse_config_from_dict():
    """Test ClickHouseConfig creation from dictionary."""
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig(
        host="localhost",
        port=9000,
        user="default",
        password="",
        database="market"
    )

    assert config.host == "localhost"
    assert config.port == 9000
    assert config.database == "market"


def test_clickhouse_config_defaults():
    """Test ClickHouseConfig default values."""
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig()

    assert config.host == "localhost"
    assert config.port == 9000
    assert config.database == "market"


def test_clickhouse_config_connection_string():
    """Test connection string generation."""
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig(
        host="db.example.com",
        port=9000,
        user="trader",
        database="trading"
    )

    assert "db.example.com" in str(config)


def test_clickhouse_config_tcp_keepalive_defaults():
    """TCP keepalive is enabled by default with sane idle/interval/count.

    Keepalive prevents the idle native connection from being reaped ~hourly
    (server keep_alive_timeout / NAT conntrack), which otherwise surfaces as
    a transparent-but-noisy reconnect WARNING. The first probe must fire well
    before the ~1h idle window, so idle is bounded under one hour.
    """
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig()

    assert config.tcp_keepalive is True
    assert config.tcp_keepalive_idle == 60
    assert config.tcp_keepalive_interval == 15
    assert config.tcp_keepalive_count == 4
    assert config.tcp_keepalive_idle < 3600


def test_clickhouse_config_tcp_keepalive_from_env(monkeypatch):
    """TCP keepalive fields are overridable via environment variables."""
    from shared.db.config import ClickHouseConfig

    monkeypatch.setenv("CLICKHOUSE_TCP_KEEPALIVE", "false")
    monkeypatch.setenv("CLICKHOUSE_TCP_KEEPALIVE_IDLE", "120")
    monkeypatch.setenv("CLICKHOUSE_TCP_KEEPALIVE_INTERVAL", "30")
    monkeypatch.setenv("CLICKHOUSE_TCP_KEEPALIVE_COUNT", "6")

    config = ClickHouseConfig.from_env()

    assert config.tcp_keepalive is False
    assert config.tcp_keepalive_idle == 120
    assert config.tcp_keepalive_interval == 30
    assert config.tcp_keepalive_count == 6
