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

Nothing here is imported by runtime code; it exists only for the test session.
"""

from __future__ import annotations

import functools
import os
import tempfile
from collections.abc import Callable, MutableMapping
from pathlib import Path

__all__ = [
    "HERMETIC_ENV",
    "LIVE_INFRA_ENV",
    "PRESERVED_ENV",
    "SCRUBBED_PREFIXES",
    "HermeticDotenvViolation",
    "env_flag",
    "install_dotenv_guard",
    "is_sandboxed",
    "sandbox_roots",
    "scrub_broker_env",
]

HERMETIC_ENV = "KIS_TEST_HERMETIC"
LIVE_INFRA_ENV = "KIS_RUN_LIVE_INFRA_TESTS"

_TRUTHY = frozenset({"1", "true", "yes", "on"})

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


class HermeticDotenvViolation(RuntimeError):
    """A test-time code path tried to load a ``.env`` outside the sandbox."""


def env_flag(name: str, environ: MutableMapping[str, str] | None = None) -> bool:
    """Whether ``name`` is set to a truthy value."""
    source = os.environ if environ is None else environ
    return source.get(name, "").strip().lower() in _TRUTHY


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


def sandbox_roots() -> tuple[Path, ...]:
    """Directories a hermetic test session may read a ``.env`` from.

    The system temp directory covers pytest's ``tmp_path``/``tmp_path_factory``
    and the session's own scratch dirs. ``PYTEST_DEBUG_TEMPROOT`` is honoured
    because it relocates exactly those.
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
    return tuple(resolved)


def is_sandboxed(path: Path) -> bool:
    """Whether ``path`` lies inside one of the :func:`sandbox_roots`."""
    try:
        resolved = path.resolve()
    except OSError:  # pragma: no cover - unreadable path
        return False
    return any(resolved == root or root in resolved.parents for root in sandbox_roots())


_GUARD_MARKER = "_kis_hermetic_guard"


def install_dotenv_guard() -> Callable[[], None]:
    """Make ``dotenv.load_dotenv`` refuse real ``.env`` files for this process.

    Two things are refused:

    * an argument-less call, because its ``find_dotenv()`` walk is the #698
      root cause and its target cannot be known in advance; and
    * an explicit path that **exists** and sits outside :func:`sandbox_roots`.

    A path that does not exist is allowed through: the load is a no-op either
    way, and letting it pass keeps CI (which has no ``.env`` anywhere) free of
    failures that say nothing about hermeticity.

    Returns:
        A callable that restores the original function. Idempotent — calling
        this twice installs one guard and the second call's restore is a no-op.
    """
    import dotenv
    import dotenv.main

    real = dotenv.main.load_dotenv
    if getattr(real, _GUARD_MARKER, False):
        return lambda: None

    @functools.wraps(real)
    def guarded(dotenv_path=None, stream=None, *args, **kwargs):  # type: ignore[no-untyped-def]
        if dotenv_path is None and stream is None:
            raise HermeticDotenvViolation(
                "argument-less load_dotenv() is refused during tests: "
                "python-dotenv resolves it with find_dotenv(), which walks out "
                "of this checkout and can read the primary checkout's real "
                ".env (#698). Use "
                "shared.config.dotenv_guard.load_project_dotenv() instead."
            )
        if dotenv_path is not None:
            candidate = Path(os.fspath(dotenv_path))
            if candidate.is_file() and not is_sandboxed(candidate):
                raise HermeticDotenvViolation(
                    f"refusing to load {candidate} during a hermetic test "
                    "session: only files under "
                    f"{', '.join(str(r) for r in sandbox_roots())} may be "
                    "loaded. A test that genuinely needs real infrastructure "
                    f"credentials must be marked live_infra and run with "
                    f"{LIVE_INFRA_ENV}=1 (#698)."
                )
        return real(dotenv_path, stream, *args, **kwargs)

    setattr(guarded, _GUARD_MARKER, True)
    dotenv.main.load_dotenv = guarded
    dotenv.load_dotenv = guarded

    def restore() -> None:
        dotenv.main.load_dotenv = real
        dotenv.load_dotenv = real

    return restore
