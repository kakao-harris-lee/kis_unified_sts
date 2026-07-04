"""Pytest configuration for test discovery and fixtures.

Adds project root to sys.path for module imports.
Loads .env for integration tests that need infrastructure credentials.
"""

import os
import sys
from contextlib import suppress
from pathlib import Path
from unittest import mock

import pytest

# Add project root to Python path immediately at module load time
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

_LIVE_INFRA_TEST_PATHS = {
    # These tests connect to real Redis DB 1. Some of them
    # write/delete runtime-shaped keys such as trading:{asset}:positions and
    # risk:portfolio:state, so they must never run accidentally while paper
    # trading is active on the same host.
    "tests/integration/test_cross_asset_trading.py",
    "tests/integration/test_graceful_shutdown.py",
    "tests/integration/test_llm_market_context.py",
    "tests/integration/test_rate_limiter_redis.py",
    "tests/integration/test_redis_tls.py",
    "tests/performance/test_redis_load.py",
    "tests/performance/test_websocket_load.py",
    "tests/services/trading/test_risk_integration.py",
    "tests/shared/risk/test_persistence.py",
}

_LIVE_INFRA_ENV = "KIS_RUN_LIVE_INFRA_TESTS"

# Load .env so tests can access infrastructure credentials (Redis, etc.)
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

# Pin MLflow to local sqlite for the whole test session. .env sets
# MLFLOW_TRACKING_URI to the docker mlflow server (http://localhost:5000), and
# clients now honor it (resolve_tracking_uri) — but the suite must never depend
# on that server running. Override (not setdefault) so the .env value can't leak
# in; individual tests still pass explicit throwaway URIs where needed.
os.environ["MLFLOW_TRACKING_URI"] = "sqlite:///mlflow.db"

# --- pytest-xdist worker isolation -------------------------------------------
# xdist workers are separate processes, so in-process singletons are already
# isolated per worker. The remaining cross-worker hazard among the *parallel*
# tests is Hypothesis' example database: by default every worker reads/writes
# the same SQLite file and they contend/corrupt each other. Give each worker
# its own directory. Tests that touch shared *external* state (e.g. Redis DB 1)
# or assert on uncontended wall-clock timing are instead marked ``serial`` and
# run in a separate non-parallel pass — see the ``serial`` marker in
# pyproject.toml and the split steps in .github/workflows/test.yml.
_xdist_worker = os.environ.get("PYTEST_XDIST_WORKER")
if _xdist_worker:
    os.environ.setdefault(
        "HYPOTHESIS_STORAGE_DIRECTORY",
        str(Path("/tmp") / f"hypothesis-{_xdist_worker}"),
    )


@pytest.fixture
def mocker():
    """Small pytest-mock compatible fixture for local patching in unit tests."""
    patchers = []

    class _PatchProxy:
        def __call__(self, *args, **kwargs):
            patcher = mock.patch(*args, **kwargs)
            patchers.append(patcher)
            return patcher.start()

        def object(self, *args, **kwargs):
            patcher = mock.patch.object(*args, **kwargs)
            patchers.append(patcher)
            return patcher.start()

    class _Mocker:
        Mock = mock.Mock
        MagicMock = mock.MagicMock
        patch = _PatchProxy()

    yield _Mocker()

    for patcher in reversed(patchers):
        with suppress(Exception):
            patcher.stop()


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
            "live Redis test skipped by default; set "
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
def _reset_futures_open_cache():
    """Clear the module-level futures-open cache between tests.

    ``shared.decision.context._load_futures_open_from_config`` memoizes the
    parsed ``futures.regular.open`` per config path. Tests that point it at a
    temp config (or rely on the default) could otherwise leak a cached value
    into a later test — especially under pytest-xdist where module state is
    shared within a worker. Clearing before AND after keeps each test hermetic.
    """
    try:
        from shared.decision.context import _reset_futures_open_cache as _clear

        _clear()
    except (ImportError, AttributeError):
        _clear = None
    yield
    if _clear is not None:
        _clear()
