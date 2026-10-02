"""Hermeticity guards: a test process must never reach a real ``.env`` (#698).

On 2026-09-15 a unit-test run inside a git worktree nested under the primary
checkout (``<repo>/.claude/worktrees/<name>/``) loaded the **primary**
checkout's ``.env``, put the operator's real KIS app key in the test process
and had a real token issued and written to ``.kis_token_real``. The mechanism
was python-dotenv's ``find_dotenv()``, which walks from the calling file up to
the filesystem root, reached by the argument-less ``load_dotenv()`` that
``cli/commands/common.py`` ran at import time.

Two layers are asserted here, and they fail independently:

* the **code** layer — ``shared.config.dotenv_guard.load_project_dotenv`` reads
  at most two exact paths and never walks up. Proven in a subprocess with no
  hermetic flag set, i.e. a production-shaped process, so these tests would
  still catch a regression if the pytest guard below were removed.
* the **session** layer — ``tests/conftest.py`` empties the ``KIS_*`` /
  ``TELEGRAM_*`` namespace, pins the config and token-cache directories, and
  makes ``dotenv.load_dotenv`` refuse real files.
"""

from __future__ import annotations

import json
import os
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

#: The session-layer assertions describe the hermetic default. The
#: live-infra opt-in deliberately loads .env, so they do not apply there.
requires_hermetic_session = pytest.mark.skipif(
    hermetic_env.live_infra_enabled(),
    reason=(
        "session is non-hermetic by operator opt-in "
        f"({hermetic_env.LIVE_INFRA_ENV}=1)"
    ),
)

CANARY_APP_KEY = "CANARY-APP-KEY-MUST-NEVER-BE-LOADED"
CANARY_PORT = "4111"
CHECKOUT_PORT = "5999"

#: The files a fake checkout needs to run the loader. Everything else is an
#: empty package marker, so the tree is self-contained: no PYTHONPATH entry
#: points at the real repository and ``project_root()`` resolves to the fake
#: checkout rather than to this one.
_COPIED = (
    "shared/config/dotenv_guard.py",
    "shared/config/runtime_defaults.py",
    "cli/commands/common.py",
)
_PACKAGE_MARKERS = (
    "shared/__init__.py",
    "shared/config/__init__.py",
    "cli/__init__.py",
    "cli/commands/__init__.py",
)

_PROBE = """
import json
import os

import cli.commands.common as common
from shared.config import dotenv_guard

loaded = dotenv_guard.load_project_dotenv()
print(json.dumps({
    "loaded": None if loaded is None else str(loaded),
    "candidates": [str(c) for c in dotenv_guard.project_dotenv_candidates()],
    "checkout": str(dotenv_guard.project_root()),
    "KIS_APP_KEY": os.environ.get("KIS_APP_KEY"),
    "KIS_STOCK_APP_KEY": os.environ.get("KIS_STOCK_APP_KEY"),
    "DASHBOARD_HOST_PORT": os.environ.get("DASHBOARD_HOST_PORT"),
    "dashboard_url": common.DEFAULT_DASHBOARD_URL,
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
    """Import the copied entrypoint in a clean process and report what it saw.

    The environment is built from scratch rather than inherited, so the result
    reflects the loader's own behavior and not this pytest session's scrub.
    """
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
    """Hand back a ConfigLoader reset that is undone at teardown.

    The singleton is class state shared by every test in the worker, so
    clearing it inline leaks a re-resolved loader into whatever runs next
    under ``-n auto``.
    """
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


# ---------------------------------------------------------------------------
# The code layer: load_project_dotenv never walks out of its own checkout
# ---------------------------------------------------------------------------


def test_nested_checkout_never_reads_the_outer_env(tmp_path):
    """#698 regression: a worktree must not load the primary checkout's .env.

    Red before the fix: ``find_dotenv()`` walked from
    ``<outer>/<inner>/cli/commands`` up to ``<outer>/.env`` and exported the
    canary key.
    """
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


def test_candidates_are_only_the_working_directory_and_the_checkout(tmp_path):
    """Nothing above either directory is ever a candidate."""
    outer = tmp_path / "primary"
    _write_canary_env(outer / ".env", CANARY_PORT)
    checkout = _make_checkout(outer / "worktree")
    workdir = tmp_path / "elsewhere"
    workdir.mkdir()

    seen = _run_probe(checkout, cwd=workdir)

    assert seen["candidates"] == [
        str(workdir / ".env"),
        str(checkout / ".env"),
    ]


# ---------------------------------------------------------------------------
# The runtime path: the CLI outside tests still loads .env exactly as before
# ---------------------------------------------------------------------------


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
    # The outer checkout's .env was right there and still was not read.
    assert seen["KIS_APP_KEY"] is None


def test_working_directory_dotenv_wins_over_the_checkout(tmp_path):
    """Running from a directory with its own .env keeps working.

    This is the pre-#698 ``python -c`` behavior, and it is what lets the
    CLI tests below fix which file the loader reads without depending on
    whether the checkout running the suite has a ``.env`` of its own.
    """
    checkout = _make_checkout(tmp_path / "checkout")
    (checkout / ".env").write_text(f"DASHBOARD_HOST_PORT={CANARY_PORT}\n")
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


# ---------------------------------------------------------------------------
# The session layer: this very pytest process is hermetic
# ---------------------------------------------------------------------------


@requires_hermetic_session
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


@requires_hermetic_session
def test_kis_auth_config_sees_no_credentials():
    """A KISAuthManager built mid-session cannot authenticate against KIS."""
    from shared.kis.auth import KISAuthConfig

    config = KISAuthConfig()

    assert config.app_key == ""
    assert config.app_secret == ""


@requires_hermetic_session
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


@requires_hermetic_session
def test_no_token_cache_was_created_or_rewritten_by_this_session(
    token_cache_snapshot,
):
    """No stray ``.kis_token_*`` appeared where the pin cannot reach.

    Compared against a snapshot taken before any test ran, never asserted
    absent. The primary checkout holds ``.kis_token_real`` (2026-07-08) and
    ``.kis_token_mock`` (2026-06-09) from ordinary host ``sts`` runs, because
    the default cache directory is ``Path.cwd()``; an existence check would
    fail there forever and blame this run for files written months earlier.
    """
    touched = hermetic_env.token_caches_touched_since(token_cache_snapshot)

    assert touched == [], (
        "a KIS token cache was created or rewritten during the test session: "
        + ", ".join(str(path) for path in touched)
        + " (#698)"
    )


@requires_hermetic_session
def test_token_cache_witnesses_cover_the_checkout_cwd_and_home(
    token_cache_snapshot,
):
    """The snapshot watches the three places a stray token can land."""
    witnesses = set(hermetic_env.token_cache_witnesses(REPO_ROOT))

    assert REPO_ROOT / ".kis_token_real" in witnesses
    assert REPO_ROOT / ".kis_token_mock" in witnesses
    assert Path.home() / ".cache" / "kis_token_stock.json" in witnesses
    assert set(token_cache_snapshot) >= witnesses


@requires_hermetic_session
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


@requires_hermetic_session
def test_config_dir_is_pinned_to_this_checkout(reset_config_loader):
    """A worktree reads its own config/, never the primary checkout's."""
    from shared.config.loader import ConfigLoader

    assert os.environ["KIS_CONFIG_DIR"] == str(REPO_ROOT / "config")

    reset_config_loader()
    assert ConfigLoader.get_config_dir() == REPO_ROOT / "config"


@requires_hermetic_session
def test_hermetic_switch_is_one_name_shared_with_the_runtime_loader():
    """conftest and the loader must never read different variables.

    They import the same constant, so this pins the literal the docs and the
    runbook name — a rename stays a deliberate, visible change.
    """
    assert dotenv_guard.HERMETIC_ENV == "KIS_TEST_HERMETIC"
    assert hermetic_env.HERMETIC_ENV is dotenv_guard.HERMETIC_ENV
    assert hermetic_env.TRUTHY_VALUES is dotenv_guard.TRUTHY_VALUES
    assert hermetic_env.env_flag is dotenv_guard.env_flag


@requires_hermetic_session
def test_argument_less_load_dotenv_is_refused():
    """The exact call that caused #698 now fails loudly instead of leaking."""
    with pytest.raises(hermetic_env.HermeticDotenvViolation, match="find_dotenv"):
        dotenv.load_dotenv()


@requires_hermetic_session
@pytest.mark.parametrize("reader", ["load_dotenv", "dotenv_values"])
def test_argument_less_readers_are_all_refused(reader):
    """Guarding load_dotenv alone left dotenv_values free to do the same walk."""
    with pytest.raises(hermetic_env.HermeticDotenvViolation, match="find_dotenv"):
        getattr(dotenv, reader)()


@requires_hermetic_session
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


@requires_hermetic_session
def test_find_dotenv_returns_nothing_when_there_is_nothing(tmp_path, monkeypatch):
    """A walk that finds no file is not an error — that is every CI checkout."""
    monkeypatch.chdir(tmp_path)

    assert dotenv.find_dotenv(usecwd=True) == ""


@requires_hermetic_session
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


@requires_hermetic_session
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


@requires_hermetic_session
def test_dotenv_inside_the_sandbox_is_allowed(tmp_path, monkeypatch):
    """pytest's own tmp_path stays usable — the guard is not a blanket ban."""
    probe = "KIS_TEST_HERMETICITY_PROBE"
    env_file = tmp_path / ".env"
    env_file.write_text(f"{probe}=inside-sandbox\n")
    # Registered with monkeypatch so the variable is removed at teardown;
    # python-dotenv writes straight into os.environ and would otherwise leave
    # it behind for the rest of the session.
    monkeypatch.setenv(probe, "placeholder")

    assert dotenv.load_dotenv(env_file, override=True) is True
    assert os.environ[probe] == "inside-sandbox"


@requires_hermetic_session
def test_missing_dotenv_path_is_allowed(tmp_path):
    """A path that does not exist loads nothing, so it needs no refusal."""
    assert dotenv.load_dotenv(tmp_path / "does-not-exist" / ".env") is False


@requires_hermetic_session
def test_guard_installs_once():
    """Re-installing the guard does not stack wrappers."""
    first = dotenv.load_dotenv
    restore = hermetic_env.install_dotenv_guard()
    assert dotenv.load_dotenv is first
    restore()
    assert dotenv.load_dotenv is first


def test_guard_installs_without_python_dotenv(monkeypatch):
    """Installing is a no-op where python-dotenv is absent.

    The ``tos-firewall`` job installs the root project with ``--no-deps``, so
    conftest runs there with no loader to wrap. Importing dotenv
    unconditionally turned that job's whole collection into an ImportError.
    """
    monkeypatch.setitem(sys.modules, "dotenv", None)
    monkeypatch.setitem(sys.modules, "dotenv.main", None)

    restore = hermetic_env.install_dotenv_guard()
    restore()


# ---------------------------------------------------------------------------
# The hermetic session and the live-infra gate are one switch, not two
# ---------------------------------------------------------------------------


def test_hermeticity_is_the_exact_negation_of_the_live_infra_gate(
    hermetic_session_state,
):
    """One predicate decides both, so no env value can split them.

    Two readings of ``KIS_RUN_LIVE_INFRA_TESTS`` with different truthy sets —
    ``live_infra.py`` accepts 1/true/yes, ``dotenv_guard`` also accepts "on" —
    would let ``=on`` drop hermeticity while leaving every live_infra test
    skipped: credentials loaded, nothing gained, and silently (#845/#698).
    """
    assert hermetic_session_state.hermetic is not (
        hermetic_session_state.live_infra_enabled
    )
    assert hermetic_session_state.live_infra_enabled is live_infra_enabled()


@requires_hermetic_session
def test_live_infra_gate_never_pings_redis_in_a_hermetic_session(
    hermetic_session_state,
):
    """The gate's one-ping-per-process must not fire when nobody opted in.

    ``pytest_runtest_setup`` reaches ``redis_failure()`` only for an item
    marked ``live_infra`` *and* ``live_infra_enabled()``. A hermetic session is
    by definition the second one being false, so the ping — a real socket to
    Redis DB 1, which the paper runtime shares — cannot happen here.
    """
    assert hermetic_session_state.live_infra_enabled is False
    assert hermetic_session_state.redis_probed() is False
