"""Storage configuration tests."""

import pytest


def test_storage_config_loads_default_yaml_without_clickhouse_env(monkeypatch):
    from shared.storage.config import StorageConfig

    monkeypatch.delenv("CLICKHOUSE_HOST", raising=False)
    monkeypatch.delenv("CLICKHOUSE_STOCK_DATABASE", raising=False)
    monkeypatch.delenv("CLICKHOUSE_FUTURES_DATABASE", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    config = StorageConfig.from_yaml()

    assert config.runtime_storage.backend == "sqlite"
    assert config.runtime_storage.sqlite.path == "data/runtime/dev/runtime.db"
    assert config.runtime_storage.sqlite.wal is True
    assert config.runtime_storage.clickhouse_mirror.enabled is False
    assert config.market_data.source == "parquet"
    assert config.market_data.parquet.root == "data/market"
    assert config.market_data.clickhouse.enabled is False
    assert config.dashboard.trade_stats_source == "runtime_ledger"


def test_storage_config_env_overrides_nested_fields(monkeypatch, tmp_path):
    from shared.storage.config import StorageConfig

    db_path = tmp_path / "runtime.db"
    parquet_root = tmp_path / "market"

    monkeypatch.setenv("RUNTIME_STORAGE_BACKEND", "null")
    monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_WAL", "false")
    monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_BUSY_TIMEOUT_MS", "1234")
    monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_SYNCHRONOUS", "full")
    monkeypatch.setenv("RUNTIME_STORAGE_CLICKHOUSE_MIRROR_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_STORAGE_CLICKHOUSE_DATABASE", "analytics")
    monkeypatch.setenv("MARKET_DATA_SOURCE", "clickhouse")
    monkeypatch.setenv("MARKET_DATA_PARQUET_ROOT", str(parquet_root))
    monkeypatch.setenv("MARKET_DATA_CLICKHOUSE_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_CLICKHOUSE_STOCK_DATABASE", "stockdb")
    monkeypatch.setenv("MARKET_DATA_CLICKHOUSE_FUTURES_DATABASE", "futuresdb")
    monkeypatch.setenv("DASHBOARD_TRADE_STATS_SOURCE", "clickhouse")

    config = StorageConfig.from_yaml()

    assert config.runtime_storage.backend == "null"
    assert config.runtime_storage.sqlite.path == str(db_path)
    assert config.runtime_storage.sqlite.wal is False
    assert config.runtime_storage.sqlite.busy_timeout_ms == 1234
    assert config.runtime_storage.sqlite.synchronous == "FULL"
    assert config.runtime_storage.clickhouse_mirror.enabled is True
    assert config.runtime_storage.clickhouse_mirror.database == "analytics"
    assert config.market_data.source == "clickhouse"
    assert config.market_data.parquet.root == str(parquet_root)
    assert config.market_data.clickhouse.enabled is True
    assert config.market_data.clickhouse.stock_database == "stockdb"
    assert config.market_data.clickhouse.futures_database == "futuresdb"
    assert config.dashboard.trade_stats_source == "clickhouse"


def test_storage_config_rejects_invalid_backend(monkeypatch):
    from shared.storage.config import StorageConfig

    monkeypatch.setenv("RUNTIME_STORAGE_BACKEND", "clickhouse-ish")

    with pytest.raises(ValueError):
        StorageConfig.from_yaml()
