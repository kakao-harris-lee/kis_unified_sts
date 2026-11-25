"""Repo-wide gate: only one module may read a ``.env`` (#698)."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

DOTENV_API = frozenset({"load_dotenv", "dotenv_values", "find_dotenv"})

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

HAND_ROLLED_READERS: dict[str, tuple[str, str]] = {}


def tracked_python_files(root: Path) -> list[Path]:
    """Every ``.py`` file git tracks in ``root``."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", "*.py"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [root / rel for rel in result.stdout.split("\0") if rel]


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
def python_files(requires_repo_checkout):
    """The tracked ``.py`` files this gate scans."""
    files = tracked_python_files(REPO_ROOT)
    assert len(files) > 500, (
        f"only {len(files)} tracked python files found under {REPO_ROOT} — "
        "the scan is not reaching the repository, so this gate would pass "
        "vacuously"
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


def _function_node(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name == name
        ):
            return node
    return None


def _calls(node: ast.AST, name: str) -> bool:
    """Whether ``node`` contains a CALL to ``name`` — not a mention of it."""
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        called = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr if isinstance(func, ast.Attribute) else None
        )
        if called == name:
            return True
    return False


@pytest.mark.parametrize("rel", sorted(HAND_ROLLED_READERS))
def test_hand_rolled_dotenv_readers_honour_the_hermetic_switch(rel):
    """Each registered reader must *call* the switch, not merely name it."""
    function, reason = HAND_ROLLED_READERS[rel]
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} is registered but missing"

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = _function_node(tree, function)
    assert node is not None, f"{rel} no longer defines {function}()"

    assert _calls(node, "hermetic_mode_enabled"), (
        f"{rel}::{function} parses .env by hand ({reason}) but does not call "
        "shared.config.dotenv_guard.hermetic_mode_enabled, so a test that "
        "imports it reads the operator's real credentials (#698)"
    )


def test_nested_checkout_is_not_scanned(tmp_path):
    """A worktree under the checkout must not become a false offender."""
    repo = tmp_path / "primary"
    (repo / "shared" / "config").mkdir(parents=True)
    repo.joinpath("shared", "config", "dotenv_guard.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "add", "shared/config/dotenv_guard.py"], check=True
    )

    nested = repo / ".claude" / "worktrees" / "wt-698" / "shared" / "config"
    nested.mkdir(parents=True)
    nested.joinpath("dotenv_guard.py").write_text("from dotenv import load_dotenv\n")

    scanned = tracked_python_files(repo)

    assert scanned == [repo / "shared" / "config" / "dotenv_guard.py"]
    assert not any(".claude" in path.parts for path in scanned)
