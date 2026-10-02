"""Repo-wide gate: only one module may read a ``.env`` (#698).

``shared.config.dotenv_guard.load_project_dotenv`` bounds ``.env`` loading to
two exact paths and honours the hermetic switch. That is worth nothing if the
next script added to ``scripts/analysis/`` calls ``load_dotenv()`` directly:
python-dotenv's ``find_dotenv()`` walks out of a worktree into the primary
checkout exactly as it did on 2026-09-15, and the runtime guard installed by
``tests/conftest.py`` only fires for modules a test happens to import — which
is almost no script under ``scripts/analysis/``.

So the rule is checked structurally rather than stated in a doc. Two halves:

* **No direct python-dotenv use.** An AST walk over every ``.py`` file in the
  repository rejects a call to, or an import of, ``load_dotenv`` /
  ``dotenv_values`` / ``find_dotenv`` outside the modules listed in
  :data:`DOTENV_API_ALLOWED`.
* **Hand-rolled parsers stay registered.** Three helpers read ``.env`` with
  their own line loop, which no dotenv-shaped check can see. Each is listed in
  :data:`HAND_ROLLED_READERS` with a reason, and each must still consult
  ``hermetic_mode_enabled`` — the allowlist is a claim the gate verifies, not
  a place to park an exemption.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

#: The python-dotenv entry points that can read a file off disk.
DOTENV_API = frozenset({"load_dotenv", "dotenv_values", "find_dotenv"})

#: The only modules allowed to touch that API, each for a stated reason.
DOTENV_API_ALLOWED: dict[str, str] = {
    "shared/config/dotenv_guard.py": (
        "the single bounded loader every entrypoint calls"
    ),
    "tests/support/hermetic_env.py": (
        "wraps the API to refuse real .env files during tests"
    ),
    "tests/unit/config/test_dotenv_hermeticity.py": (
        "exercises the wrapper's refusals directly"
    ),
    "tests/unit/config/test_dotenv_call_gate.py": "this gate names the API",
}

#: Helpers that parse ``.env`` themselves. Each must honour the hermetic
#: switch, because nothing else can see them.
HAND_ROLLED_READERS: dict[str, str] = {
    "scripts/analysis/stock_paper_daily_verification.py": (
        "keeps a no-dependency fallback for standalone verifier runs"
    ),
    "scripts/analysis/validate_opening_volume_surge_candidates.py": (
        "best-effort loader written before python-dotenv was a dependency"
    ),
    "scripts/analysis/kis_daily_futures_probe.py": (
        "reads two KIS_FUTURES_* keys out of .env by hand"
    ),
}

_SKIPPED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".omc",
        "build",
        "dist",
        "htmlcov",
        "site-packages",
    }
)


def _python_files() -> list[Path]:
    """Every ``.py`` file in the checkout, minus caches and vendored trees."""
    found = []
    for path in REPO_ROOT.rglob("*.py"):
        if any(part in _SKIPPED_DIRS for part in path.relative_to(REPO_ROOT).parts):
            continue
        found.append(path)
    return sorted(found)


def _dotenv_api_uses(tree: ast.AST) -> set[str]:
    """Names from :data:`DOTENV_API` this module calls or imports."""
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "dotenv"
        ):
            used.update(alias.name for alias in node.names if alias.name in DOTENV_API)
        elif isinstance(node, ast.Call):
            func = node.func
            name = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr if isinstance(func, ast.Attribute) else None
            )
            if name in DOTENV_API:
                used.add(name)
    return used


@pytest.fixture(scope="module")
def python_files():
    files = _python_files()
    assert len(files) > 500, (
        f"only {len(files)} python files found under {REPO_ROOT} — the scan is "
        "not reaching the repository, so this gate would pass vacuously"
    )
    return files


def test_only_the_bounded_loader_touches_python_dotenv(python_files):
    """No module outside the allowlist may call or import the dotenv API."""
    offenders: dict[str, set[str]] = {}
    for path in python_files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in DOTENV_API_ALLOWED:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        used = _dotenv_api_uses(tree)
        if used:
            offenders[rel] = used

    assert offenders == {}, (
        "python-dotenv must only be used by "
        f"{', '.join(sorted(DOTENV_API_ALLOWED))}; these call or import it "
        "directly and so can walk out of a worktree into the primary "
        "checkout's .env (#698): "
        + "; ".join(
            f"{rel} → {sorted(names)}" for rel, names in sorted(offenders.items())
        )
        + ". Call shared.config.dotenv_guard.load_project_dotenv() instead."
    )


def test_allowlisted_modules_still_exist():
    """A stale allowlist entry would silently widen the gate."""
    missing = [rel for rel in DOTENV_API_ALLOWED if not (REPO_ROOT / rel).is_file()]
    assert missing == [], f"allowlist names files that no longer exist: {missing}"


@pytest.mark.parametrize("rel", sorted(HAND_ROLLED_READERS))
def test_hand_rolled_dotenv_readers_honour_the_hermetic_switch(rel):
    """Each registered hand-rolled reader must check the switch itself.

    No dotenv-shaped gate can see these, so the registration is only
    meaningful if the thing it claims is verified.
    """
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} is registered but missing"

    source = path.read_text(encoding="utf-8")
    assert "hermetic_mode_enabled" in source, (
        f"{rel} parses .env by hand ({HAND_ROLLED_READERS[rel]}) but never "
        "consults shared.config.dotenv_guard.hermetic_mode_enabled, so a test "
        "that imports it reads the operator's real credentials (#698)"
    )
