"""tools/tos_cp3/ops/restart_stock_tenant.sh — the gates that run before anything is touched.

Every case here stops in the argument/precondition block, so the script never
stops a session, never reads a balance and never moves a leaf: the assertions are
that it exits 2 and that the state root is still empty. That ordering is the
safety property — a restart that was invoked without the account fingerprint, or
for a symbol that is not a tenant, must not have killed the session it was about
to repair.

Hermetic: fake state root, fake primary checkout, no broker call, no git clone.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import threading
from collections.abc import Iterator
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[2] / "tools/tos_cp3/ops/restart_stock_tenant.sh"
)
_FP = "ee1bdb5f1ca2"


@pytest.fixture()
def host(tmp_path: Path) -> Path:
    """A state root with the session directory the script requires, nothing else."""
    (tmp_path / "state" / "cp3-sessions").mkdir(parents=True)
    (tmp_path / "main").mkdir()
    return tmp_path


def _run(
    host: Path, *args: str, fingerprint: str | None = None
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(host),
        "CP3_DAILY_MAIN": str(host / "main"),
        "CP3_DAILY_STATE": str(host / "state"),
    }
    if fingerprint is not None:
        env["CP3_EXPECT_ACCOUNT_FP"] = fingerprint
    return subprocess.run(
        ["bash", str(_SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _untouched(host: Path) -> bool:
    return list((host / "state").iterdir()) == [host / "state" / "cp3-sessions"] and (
        list((host / "state" / "cp3-sessions").iterdir()) == []
    )


def test_script_parses() -> None:
    result = subprocess.run(
        ["bash", "-n", str(_SCRIPT)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_missing_fingerprint_refuses_before_touching_anything(host: Path) -> None:
    result = _run(host, "005930")
    assert result.returncode == 2, result.stderr
    assert "CP3_EXPECT_ACCOUNT_FP" in result.stderr
    assert _untouched(host)


def test_empty_fingerprint_env_is_still_a_refusal(host: Path) -> None:
    result = _run(host, "005930", fingerprint="")
    assert result.returncode == 2, result.stderr
    assert "CP3_EXPECT_ACCOUNT_FP" in result.stderr
    assert _untouched(host)


def test_fingerprint_flag_is_accepted_and_the_next_gate_refuses(host: Path) -> None:
    # The flag satisfies the fingerprint gate; the fake primary checkout has no
    # .venv, so the run still stops — before the stop/flat-check/archive steps.
    result = _run(host, "005930", "--expect-account-fingerprint", _FP)
    assert result.returncode == 2, result.stderr
    assert ".venv/bin/python" in result.stdout + result.stderr
    assert _untouched(host)


def test_fingerprint_flag_without_a_value_is_a_usage_error(host: Path) -> None:
    result = _run(host, "005930", "--expect-account-fingerprint")
    assert result.returncode == 2, result.stderr
    assert _untouched(host)


@pytest.mark.parametrize("symbol", ["5930", "0059300", "00593a"])
def test_symbol_must_be_six_digits(host: Path, symbol: str) -> None:
    result = _run(host, symbol, fingerprint=_FP)
    assert result.returncode == 2, result.stderr
    assert "6자리" in result.stderr
    assert _untouched(host)


def test_symbol_must_be_one_of_the_runners_tenants(host: Path) -> None:
    result = _run(host, "999999", fingerprint=_FP)
    assert result.returncode == 2, result.stderr
    assert "STOCK_SYMBOLS" in result.stderr
    assert _untouched(host)


def test_tag_cannot_escape_the_archive_directory_name(host: Path) -> None:
    result = _run(host, "005930", "../../etc", fingerprint=_FP)
    assert result.returncode == 2, result.stderr
    assert _untouched(host)


def test_extra_positional_arguments_are_refused(host: Path) -> None:
    result = _run(host, "005930", "tag", "surplus", fingerprint=_FP)
    assert result.returncode == 2, result.stderr
    assert _untouched(host)


def test_help_exits_zero_without_touching_the_host(host: Path) -> None:
    result = _run(host, "--help")
    assert result.returncode == 0, result.stderr
    assert "restart_stock_tenant.sh" in result.stdout
    assert _untouched(host)


# ---------------------------------------------------------------------------
# Steps 2–7, on a scratch host: the ORDER is the contract
# ---------------------------------------------------------------------------
#
# Still hermetic: `git` and the venv interpreter are stubs on PATH, the session
# runner is a stub inside the stub worktree, and no broker call, no clone and no
# network happen. What these pin is what the comments in the script claim and
# nothing else could check — that a NOT-flat answer leaves both the leaf and the
# approval alone, that the approval is moved BEFORE the runner starts and
# written only AFTER `render ok`, and that a pid that is not this runner is
# never signalled.

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SESSION_RUNNER = _REPO_ROOT / "tools/tos_cp3/runners/run_tenant_session.sh"
_SYMBOL = "005930"

_FAKE_PYTHON = """#!/usr/bin/env bash
# Stands in for $MAIN/.venv/bin/python. Answers the two calls the script makes.
printf '%s\\n' "$*" >>"$FAKE_PY_LOG"
case "$*" in
*mock_flat_check*) exit "${FAKE_FLAT_RC:-0}" ;;
*write-standing-approval*)
  CFG=""; PREV=""
  for A in "$@"; do
    [ "$PREV" = "--config-dir" ] && CFG=$A
    PREV=$A
  done
  S=$(dirname "$CFG")
  if grep -q 'render ok' "$S/session.log" 2>/dev/null; then
    echo yes >"$S/approval-saw-render-ok"
  else
    echo no >"$S/approval-saw-render-ok"
  fi
  printf '%s\\n' "$*" >"$S/approval-args.txt"
  exit "${FAKE_APPROVAL_RC:-0}"
  ;;
esac
exit 0
"""

_FAKE_GIT = """#!/usr/bin/env bash
# Stands in for git: no clone, no fetch, no real worktree.
printf '%s\\n' "$*" >>"$FAKE_GIT_LOG"
case "$*" in
*"rev-parse --show-toplevel"*) echo "$FAKE_REPO_ROOT" ;;
*"rev-parse --short=12 HEAD"*) echo abcdef123456 ;;
*"worktree add"*)
  WT=""; PREV=""
  for A in "$@"; do
    [ "$A" = "origin/main" ] && WT=$PREV
    PREV=$A
  done
  mkdir -p "$WT/tools/tos_cp3/runners"
  cp "$FAKE_RUNNER_SRC" "$WT/tools/tos_cp3/runners/run_tenant_session.sh"
  cp "$FAKE_REPO_ROOT/tools/tos_cp3/runners/stock-mock-session.env.example" \\
    "$WT/tools/tos_cp3/runners/stock-mock-session.env.example"
  ;;
esac
exit 0
"""

_STUB_RUNNER = """#!/usr/bin/env bash
# Stands in for run_tenant_session.sh: records what custody looked like the
# moment it started, then says `render ok` and idles. The real runner stops on
# SIGTERM, so this one does too — `sleep &` + `wait`, because bash defers a
# signal until a FOREGROUND child returns.
trap 'exit 143' TERM
S=${TOS_STOCK_SESSION_ROOT:?}
ls "${TOS_STOCK_CUSTODY_ROOT:?}/approvals" >"$S/approvals-at-start.txt" 2>&1 || true
echo 'render ok' >>"$S/session.log"
sleep "${STUB_RUNNER_SLEEP_S:-8}" &
wait
"""


def _write_exec(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


class _Stage:
    """A scratch host the restart script can run end to end against."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.state = root / "state"
        self.main = root / "main"
        self.data_parent = self.state / f"cp3-setup-d-stock-{_SYMBOL}-data"
        self.leaf = self.data_parent / _SYMBOL
        self.custody = self.state / "cp3-setup-d-stock-custody"
        self.approval = self.custody / "approvals" / "standing-session.yaml"
        self.py_log = root / "python-calls.log"
        self.git_log = root / "git-calls.log"
        self.date = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")

    def build(self) -> None:
        (self.state / "cp3-sessions").mkdir(parents=True)
        self.leaf.mkdir(parents=True)
        (self.leaf / "evidence.sqlite3").write_text("leaf", encoding="utf-8")
        self.approval.parent.mkdir(parents=True)
        self.approval.write_text("standing: yesterday\n", encoding="utf-8")
        _write_exec(self.main / ".venv/bin/python", _FAKE_PYTHON)
        (self.main / ".env.mock").write_text("KIS_STOCK_ACCOUNT_NO=x\n", "utf-8")
        _write_exec(self.root / "bin/git", _FAKE_GIT)
        _write_exec(self.root / "stub/run_tenant_session.sh", _STUB_RUNNER)

    def env(self, **extra: str) -> dict[str, str]:
        env = {
            "PATH": f"{self.root / 'bin'}:/usr/bin:/bin",
            "HOME": str(self.root),
            "CP3_DAILY_MAIN": str(self.main),
            "CP3_DAILY_STATE": str(self.state),
            "CP3_EXPECT_ACCOUNT_FP": _FP,
            # The calendar read is the runner's; forcing it keeps this test off
            # the real tree's config (the handle the script documents).
            "CP3_DAILY_STOP_AT": "15:40",
            "CP3_DAILY_APPROVAL_WAIT_TRIES": "30",
            "CP3_DAILY_APPROVAL_WAIT_SLEEP_S": "1",
            "TOS_ENV_MOCK": str(self.main / ".env.mock"),
            "FAKE_PY_LOG": str(self.py_log),
            "FAKE_GIT_LOG": str(self.git_log),
            "FAKE_REPO_ROOT": str(_REPO_ROOT),
            "FAKE_RUNNER_SRC": str(self.root / "stub/run_tenant_session.sh"),
            "STUB_RUNNER_SLEEP_S": "8",
        }
        env.update(extra)
        return env

    def run(self, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(_SCRIPT), *(args or (_SYMBOL,))],
            env=self.env(**extra),
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )

    def sessions(self) -> list[Path]:
        return sorted((self.state / "cp3-sessions").iterdir())

    def archived(self) -> list[Path]:
        archive = self.data_parent / "archive"
        return sorted(archive.iterdir()) if archive.is_dir() else []


@pytest.fixture()
def stage(tmp_path: Path) -> Iterator[_Stage]:
    staged = _Stage(tmp_path)
    staged.build()
    yield staged
    for pid_file in tmp_path.glob("state/cp3-sessions/*/runner.pid"):
        with suppress(ValueError, OSError):
            os.kill(int(pid_file.read_text().strip()), signal.SIGKILL)


def test_a_symbol_that_is_not_flat_keeps_the_leaf_and_the_approval(
    stage: _Stage,
) -> None:
    """flat check rc 3 (held, or an order still working) — nothing is touched."""
    result = stage.run(FAKE_FLAT_RC="3")
    assert result.returncode == 2, result.stdout + result.stderr
    assert stage.leaf.is_dir()
    assert stage.archived() == []
    assert stage.approval.is_file()
    assert stage.sessions() == []
    assert "worktree add" not in stage.git_log.read_text(encoding="utf-8")


def test_the_happy_path_archives_then_starts_then_writes_the_approval(
    stage: _Stage,
) -> None:
    result = stage.run()
    assert result.returncode == 0, result.stdout + result.stderr
    # 4. the leaf was MOVED, not deleted.
    assert not stage.leaf.exists()
    archived = stage.archived()
    assert len(archived) == 1 and archived[0].name.startswith(f"{_SYMBOL}.restart-")
    assert (archived[0] / "evidence.sqlite3").is_file()
    # 6. the previous approval was moved out of the slot BEFORE the runner ran —
    # a file written after boot is refused as `digest_changed_since_bound`.
    assert not stage.approval.exists()
    assert len(list((stage.custody / "approvals-archive").iterdir())) == 1
    session = stage.sessions()[0]
    assert session.name == f"stock-r1-{stage.date}"
    seen_at_start = (session / "approvals-at-start.txt").read_text(encoding="utf-8")
    assert "standing-session.yaml" not in seen_at_start
    # 7. and the new one was written only after `render ok`.
    assert (session / "approval-saw-render-ok").read_text(encoding="utf-8") == "yes\n"
    approval_args = (session / "approval-args.txt").read_text(encoding="utf-8")
    assert f"--custody-root {stage.custody}" in approval_args
    assert "--environment-label paper" in approval_args
    # and the flat check came first of the two python calls.
    calls = stage.py_log.read_text(encoding="utf-8").splitlines()
    assert "mock_flat_check" in calls[0]
    assert "write-standing-approval" in calls[-1]


def test_a_failed_approval_write_prints_the_command_that_recovers_it(
    stage: _Stage,
) -> None:
    result = stage.run(FAKE_APPROVAL_RC="1")
    assert result.returncode == 1, result.stdout + result.stderr
    session = stage.sessions()[0]
    assert "write-standing-approval" in result.stdout
    assert f"--config-dir {session}/render" in result.stdout
    assert f"--custody-root {stage.custody}" in result.stdout
    assert "--replace" in result.stdout


def test_a_pid_that_is_not_the_runner_is_skipped_not_signalled(
    stage: _Stage,
) -> None:
    """runner.pid outlives its session; the number can belong to anyone."""
    session = stage.state / "cp3-sessions" / f"stock-r1-{stage.date}"
    session.mkdir(parents=True)
    bystander = subprocess.Popen(
        ["sleep", "60"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        (session / "runner.pid").write_text(f"{bystander.pid}\n", encoding="utf-8")
        result = stage.run(FAKE_FLAT_RC="3")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "skip" in result.stdout
        assert bystander.poll() is None, "a bystander process was signalled"
    finally:
        bystander.kill()
        bystander.wait(timeout=10)


def test_the_stop_bound_is_read_from_the_session_runner(stage: _Stage) -> None:
    """Not a second copy of 120: the wait is the runner's own stop constants."""
    runner_text = _SESSION_RUNNER.read_text(encoding="utf-8")

    def const(name: str) -> int:
        match = re.search(rf"^{name}=(\d+)$", runner_text, re.MULTILINE)
        assert match is not None, f"{name} is not a plain constant any more"
        return int(match.group(1))

    expected = (
        const("SIGKILL_AFTER_S")
        + const("PRODUCER_SIGKILL_AFTER_S")
        + const("BAND_PROCESS_KILL_AFTER_S")
        + 5  # stop_wait()'s own grace, a literal in that same file
    )
    session = stage.state / "cp3-sessions" / f"stock-r1-{stage.date}"
    session.mkdir(parents=True)
    # A process whose cmdline IS the session runner, so the identity gate passes.
    impostor = subprocess.Popen(
        ["bash", str(stage.root / "stub/run_tenant_session.sh")],
        env={
            "PATH": "/usr/bin:/bin",
            "TOS_STOCK_SESSION_ROOT": str(session),
            "TOS_STOCK_CUSTODY_ROOT": str(stage.custody),
            "STUB_RUNNER_SLEEP_S": "60",
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Reap it as init would. Without this the exited process stays a zombie —
    # pytest is its parent and never waits — and a zombie still answers
    # `kill -0`, so the script would wait out its whole bound on a dead runner.
    reaper = threading.Thread(target=impostor.wait, daemon=True)
    reaper.start()
    try:
        (session / "runner.pid").write_text(f"{impostor.pid}\n", encoding="utf-8")
        result = stage.run(FAKE_FLAT_RC="3")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "stop sent" in result.stdout
        assert f"상한 {expected}s" in result.stdout
        reaper.join(timeout=10)
        assert impostor.poll() == 143, "the runner was not stopped by our SIGTERM"
    finally:
        if impostor.poll() is None:
            impostor.kill()
        impostor.wait(timeout=10)
