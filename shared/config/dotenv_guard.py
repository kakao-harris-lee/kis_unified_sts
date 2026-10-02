"""Bounded ``.env`` loading for this project's entrypoints.

Why this module exists
----------------------
``python-dotenv``'s argument-less ``load_dotenv()`` resolves its file with
``find_dotenv()``, which walks from the *calling file's* directory up to the
filesystem root. A checkout nested inside another checkout — a git worktree
under ``<repo>/.claude/worktrees/<name>/`` — therefore reaches the **outer**
checkout's ``.env``, which on the deploy host holds real KIS credentials.
Importing ``cli.commands.common`` during pytest collection was enough to put a
real app key in the test process, and on 2026-09-15 that led to a real KIS
token being issued and cached as ``.kis_token_real`` inside the worktree
(issue #698).

Two rules close that hole, and both live here so every entrypoint gets them:

1. **Never walk above the checkout.** :func:`load_project_dotenv` looks at
   exactly two paths — ``<checkout>/.env`` and ``<cwd>/.env`` — and loads the
   first that exists. Neither can escape into a parent checkout.
2. **Honour the hermetic switch.** While :data:`HERMETIC_ENV` is set to a
   truthy value this module loads nothing at all. ``tests/conftest.py`` sets it
   for the whole pytest session, so a test process never injects a ``.env``
   no matter which entrypoint module it happens to import.

:data:`HERMETIC_ENV` is the only knob added here. It is a *test* switch, not a
runtime configuration surface: the paper/live runtime never sets it, and with
it unset this module behaves exactly like the entrypoints did before — the
checkout's ``.env`` is loaded at import time, existing environment values win.
"""

from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path

__all__ = [
    "HERMETIC_ENV",
    "hermetic_mode_enabled",
    "load_project_dotenv",
    "project_dotenv_candidates",
    "project_root",
]

#: Env var that disables every ``.env`` load performed through this module.
HERMETIC_ENV = "KIS_TEST_HERMETIC"

_TRUTHY = frozenset({"1", "true", "yes", "on"})

# shared/config/dotenv_guard.py -> shared/config -> shared -> <checkout root>
_CHECKOUT_ROOT = Path(__file__).resolve().parents[2]


def hermetic_mode_enabled() -> bool:
    """Whether ``.env`` loading is switched off for this process."""
    return os.environ.get(HERMETIC_ENV, "").strip().lower() in _TRUTHY


def project_root() -> Path:
    """The checkout that contains the running code.

    Resolved from this file, so a worktree gets its own root rather than the
    primary checkout it may be nested under.
    """
    return _CHECKOUT_ROOT


def project_dotenv_candidates() -> tuple[Path, ...]:
    """The only files :func:`load_project_dotenv` will ever read, in order.

    The checkout's own ``.env`` wins over the working directory's, and no
    ancestor directory is consulted at all.
    """
    candidates = [_CHECKOUT_ROOT / ".env"]
    with suppress(OSError):
        cwd_env = Path.cwd() / ".env"
        if cwd_env != candidates[0]:
            candidates.append(cwd_env)
    return tuple(candidates)


def load_project_dotenv(*, override: bool = False) -> Path | None:
    """Load this checkout's ``.env`` into ``os.environ``.

    Args:
        override: Replace values already present in the environment. Defaults
            to ``False``, matching python-dotenv and every caller replaced in
            #698 — an exported variable still beats the file.

    Returns:
        The file that was loaded, or ``None`` when hermetic mode is on or
        neither candidate exists.
    """
    if hermetic_mode_enabled():
        return None

    from dotenv import load_dotenv

    for candidate in project_dotenv_candidates():
        if candidate.is_file():
            load_dotenv(candidate, override=override)
            return candidate
    return None
