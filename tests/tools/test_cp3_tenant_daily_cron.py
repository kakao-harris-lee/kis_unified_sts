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
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNERS = _REPO_ROOT / "tools" / "tos_cp3" / "runners"
_WRAPPER_REL = "tools/tos_cp3/runners/cp3_tenant_daily.sh"
_INSTALLER_REL = "tools/tos_cp3/runners/install_tenant_cron.sh"

_HOLIDAY = "2026-11-03"  # a Tuesday, listed as a holiday in the fixture calendars
_OPEN_DAY = "2026-10-26"  # a Monday, not a holiday
#: A FICTITIOUS dated session override (#924 shape): a Thursday the fixture calendar
#: shifts an hour late. Not a real KRX notice — tests only.
_OVERRIDE_DAY = "2026-12-03"

#: Like the real tenant calendars (§7.2-g keeps the four byte-identical), this
#: carries BOTH session classes: the futures wrapper reads ``krx-index-futures``
#: and the stock one ``krx-stock``, whose CONTINUOUS close is 15:30.
_CALENDAR = f"""calendar_version: "t"
holidays:
  - "{_HOLIDAY}"
sessions:
  krx-index-futures:
    - {{phase: CONTINUOUS, start: "08:45", end: "15:45", days: [MON,TUE,WED,THU,FRI], crosses_midnight: false}}
  krx-stock:
    - {{phase: PRE_OPEN,    start: "08:30", end: "08:40", days: [MON,TUE,WED,THU,FRI], crosses_midnight: false}}
    - {{phase: CONTINUOUS,  start: "09:00", end: "15:30", days: [MON,TUE,WED,THU,FRI], crosses_midnight: false}}
    - {{phase: AFTER_HOURS, start: "15:40", end: "16:00", days: [MON,TUE,WED,THU,FRI], crosses_midnight: false}}
session_overrides:
  "{_OVERRIDE_DAY}":
    reason: "test fixture — fictitious late open"
    sessions:
      krx-index-futures:
        - {{phase: CONTINUOUS, start: "09:45", end: "16:45", crosses_midnight: false}}
      krx-stock:
        - {{phase: CONTINUOUS, start: "10:00", end: "16:30", crosses_midnight: false}}
"""

_PRODUCER_CONFIG = """calendar_yaml: config/tos_runtime/cp3-setup-d-long/calendar.yaml
calendar_session_id: krx-index-futures
calendar_session_phase: CONTINUOUS
"""

_STOCK_PRODUCER_CONFIG = """calendar_yaml: config/tos_runtime/cp3-setup-d-stock-005930/calendar.yaml
calendar_session_id: krx-stock
calendar_session_phase: CONTINUOUS
market: stock
"""

_STUB_RUNNER = """#!/bin/bash
# Test stub: record what the wrapper handed over, exit with the requested rc.
env | grep '^TENANT_' | sort
# A stock session: the wrapper waits for this line in TENANT_LOG before it writes
# today's standing approval. CP3_TEST_STUB_NO_RENDER=1 withholds it.
if [ -n "${TENANT_KIS_MOCK_TRANSPORT_CONFIG:-}" ] && [ -z "${CP3_TEST_STUB_NO_RENDER:-}" ]; then
  echo "render ok -> ${TENANT_RENDER_OUT:-}" >>"$TENANT_LOG"
fi
[ -n "${CP3_TEST_STUB_SLEEP_S:-}" ] && sleep "$CP3_TEST_STUB_SLEEP_S"
exit "${CP3_TEST_STUB_RC:-0}"
"""

#: Stub of the runtime CLI the wrapper reaches with the `-c` form (§7.2-f: `-m`
#: would do nothing and exit 0). Records argv so the invocation itself is pinned.
_STUB_COMPOSE_CLI = '''"""Test stub of tos_runtime.compose.cli."""

import os
import pathlib


def main(argv):
    out = os.environ.get("FAKE_APPROVAL_OUT")
    if out:
        pathlib.Path(out).write_text("\\n".join(argv) + "\\n", encoding="utf-8")
    return int(os.environ.get("FAKE_APPROVAL_RC", "0"))
'''

_FAKE_CRONTAB = """#!/bin/bash
# Test stub: `crontab -l` prints $FAKE_CRONTAB_FILE, `crontab FILE` replaces it.
# FAKE_CRONTAB_LIST_ERR makes -l fail with that stderr; every write is counted.
if [ "${1:-}" = "-l" ]; then
  if [ -n "${FAKE_CRONTAB_LIST_ERR:-}" ]; then echo "$FAKE_CRONTAB_LIST_ERR" >&2; exit 1; fi
  [ -f "$FAKE_CRONTAB_FILE" ] || { echo "no crontab for test" >&2; exit 1; }
  cat "$FAKE_CRONTAB_FILE"
else
  echo "$1" >>"$FAKE_CRONTAB_FILE.writes"
  cp "$1" "$FAKE_CRONTAB_FILE"
fi
"""

_FAKE_INSTALL = """#!/bin/bash
# Test stub: fail when FAKE_INSTALL_FAIL is set, otherwise the real install(1).
[ -n "${FAKE_INSTALL_FAIL:-}" ] && { echo "install: simulated failure" >&2; exit 1; }
exec /usr/bin/install "$@"
"""

_NO_YAML_PYTHON = """#!/bin/bash
echo "ModuleNotFoundError: No module named 'yaml'" >&2
exit 1
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
53 8 * * 1-5 /bin/bash /x/run-cp3-tenant-daily.sh STOCK >> /x/k.log 2>&1 # cp3-stock-tenant-daily
"""


def _canonical_transport_block() -> str:
    """The `mode: live` … `allow_plaintext…` block of the real setup script.

    Read from the shipped ``setup_stock_mock_once.sh`` rather than copied here, so
    the "keys agree" case keeps agreeing when a key is added to the canonical set
    (the #979 / 10-30 r1 failure was exactly a key added on one side only).
    """
    lines = (
        (_REPO_ROOT / "tools/tos_cp3/runners/setup_stock_mock_once.sh")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    start = next(i for i, ln in enumerate(lines) if ln.startswith("mode: live"))
    end = next(i for i, ln in enumerate(lines) if ln.startswith("allow_plaintext"))
    return "\n".join(lines[start : end + 1]) + "\n"


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
        for tree in (
            "cp3-setup-d-long",
            "cp3-setup-d-short",
            "cp3-setup-d-stock-005930",
        ):
            _write(seed / f"config/tos_runtime/{tree}/calendar.yaml", _CALENDAR)
        _write(seed / "config/tos_probes/cp3-live-producer.yaml", _PRODUCER_CONFIG)
        _write(
            seed / "config/tos_probes/cp3-live-producer-stock-005930.yaml",
            _STOCK_PRODUCER_CONFIG,
        )
        # The stock session's TENANT_* set and the canonical transport keys are the
        # SHIPPED files, not copies: the wrapper sources one and diffs against the
        # other, so a drifting copy here would hide the drift it is meant to catch.
        for rel in (
            "tools/tos_cp3/runners/stock-mock-session.env.example",
            "tools/tos_cp3/runners/setup_stock_mock_once.sh",
        ):
            shutil.copy(_REPO_ROOT / rel, seed / rel)
        for rel in (
            "tos/runtime/src/tos_runtime/__init__.py",
            "tos/runtime/src/tos_runtime/compose/__init__.py",
        ):
            _write(seed / rel, "")
        _write(seed / "tos/runtime/src/tos_runtime/compose/cli.py", _STUB_COMPOSE_CLI)
        # The wrapper derives the stop time through the SHIPPED day-window reader.
        shutil.copy(
            _REPO_ROOT / "tools/tos_cp3/session_day.py",
            seed / "tools/tos_cp3/session_day.py",
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
        _write(bindir / "install", _FAKE_INSTALL, 0o755)
        self.crontab = tmp / "crontab.txt"
        self.approval_argv = tmp / "approval-argv.txt"
        self.base_env = {
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "HOME": str(self.home),
            "TZ": "Asia/Seoul",
            "FAKE_CRONTAB_FILE": str(self.crontab),
            "FAKE_APPROVAL_OUT": str(self.approval_argv),
            "CP3_DAILY_MAIN": str(self.main),
            "CP3_DAILY_STATE": str(self.state),
            "CP3_DAILY_LOCK_DIR": str(self.locks),
            "CP3_DAILY_NOTIFY": "0",
            # The 20-minute `render ok` wait, shortened: 3 × 1 s.
            "CP3_DAILY_APPROVAL_WAIT_TRIES": "3",
            "CP3_DAILY_APPROVAL_WAIT_SLEEP_S": "1",
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
    _stock_host_state(env)


def _stock_host_state(env: Env, *, transport: str | None = None) -> Path:
    """The STOCK tenant's one-time host state (§7.2-f): durable parent, custody,
    and the operation transport config. Returns the transport config's path."""
    for name in (
        "cp3-setup-d-stock-005930-data",
        "cp3-setup-d-stock-custody",
        "cp3-setup-d-stock-ops",
    ):
        (env.state / name).mkdir(mode=0o700, exist_ok=True)
    path = env.state / "cp3-setup-d-stock-ops/kis_mock_transport.yaml"
    path.write_text(
        _canonical_transport_block() if transport is None else transport,
        encoding="utf-8",
    )
    return path


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
    # STOCK: 08:53, inside §7.2-f's 08:52-09:05 start window.
    assert (
        f"+53 8 * * 1-5 /bin/bash {dest} STOCK >> {env.state}/cp3-stock-tenant-daily.cron.log 2>&1 # cp3-stock-tenant-daily"
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
    assert "/x/k.log" not in tab  # the one-off stock line too
    assert tab.count("# cp3-long-tenant-daily") == 1
    assert tab.count("# cp3-short-tenant-daily") == 1
    assert tab.count("# cp3-stock-tenant-daily") == 1
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
    # 2026-12-30 (Wed) is open in the fixture calendar — closed only via the knob.
    r = env.daily(
        "SHORT", CP3_DAILY_TODAY="2026-12-30", CP3_DAILY_EXTRA_CLOSED="2026-12-30"
    )
    assert r.returncode == 0 and "SKIP" in r.stdout


def test_real_tenant_calendars_carry_the_krx_year_end_close() -> None:
    """The wrapper no longer defaults 2026-12-31 into the extra closed dates (#964):
    the KRX year-end close (유가증권시장 업무규정 제5조) must come from each tree's own
    calendar, or the cron would boot a session on a closed day."""
    for tree in ("cp3-setup-d-long", "cp3-setup-d-short", "cp3-setup-d-stock-005930"):
        path = _REPO_ROOT / "config" / "tos_runtime" / tree / "calendar.yaml"
        holidays = {
            str(h) for h in yaml.safe_load(path.read_text(encoding="utf-8"))["holidays"]
        }
        assert "2026-12-31" in holidays, tree


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


def _runner_out(env: Env, lc: str, day: str) -> str:
    session = env.state / "cp3-sessions" / f"{lc}-{day.replace('-', '')}"
    return (session / "runner.out").read_text(encoding="utf-8")


def test_924_a_dated_override_moves_the_stop_time_with_the_close(env: Env) -> None:
    """#924: the stop comes from THAT day's close in the tree's calendar (16:45 + 5),
    not from a literal 15:50 that would kill an exam-day session an hour early."""
    _data_parents(env)
    r = env.daily("LONG", CP3_DAILY_TODAY=_OVERRIDE_DAY)
    assert r.returncode == 0, r.stdout
    assert "TENANT_STOP_AT=16:50" in _runner_out(env, "long", _OVERRIDE_DAY)
    assert "09:45-16:45 OVERRIDE" in r.stdout


def test_924_a_regular_day_keeps_15_50_and_the_knobs_still_work(env: Env) -> None:
    _data_parents(env)
    r = env.daily(
        "SHORT", CP3_DAILY_TODAY=_OPEN_DAY, CP3_DAILY_STOP_AFTER_CLOSE_MIN="7"
    )
    assert r.returncode == 0, r.stdout
    assert "TENANT_STOP_AT=15:52" in _runner_out(env, "short", _OPEN_DAY)
    r = env.daily("LONG", CP3_DAILY_TODAY=_OVERRIDE_DAY, CP3_DAILY_STOP_AT="14:00")
    assert r.returncode == 0, r.stdout
    assert "TENANT_STOP_AT=14:00" in _runner_out(env, "long", _OVERRIDE_DAY)


def test_924_an_unreadable_session_window_is_a_failure_not_a_run(env: Env) -> None:
    _data_parents(env)
    cfg = env.main / "config/tos_probes/cp3-live-producer.yaml"
    cfg.write_text(_PRODUCER_CONFIG.replace("CONTINUOUS", "NOPE"), encoding="utf-8")
    _git("commit", "-qam", "break the phase", cwd=env.main)
    _git("push", "-q", "origin", "HEAD:main", cwd=env.main)
    r = env.daily("LONG", CP3_DAILY_TODAY=_OPEN_DAY)
    assert r.returncode == 2, r.stdout
    assert "stop time not derivable" in r.stdout
    assert not (
        env.state / "cp3-sessions" / f"long-{_OPEN_DAY.replace('-', '')}"
    ).exists()


def test_924_preflight_shows_the_dated_window_and_stop(env: Env) -> None:
    r = env.daily("LONG", "--preflight", _OVERRIDE_DAY)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "09:45-16:45 OVERRIDE" in r.stdout and "stop_at=16:50" in r.stdout
    r = env.daily("LONG", "--preflight", _OPEN_DAY)
    assert "08:45-15:45 regular" in r.stdout and "stop_at=15:50" in r.stdout


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
    with open(env.locks / "cp3-long-tenant-daily.wrapper.lock", "w") as fh:
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


# ------------------------------------------------- review #933 regressions


def _assert_alerted_failure(r: subprocess.CompletedProcess[str], rc: int = 2) -> None:
    assert r.returncode == rc, r.stdout + r.stderr
    assert "SKIP" not in r.stdout
    assert "일일 세션 실패" in r.stdout and "notify-body" in r.stdout


def test_b1_a_python_that_cannot_import_yaml_is_a_failure_not_a_skip(env: Env) -> None:
    _data_parents(env)
    py = env.main / ".venv/bin/python"
    py.unlink()
    _write(py, _NO_YAML_PYTHON, 0o755)
    r = env.daily("LONG", CP3_DAILY_TODAY=_OPEN_DAY)
    _assert_alerted_failure(r)
    assert "holiday check failed (rc=1)" in r.stdout
    assert not (env.state / "cp3-sessions").exists()
    assert not (
        env.state / f"measure/wt-cp3-long-{_OPEN_DAY.replace('-', '')}"
    ).exists()
    pre = env.daily("LONG", "--preflight", _OPEN_DAY)
    assert pre.returncode == 2 and "market=" not in pre.stdout


def test_b1_an_impossible_date_is_a_failure_not_a_skip(env: Env) -> None:
    _data_parents(env)
    _assert_alerted_failure(env.daily("SHORT", CP3_DAILY_TODAY="2026-02-30"))
    assert env.daily("SHORT", "--preflight", "2026-02-30").returncode == 2


def test_n3_a_calendar_without_this_years_holidays_is_refused(env: Env) -> None:
    _data_parents(env)
    r = env.daily("LONG", CP3_DAILY_TODAY="2027-01-04")
    _assert_alerted_failure(r)
    assert "lists no holiday in 2027" in r.stdout
    pre = env.daily("LONG", "--preflight", "2027-01-04")
    assert pre.returncode == 2 and "no holiday in 2027" in pre.stdout


def test_n1_a_non_kst_host_zone_is_refused_at_run_time(env: Env) -> None:
    _data_parents(env)
    r = env.daily("LONG", CP3_DAILY_TODAY=_OPEN_DAY, TZ="UTC")
    _assert_alerted_failure(r)
    assert "not +0900" in r.stdout
    assert not (env.state / "cp3-sessions").exists()


def test_n4_the_hand_lines_outer_lock_does_not_block_the_new_wrapper(env: Env) -> None:
    # 10-22 hand lines hold `cp3-long-tenant-daily.lock` around the call.
    _data_parents(env)
    env.locks.mkdir()
    with open(env.locks / "cp3-long-tenant-daily.lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        r = env.daily("LONG", CP3_DAILY_TODAY=_OPEN_DAY)
    assert r.returncode == 0, r.stdout


def test_n4_a_failed_wrapper_install_rolls_the_crontab_back(env: Env) -> None:
    env.crontab.write_text(_OTHER_LINES + _LEGACY_LINES, encoding="utf-8")
    env.dest_dir.mkdir(parents=True)
    old = env.dest_dir / "run-cp3-tenant-daily.sh"
    old.write_text("#!/bin/bash\necho hand-made\n", encoding="utf-8")
    r = env.install("--apply", FAKE_INSTALL_FAIL="1")
    assert r.returncode == 2
    assert "rolled back crontab" in r.stderr
    assert env.crontab.read_text(encoding="utf-8") == _OTHER_LINES + _LEGACY_LINES
    assert old.read_text(encoding="utf-8") == "#!/bin/bash\necho hand-made\n"


def test_n5_missing_credentials_are_logged_as_a_failed_notify(env: Env) -> None:
    r = env.daily("LONG", CP3_DAILY_TODAY=_OPEN_DAY, CP3_DAILY_NOTIFY="1")
    assert r.returncode == 2
    assert (
        "telegram notify FAILED: TELEGRAM_BRIEFING_BOT_TOKEN and TELEGRAM_BRIEFING_CHAT_ID missing"
        in r.stdout
    )


def test_n5_curl_treats_http_errors_as_failure() -> None:
    text = (_REPO_ROOT / _WRAPPER_REL).read_text(encoding="utf-8")
    assert "curl --fail " in text


@pytest.mark.parametrize("apply", [False, True])
def test_n6_a_crontab_read_error_aborts_instead_of_wiping(
    env: Env, apply: bool
) -> None:
    env.crontab.write_text(_OTHER_LINES, encoding="utf-8")
    args = ("--apply",) if apply else ()
    r = env.install(
        *args, FAKE_CRONTAB_LIST_ERR="crontab: cannot open spool: Permission denied"
    )
    assert r.returncode == 2
    assert "crontab -l failed" in r.stderr
    assert env.crontab.read_text(encoding="utf-8") == _OTHER_LINES
    assert not Path(f"{env.crontab}.writes").exists()


def test_n6_no_crontab_at_all_is_an_empty_crontab(env: Env) -> None:
    r = env.install("--apply")
    assert r.returncode == 0, r.stderr
    assert "# BEGIN CP3_TENANT_DAILY" in env.crontab.read_text(encoding="utf-8")


# --------------------------------------------- STOCK (#M2, operator 2026-11-05)
#
# The third direction: the kis-mock tenant of runbook §7.2-f, which SENDS. What is
# new next to LONG/SHORT is the stock session window (krx-stock, close 15:30), the
# `stock-r<RUN>-` session naming, the transport-key precheck and the standing
# approval the session cannot send without.


def _stock_session(env: Env, day: str, run: int = 1) -> Path:
    return env.state / "cp3-sessions" / f"stock-r{run}-{day.replace('-', '')}"


def _stock_wt(env: Env, day: str, run: int = 1) -> Path:
    return env.state / "measure" / f"wt-cp3-stock-r{run}-{day.replace('-', '')}"


def test_stock_open_day_hands_the_runner_the_env_examples_tenant_values(
    env: Env,
) -> None:
    _data_parents(env)
    r = env.daily("STOCK", CP3_DAILY_TODAY=_OPEN_DAY)
    assert r.returncode == 0, r.stdout
    session = _stock_session(env, _OPEN_DAY)
    out = (session / "runner.out").read_text(encoding="utf-8")
    for expected in (
        "TENANT_TREE=cp3-setup-d-stock-005930",
        # The wrapper's direction is STOCK; the SESSION's direction is Setup D LONG,
        # and the runner accepts only LONG/SHORT.
        "TENANT_DIRECTION=LONG",
        "TENANT_INSTRUMENT=005930",
        "TENANT_ENVIRONMENT_LABEL=paper",
        # krx-stock CONTINUOUS close 15:30 + 10 — the 11-03 sequence's 15:40.
        "TENANT_STOP_AT=15:40",
        f"TENANT_DATA_PARENT={env.state}/cp3-setup-d-stock-005930-data",
        f"TENANT_CUSTODY_ROOT={env.state}/cp3-setup-d-stock-custody",
        f"TENANT_KIS_MOCK_TRANSPORT_CONFIG={env.state}/cp3-setup-d-stock-ops/kis_mock_transport.yaml",
        f"TENANT_ENV_FILE={env.main}/.env.mock",
        f"TENANT_LOG={session}/session.log",
        f"TENANT_RENDER_OUT={session}/render",
        f"TENANT_JOURNAL={session}/journal.jsonl",
        f"TENANT_PRODUCER_SESSION_DIR={session}/producer",
        f"TENANT_PRODUCER_CONFIG={_stock_wt(env, _OPEN_DAY)}"
        "/config/tos_probes/cp3-live-producer-stock-005930.yaml",
    ):
        assert expected in out, out
    assert (session / "runner.pid").read_text(encoding="utf-8").strip().isdigit()
    assert "일일 세션 종료" in r.stdout and "정상" in r.stdout
    assert _git("rev-parse", "HEAD", cwd=_stock_wt(env, _OPEN_DAY)) == _git(
        "rev-parse", "origin/main", cwd=env.main
    )


def test_stock_the_standing_approval_is_written_after_render_ok(env: Env) -> None:
    """#955: without today's standing approval the flow stops at step 4 and the
    session sends nothing, so writing it is part of the unattended run. The `-c`
    form is what runs — `python -m tos_runtime.compose.cli` would exit 0 silently."""
    _data_parents(env)
    r = env.daily("STOCK", CP3_DAILY_TODAY=_OPEN_DAY)
    assert r.returncode == 0, r.stdout
    assert "write-standing-approval rc=0" in r.stdout
    session = _stock_session(env, _OPEN_DAY)
    assert env.approval_argv.read_text(encoding="utf-8").splitlines() == [
        "write-standing-approval",
        "--config-dir",
        f"{session}/render",
        "--custody-root",
        f"{env.state}/cp3-setup-d-stock-custody",
        "--environment-label",
        "paper",
        "--trading-date",
        _OPEN_DAY,
    ]
    assert (session / "approval.out").exists()


def test_stock_no_approval_when_the_session_ends_before_render_ok(env: Env) -> None:
    _data_parents(env)
    r = env.daily(
        "STOCK",
        CP3_DAILY_TODAY=_OPEN_DAY,
        CP3_TEST_STUB_NO_RENDER="1",
        CP3_TEST_STUB_RC="3",
    )
    assert r.returncode == 3, r.stdout
    assert not env.approval_argv.exists()
    assert "write-standing-approval rc=" not in r.stdout
    assert "render ok 전에 끝났다" in r.stdout
    assert f"일일 세션 실패 ({_OPEN_DAY}) rc=3" in r.stdout


def test_stock_a_session_that_never_renders_alerts_and_keeps_running(env: Env) -> None:
    _data_parents(env)
    r = env.daily(
        "STOCK",
        CP3_DAILY_TODAY=_OPEN_DAY,
        CP3_TEST_STUB_NO_RENDER="1",
        CP3_TEST_STUB_SLEEP_S="6",
    )
    assert r.returncode == 0, r.stdout  # the runner's own rc, waited for
    assert not env.approval_argv.exists()
    assert "no 'render ok' within 3s" in r.stdout
    assert "상시 승인 못 씀" in r.stdout


def test_stock_a_failed_approval_write_alerts_but_does_not_kill_the_session(
    env: Env,
) -> None:
    _data_parents(env)
    r = env.daily("STOCK", CP3_DAILY_TODAY=_OPEN_DAY, FAKE_APPROVAL_RC="1")
    assert r.returncode == 0, r.stdout  # the runner's rc decides, not the approval's
    assert "write-standing-approval rc=1" in r.stdout
    assert "상시 승인 쓰기 실패" in r.stdout and "notify-body" in r.stdout
    assert "일일 세션 종료" in r.stdout and "정상" in r.stdout


def test_stock_a_transport_key_missing_from_the_operation_file_is_refused(
    env: Env,
) -> None:
    """The 10-30 r1 failure: #979 added `app_key_request_wait_budget_ms` on 10-28,
    the 10-26 operation file did not have it, and the session refused at boot with
    0 sends. Refused here instead, before anything is created."""
    _data_parents(env)
    path = env.state / "cp3-setup-d-stock-ops/kis_mock_transport.yaml"
    kept = [
        ln
        for ln in path.read_text(encoding="utf-8").splitlines()
        if not ln.startswith("app_key_request_wait_budget_ms:")
    ]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    r = env.daily("STOCK", CP3_DAILY_TODAY=_OPEN_DAY)
    assert r.returncode == 2, r.stdout
    assert "운영 전송 설정 키가 정본" in r.stdout and "notify-body" in r.stdout
    assert "app_key_request_wait_budget_ms:" in r.stdout  # the diff names the key
    assert not _stock_session(env, _OPEN_DAY).exists()
    assert not _stock_wt(env, _OPEN_DAY).exists()
    assert not env.approval_argv.exists()


def test_stock_a_missing_transport_config_is_refused_not_skipped(env: Env) -> None:
    _data_parents(env)
    (env.state / "cp3-setup-d-stock-ops/kis_mock_transport.yaml").unlink()
    r = env.daily("STOCK", CP3_DAILY_TODAY=_OPEN_DAY)
    assert r.returncode == 2, r.stdout
    assert "SKIP" not in r.stdout
    assert (
        "전송 설정 키 대조 실패" in r.stdout and "transport config missing" in r.stdout
    )
    assert not _stock_wt(env, _OPEN_DAY).exists()


def test_stock_holiday_is_a_silent_skip(env: Env) -> None:
    _data_parents(env)
    r = env.daily("STOCK", CP3_DAILY_TODAY=_HOLIDAY)
    assert r.returncode == 0, r.stdout
    assert "SKIP" in r.stdout
    assert "notify-body" not in r.stdout
    assert not (env.state / "cp3-sessions").exists()
    assert not _stock_wt(env, _HOLIDAY).exists()
    assert not env.approval_argv.exists()


def test_stock_924_a_dated_override_moves_the_stop_with_the_stock_close(
    env: Env,
) -> None:
    _data_parents(env)
    r = env.daily("STOCK", CP3_DAILY_TODAY=_OVERRIDE_DAY)
    assert r.returncode == 0, r.stdout
    out = (_stock_session(env, _OVERRIDE_DAY) / "runner.out").read_text(
        encoding="utf-8"
    )
    assert "TENANT_STOP_AT=16:40" in out  # 16:30 + 10, not the futures 16:50
    assert "10:00-16:30 OVERRIDE" in r.stdout


def test_stock_one_session_per_day_and_old_worktrees_are_cleared(env: Env) -> None:
    _data_parents(env)
    assert env.daily("STOCK", CP3_DAILY_TODAY="2026-10-23").returncode == 0
    r = env.daily("STOCK", CP3_DAILY_TODAY=_OPEN_DAY)
    assert r.returncode == 0, r.stdout
    assert "removed old worktree" in r.stdout
    assert not _stock_wt(env, "2026-10-23").exists()
    again = env.daily("STOCK", CP3_DAILY_TODAY=_OPEN_DAY)
    assert again.returncode == 2
    assert "already exists" in again.stdout and "실패" in again.stdout


def test_stock_holds_its_own_lock(env: Env) -> None:
    _data_parents(env)
    env.locks.mkdir(exist_ok=True)
    with open(env.locks / "cp3-stock-tenant-daily.wrapper.lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        r = env.daily("STOCK", CP3_DAILY_TODAY=_OPEN_DAY)
        assert env.daily("LONG", CP3_DAILY_TODAY=_OPEN_DAY).returncode == 0
    assert r.returncode == 75
    assert "lock busy" in r.stdout and "실패" in r.stdout
    assert not _stock_session(env, _OPEN_DAY).exists()


def test_stock_preflight_reports_the_window_leaf_and_transport_keys(env: Env) -> None:
    _data_parents(env)
    before = sorted(
        p.relative_to(env.tmp) for p in env.tmp.rglob("*") if ".git" not in p.parts
    )
    r = env.daily("STOCK", "--preflight", _OPEN_DAY)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"krx-stock CONTINUOUS {_OPEN_DAY} 09:00-15:30 regular" in r.stdout
    assert "stop_at=15:40" in r.stdout
    assert "market=OPEN" in r.stdout and "instrument=005930" in r.stdout
    assert f"leaf {env.state}/cp3-setup-d-stock-005930-data/005930" in r.stdout
    assert "transport config keys = 정본" in r.stdout
    assert f"session dir {_stock_session(env, _OPEN_DAY)}" in r.stdout
    assert f"worktree {_stock_wt(env, _OPEN_DAY)}" in r.stdout

    closed = env.daily("STOCK", "--preflight", _HOLIDAY)
    assert closed.returncode == 0 and "market=CLOSED" in closed.stdout

    override = env.daily("STOCK", "--preflight", _OVERRIDE_DAY)
    assert "10:00-16:30 OVERRIDE" in override.stdout
    assert "stop_at=16:40" in override.stdout

    after = sorted(
        p.relative_to(env.tmp) for p in env.tmp.rglob("*") if ".git" not in p.parts
    )
    assert after == before


def test_stock_preflight_names_a_transport_key_difference_without_refusing(
    env: Env,
) -> None:
    _data_parents(env)
    _stock_host_state(env, transport="mode: live\nonly_key: 1\n")
    r = env.daily("STOCK", "--preflight", _OPEN_DAY)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "keys DIFFER" in r.stdout and "a run would refuse" in r.stdout
    assert "only_key:" in r.stdout
    assert "market=OPEN" in r.stdout  # the rest of the preflight still reports


@pytest.mark.parametrize("apply", [False, True])
def test_n6_a_begin_without_end_aborts(env: Env, apply: bool) -> None:
    broken = (
        _OTHER_LINES
        + "# BEGIN CP3_TENANT_DAILY (half-edited)\nCRON_TZ=Asia/Seoul\n0 3 * * 0 /x/keep-me.sh\n"
    )
    env.crontab.write_text(broken, encoding="utf-8")
    args = ("--apply",) if apply else ()
    r = env.install(*args)
    assert r.returncode == 2
    assert "without a matching" in r.stderr
    assert env.crontab.read_text(encoding="utf-8") == broken
    assert not Path(f"{env.crontab}.writes").exists()
