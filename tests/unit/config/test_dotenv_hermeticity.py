"""Hermeticity guards: a test process must never reach a real ``.env`` (#698)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import dotenv
import pytest

from shared.config import dotenv_guard
from tests.support import hermetic_env
from tests.support.live_infra import live_infra_enabled

REPO_ROOT = Path(__file__).resolve().parents[3]


CANARY_APP_KEY = "CANARY-APP-KEY-MUST-NEVER-BE-LOADED"
CANARY_PORT = "4111"
CHECKOUT_PORT = "5999"

_COPIED = (
    "shared/config/dotenv_guard.py",
    "shared/config/runtime_defaults.py",
)
_PACKAGE_MARKERS = (
    "shared/__init__.py",
    "shared/config/__init__.py",
)

_PROBE = """
import json
import os

from shared.config import dotenv_guard
from shared.config.runtime_defaults import dashboard_host_port_from_env

loaded = dotenv_guard.load_project_dotenv()
dashboard_url = f"http://localhost:{dashboard_host_port_from_env()}"
print(json.dumps({
    "loaded": None if loaded is None else str(loaded),
    "candidates": [str(c) for c in dotenv_guard.project_dotenv_candidates()],
    "checkout": str(dotenv_guard.project_root()),
    "KIS_APP_KEY": os.environ.get("KIS_APP_KEY"),
    "KIS_STOCK_APP_KEY": os.environ.get("KIS_STOCK_APP_KEY"),
    "DASHBOARD_HOST_PORT": os.environ.get("DASHBOARD_HOST_PORT"),
    "dashboard_url": dashboard_url,
}))
"""


def _write_canary_env(path: Path, port: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"KIS_APP_KEY={CANARY_APP_KEY}\n"
        f"KIS_STOCK_APP_KEY={CANARY_APP_KEY}\n"
        f"DASHBOARD_HOST_PORT={port}\n"
    )


def _make_checkout(root: Path) -> Path:
    """Build a minimal, self-contained copy of this project's loader."""
    for marker in _PACKAGE_MARKERS:
        target = root / marker
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("")
    for rel in _COPIED:
        shutil.copy2(REPO_ROOT / rel, root / rel)
    (root / "_probe.py").write_text(_PROBE)
    return root


def _run_probe(checkout: Path, cwd: Path, *, hermetic: bool = False) -> dict:
    """Import the copied entrypoint in a clean process and report what it saw."""
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONPATH": str(checkout),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if hermetic:
        env[hermetic_env.HERMETIC_ENV] = "1"

    result = subprocess.run(
        [sys.executable, str(checkout / "_probe.py")],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture
def reset_config_loader():
    """Hand back a ConfigLoader reset that is undone at teardown."""
    from shared.config.loader import ConfigLoader

    saved_instance = ConfigLoader._instance
    saved_dir = ConfigLoader._config_dir
    saved_cache = dict(ConfigLoader._cache)

    def _reset():
        ConfigLoader._instance = None
        ConfigLoader._config_dir = None
        ConfigLoader._cache.clear()

    yield _reset

    ConfigLoader._instance = saved_instance
    ConfigLoader._config_dir = saved_dir
    ConfigLoader._cache.clear()
    ConfigLoader._cache.update(saved_cache)


def test_nested_checkout_never_reads_the_outer_env(tmp_path):
    """#698 regression: a worktree must not load the primary checkout's .env."""
    outer = tmp_path / "primary"
    _write_canary_env(outer / ".env", CANARY_PORT)
    checkout = _make_checkout(outer / "worktree")

    seen = _run_probe(checkout, cwd=checkout)

    assert seen["loaded"] is None
    assert seen["KIS_APP_KEY"] is None
    assert seen["KIS_STOCK_APP_KEY"] is None
    assert seen["DASHBOARD_HOST_PORT"] is None
    assert str(outer / ".env") not in seen["candidates"]
    assert seen["dashboard_url"] == "http://localhost:5081"


def test_candidates_are_only_the_checkout_and_the_working_directory(tmp_path):
    """Nothing above either directory is ever a candidate, checkout first."""
    outer = tmp_path / "primary"
    _write_canary_env(outer / ".env", CANARY_PORT)
    checkout = _make_checkout(outer / "worktree")
    workdir = tmp_path / "elsewhere"
    workdir.mkdir()

    seen = _run_probe(checkout, cwd=workdir)

    assert seen["candidates"] == [
        str(checkout / ".env"),
        str(workdir / ".env"),
    ]


def test_checkout_dotenv_still_loads_outside_tests(tmp_path):
    """The paper/live CLI keeps reading its own checkout's .env."""
    outer = tmp_path / "primary"
    _write_canary_env(outer / ".env", CANARY_PORT)
    checkout = _make_checkout(outer / "worktree")
    (checkout / ".env").write_text(f"DASHBOARD_HOST_PORT={CHECKOUT_PORT}\n")
    workdir = tmp_path / "elsewhere"
    workdir.mkdir()

    seen = _run_probe(checkout, cwd=workdir)

    assert seen["loaded"] == str(checkout / ".env")
    assert seen["DASHBOARD_HOST_PORT"] == CHECKOUT_PORT
    assert seen["dashboard_url"] == f"http://localhost:{CHECKOUT_PORT}"
    assert seen["KIS_APP_KEY"] is None


def test_checkout_dotenv_wins_over_the_working_directory(tmp_path):
    """Another project's directory must not supply this project's config."""
    checkout = _make_checkout(tmp_path / "checkout")
    (checkout / ".env").write_text(f"DASHBOARD_HOST_PORT={CHECKOUT_PORT}\n")
    foreign = tmp_path / "other-project"
    foreign.mkdir()
    _write_canary_env(foreign / ".env", CANARY_PORT)

    seen = _run_probe(checkout, cwd=foreign)

    assert seen["loaded"] == str(checkout / ".env")
    assert seen["dashboard_url"] == f"http://localhost:{CHECKOUT_PORT}"
    assert seen["KIS_APP_KEY"] is None


def test_working_directory_dotenv_loads_when_the_checkout_has_none(tmp_path):
    """The working directory is a fallback, not a loss of function."""
    checkout = _make_checkout(tmp_path / "checkout")
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    (workdir / ".env").write_text(f"DASHBOARD_HOST_PORT={CHECKOUT_PORT}\n")

    seen = _run_probe(checkout, cwd=workdir)

    assert seen["loaded"] == str(workdir / ".env")
    assert seen["dashboard_url"] == f"http://localhost:{CHECKOUT_PORT}"


def test_hermetic_flag_disables_every_load(tmp_path):
    """With the switch on, neither candidate is read even when both exist."""
    checkout = _make_checkout(tmp_path / "checkout")
    _write_canary_env(checkout / ".env", CHECKOUT_PORT)
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    _write_canary_env(workdir / ".env", CANARY_PORT)

    seen = _run_probe(checkout, cwd=workdir, hermetic=True)

    assert seen["loaded"] is None
    assert seen["KIS_APP_KEY"] is None
    assert seen["dashboard_url"] == "http://localhost:5081"


def test_session_carries_no_broker_credentials():
    """No KIS_*/TELEGRAM_* value survives into the session but the switches."""
    leaked = sorted(
        key
        for key in os.environ
        if key.startswith(hermetic_env.SCRUBBED_PREFIXES)
        and key not in hermetic_env.PRESERVED_ENV
        and key not in {"KIS_CONFIG_DIR", "KIS_TOKEN_CACHE_DIR"}
    )
    assert leaked == []


def test_kis_auth_config_sees_no_credentials():
    """A KISAuthManager built mid-session cannot authenticate against KIS."""
    from shared.kis.auth import KISAuthConfig

    config = KISAuthConfig()

    assert config.app_key == ""
    assert config.app_secret == ""


def test_token_cache_is_pinned_outside_the_checkout_and_home():
    """The default cache directory is cwd — which is how #698 wrote a token."""
    from shared.kis.auth import KISAuthConfig

    cache_dir = os.environ.get("KIS_TOKEN_CACHE_DIR")
    assert cache_dir, "conftest must pin KIS_TOKEN_CACHE_DIR"
    assert hermetic_env.is_sandboxed(Path(cache_dir))

    for is_real in (True, False):
        path = KISAuthConfig(is_real=is_real).token_cache_path
        assert path.parent == Path(cache_dir)
        assert REPO_ROOT not in path.parents
        assert Path.home() not in path.parents


def test_no_token_cache_was_created_or_rewritten_by_this_session(
    token_cache_snapshot,
):
    """No stray ``.kis_token_*`` appeared where the pin cannot reach."""
    touched = hermetic_env.token_caches_touched_since(token_cache_snapshot)

    assert touched == [], (
        "a KIS token cache was created or rewritten during the test session: "
        + ", ".join(str(path) for path in touched)
        + " (#698)"
    )


def test_token_cache_witnesses_cover_the_checkout_cwd_and_home(
    token_cache_snapshot,
):
    """The snapshot watches the three places a stray token can land."""
    witnesses = set(hermetic_env.token_cache_witnesses(REPO_ROOT))

    assert REPO_ROOT / ".kis_token_real" in witnesses
    assert REPO_ROOT / ".kis_token_mock" in witnesses
    assert Path.home() / ".cache" / "kis_token_stock.json" in witnesses
    assert set(token_cache_snapshot) >= witnesses


def test_token_cache_snapshot_reports_only_what_changed(tmp_path):
    """A pre-existing, untouched file is not reported; a rewrite is."""
    stale = tmp_path / ".kis_token_real"
    stale.write_text("written long before this session")
    snapshot = hermetic_env.snapshot_token_caches([stale, tmp_path / ".kis_token_mock"])

    assert hermetic_env.token_caches_touched_since(snapshot) == []

    (tmp_path / ".kis_token_mock").write_text("issued by a test")
    assert hermetic_env.token_caches_touched_since(snapshot) == [
        tmp_path / ".kis_token_mock"
    ]

    stale.write_text("rewritten by a test, same length...")
    assert sorted(hermetic_env.token_caches_touched_since(snapshot)) == sorted(
        [stale, tmp_path / ".kis_token_mock"]
    )


def test_config_dir_is_pinned_to_this_checkout(reset_config_loader):
    """A worktree reads its own config/, never the primary checkout's."""
    from shared.config.loader import ConfigLoader

    assert os.environ["KIS_CONFIG_DIR"] == str(REPO_ROOT / "config")

    reset_config_loader()
    assert ConfigLoader.get_config_dir() == REPO_ROOT / "config"


def test_hermetic_switch_is_one_name_shared_with_the_runtime_loader():
    """conftest and the loader must never read different variables."""
    assert dotenv_guard.HERMETIC_ENV == "KIS_TEST_HERMETIC"
    assert hermetic_env.HERMETIC_ENV is dotenv_guard.HERMETIC_ENV
    assert hermetic_env.TRUTHY_VALUES is dotenv_guard.TRUTHY_VALUES
    assert hermetic_env.env_flag is dotenv_guard.env_flag


def test_argument_less_load_dotenv_is_refused():
    """The exact call that caused #698 now fails loudly instead of leaking."""
    with pytest.raises(hermetic_env.HermeticDotenvViolation, match="find_dotenv"):
        dotenv.load_dotenv()


@pytest.mark.parametrize("reader", ["load_dotenv", "dotenv_values"])
def test_argument_less_readers_are_all_refused(reader):
    """Guarding load_dotenv alone left dotenv_values free to do the same walk."""
    with pytest.raises(hermetic_env.HermeticDotenvViolation, match="find_dotenv"):
        getattr(dotenv, reader)()


def test_find_dotenv_may_not_hand_back_a_real_env(tmp_path, monkeypatch):
    """The walk itself is fine; returning a real file outside the sandbox is not."""
    inside = tmp_path / "inside"
    inside.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _write_canary_env(outside / ".env", CANARY_PORT)
    monkeypatch.setattr(hermetic_env, "sandbox_roots", lambda: (inside,))
    monkeypatch.chdir(outside)

    with pytest.raises(hermetic_env.HermeticDotenvViolation, match="refusing to load"):
        dotenv.find_dotenv(usecwd=True)


def test_find_dotenv_returns_nothing_when_there_is_nothing(tmp_path, monkeypatch):
    """A walk that finds no file is not an error — that is every CI checkout."""
    monkeypatch.chdir(tmp_path)

    assert dotenv.find_dotenv(usecwd=True) == ""


@pytest.mark.parametrize("reader", ["load_dotenv", "dotenv_values"])
def test_every_reader_refuses_a_real_env_outside_the_sandbox(
    reader, tmp_path, monkeypatch
):
    """The refusal is per-reader, not only on the one that caused #698."""
    inside = tmp_path / "inside"
    inside.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _write_canary_env(outside / ".env", CANARY_PORT)
    monkeypatch.setattr(hermetic_env, "sandbox_roots", lambda: (inside,))

    with pytest.raises(hermetic_env.HermeticDotenvViolation, match="refusing to load"):
        getattr(dotenv, reader)(outside / ".env")

    assert os.environ.get("KIS_APP_KEY") is None


def test_existing_dotenv_outside_the_sandbox_is_refused(tmp_path, monkeypatch):
    """A real .env outside the sandbox is refused even with an explicit path."""
    inside = tmp_path / "inside"
    inside.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _write_canary_env(outside / ".env", CANARY_PORT)
    monkeypatch.setattr(hermetic_env, "sandbox_roots", lambda: (inside,))

    with pytest.raises(hermetic_env.HermeticDotenvViolation, match="refusing to load"):
        dotenv.load_dotenv(outside / ".env")

    assert os.environ.get("KIS_APP_KEY") is None


def test_dotenv_inside_the_sandbox_is_allowed(tmp_path, monkeypatch):
    """pytest's own tmp_path stays usable — the guard is not a blanket ban."""
    probe = "KIS_TEST_HERMETICITY_PROBE"
    env_file = tmp_path / ".env"
    env_file.write_text(f"{probe}=inside-sandbox\n")
    monkeypatch.setenv(probe, "placeholder")

    assert dotenv.load_dotenv(env_file, override=True) is True
    assert os.environ[probe] == "inside-sandbox"


def test_missing_dotenv_path_is_allowed(tmp_path):
    """A path that does not exist loads nothing, so it needs no refusal."""
    assert dotenv.load_dotenv(tmp_path / "does-not-exist" / ".env") is False


def test_guard_installs_once():
    """Re-installing the guard does not stack wrappers."""
    first = dotenv.load_dotenv
    restore = hermetic_env.install_dotenv_guard()
    assert dotenv.load_dotenv is first
    restore()
    assert dotenv.load_dotenv is first


def test_guard_installs_without_python_dotenv(monkeypatch):
    """Installing is a no-op where python-dotenv is absent."""
    monkeypatch.setitem(sys.modules, "dotenv", None)
    monkeypatch.setitem(sys.modules, "dotenv.main", None)

    restore = hermetic_env.install_dotenv_guard()
    restore()


def test_hermeticity_does_not_depend_on_the_live_infra_gate(
    hermetic_session_state,
):
    """Hermeticity is unconditional; the opt-in lifts the Redis gate only."""
    assert hermetic_session_state.hermetic is True
    assert os.environ[hermetic_env.HERMETIC_ENV] == "1"
    assert hermetic_session_state.live_infra_enabled is live_infra_enabled()

    leaked = [
        key
        for key in os.environ
        if key.startswith(hermetic_env.SCRUBBED_PREFIXES)
        and key not in hermetic_env.PRESERVED_ENV
        and key not in {"KIS_CONFIG_DIR", "KIS_TOKEN_CACHE_DIR"}
    ]
    assert leaked == []


def test_redis_is_not_pinged_unless_the_live_infra_gate_is_open(
    hermetic_session_state,
):
    """No real socket to Redis DB 1 — which the paper runtime shares — unless"""
    if hermetic_session_state.live_infra_enabled:
        pytest.skip("the operator opened the gate; probing is the point")

    assert hermetic_session_state.redis_probed() is False


def test_basetemp_outside_the_system_temp_dir_must_be_registered(tmp_path, monkeypatch):
    """A relocated basetemp is not sandboxed until the session registers it."""
    fake_system_tmp = tmp_path / "system-tmp"
    fake_system_tmp.mkdir()
    monkeypatch.setattr(
        hermetic_env.tempfile, "gettempdir", lambda: str(fake_system_tmp)
    )
    monkeypatch.setattr(hermetic_env, "_REGISTERED_SANDBOX_ROOTS", [])
    monkeypatch.delenv("PYTEST_DEBUG_TEMPROOT", raising=False)

    relocated = tmp_path / "in-checkout-basetemp"
    relocated.mkdir()
    env_file = relocated / "sub" / ".env"
    env_file.parent.mkdir()
    env_file.write_text("KIS_TEST_BASETEMP_PROBE=1\n")

    assert hermetic_env.is_sandboxed(env_file) is False

    hermetic_env.register_sandbox_root(relocated)

    assert hermetic_env.is_sandboxed(env_file) is True
    assert relocated.resolve() in hermetic_env.sandbox_roots()


def test_register_sandbox_root_ignores_none_and_deduplicates(monkeypatch):
    """`pytest_configure` passes `--basetemp` straight through, usually None."""
    monkeypatch.setattr(hermetic_env, "_REGISTERED_SANDBOX_ROOTS", [])

    hermetic_env.register_sandbox_root(None)
    assert hermetic_env._REGISTERED_SANDBOX_ROOTS == []

    hermetic_env.register_sandbox_root("/")
    hermetic_env.register_sandbox_root("/")
    assert len(hermetic_env._REGISTERED_SANDBOX_ROOTS) == 1


def test_this_session_registered_its_basetemp(request):
    """When this run uses --basetemp, the session must have registered it."""
    basetemp = getattr(request.config.option, "basetemp", None)
    if basetemp is None:
        pytest.skip("this run did not pass --basetemp")

    assert hermetic_env.is_sandboxed(Path(basetemp))


def test_pinned_token_cache_is_under_one_session_wide_root(hermetic_session_state):
    """Every process's pin lives under a root the controller can scan."""
    base = hermetic_session_state.token_cache_base
    pinned = hermetic_session_state.token_cache_dir

    assert base is not None
    assert os.environ[hermetic_env.TOKEN_CACHE_BASE_ENV] == str(base)
    assert pinned == base or base in pinned.parents

    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker:
        assert pinned.name == worker


def test_scrub_keeps_redis_connection_variables():
    """``REDIS_*`` survives the scrub, which touches only KIS_*/TELEGRAM_*."""
    environ = {
        "REDIS_HOST": "redis.example",
        "REDIS_PORT": "6399",
        "REDIS_DB": "1",
        "REDIS_PASSWORD": "secret",
        "REDIS_URL": "redis://redis.example:6399/1",
        "KIS_STOCK_APP_KEY": "must-go",
        "TELEGRAM_BOT_TOKEN": "must-go",
        hermetic_env.LIVE_INFRA_ENV: "1",
    }

    removed = hermetic_env.scrub_broker_env(environ)

    assert removed == ["KIS_STOCK_APP_KEY", "TELEGRAM_BOT_TOKEN"]
    assert environ == {
        "REDIS_HOST": "redis.example",
        "REDIS_PORT": "6399",
        "REDIS_DB": "1",
        "REDIS_PASSWORD": "secret",
        "REDIS_URL": "redis://redis.example:6399/1",
        hermetic_env.LIVE_INFRA_ENV: "1",
    }


_GATED_MODULE = "tests/integration/test_redis_tls.py"


def _run_gated_module(*, flag: str | None, args: tuple[str, ...] = ()) -> str:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONDONTWRITEBYTECODE": "1",
        "REDIS_HOST": "127.0.0.1",
        "REDIS_PORT": "1",
        "REDIS_DB": "1",
    }
    if flag is not None:
        env[hermetic_env.LIVE_INFRA_ENV] = flag

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            _GATED_MODULE,
            "-x",
            "-q",
            "-rsf",
            "--no-header",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:warnings",
            "-p",
            "no:randomly",
            *args,
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    return result.stdout + result.stderr


def test_live_infra_item_skips_without_the_flag():
    """The default session must not touch Redis DB 1, which paper shares."""
    collected = _run_gated_module(
        flag=None, args=("--collect-only", "-m", "live_infra")
    )
    selected = re.search(rf"{re.escape(_GATED_MODULE)}: (\d+)", collected)
    assert selected is not None, collected
    assert int(selected.group(1)) > 0

    output = _run_gated_module(flag=None)

    assert "SKIPPED" in output
    assert "is unreachable" not in output


def test_live_infra_item_runs_when_the_flag_is_set():
    """With the flag set the item RUNS — the hermetic session must not close"""
    output = _run_gated_module(flag="1")

    assert f"{hermetic_env.LIVE_INFRA_ENV} is set" in output
    assert "is unreachable" in output
    assert "SKIPPED" not in output
