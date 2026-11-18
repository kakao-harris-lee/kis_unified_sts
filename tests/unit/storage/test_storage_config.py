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
# tests skipped. Three of those four went with the legacy runtime (L1-L7), but
# a repo-wide scan for the literal found two the issue never listed:
# `shared/config/base.py` (same set) and `tests/integration/test_redis_tls.py`
# (a second reading of KIS_RUN_LIVE_INFRA_TESTS that dropped "on" -- the very
# failure live_infra.py's docstring warns about, re-created one directory over).
# All of them now read one set. These pin that it stays that way.
#
# `shared/models/stream_models.py::_parse_bool` keeps its own, wider set on
# purpose and is NOT unified here: it parses broker STREAM payloads, not env
# vars, where "Y"/"N" is the KIS field convention, and it is tri-state with a
# matching falsy set. Folding it into the env set would narrow what the feed
# parses -- the "동작이 좁아진다" risk #847 itself flagged.


def test_service_config_base_env_bool_reads_the_shared_truthy_set():
    """`ServiceConfigBase._parse_env_value` coerces bools by the shared set."""
    from shared.config import TRUTHY_VALUES
    from shared.config import base as config_base

    assert config_base.TRUTHY_VALUES is TRUTHY_VALUES

    for value in ["1", "true", "TRUE", "yes", "on", "ON"]:
        assert config_base.ServiceConfigBase._parse_env_value(value, bool) is True
    for value in ["0", "false", "no", "off", "y", "nonsense"]:
        assert config_base.ServiceConfigBase._parse_env_value(value, bool) is False


def test_redis_tls_module_shares_the_one_live_infra_reading():
    """The two readings of KIS_RUN_LIVE_INFRA_TESTS are now the same function.

    The input that used to split them is "on": `tests/conftest.py` dropped the
    hermetic session and loaded real credentials, while the TLS module's own
    copy skipped every test in it.

    Read as SOURCE, never imported. `tests/integration/test_redis_tls.py` carries
    five module-level `@pytest.mark.skipif(not redis_available(), ...)`, and a
    skipif argument is evaluated at import time -- so importing that module from
    this unit test would make up to five real Redis connections (1s socket
    timeout each) whenever KIS_RUN_LIVE_INFRA_TESTS is set and Redis is down.
    A unit test must not reach for the network to check a fact about a file.
    """
    import ast
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "integration"
        / "test_redis_tls.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_from = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and any(alias.name == "live_infra_enabled" for alias in node.names)
    }
    assert imported_from == {"tests.support.live_infra"}, (
        "test_redis_tls.py must take live_infra_enabled from the shared helper; "
        f"found {imported_from or 'no import of it'}"
    )

    local_definitions = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "live_infra_enabled"
    ]
    assert not local_definitions, (
        "test_redis_tls.py defines its own live_infra_enabled again -- that is "
        "the second truthy set #847 removed"
    )


@pytest.mark.parametrize("value", ["on", "ON", "1", "true", "yes", " 1 "])
def test_live_infra_reading_accepts_on_like_the_hermetic_gate(monkeypatch, value):
    """Pins the concrete failing input from #847 for every truthy token.

    Exercises the shared helper itself, which the test above proves is the one
    `test_redis_tls.py` now calls -- so this stays a unit test and makes no
    Redis connection. `" 1 "` is here because routing the TLS module through
    `env_flag` also gained it `.strip()`: the old local copy read it as False.
    """
    from tests.support.live_infra import LIVE_INFRA_ENV, live_infra_enabled

    monkeypatch.setenv(LIVE_INFRA_ENV, value)

    assert live_infra_enabled() is True


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
