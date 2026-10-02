"""Hermetic pytest-session helpers (#698).

A pytest process must never reach a real ``.env``, a real broker credential or
a real token cache. Three separate paths could put one there before this
module existed:

1. ``cli/commands/common.py`` called ``load_dotenv()`` with no argument, and
   python-dotenv's ``find_dotenv()`` walks from the *calling file* up to the
   filesystem root — out of a nested worktree and into the primary checkout's
   ``.env``. Fixed at the source by
   :func:`shared.config.dotenv_guard.load_project_dotenv`.
2. ``tests/conftest.py`` loaded ``<checkout>/.env`` on purpose, so the main
   checkout's own suite ran with the operator's real keys.
3. The variables were already exported in the operator's shell.

:func:`scrub_broker_env` closes (2) and (3) by emptying the whole ``KIS_*`` and
``TELEGRAM_*`` namespace, and :func:`install_dotenv_guard` turns any *remaining*
``.env`` read into a loud, named failure instead of a silent credential
injection — including for a caller added after this was written.

:func:`token_cache_witnesses` and :func:`token_caches_touched_since` cover the
other half of the 2026-09-15 incident: the token file that a leaked credential
produced. They compare against a snapshot taken at session start rather than
asserting absence, because the primary checkout legitimately holds
``.kis_token_real`` / ``.kis_token_mock`` from ordinary host ``sts`` runs
(the default cache directory is ``Path.cwd()``) and a plain existence check
would blame the test run for files written months earlier.

The switch name and its truthy values are imported from
``shared.config.dotenv_guard`` rather than repeated, so the two halves cannot
drift: conftest setting one name while the loader reads another would silently
re-open every path above.

Nothing here is imported by runtime code; it exists only for the test session.
"""

from __future__ import annotations

import functools
import os
import sys
import tempfile
from collections.abc import Callable, Iterable, MutableMapping
from pathlib import Path

from shared.config.dotenv_guard import HERMETIC_ENV, TRUTHY_VALUES, env_flag
from tests.support.live_infra import LIVE_INFRA_ENV, live_infra_enabled

__all__ = [
    "HERMETIC_ENV",
    "HOME_TOKEN_CACHE_NAMES",
    "LIVE_INFRA_ENV",
    "live_infra_enabled",
    "PRESERVED_ENV",
    "SCRUBBED_PREFIXES",
    "TRUTHY_VALUES",
    "TokenCacheSnapshot",
    "HermeticDotenvViolation",
    "env_flag",
    "install_dotenv_guard",
    "is_sandboxed",
    "sandbox_roots",
    "scrub_broker_env",
    "register_sandbox_root",
    "snapshot_token_caches",
    "token_cache_witnesses",
    "token_caches_touched_since",
]

#: Every variable in these namespaces is removed from a hermetic session. Both
#: carry broker or operator credentials (``KIS_*_APP_KEY``, ``KIS_*_ACCOUNT_NO``,
#: ``TELEGRAM_*_BOT_TOKEN``) and both are populated by the deploy host's ``.env``.
SCRUBBED_PREFIXES = ("KIS_", "TELEGRAM_")

#: Test-control variables that happen to share the ``KIS_`` prefix. They carry
#: no credential and the session reads them to decide how to run.
PRESERVED_ENV = frozenset(
    {
        HERMETIC_ENV,
        LIVE_INFRA_ENV,
        "KIS_TEST_IMAGE_NO_GIT_METADATA",
    }
)

#: ``shared/kis/auth.py::KISAuthConfig.token_cache_path`` writes these into the
#: token cache directory, which defaults to ``Path.cwd()``.
CWD_TOKEN_CACHE_NAMES = (".kis_token_real", ".kis_token_mock")

#: ``shared/collector/historical/{stock,backfill}.py`` keep their own caches
#: under the user's home, outside any directory this session can pin.
HOME_TOKEN_CACHE_NAMES = ("kis_token_stock.json", "kis_token_futures.json")

#: What a file looked like when the snapshot was taken: ``None`` for absent,
#: otherwise identity enough to notice a rewrite.
_Stat = tuple[int, int, int] | None

TokenCacheSnapshot = dict[Path, _Stat]


class HermeticDotenvViolation(RuntimeError):
    """A test-time code path tried to load a ``.env`` outside the sandbox."""


def scrub_broker_env(
    environ: MutableMapping[str, str] | None = None,
) -> list[str]:
    """Remove every broker/notification credential from ``environ``.

    Returns:
        The names removed, sorted — useful for a diagnostic message.
    """
    target = os.environ if environ is None else environ
    removed = [
        key
        for key in list(target)
        if key.startswith(SCRUBBED_PREFIXES) and key not in PRESERVED_ENV
    ]
    for key in removed:
        del target[key]
    return sorted(removed)


# ---------------------------------------------------------------------------
# Token-cache witnesses
# ---------------------------------------------------------------------------


def token_cache_witnesses(
    project_root: Path, token_cache_dir: Path | None = None
) -> tuple[Path, ...]:
    """Every place a KIS token cache could land during a test run.

    The checkout root and the working directory because
    ``KISAuthConfig.token_cache_path`` defaults to ``Path.cwd()``; the home
    cache because two collectors hardcode ``~/.cache/kis_token_*.json``; and
    the session's pinned ``KIS_TOKEN_CACHE_DIR``, because pinning decides
    *where* a token lands, not whether one is issued — a test that reaches the
    KIS token endpoint is the thing #698 is about, and it would otherwise
    write there unobserved.
    """
    roots = [project_root]
    if token_cache_dir is not None:
        roots.append(token_cache_dir)
    try:
        cwd = Path.cwd()
    except OSError:  # pragma: no cover - cwd deleted under us
        cwd = None
    if cwd is not None and cwd != project_root:
        roots.append(cwd)

    witnesses = [root / name for root in roots for name in CWD_TOKEN_CACHE_NAMES]
    home_cache = Path.home() / ".cache"
    witnesses.extend(home_cache / name for name in HOME_TOKEN_CACHE_NAMES)
    return tuple(witnesses)


def _stat_or_none(path: Path) -> _Stat:
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def snapshot_token_caches(paths: Iterable[Path]) -> TokenCacheSnapshot:
    """Record what each witness looked like before any test ran."""
    return {path: _stat_or_none(path) for path in paths}


def token_caches_touched_since(snapshot: TokenCacheSnapshot) -> list[Path]:
    """Witnesses this session created or rewrote, in snapshot order.

    A file that already existed and has not changed is *not* reported: on the
    primary checkout ``.kis_token_real`` predates this work by months, and
    failing on it would accuse the current run of something it did not do.
    """
    return [path for path, before in snapshot.items() if _stat_or_none(path) != before]


# ---------------------------------------------------------------------------
# dotenv guard
# ---------------------------------------------------------------------------


#: Extra roots registered once pytest's config exists. The guard is installed
#: at conftest *import* time, before `--basetemp` has been parsed, so the set
#: is read lazily on every check rather than frozen at install.
_REGISTERED_SANDBOX_ROOTS: list[Path] = []


def register_sandbox_root(path: Path | str | None) -> None:
    """Add a directory the session may read a ``.env`` from.

    ``tests/conftest.py`` calls this from ``pytest_configure`` with
    ``--basetemp``. Without it, ``pytest --basetemp=./.pytest-tmp`` (common
    when inspecting outputs) puts every ``tmp_path`` inside the checkout, and
    the guard then refuses the suite's own fixture files.
    """
    if path is None:
        return
    candidate = Path(path)
    try:
        resolved = candidate.resolve()
    except OSError:  # pragma: no cover - unreadable path
        return
    if resolved not in _REGISTERED_SANDBOX_ROOTS:
        _REGISTERED_SANDBOX_ROOTS.append(resolved)


def sandbox_roots() -> tuple[Path, ...]:
    """Directories a hermetic test session may read a ``.env`` from.

    The system temp directory covers pytest's ``tmp_path``/``tmp_path_factory``
    in its default location; ``PYTEST_DEBUG_TEMPROOT`` and anything passed to
    :func:`register_sandbox_root` cover the relocated ones.
    """
    roots = [Path(tempfile.gettempdir())]
    debug_temproot = os.environ.get("PYTEST_DEBUG_TEMPROOT")
    if debug_temproot:
        roots.append(Path(debug_temproot))
    resolved = []
    for root in roots:
        try:
            resolved.append(root.resolve())
        except OSError:  # pragma: no cover - unreadable temp root
            continue
    resolved.extend(_REGISTERED_SANDBOX_ROOTS)
    return tuple(dict.fromkeys(resolved))


def is_sandboxed(path: Path) -> bool:
    """Whether ``path`` lies inside one of the :func:`sandbox_roots`."""
    try:
        resolved = path.resolve()
    except OSError:  # pragma: no cover - unreadable path
        return False
    return any(resolved == root or root in resolved.parents for root in sandbox_roots())


_GUARD_MARKER = "_kis_hermetic_guard"

#: Every python-dotenv entry point that can read a file off disk. Guarding only
#: ``load_dotenv`` left ``dotenv_values()`` and ``find_dotenv()`` free to walk
#: out of the checkout exactly as #698 did.
_GUARDED_NAMES = ("load_dotenv", "dotenv_values", "find_dotenv")


def _refuse_argument_less(name: str) -> HermeticDotenvViolation:
    return HermeticDotenvViolation(
        f"argument-less {name}() is refused during tests: python-dotenv "
        "resolves it with find_dotenv(), which walks out of this checkout and "
        "can read the primary checkout's real .env (#698). Use "
        "shared.config.dotenv_guard.load_project_dotenv() instead."
    )


def _refuse_path(name: str, candidate: Path) -> HermeticDotenvViolation:
    return HermeticDotenvViolation(
        f"refusing to load {candidate} during a hermetic test session "
        f"(via {name}): only files under "
        f"{', '.join(str(r) for r in sandbox_roots())} may be read. A test "
        "that genuinely needs real infrastructure credentials must be marked "
        f"live_infra and run with {LIVE_INFRA_ENV}=1 (#698)."
    )


def _guard_reader(real: Callable[..., object], name: str) -> Callable[..., object]:
    """Wrap ``load_dotenv``/``dotenv_values``: same first two parameters."""

    @functools.wraps(real)
    def guarded(dotenv_path=None, stream=None, *args, **kwargs):  # type: ignore[no-untyped-def]
        if dotenv_path is None and stream is None:
            raise _refuse_argument_less(name)
        if dotenv_path is not None:
            candidate = Path(os.fspath(dotenv_path))
            if candidate.is_file() and not is_sandboxed(candidate):
                raise _refuse_path(name, candidate)
        return real(dotenv_path, stream, *args, **kwargs)

    return guarded


def _guard_finder(real: Callable[..., str]) -> Callable[..., str]:
    """Wrap ``find_dotenv``: let it walk, refuse what the walk found.

    Refusing the call outright would be louder than it needs to be — the walk
    is harmless when it finds nothing, which is every CI checkout. What must
    not happen is handing back a real ``.env`` from outside the sandbox for a
    caller to read.
    """

    @functools.wraps(real)
    def guarded(*args, **kwargs):  # type: ignore[no-untyped-def]
        found = real(*args, **kwargs)
        if found:
            candidate = Path(found)
            if candidate.is_file() and not is_sandboxed(candidate):
                raise _refuse_path("find_dotenv", candidate)
        return found

    return guarded


def _rebind_early_importers(
    originals: dict[str, object], guards: dict[str, object]
) -> None:
    """Replace names other modules bound before the guard was installed.

    ``from dotenv import load_dotenv`` copies the function object, so a pytest
    plugin or ``sitecustomize`` imported before ``tests/conftest.py`` keeps the
    raw one. Sweeping ``sys.modules`` once catches those bindings.
    """
    for module in list(sys.modules.values()):
        if module is None:
            continue
        try:
            namespace = vars(module)
        except TypeError:  # pragma: no cover - exotic module object
            continue
        if str(namespace.get("__name__", "")).startswith("dotenv"):
            continue
        for name, original in originals.items():
            # `name in vars(module)` rather than getattr: a package with a
            # module-level __getattr__ (lazy_loader, scipy/numpy shims,
            # six.moves) would otherwise run its import path three times per
            # module, during conftest import, with the cost hidden by the
            # except below.
            if name in namespace and namespace[name] is original:
                try:
                    setattr(module, name, guards[name])
                except Exception:  # pragma: no cover - read-only module
                    continue


def install_dotenv_guard() -> Callable[[], None]:
    """Make python-dotenv refuse real ``.env`` files for this process.

    Every reader in :data:`_GUARDED_NAMES` is wrapped. Two things are refused:

    * an argument-less call, because its ``find_dotenv()`` walk is the #698
      root cause and its target cannot be known in advance; and
    * a path that **exists** and sits outside :func:`sandbox_roots`.

    A path that does not exist is allowed through: the read is a no-op either
    way, and letting it pass keeps CI (which has no ``.env`` anywhere) free of
    failures that say nothing about hermeticity.

    Returns:
        A callable that restores the original functions. Idempotent — calling
        this twice installs one guard and the second call's restore is a no-op.
        A no-op too when python-dotenv is not installed: the ``tos-firewall``
        job installs the root project with ``--no-deps``, and with no loader
        present there is nothing to guard.
    """
    try:
        import dotenv
        import dotenv.main
    except ImportError:
        return lambda: None

    originals: dict[str, object] = {}
    for name in _GUARDED_NAMES:
        real = getattr(dotenv.main, name, None)
        if real is None:  # pragma: no cover - python-dotenv dropped an API
            continue
        if getattr(real, _GUARD_MARKER, False):
            return lambda: None
        originals[name] = real

    guards: dict[str, object] = {}
    for name, real in originals.items():
        guard = (
            _guard_finder(real)  # type: ignore[arg-type]
            if name == "find_dotenv"
            else _guard_reader(real, name)  # type: ignore[arg-type]
        )
        setattr(guard, _GUARD_MARKER, True)
        guards[name] = guard

    for name, guard in guards.items():
        setattr(dotenv.main, name, guard)
        if hasattr(dotenv, name):
            setattr(dotenv, name, guard)
    _rebind_early_importers(originals, guards)

    def restore() -> None:
        for name, real in originals.items():
            setattr(dotenv.main, name, real)
            if hasattr(dotenv, name):
                setattr(dotenv, name, real)
        _rebind_early_importers(guards, originals)

    return restore
