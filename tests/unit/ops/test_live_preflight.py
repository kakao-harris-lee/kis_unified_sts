"""Tests for scripts/ops/live_preflight.sh (live validated-code guardrail)."""
from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PREFLIGHT = REPO / "scripts" / "ops" / "live_preflight.sh"

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True,
        env={**os.environ, **_GIT_ENV},
    )


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "live"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "f.txt").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _run(repo: Path, **env: str) -> subprocess.CompletedProcess:
    full = {
        **os.environ,
        "KIS_LIVE_PROJECT": str(repo),
        "LIVE_PREFLIGHT_CHECK_REDIS": "0",
        "REDIS_PORT": "6382",
        **env,
    }
    return subprocess.run(
        ["bash", str(PREFLIGHT)], capture_output=True, text=True, env=full
    )


def test_passes_on_clean_annotated_tag(tmp_path):
    repo = _make_repo(tmp_path)
    _git(repo, "tag", "-a", "v2026.06.04", "-m", "validated")
    r = _run(repo)
    assert r.returncode == 0, r.stderr


def test_fails_when_not_on_tag(tmp_path):
    repo = _make_repo(tmp_path)
    r = _run(repo)
    assert r.returncode != 0
    assert "annotated tag" in r.stderr


def test_fails_on_lightweight_tag(tmp_path):
    repo = _make_repo(tmp_path)
    _git(repo, "tag", "v-light")  # lightweight, not annotated
    r = _run(repo)
    assert r.returncode != 0
    assert "annotated tag" in r.stderr


def test_fails_when_dirty(tmp_path):
    repo = _make_repo(tmp_path)
    _git(repo, "tag", "-a", "v1", "-m", "v")
    (repo / "f.txt").write_text("changed")
    r = _run(repo)
    assert r.returncode != 0
    assert "dirty" in r.stderr


def test_fails_on_wrong_redis_port(tmp_path):
    repo = _make_repo(tmp_path)
    _git(repo, "tag", "-a", "v1", "-m", "v")
    r = _run(repo, REDIS_PORT="6381")  # paper's port -> isolation breach
    assert r.returncode != 0
    assert "isolation" in r.stderr.lower()


def test_fails_when_redis_unreachable(tmp_path):
    repo = _make_repo(tmp_path)
    _git(repo, "tag", "-a", "v1", "-m", "v")
    closed = str(_free_port())
    r = _run(
        repo,
        LIVE_PREFLIGHT_CHECK_REDIS="1",
        REDIS_PORT=closed,
        LIVE_EXPECT_REDIS_PORT=closed,
    )
    assert r.returncode != 0
    assert "not reachable" in r.stderr
