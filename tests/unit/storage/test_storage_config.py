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


# ---------------------------------------------------------------------------
# One truthy set for every env flag (#847)
# ---------------------------------------------------------------------------
#
# The repo had FOUR env-boolean helpers with hand-written truthy tuples, and
# they had already drifted: `services/stock_strategy/daemon.py` additionally
# accepted "y", and `tests/support/live_infra.py` did NOT accept "on", so
# `KIS_RUN_LIVE_INFRA_TESTS=on` lifted hermeticity while leaving the live_infra
# tests skipped. Three of those four went with the legacy runtime (L1-L7); the
# two below are what survives, and the only thing that could still split them
# was the duplicated literal set. These pin that it stays shared.


def test_storage_env_bool_reads_the_shared_truthy_set():
    """`_env_bool` judges truth by `shared.config.TRUTHY_VALUES`, not its own copy."""
    from shared.config import TRUTHY_VALUES
    from shared.storage import config as storage_config

    assert storage_config.TRUTHY_VALUES is TRUTHY_VALUES
    assert set(TRUTHY_VALUES) == {"1", "true", "yes", "on"}


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "Yes", "on", "ON"])
def test_storage_env_bool_is_true_for_every_shared_truthy_token(monkeypatch, value):
    from shared.storage.config import _env_bool

    monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_WAL", value)

    assert _env_bool("RUNTIME_STORAGE_SQLITE_WAL") is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "y", "maybe", " "])
def test_storage_env_bool_is_false_outside_the_shared_truthy_set(monkeypatch, value):
    """Notably "y": the one token a deleted helper accepted and this one never did."""
    from shared.storage.config import _env_bool

    monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_WAL", value)

    assert _env_bool("RUNTIME_STORAGE_SQLITE_WAL") is False


@pytest.mark.parametrize("unset_value", [None, ""])
def test_storage_env_bool_keeps_its_tri_state(monkeypatch, unset_value):
    """Unset and empty stay `None` — the reason this is not `shared.config.env_flag`.

    `StorageConfig.apply_env_overrides` only overrides `sqlite.wal` when this
    returns a bool, so folding "unset" into `False` (what `env_flag` does)
    would silently turn WAL off for every process that never set the variable.
    """
    from shared.storage.config import _env_bool

    if unset_value is None:
        monkeypatch.delenv("RUNTIME_STORAGE_SQLITE_WAL", raising=False)
    else:
        monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_WAL", unset_value)

    assert _env_bool("RUNTIME_STORAGE_SQLITE_WAL") is None


def test_env_flag_and_storage_env_bool_agree_on_every_set_value(monkeypatch):
    """The two surviving helpers never disagree about a value that IS set."""
    from shared.config import env_flag
    from shared.storage.config import _env_bool

    for value in ["1", "true", "TRUE", "yes", "on", "0", "false", "no", "off", "y"]:
        monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_WAL", value)

        assert _env_bool("RUNTIME_STORAGE_SQLITE_WAL") is env_flag(
            "RUNTIME_STORAGE_SQLITE_WAL"
        ), value
