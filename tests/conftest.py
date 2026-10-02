"""Pytest configuration for test discovery and fixtures.

Adds project root to sys.path for module imports.

The session is hermetic by default: no ``.env`` is loaded, the whole ``KIS_*``
and ``TELEGRAM_*`` namespace is emptied, and the config and token-cache
directories are pinned to this checkout and a temp dir. Set
``KIS_RUN_LIVE_INFRA_TESTS=1`` to opt back into real infrastructure
credentials — the same switch that un-skips the ``live_infra`` tests. See
``docs/CI_PARALLEL_NOTES.md`` and #698.
"""

import atexit
import os
import shutil
import sys
import tempfile
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

# Add project root to Python path immediately at module load time
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

# Imported AFTER project_root lands on sys.path — `tests` is a namespace package.
from tests.support import git_env, hermetic_env  # noqa: E402
from tests.support.live_infra import (  # noqa: E402
    live_infra_enabled,
    redis_failure,
    redis_unreachable_message,
    skip_reason,
)

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


# --- Hermetic session --------------------------------------------------------
# Everything below runs at conftest *import* time, before collection, because
# the leak this closes happens at import time: a test module that imports
# `cli.commands.common` (or any script entrypoint) used to run an
# argument-less load_dotenv() during collection, which walked out of a nested
# worktree into the primary checkout's real .env. A fixture runs too late to
# stop that; `_hermetic_broker_env` below re-asserts the same invariants once
# the session starts.
#
# Opting into live infrastructure restores the previous behavior: this
# checkout's .env is loaded exactly as the runtime loads it.
#
# `live_infra_enabled()` decides — not a second reading of the same variable —
# so hermeticity is the exact negation of the live-infra gate (#845/#698). A
# duplicate predicate with its own truthy set would let
# KIS_RUN_LIVE_INFRA_TESTS=on drop hermeticity while leaving every live_infra
# test skipped: credentials loaded, nothing gained, and silently. Sharing the
# function is also what keeps `pytest_runtest_setup`'s Redis ping out of a
# hermetic session, because that hook asks the same question.
HERMETIC_SESSION = not live_infra_enabled()

#: The throwaway directory every token cache is pinned to, or ``None`` under
#: the live-infra opt-in. One per process, so xdist workers do not share it.
TOKEN_CACHE_DIR: Path | None = None

#: What the stray-token-cache witnesses looked like before any test ran.
#: Compared against, not asserted absent: the primary checkout legitimately
#: holds ``.kis_token_real`` from ordinary host ``sts`` runs, and blaming the
#: test run for a file written months earlier is a false accusation (#698).
TOKEN_CACHE_SNAPSHOT: hermetic_env.TokenCacheSnapshot = {}


def _apply_hermetic_pins() -> None:
    """Write every hermetic invariant into ``os.environ``.

    One function, called from the import-time block below *and* from the
    session fixture, so a pin added to one is never missing from the other —
    re-asserting a subset would quietly defeat the fixture's whole purpose.

    The scrub empties the entire ``KIS_*``/``TELEGRAM_*`` namespace whatever
    its source: a ``.env`` already loaded by a plugin, or variables exported in
    the operator's shell. Credentials aside, that is also what keeps a local
    run honest, because CI sets none of them and a test that quietly depended
    on one used to pass locally and fail in CI. Notably it blanks
    ``TELEGRAM_*_BOT_TOKEN``, without which a test that starts a real
    ``TradingOrchestrator`` and does not mock ``_notify`` (e.g.
    ``test_orchestrator_lifecycle``) sends real "🚀 Trading Started" messages
    to the operator. Tests that exercise Telegram routing self-provision
    credentials via monkeypatch, which auto-restores per test.
    """
    if TOKEN_CACHE_DIR is None:
        # Without this, the pin below writes the string "None" and every token
        # cache lands in a directory called None next to the working
        # directory — a silent failure that looks exactly like a pinned cache.
        raise RuntimeError(
            "_apply_hermetic_pins() called before TOKEN_CACHE_DIR was created; "
            "it is only valid in a hermetic session (#698)"
        )

    os.environ[hermetic_env.HERMETIC_ENV] = "1"
    hermetic_env.scrub_broker_env()
    # Pin the config directory to THIS checkout. A worktree then reads its own
    # config/, never the primary checkout's, and the value no longer depends
    # on whether the operator exported KIS_CONFIG_DIR.
    os.environ["KIS_CONFIG_DIR"] = str(project_root / "config")
    # Send token caches to a throwaway directory. The default is Path.cwd(),
    # which is how a real .kis_token_real landed in a worktree root on
    # 2026-09-15.
    os.environ["KIS_TOKEN_CACHE_DIR"] = str(TOKEN_CACHE_DIR)


if HERMETIC_SESSION:
    TOKEN_CACHE_DIR = Path(tempfile.mkdtemp(prefix="kis-test-token-cache-"))
    atexit.register(shutil.rmtree, TOKEN_CACHE_DIR, True)
    _apply_hermetic_pins()

    # Turn any remaining .env read into a named failure instead of a silent
    # credential injection — including from a caller added after #698.
    hermetic_env.install_dotenv_guard()

    TOKEN_CACHE_SNAPSHOT = hermetic_env.snapshot_token_caches(
        hermetic_env.token_cache_witnesses(project_root)
    )
else:
    # Live-infra opt-in: the operator asked for real Redis and friends, so this
    # checkout's .env is loaded exactly as the runtime loads it. Telegram stays
    # scrubbed even here — a live-infra run must still not message the operator
    # from a test (the pre-#698 behavior, kept).
    os.environ.pop(hermetic_env.HERMETIC_ENV, None)

    with suppress(ImportError):
        # python-dotenv is a runtime dependency, but the tos-firewall job
        # installs the root project with --no-deps.
        from shared.config.dotenv_guard import load_project_dotenv  # noqa: E402

        load_project_dotenv()

    for _tg_key in [key for key in list(os.environ) if key.startswith("TELEGRAM_")]:
        del os.environ[_tg_key]

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
    allow_live_infra = live_infra_enabled()
    # One gate, one message: the wording lives in tests/support/live_infra.py
    # so the skip reason and the failure text cannot drift apart.
    skip_live_infra = pytest.mark.skip(reason=skip_reason())

    for item in items:
        try:
            rel_path = Path(str(item.fspath)).resolve().relative_to(project_root)
        except ValueError:
            continue

        if rel_path.as_posix() in _LIVE_INFRA_TEST_PATHS:
            item.add_marker(pytest.mark.live_infra)
            if not allow_live_infra:
                item.add_marker(skip_live_infra)


@pytest.fixture(scope="session", autouse=True)
def _hermetic_broker_env():
    """Re-assert the hermetic invariants once the session starts.

    The import-time block at the top of this file is what actually makes
    collection safe. This fixture is the backstop for anything that ran
    *during* collection and re-introduced a credential — a plugin, a module
    that reads a file at import, a conftest further down the tree. It re-scrubs
    rather than failing, so the session gets the safe state either way; the
    assertions live in ``tests/unit/config/test_dotenv_hermeticity.py``, which
    fails loudly and names itself.

    Skipped entirely under ``KIS_RUN_LIVE_INFRA_TESTS=1``, where the operator
    has asked for real infrastructure credentials on purpose.
    """
    if not HERMETIC_SESSION:
        yield
        return

    _apply_hermetic_pins()
    yield


@pytest.fixture(scope="session")
def token_cache_snapshot():
    """What every stray-token-cache witness looked like before any test ran.

    Requested by the guard test that asserts no test issued a KIS token. It is
    a snapshot rather than an absence check because the primary checkout
    legitimately holds ``.kis_token_real``/``.kis_token_mock`` from host
    ``sts`` runs (#698).
    """
    return TOKEN_CACHE_SNAPSHOT


# Probe result for this process, computed at most once: ``None`` = not probed
# yet, ``(failure_or_None,)`` = probed. A tuple rather than a bare value so
# "probed, and it was fine" is distinguishable from "not probed".
_REDIS_PROBE: tuple[str | None] | None = None


def _redis_failure_once() -> str | None:
    """Ping Redis at most once per process; return why it is unusable."""
    global _REDIS_PROBE
    if _REDIS_PROBE is None:
        _REDIS_PROBE = (redis_failure(),)
    return _REDIS_PROBE[0]


def pytest_runtest_setup(item):
    """Fail — never skip — a live-infra test that cannot reach Redis.

    This is the second half of the gate whose first half is in
    ``pytest_collection_modifyitems`` above. Not opted in: that hook already
    skipped the item and the builtin skipping plugin (``tryfirst``) short-
    circuits before this runs. Opted in: the test must run, so an unreachable
    Redis is a failure, not silence. A skip here is exactly how the CI
    ``performance`` job reported green for four months while measuring 13 of
    its 25 benchmarks.

    Failing per item, rather than raising at import time in the test modules,
    keeps the blast radius to the gated tests: the rest of the session still
    runs instead of pytest aborting collection with zero tests executed. It
    also covers all of ``_LIVE_INFRA_TEST_PATHS``, not just the two
    performance modules.
    """
    if "live_infra" not in item.keywords or not live_infra_enabled():
        return
    failure = _redis_failure_once()
    if failure is not None:
        pytest.fail(redis_unreachable_message(failure), pytrace=False)


@pytest.fixture(scope="session")
def hermetic_session_state():
    """How this session was configured, for the guard tests to assert on.

    ``redis_probed`` is a callable rather than a value because the live-infra
    gate pings lazily, at the first gated item — reading the flag at fixture
    setup would always see "not probed" and pin nothing.
    """
    return SimpleNamespace(
        hermetic=HERMETIC_SESSION,
        live_infra_enabled=live_infra_enabled(),
        token_cache_dir=TOKEN_CACHE_DIR,
        redis_probed=lambda: _REDIS_PROBE is not None,
    )


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
    """Clear the module-level futures open/close cache between tests.

    ``shared.decision.context.load_futures_open_from_config`` (and the
    ``close`` twin) memoizes the parsed ``futures.regular`` time per config
    path. Tests that point it at a
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


@pytest.fixture(scope="session")
def requires_repo_checkout():
    """Precondition for a test that clones THIS repository.

    Request it from any test that runs ``git clone <repo root>``. It skips in exactly one
    place — the ``Dockerfile.test`` image, which sets
    ``KIS_TEST_IMAGE_NO_GIT_METADATA`` because ``.dockerignore`` excludes ``.git`` — and
    nowhere else. With no repository and no marker the test is allowed to run and fail
    loudly, so a broken checkout on a real gate never reads as a green skip (#835).

    The probe runs lazily, once per session, and raises rather than skipping when git fails
    for a reason other than "no repository here" (dubious ownership and friends).
    """
    reason = git_env.repo_checkout_skip_reason(
        git_env.repo_checkout_state(project_root),
        os.environ.get(git_env.NO_GIT_METADATA_ENV),
    )
    if reason is not None:
        pytest.skip(reason)
