"""Test ClickHouse configuration."""
import pytest


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
