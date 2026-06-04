"""Tests for scripts/ops/promote_live.sh (promote validated tag into live clone)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PROMOTE = REPO / "scripts" / "ops" / "promote_live.sh"

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def _git(cwd: Path, *args: str, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=capture, text=True,
        env={**os.environ, **_GIT_ENV},
    )


def _origin_and_live(tmp_path: Path):
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q")
    (origin / "f.txt").write_text("x")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", "init")
    _git(origin, "tag", "-a", "v1", "-m", "validated")  # annotated
    _git(origin, "tag", "v-light")  # lightweight
    live = tmp_path / "live"
    _git(tmp_path, "clone", "-q", str(origin), str(live))
    return origin, live


def _promote(live: Path, tag: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "KIS_LIVE_PROJECT": str(live), "PROMOTE_CHECK_REDIS": "0", "REDIS_PORT": "6382"}
    return subprocess.run(
        ["bash", str(PROMOTE), tag], capture_output=True, text=True, env=env
    )


def test_promote_checks_out_annotated_tag(tmp_path):
    _, live = _origin_and_live(tmp_path)
    r = _promote(live, "v1")
    assert r.returncode == 0, r.stderr
    head = _git(live, "rev-parse", "HEAD").stdout.strip()
    tag_commit = _git(live, "rev-list", "-n1", "v1").stdout.strip()
    assert head == tag_commit


def test_promote_rejects_lightweight_tag(tmp_path):
    _, live = _origin_and_live(tmp_path)
    r = _promote(live, "v-light")
    assert r.returncode != 0
    assert "annotated" in r.stderr


def test_promote_rejects_unknown_tag(tmp_path):
    _, live = _origin_and_live(tmp_path)
    r = _promote(live, "v-does-not-exist")
    assert r.returncode != 0
    assert "not found" in r.stderr


def test_promote_requires_tag_arg(tmp_path):
    _, live = _origin_and_live(tmp_path)
    env = {**os.environ, "KIS_LIVE_PROJECT": str(live)}
    r = subprocess.run(["bash", str(PROMOTE)], capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "usage" in r.stderr.lower()
