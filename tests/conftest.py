"""Pytest configuration for test discovery and fixtures.

Adds project root to sys.path for module imports.
Loads .env for integration tests that need infrastructure credentials.
"""

import os
import sys
from contextlib import suppress
from pathlib import Path

import pytest

# Add project root to Python path immediately at module load time
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

_LIVE_INFRA_TEST_PATHS = {
    # These tests connect to real Redis DB 1 and/or ClickHouse. Some of them
    # write/delete runtime-shaped keys such as trading:{asset}:positions and
    # risk:portfolio:state, so they must never run accidentally while paper
    # trading is active on the same host.
    "tests/integration/test_clickhouse_tls.py",
    "tests/integration/test_cross_asset_trading.py",
    "tests/integration/test_graceful_shutdown.py",
    "tests/integration/test_llm_market_context.py",
    "tests/integration/test_rate_limiter_redis.py",
    "tests/integration/test_redis_tls.py",
    "tests/performance/test_clickhouse_load.py",
    "tests/performance/test_redis_load.py",
    "tests/performance/test_websocket_load.py",
    "tests/services/trading/test_risk_integration.py",
    "tests/shared/risk/test_persistence.py",
    "tests/unit/db/test_async_client_integration.py",
}

_LIVE_INFRA_ENV = "KIS_RUN_LIVE_INFRA_TESTS"

# Load .env so tests can access infrastructure credentials (ClickHouse, Redis, etc.)
_env_file = project_root / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_file, override=False)
    except ImportError:
        pass

# Cap MLflow's HTTP retry budget for tests so dashboard tests don't spend
# 4+ minutes retrying against an unreachable tracking server. Default is 7
# retries with exponential backoff. Set BEFORE any test imports MLflow so
# the env var is read at client construction.
os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")
os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "5")


def pytest_configure(config):
    """Configure pytest before test collection.

    This hook runs before test collection, ensuring sys.path is set up correctly
    for importing project modules in fixtures and tests.
    """
    # Ensure project root is at the beginning of sys.path
    project_root_str = str(project_root)
    if project_root_str in sys.path:
        sys.path.remove(project_root_str)
    sys.path.insert(0, project_root_str)


def pytest_collection_modifyitems(config, items):
    """Skip live-infra tests unless explicitly enabled.

    The production/paper runtime and integration tests both use Redis DB 1 by
    policy. Skipping these tests by default prevents accidental deletion or
    overwrite of active paper-trading keys during ordinary local test runs.
    """
    allow_live_infra = os.getenv(_LIVE_INFRA_ENV, "").lower() in {
        "1",
        "true",
        "yes",
    }
    skip_live_infra = pytest.mark.skip(
        reason=(
            "live Redis/ClickHouse test skipped by default; set "
            f"{_LIVE_INFRA_ENV}=1 only on an isolated test host or after "
            "stopping paper trading"
        )
    )

    for item in items:
        try:
            rel_path = Path(str(item.fspath)).resolve().relative_to(project_root)
        except ValueError:
            continue

        if rel_path.as_posix() in _LIVE_INFRA_TEST_PATHS:
            item.add_marker(pytest.mark.live_infra)
            if not allow_live_infra:
                item.add_marker(skip_live_infra)


@pytest.fixture(autouse=True)
def _clean_prometheus_registry():
    """Clean up Prometheus metric registry between tests to prevent pollution.

    Some tests import modules that register Prometheus metrics at module level.
    Without cleanup, these registrations persist and cause 'Duplicated timeseries'
    errors in subsequent tests that import the same modules.
    """
    try:
        from prometheus_client import REGISTRY

        # Snapshot metric names registered before the test
        names_before = set(REGISTRY._names_to_collectors.keys())
    except ImportError:
        yield
        return

    yield

    # Remove any metrics registered during the test
    names_after = set(REGISTRY._names_to_collectors.keys())
    new_names = names_after - names_before
    if new_names:
        collectors_to_remove = set()
        for name in new_names:
            collector = REGISTRY._names_to_collectors.get(name)
            if collector is not None:
                collectors_to_remove.add(id(collector))
        for _name, collector in list(REGISTRY._names_to_collectors.items()):
            if id(collector) in collectors_to_remove:
                with suppress(Exception):
                    REGISTRY.unregister(collector)


@pytest.fixture(autouse=True)
def _reset_config_loader_singleton():
    """Reset ConfigLoader singleton between tests to prevent config dir pollution.

    Tests that set KIS_CONFIG_DIR via monkeypatch can leave the ConfigLoader
    singleton pointing to a tmp directory, causing subsequent tests to fail
    with ConfigNotFoundError.
    """
    yield
    try:
        from shared.config.loader import ConfigLoader

        # Reset singleton so next test re-initializes with correct config dir
        ConfigLoader._instance = None
        ConfigLoader._config_dir = None
        ConfigLoader._cache.clear()
    except (ImportError, AttributeError):
        pass


@pytest.fixture(autouse=True)
def _reset_clickhouse_client_singleton():
    """Reset ClickHouseClient singleton between tests to prevent config pollution.

    ClickHouseClient is a singleton: the first ``ClickHouseClient(cfg)`` call
    locks the config and subsequent calls ignore their argument. A test that
    instantiates it with throwaway/credential-less config (e.g. TLS tests that
    strip CLICKHOUSE_* env) would otherwise leave the singleton pinned to the
    wrong credentials, making later DB-touching tests fail auth in the full
    suite while passing in isolation.
    """
    yield
    try:
        from shared.db.client import ClickHouseClient

        ClickHouseClient.reset_singleton()
    except (ImportError, AttributeError):
        pass
