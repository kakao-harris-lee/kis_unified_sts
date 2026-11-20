"""Pytest configuration for test discovery and fixtures."""

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

project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from tests.support import git_env, hermetic_env  # noqa: E402
from tests.support.live_infra import (  # noqa: E402
    live_infra_enabled,
    redis_failure,
    redis_unreachable_message,
    skip_reason,
)

_LIVE_INFRA_TEST_PATHS = {
    "tests/integration/test_redis_tls.py",
}


HERMETIC_SESSION = True

TOKEN_CACHE_DIR: Path | None = None

TOKEN_CACHE_SNAPSHOT: hermetic_env.TokenCacheSnapshot = {}


def _apply_hermetic_pins() -> None:
    """Write every hermetic invariant into ``os.environ``."""
    if TOKEN_CACHE_DIR is None:
        raise RuntimeError(
            "_apply_hermetic_pins() called before TOKEN_CACHE_DIR was created; "
            "it is only valid in a hermetic session (#698)"
        )

    os.environ[hermetic_env.HERMETIC_ENV] = "1"
    hermetic_env.scrub_broker_env()
    os.environ["KIS_CONFIG_DIR"] = str(project_root / "config")
    os.environ["KIS_TOKEN_CACHE_DIR"] = str(TOKEN_CACHE_DIR)
    os.environ[hermetic_env.TOKEN_CACHE_BASE_ENV] = str(TOKEN_CACHE_BASE)


TOKEN_CACHE_BASE: Path | None = None

_inherited_base = os.environ.get(hermetic_env.TOKEN_CACHE_BASE_ENV)
_xdist_worker_id = os.environ.get("PYTEST_XDIST_WORKER")
if _xdist_worker_id and _inherited_base:
    TOKEN_CACHE_BASE = Path(_inherited_base)
else:
    TOKEN_CACHE_BASE = Path(tempfile.mkdtemp(prefix="kis-test-token-cache-"))
    atexit.register(shutil.rmtree, TOKEN_CACHE_BASE, True)

TOKEN_CACHE_DIR = (
    TOKEN_CACHE_BASE / _xdist_worker_id if _xdist_worker_id else TOKEN_CACHE_BASE
)
TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_apply_hermetic_pins()

hermetic_env.install_dotenv_guard()

TOKEN_CACHE_SNAPSHOT = hermetic_env.snapshot_token_caches(
    hermetic_env.token_cache_witnesses(project_root)
)

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
    """Configure pytest before test collection."""
    project_root_str = str(project_root)
    if project_root_str in sys.path:
        sys.path.remove(project_root_str)
    sys.path.insert(0, project_root_str)

    hermetic_env.register_sandbox_root(getattr(config.option, "basetemp", None))


def pytest_sessionfinish(session, exitstatus):
    """Fail the session if any test issued or rewrote a KIS token cache."""
    if not TOKEN_CACHE_SNAPSHOT:
        return

    touched = hermetic_env.token_caches_touched_since(TOKEN_CACHE_SNAPSHOT)
    touched += hermetic_env.new_token_caches_under(TOKEN_CACHE_BASE)
    if not touched:
        return

    message = (
        "KIS token cache written during the test session: "
        + ", ".join(str(path) for path in touched)
        + " — a test reached the KIS token endpoint, or wrote a cache where "
        "nothing should (#698)."
    )
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:  # pragma: no branch - always present in practice
        reporter.write_line(f"ERROR: {message}", red=True)
    session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_collection_modifyitems(config, items):
    """Skip live-infra tests unless explicitly enabled."""
    allow_live_infra = live_infra_enabled()
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
    """Re-assert the hermetic invariants once the session starts."""
    _apply_hermetic_pins()
    yield


@pytest.fixture(scope="session")
def token_cache_snapshot():
    """What every stray-token-cache witness looked like before any test ran."""
    return TOKEN_CACHE_SNAPSHOT


_REDIS_PROBE: tuple[str | None] | None = None


def _redis_failure_once() -> str | None:
    """Ping Redis at most once per process; return why it is unusable."""
    global _REDIS_PROBE
    if _REDIS_PROBE is None:
        _REDIS_PROBE = (redis_failure(),)
    return _REDIS_PROBE[0]


def pytest_runtest_setup(item):
    """Fail — never skip — a live-infra test that cannot reach Redis."""
    if "live_infra" not in item.keywords or not live_infra_enabled():
        return
    failure = _redis_failure_once()
    if failure is not None:
        pytest.fail(redis_unreachable_message(failure), pytrace=False)


@pytest.fixture(scope="session")
def hermetic_session_state():
    """How this session was configured, for the guard tests to assert on."""
    return SimpleNamespace(
        hermetic=HERMETIC_SESSION,
        live_infra_enabled=live_infra_enabled(),
        token_cache_dir=TOKEN_CACHE_DIR,
        token_cache_base=TOKEN_CACHE_BASE,
        redis_probed=lambda: _REDIS_PROBE is not None,
    )


@pytest.fixture(autouse=True)
def _clean_prometheus_registry():
    """Clean up Prometheus metric registry between tests to prevent pollution."""
    try:
        from prometheus_client import REGISTRY

        names_before = set(REGISTRY._names_to_collectors.keys())
    except ImportError:
        yield
        return

    yield

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


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """A temp config directory that BOTH the loader and the env var name."""
    from shared.config.loader import ConfigLoader

    path = tmp_path / "config"
    path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("KIS_CONFIG_DIR", str(path))
    ConfigLoader.set_config_dir(path)

    yield path

    ConfigLoader._instance = None
    ConfigLoader._config_dir = None
    ConfigLoader._cache.clear()


@pytest.fixture(autouse=True)
def _reset_config_loader_singleton():
    """Reset ConfigLoader singleton between tests to prevent config dir pollution."""
    yield
    try:
        from shared.config.loader import ConfigLoader

        ConfigLoader._instance = None
        ConfigLoader._config_dir = None
        ConfigLoader._cache.clear()
    except (ImportError, AttributeError):
        pass


@pytest.fixture(autouse=True)
def _reset_futures_open_cache():
    """Clear the module-level futures open/close cache between tests."""
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
    """Precondition for a test that needs THIS repository's git metadata."""
    reason = git_env.repo_checkout_skip_reason(
        git_env.repo_checkout_state(project_root),
        os.environ.get(git_env.NO_GIT_METADATA_ENV),
    )
    if reason is not None:
        pytest.skip(reason)
