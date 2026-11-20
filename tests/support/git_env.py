"""One answer, for the whole suite, to "can a test use git here?"."""

from __future__ import annotations

import functools
import os
import shutil
import subprocess
from pathlib import Path

NO_GIT_METADATA_ENV = "KIS_TEST_IMAGE_NO_GIT_METADATA"

CHECKOUT = "checkout"
NO_WORK_TREE = "no-work-tree"
NO_GIT_CLI = "no-git-cli"


@functools.lru_cache(maxsize=1)
def git_cli_available() -> bool:
    """Is the ``git`` binary on PATH?"""
    return shutil.which("git") is not None


def classify_git_probe(
    root: Path, returncode: int, stdout: bytes, stderr: bytes
) -> str:
    """Turn one ``git rev-parse --show-toplevel`` result into a state. Pure."""
    if returncode == 0:
        toplevel = Path(os.fsdecode(stdout.strip())).resolve()
        return CHECKOUT if toplevel == root.resolve() else NO_WORK_TREE
    text = stderr.decode("utf-8", errors="replace")
    if "not a git repository" in text:
        return NO_WORK_TREE
    raise RuntimeError(
        f"git rev-parse --show-toplevel failed unexpectedly in {root} (exit {returncode}). "
        "This is NOT a plain 'no repository here' answer — dubious ownership, a leaked "
        "GIT_DIR, or a corrupt repository look like this, and silently reading them as "
        f"'no repository' would skip guards that need one: {text.strip()}"
    )


@functools.cache
def repo_checkout_state(root: Path) -> str:
    """:data:`CHECKOUT`, :data:`NO_WORK_TREE` or :data:`NO_GIT_CLI` for ``root``."""
    try:
        probe = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=False,
        )
    except OSError:
        return NO_GIT_CLI
    return classify_git_probe(root, probe.returncode, probe.stdout, probe.stderr)


def repo_checkout_skip_reason(state: str, marker: str | None) -> str | None:
    """Why a clone-the-repo test must skip, or ``None`` if it must run. Pure."""
    if state == CHECKOUT:
        return None
    if not marker:
        return None
    detail = (
        "the git CLI is not installed"
        if state == NO_GIT_CLI
        else "the repository root is not a git work tree"
    )
    return (
        f"{detail}, and {NO_GIT_METADATA_ENV} declares that intentional. Only "
        "Dockerfile.test sets it: `.dockerignore` excludes `.git`, so /app is a plain "
        "directory and `git clone /app` exits 128 (#835). Everywhere else — the host "
        "`test` job above all — this test runs."
    )
