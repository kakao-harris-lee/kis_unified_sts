"""Storage configuration tests."""

import pytest


def test_storage_config_loads_default_yaml_without_storage_env(monkeypatch):
    from shared.storage.config import StorageConfig

    monkeypatch.delenv("RUNTIME_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("RUNTIME_STORAGE_SQLITE_PATH", raising=False)
    monkeypatch.delenv("MARKET_DATA_SOURCE", raising=False)
    monkeypatch.delenv("MARKET_DATA_PARQUET_ROOT", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    config = StorageConfig.from_yaml()

    assert config.runtime_storage.backend == "sqlite"
    assert config.runtime_storage.sqlite.path == "data/runtime/dev/runtime.db"
    assert config.runtime_storage.sqlite.wal is True
    assert config.market_data.source == "parquet"
    assert config.market_data.parquet.root == "data/market"
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
    monkeypatch.setenv("MARKET_DATA_SOURCE", "parquet")
    monkeypatch.setenv("MARKET_DATA_PARQUET_ROOT", str(parquet_root))
    monkeypatch.setenv("DASHBOARD_TRADE_STATS_SOURCE", "runtime_ledger")

    config = StorageConfig.from_yaml()

    assert config.runtime_storage.backend == "null"
    assert config.runtime_storage.sqlite.path == str(db_path)
    assert config.runtime_storage.sqlite.wal is False
    assert config.runtime_storage.sqlite.busy_timeout_ms == 1234
    assert config.runtime_storage.sqlite.synchronous == "FULL"
    assert config.market_data.source == "parquet"
    assert config.market_data.parquet.root == str(parquet_root)
    assert config.dashboard.trade_stats_source == "runtime_ledger"


def test_storage_config_rejects_invalid_backend(monkeypatch):
    from shared.storage.config import StorageConfig

    monkeypatch.setenv("RUNTIME_STORAGE_BACKEND", "invalid-backend")

    with pytest.raises(ValueError):
        StorageConfig.from_yaml()


def test_storage_config_rejects_clickhouse_market_data_source(monkeypatch):
    from shared.storage.config import StorageConfig

    monkeypatch.setenv("MARKET_DATA_SOURCE", "clickhouse")

    with pytest.raises(ValueError):
        StorageConfig.from_yaml()
