"""Tests for scripts/kill_switch_clear.sh — Docker Compose sentinel-clear convention.

Hermetic: exercises only file/env plumbing via subprocess + `bash`. No Redis,
no network. Skips if `bash` is not on PATH.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "kill_switch_clear.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")


def _run(
    args: list[str],
    env_overrides: dict[str, str],
    tmp_path: Path,
    stdin: str | None = None,
):
    env = dict(os.environ)
    env.update(env_overrides)
    return subprocess.run(
        ["bash", str(_SCRIPT), *args],
        cwd=str(tmp_path),
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_no_sentinel_exits_zero_nothing_to_clear(tmp_path):
    sentinel = tmp_path / "kis_kill_switch.tripped"
    log_dir = tmp_path / "logs" / "kill_switch"

    result = _run(
        ["--confirm"],
        {
            "KILL_SWITCH_SENTINEL_PATH": str(sentinel),
            "KIS_KILL_SWITCH_LOG_DIR": str(log_dir),
        },
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "nothing to clear" in result.stdout


def test_confirm_flag_clears_sentinel_and_snapshots_to_journal(tmp_path):
    sentinel = tmp_path / "kis_kill_switch.tripped"
    content = '{"reason": "daily_loss", "value": 0.05}'
    sentinel.write_text(content)
    log_dir = tmp_path / "logs" / "kill_switch"

    result = _run(
        ["--confirm"],
        {
            "KILL_SWITCH_SENTINEL_PATH": str(sentinel),
            "KIS_KILL_SWITCH_LOG_DIR": str(log_dir),
        },
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert not sentinel.exists()

    snapshots = sorted(glob.glob(str(log_dir / "cleared_*.log")))
    assert len(snapshots) == 1
    assert Path(snapshots[0]).read_text() == content


def test_no_confirm_declined_leaves_sentinel_intact(tmp_path):
    sentinel = tmp_path / "kis_kill_switch.tripped"
    sentinel.write_text('{"reason": "weekly_loss"}')
    log_dir = tmp_path / "logs" / "kill_switch"

    result = _run(
        [],
        {
            "KILL_SWITCH_SENTINEL_PATH": str(sentinel),
            "KIS_KILL_SWITCH_LOG_DIR": str(log_dir),
        },
        tmp_path,
        stdin="no\n",
    )

    assert result.returncode == 1
    assert "Aborted" in result.stdout
    assert sentinel.exists()


def test_recovery_flag_clears_only_recovery_sentinel(tmp_path):
    kill_content = '{"reason": "daily_loss", "value": 0.05}'
    recovery_content = '{"symbol": "101W09", "divergence": true}'
    kill_sentinel = tmp_path / "kis_kill_switch.tripped"
    recovery_sentinel = tmp_path / "kis_position_recovery.tripped"
    kill_sentinel.write_text(kill_content)
    recovery_sentinel.write_text(recovery_content)
    log_dir = tmp_path / "logs" / "kill_switch"

    result = _run(
        ["--recovery", "--confirm"],
        {
            "KILL_SWITCH_SENTINEL_PATH": str(kill_sentinel),
            "KILL_SWITCH_RECOVERY_SENTINEL_PATH": str(recovery_sentinel),
            "KIS_KILL_SWITCH_LOG_DIR": str(log_dir),
        },
        tmp_path,
    )

    assert result.returncode == 0, result.stderr

    # Recovery sentinel is gone; the unrelated kill-switch sentinel is
    # untouched, both in existence and in content.
    assert not recovery_sentinel.exists()
    assert kill_sentinel.exists()
    assert kill_sentinel.read_text() == kill_content

    # Journal snapshot is named/prefixed for the recovery flow and holds the
    # recovery sentinel's content, not the kill-switch sentinel's.
    recovery_snapshots = sorted(glob.glob(str(log_dir / "cleared_recovery_*.log")))
    assert len(recovery_snapshots) == 1
    assert Path(recovery_snapshots[0]).read_text() == recovery_content

    all_snapshots = sorted(glob.glob(str(log_dir / "cleared_*.log")))
    assert all_snapshots == recovery_snapshots


def test_print_path_with_no_override_matches_config_derivation():
    result = subprocess.run(
        ["bash", str(_SCRIPT), "--print-path"],
        cwd=str(_REPO_ROOT),
        env={k: v for k, v in os.environ.items() if k != "KILL_SWITCH_SENTINEL_PATH"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr

    from services.kill_switch.config import KillSwitchConfig
    from shared.config.runtime_defaults import host_path_for_container_runtime_path

    expected = host_path_for_container_runtime_path(
        KillSwitchConfig.from_yaml().sentinel_path
    )
    assert result.stdout.strip() == str(expected)


def test_print_path_recovery_with_no_override_matches_config_derivation():
    result = subprocess.run(
        ["bash", str(_SCRIPT), "--print-path", "--recovery"],
        cwd=str(_REPO_ROOT),
        env={
            k: v
            for k, v in os.environ.items()
            if k != "KILL_SWITCH_RECOVERY_SENTINEL_PATH"
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr

    from services.kill_switch.config import KillSwitchConfig
    from shared.config.runtime_defaults import host_path_for_container_runtime_path

    expected = host_path_for_container_runtime_path(
        KillSwitchConfig.from_yaml().recovery_sentinel_path
    )
    assert result.stdout.strip() == str(expected)
