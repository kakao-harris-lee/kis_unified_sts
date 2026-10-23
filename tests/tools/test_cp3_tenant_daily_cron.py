"""CP-3 tenant daily cron — the wrapper and its installer, end to end, hermetically.

Nothing here touches the real crontab, the real ``~/.config/kis-probes`` or
``~/.local/state/tos``: every call gets a fixture git ``origin`` (the two scripts,
a stub ``run_tenant_session.sh``, the two tenant calendars, a copy of the
front-month helper), a clone of it as ``MAIN``, a tmp ``HOME`` and a fake
``crontab`` on ``PATH`` that reads and writes a file.

Runbook: docs/runbooks/tos-paper-boot.md §7.2-e.
"""

from __future__ import annotations

import fcntl
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNERS = _REPO_ROOT / "tools" / "tos_cp3" / "runners"
_WRAPPER_REL = "tools/tos_cp3/runners/cp3_tenant_daily.sh"
_INSTALLER_REL = "tools/tos_cp3/runners/install_tenant_cron.sh"

_HOLIDAY = "2026-11-03"  # a Tuesday, listed as a holiday in the fixture calendars
_OPEN_DAY = "2026-10-26"  # a Monday, not a holiday

_STUB_RUNNER = """#!/bin/bash
# Test stub: record what the wrapper handed over, exit with the requested rc.
env | grep '^TENANT_' | sort
exit "${CP3_TEST_STUB_RC:-0}"
"""

_FAKE_CRONTAB = """#!/bin/bash
# Test stub: `crontab -l` prints $FAKE_CRONTAB_FILE, `crontab FILE` replaces it.
if [ "${1:-}" = "-l" ]; then
  [ -f "$FAKE_CRONTAB_FILE" ] || { echo "no crontab for test" >&2; exit 1; }
  cat "$FAKE_CRONTAB_FILE"
else
  cp "$1" "$FAKE_CRONTAB_FILE"
fi
"""

_OTHER_LINES = """SHELL=/bin/bash
# TOS paper 상주 세션
CRON_TZ=Asia/Seoul
45 8  * * 1-5 /bin/bash /x/tos-paper-session.sh start >> /x/cron.log 2>&1 # tos-paper-session
0 18 * * 1-5 /x/cold-backup-nightly.sh >> /x/cold.log 2>&1 # cold-backup-nightly
"""

_LEGACY_LINES = """CRON_TZ=Asia/Seoul
38 8 * * 1-5 /usr/bin/flock -n /tmp/a.lock /bin/bash /x/run-cp3-tenant-daily.sh LONG >> /x/l.log 2>&1 # cp3-long-tenant-daily
40 8 * * 1-5 /usr/bin/flock -n /tmp/b.lock /bin/bash /x/run-cp3-tenant-daily.sh SHORT >> /x/s.log 2>&1 # cp3-short-tenant-daily
"""


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _write(path: Path, text: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


class Env:
    """One hermetic world: origin, MAIN clone, HOME, STATE, fake crontab."""

    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        seed = tmp / "seed"
        for rel in (_WRAPPER_REL, _INSTALLER_REL):
            _write(seed / rel, (_REPO_ROOT / rel).read_text(encoding="utf-8"), 0o755)
        _write(
            seed / "tools/tos_cp3/runners/run_tenant_session.sh", _STUB_RUNNER, 0o755
        )
        calendar = f'calendar_version: "t"\nholidays:\n  - "{_HOLIDAY}"\n'
        for lc in ("long", "short"):
            _write(
                seed / f"config/tos_runtime/cp3-setup-d-{lc}/calendar.yaml", calendar
            )
        _write(seed / "shared/__init__.py", "")
        _write(seed / "shared/instruments/__init__.py", "")
        shutil.copy(
            _REPO_ROOT / "shared/instruments/futures.py",
            seed / "shared/instruments/futures.py",
        )
        _git("init", "-q", "-b", "main", cwd=seed)
        _git("add", "-A", cwd=seed)
        _git("commit", "-q", "-m", "seed", cwd=seed)
        self.origin = tmp / "origin.git"
        _git("clone", "-q", "--bare", str(seed), str(self.origin), cwd=tmp)
        self.main = tmp / "main"
        _git("clone", "-q", str(self.origin), str(self.main), cwd=tmp)
        (self.main / ".venv/bin").mkdir(parents=True)
        (self.main / ".venv/bin/python").symlink_to(sys.executable)

        self.home = tmp / "home"
        self.state = self.home / ".local/state/tos"
        self.state.mkdir(parents=True)
        self.dest_dir = self.home / ".config/kis-probes"
        self.locks = tmp / "locks"
        bindir = tmp / "bin"
        _write(bindir / "crontab", _FAKE_CRONTAB, 0o755)
        self.crontab = tmp / "crontab.txt"
        self.base_env = {
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "HOME": str(self.home),
            "TZ": "Asia/Seoul",
            "FAKE_CRONTAB_FILE": str(self.crontab),
            "CP3_DAILY_MAIN": str(self.main),
            "CP3_DAILY_STATE": str(self.state),
            "CP3_DAILY_LOCK_DIR": str(self.locks),
            "CP3_DAILY_NOTIFY": "0",
            "LANG": "C.UTF-8",
        }

    def run(
        self, rel: str, *args: str, **extra: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["/bin/bash", str(self.main / rel), *args],
            env={**self.base_env, **extra},
            capture_output=True,
            text=True,
            timeout=120,
        )

    def daily(self, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
        return self.run(_WRAPPER_REL, *args, **extra)

    def install(self, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
        return self.run(_INSTALLER_REL, *args, **extra)


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return Env(tmp_path)


def _data_parents(env: Env) -> None:
    for lc in ("long", "short"):
        (env.state / f"cp3-setup-d-{lc}-data").mkdir(mode=0o700)


# ------------------------------------------------------------------ installer


def test_dry_run_is_the_default_and_writes_nothing(env: Env) -> None:
    env.crontab.write_text(_OTHER_LINES, encoding="utf-8")
    r = env.install()
    assert r.returncode == 0, r.stderr
    assert "DRY-RUN" in r.stdout
    assert env.crontab.read_text(encoding="utf-8") == _OTHER_LINES
    assert not env.dest_dir.exists()
    dest = env.dest_dir / "run-cp3-tenant-daily.sh"
    assert (
        f"+38 8 * * 1-5 /bin/bash {dest} LONG >> {env.state}/cp3-long-tenant-daily.cron.log 2>&1 # cp3-long-tenant-daily"
        in r.stdout
    )
    assert (
        f"+40 8 * * 1-5 /bin/bash {dest} SHORT >> {env.state}/cp3-short-tenant-daily.cron.log 2>&1 # cp3-short-tenant-daily"
        in r.stdout
    )
    assert "+CRON_TZ=Asia/Seoul" in r.stdout


def test_apply_replaces_hand_lines_keeps_the_rest_and_is_idempotent(env: Env) -> None:
    env.crontab.write_text(_OTHER_LINES + _LEGACY_LINES, encoding="utf-8")
    r = env.install("--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    tab = env.crontab.read_text(encoding="utf-8")
    assert tab.startswith(_OTHER_LINES)
    assert "/usr/bin/flock -n /tmp/a.lock" not in tab  # hand lines gone
    assert tab.count("# cp3-long-tenant-daily") == 1
    assert tab.count("# cp3-short-tenant-daily") == 1
    assert tab.count("# BEGIN CP3_TENANT_DAILY") == 1
    assert "CP3_DAILY_TODAY" not in tab  # the test-only knob never reaches cron

    dest = env.dest_dir / "run-cp3-tenant-daily.sh"
    assert dest.read_bytes() == (_REPO_ROOT / _WRAPPER_REL).read_bytes()
    assert stat.S_IMODE(dest.stat().st_mode) == 0o700
    assert list(env.dest_dir.glob("crontab.bak.*"))

    again = env.install("--apply")
    assert again.returncode == 0, again.stderr
    assert "crontab unchanged" in again.stdout
    assert "(no change)" in again.stdout
    assert env.crontab.read_text(encoding="utf-8") == tab


def test_apply_backs_up_a_different_existing_wrapper(env: Env) -> None:
    env.dest_dir.mkdir(parents=True)
    old = env.dest_dir / "run-cp3-tenant-daily.sh"
    old.write_text("#!/bin/bash\necho hand-made\n", encoding="utf-8")
    r = env.install("--apply")
    assert r.returncode == 0, r.stderr
    assert [
        p.read_text(encoding="utf-8")
        for p in env.dest_dir.glob("run-cp3-tenant-daily.sh.bak.*")
    ] == ["#!/bin/bash\necho hand-made\n"]


def test_remove_drops_only_our_lines(env: Env) -> None:
    env.crontab.write_text(_OTHER_LINES + _LEGACY_LINES, encoding="utf-8")
    assert env.install("--apply").returncode == 0
    dry = env.install("--remove")
    assert dry.returncode == 0 and "DRY-RUN" in dry.stdout
    assert "# BEGIN CP3_TENANT_DAILY" in env.crontab.read_text(encoding="utf-8")
    r = env.install("--remove", "--apply")
    assert r.returncode == 0, r.stderr
    tab = env.crontab.read_text(encoding="utf-8")
    assert "tenant-daily" not in tab and "CP3_TENANT_DAILY" not in tab
    assert tab.startswith(_OTHER_LINES)


def test_apply_refuses_an_unmerged_installer(env: Env) -> None:
    inst = env.main / _INSTALLER_REL
    inst.write_text(
        inst.read_text(encoding="utf-8") + "# local edit\n", encoding="utf-8"
    )
    env.crontab.write_text(_OTHER_LINES, encoding="utf-8")
    r = env.install("--apply")
    assert r.returncode == 2
    assert "differs from origin/main" in r.stderr
    assert env.crontab.read_text(encoding="utf-8") == _OTHER_LINES


def test_apply_refuses_a_non_kst_host(env: Env) -> None:
    env.crontab.write_text(_OTHER_LINES, encoding="utf-8")
    r = env.install("--apply", TZ="UTC")
    assert r.returncode == 2
    assert "no working CRON_TZ" in r.stderr
    assert env.crontab.read_text(encoding="utf-8") == _OTHER_LINES


# ------------------------------------------------------------------- wrapper


def test_holiday_is_a_silent_skip(env: Env) -> None:
    _data_parents(env)
    r = env.daily("LONG", CP3_DAILY_TODAY=_HOLIDAY)
    assert r.returncode == 0, r.stdout
    assert "SKIP" in r.stdout
    assert "notify-body" not in r.stdout
    assert not (env.state / "cp3-sessions").exists()
    assert not (env.state / f"measure/wt-cp3-long-{_HOLIDAY.replace('-', '')}").exists()


def test_weekend_and_extra_closed_dates_skip(env: Env) -> None:
    _data_parents(env)
    assert "SKIP" in env.daily("SHORT", CP3_DAILY_TODAY="2026-10-24").stdout  # Saturday
    r = env.daily("SHORT", CP3_DAILY_TODAY="2026-12-31")  # KRX year-end, default extra
    assert r.returncode == 0 and "SKIP" in r.stdout


def test_open_day_runs_the_runner_with_every_tenant_value(env: Env) -> None:
    _data_parents(env)
    r = env.daily("LONG", CP3_DAILY_TODAY=_OPEN_DAY)
    assert r.returncode == 0, r.stdout
    session = env.state / "cp3-sessions" / f"long-{_OPEN_DAY.replace('-', '')}"
    out = (session / "runner.out").read_text(encoding="utf-8")
    wt = env.state / "measure" / f"wt-cp3-long-{_OPEN_DAY.replace('-', '')}"
    for expected in (
        "TENANT_DIRECTION=LONG",
        "TENANT_TREE=cp3-setup-d-long",
        f"TENANT_DATA_PARENT={env.state}/cp3-setup-d-long-data",
        f"TENANT_JOURNAL={session}/journal.jsonl",
        "TENANT_STOP_AT=15:50",
        f"TENANT_ENV_FILE={env.main}/.env.mock",
        "TENANT_ENVIRONMENT_LABEL=paper",
        f"TENANT_PRODUCER_CONFIG={wt}/config/tos_probes/cp3-live-producer.yaml",
    ):
        assert expected in out
    assert "일일 세션 종료" in r.stdout and "정상" in r.stdout
    # the session's worktree stays for the session; detached at origin/main
    assert _git("rev-parse", "HEAD", cwd=wt) == _git(
        "rev-parse", "origin/main", cwd=env.main
    )


def test_normal_sigterm_end_is_not_a_failure(env: Env) -> None:
    _data_parents(env)
    r = env.daily("SHORT", CP3_DAILY_TODAY=_OPEN_DAY, CP3_TEST_STUB_RC="143")
    assert r.returncode == 143
    assert "정상" in r.stdout and "실패" not in r.stdout


@pytest.mark.parametrize("rc", ["3", "4", "5", "1"])
def test_runner_failure_alerts(env: Env, rc: str) -> None:
    _data_parents(env)
    r = env.daily("LONG", CP3_DAILY_TODAY=_OPEN_DAY, CP3_TEST_STUB_RC=rc)
    assert r.returncode == int(rc)
    assert f"일일 세션 실패 ({_OPEN_DAY}) rc={rc}" in r.stdout


def test_one_session_per_day_and_old_worktrees_are_cleared(env: Env) -> None:
    _data_parents(env)
    assert env.daily("LONG", CP3_DAILY_TODAY="2026-10-23").returncode == 0
    r = env.daily("LONG", CP3_DAILY_TODAY=_OPEN_DAY)
    assert r.returncode == 0, r.stdout
    assert "removed old worktree" in r.stdout
    assert not (env.state / "measure/wt-cp3-long-20261023").exists()
    again = env.daily("LONG", CP3_DAILY_TODAY=_OPEN_DAY)
    assert again.returncode == 2
    assert "already exists" in again.stdout and "실패" in again.stdout


def test_missing_data_parent_is_refused_with_an_alert(env: Env) -> None:
    r = env.daily("LONG", CP3_DAILY_TODAY=_OPEN_DAY)
    assert r.returncode == 2
    assert "data parent missing" in r.stdout and "notify-body" in r.stdout
    assert not (env.state / "cp3-sessions").exists()


def test_a_held_lock_is_a_failure_not_a_second_session(env: Env) -> None:
    _data_parents(env)
    env.locks.mkdir()
    with open(env.locks / "cp3-long-tenant-daily.lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        r = env.daily("LONG", CP3_DAILY_TODAY=_OPEN_DAY)
    assert r.returncode == 75
    assert "lock busy" in r.stdout and "실패" in r.stdout
    assert not (env.state / "cp3-sessions").exists()
    # the other direction has its own lock
    assert env.daily("SHORT", CP3_DAILY_TODAY=_OPEN_DAY).returncode == 0


def test_bad_arguments(env: Env) -> None:
    assert env.daily().returncode == 2
    assert env.daily("BOTH").returncode == 2
    assert env.daily("LONG", "--now").returncode == 2


# ----------------------------------------------------------------- preflight


def test_preflight_reports_the_roll_and_writes_nothing(env: Env) -> None:
    _data_parents(env)
    (env.state / "cp3-setup-d-long-data/A05611").mkdir()
    before = sorted(
        p.relative_to(env.tmp) for p in env.tmp.rglob("*") if ".git" not in p.parts
    )

    r11 = env.daily(
        "LONG", "--preflight", "2026-11-12"
    )  # expiry day: still the November leaf
    assert r11.returncode == 0, r11.stdout + r11.stderr
    assert "market=OPEN" in r11.stdout and "instrument=A05611" in r11.stdout
    assert "present (continues)" in r11.stdout

    r13 = env.daily(
        "LONG", "--preflight", "2026-11-13"
    )  # first session on the December leaf
    assert "instrument=A05612" in r13.stdout
    assert "absent (first session genesis)" in r13.stdout

    closed = env.daily("SHORT", "--preflight", _HOLIDAY)
    assert "market=CLOSED" in closed.stdout

    after = sorted(
        p.relative_to(env.tmp) for p in env.tmp.rglob("*") if ".git" not in p.parts
    )
    assert after == before
