"""Hermetic pytest-session helpers (#698)."""

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
    "TOKEN_CACHE_BASE_ENV",
    "new_token_caches_under",
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

TOKEN_CACHE_BASE_ENV = "KIS_TEST_TOKEN_CACHE_BASE"

SCRUBBED_PREFIXES = ("KIS_", "TELEGRAM_")

PRESERVED_ENV = frozenset(
    {
        HERMETIC_ENV,
        LIVE_INFRA_ENV,
        TOKEN_CACHE_BASE_ENV,
        "KIS_TEST_IMAGE_NO_GIT_METADATA",
    }
)

CWD_TOKEN_CACHE_NAMES = (".kis_token_real", ".kis_token_mock")

HOME_TOKEN_CACHE_NAMES = ("kis_token_stock.json", "kis_token_futures.json")

_Stat = tuple[int, int, int] | None

TokenCacheSnapshot = dict[Path, _Stat]


class HermeticDotenvViolation(RuntimeError):
    """A test-time code path tried to load a ``.env`` outside the sandbox."""


def scrub_broker_env(
    environ: MutableMapping[str, str] | None = None,
) -> list[str]:
    """Remove every broker/notification credential from ``environ``."""
    target = os.environ if environ is None else environ
    removed = [
        key
        for key in list(target)
        if key.startswith(SCRUBBED_PREFIXES) and key not in PRESERVED_ENV
    ]
    for key in removed:
        del target[key]
    return sorted(removed)


def token_cache_witnesses(project_root: Path) -> tuple[Path, ...]:
    """Fixed paths where a KIS token cache could land during a test run."""
    roots = [project_root]
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


def new_token_caches_under(root: Path | None) -> list[Path]:
    """Any ``.kis_token_*`` anywhere under the session's pinned cache root."""
    if root is None:
        return []
    try:
        return sorted(path for path in root.rglob(".kis_token_*") if path.is_file())
    except OSError:  # pragma: no cover - root removed mid-run
        return []


def token_caches_touched_since(snapshot: TokenCacheSnapshot) -> list[Path]:
    """Witnesses this session created or rewrote, in snapshot order."""
    return [path for path, before in snapshot.items() if _stat_or_none(path) != before]


_REGISTERED_SANDBOX_ROOTS: list[Path] = []


def register_sandbox_root(path: Path | str | None) -> None:
    """Add a directory the session may read a ``.env`` from."""
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
    """Directories a hermetic test session may read a ``.env`` from."""
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
    """Wrap ``find_dotenv``: let it walk, refuse what the walk found."""

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
    """Replace names other modules bound before the guard was installed."""
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
            if name in namespace and namespace[name] is original:
                try:
                    setattr(module, name, guards[name])
                except Exception:  # pragma: no cover - read-only module
                    continue


def install_dotenv_guard() -> Callable[[], None]:
    """Make python-dotenv refuse real ``.env`` files for this process."""
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
