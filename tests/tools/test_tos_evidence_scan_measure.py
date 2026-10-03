"""Tests for the evidence-scan measurement driver (growth plan §2 A1-b,
``tools/tos_evidence_scan_measure.py``).

What has to be tested here is not "does it run the bench" but "does it really refuse".
The 2026-09-30 A1 run's guards were never committed and are gone (plan §7.1.7 deviation 11),
and the swap floor the operator's global rule requires was missing from them entirely
(deviation 11-b) — a hole nothing detected because a guard that never fires and a guard that
does not exist look identical from outside. So every refusal below is exercised against a
real host reader pointed at a fake ``/proc/meminfo`` and a fake ``pgrep``, each guard is
proven to fail red when neutralized, and the watchdog is proven to actually kill a live
child rather than merely to return a verdict.

Hermetic: every file these tests write goes under ``tmp_path``, no network, and the only
processes started are ``sleep``/``python -c`` children of the test itself.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import os
import shlex
import signal
import sqlite3
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "tos_evidence_scan_measure.py"
_BENCH_PATH = _REPO_ROOT / "tools" / "tos_evidence_scan_bench.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


driver = _load("tos_evidence_scan_measure", _MODULE_PATH)
bench = _load("tos_evidence_scan_bench_for_tests", _BENCH_PATH)

_GB = 1024**3

#: One fabricated competing driver's command line, shared by several tests below.
_A_SECOND_DRIVER = "/usr/bin/python tools/tos_evidence_scan_measure.py run --days 90"


# ---------------------------------------------------------------------------------------
# Fabricated processes (#848)
# ---------------------------------------------------------------------------------------
#
# A test that invents a competing process has to invent the whole world that process lives
# in. The driver does not take a ``pgrep`` line at face value: it drops lines whose PID is
# its own, is one of its own ancestors or descendants, or has a ``pytest`` ancestor
# (round-2 F2). Every one of those questions is answered by reading ``/proc`` and by
# asking the OS which PID the driver is. Leave either of those pointed at the real host
# and the fabrication is judged against whatever the runner happened to allocate: on
# tos-firewall run 36997189121 the hardcoded ``5150`` was a live pytest descendant, the
# driver dropped the only injected line as a colleague's test run, and a refusal test
# silently read ``assert 'ok' == 'refused'`` (#848).
#
# So a fabricated process table comes with both halves of that world:
#
# * a fake ``/proc`` built from the SAME table (:func:`_fake_proc_for`), so the ancestry
#   rules read the tree the test described;
# * a ``self_pid`` that is part of the fabrication too. ``HostReader.self_pid`` exists for
#   this (review F5): without it ``_self_pid_chain`` starts at the runner's ``os.getpid()``
#   and no ``proc_root`` can redirect it.
#
# :func:`_fake_pid` keeps every invented PID above the kernel's ceiling on top of that.
# That is hygiene for the fabricated trees, and it is load-bearing for exactly one reader:
# :func:`_reader_that_reports_a_build_once` watches a REAL bench child, so it must read the
# real ``/proc``, and an unassignable PID is what makes its one invented process invisible
# there (review F4).


def _pid_ceiling() -> int:
    """The first number the kernel will not hand out as a PID.

    ``/proc/sys/kernel/pid_max`` is one GREATER than the largest assignable PID, so the
    value itself is already unassignable.
    """
    try:
        return int(Path("/proc/sys/kernel/pid_max").read_text().strip())
    except (OSError, ValueError):  # pragma: no cover - every Linux has this file
        return 4 * 1024 * 1024


_FAKE_PID_BASE = _pid_ceiling()

#: The stand-in for ``init`` in every fabricated tree. Fabricated processes hang off this
#: instead of off real pid 1, so a runner where the test process itself is pid 1 (a
#: container) cannot make a fabrication look like the driver's own ancestor.
_FAKE_INIT_PID = _FAKE_PID_BASE


def _fake_pid(n: int) -> int:
    """The ``n``-th PID (``n >= 0``) that no live process can hold.

    ``n`` only has to be unique within one fabricated tree; each test builds its own.
    """
    return _FAKE_PID_BASE + 1 + n


def _real_self_cmdline() -> str:
    """This process's real command line, in the shape ``/proc/<pid>/cmdline`` has it."""
    return (
        Path("/proc/self/cmdline")
        .read_bytes()
        .replace(b"\0", b" ")
        .decode("utf-8", "replace")
    )


def _proc_table(processes: Sequence[tuple[int, str]]) -> str:
    """``pgrep -af`` text for these processes.

    The ONE place a ``(pid, args)`` pair becomes a line, so the table a test feeds to
    ``pgrep`` and the ``/proc`` it feeds to the ancestry walk cannot describe different
    hosts (review F7).
    """
    return "".join(f"{pid} {args}\n" for pid, args in processes)


def _fake_proc(root: Path, tree: dict[int, tuple[int, str]]) -> Path:
    """A `/proc` with just the two files the ancestry walk reads: `status` (PPid) and
    `cmdline`."""
    for pid, (ppid, cmdline) in tree.items():
        entry = root / str(pid)
        entry.mkdir(parents=True, exist_ok=True)
        (entry / "status").write_text(f"Name:\tx\nPPid:\t{ppid}\n")
        (entry / "cmdline").write_bytes(cmdline.replace(" ", "\0").encode())
    return root


def _fake_proc_for(
    root: Path, processes: Sequence[tuple[int, str]], *, self_pid: int
) -> Path:
    """The ``/proc`` that belongs with a fabricated ``pgrep`` table.

    Three rules, each closing a way the fabrication could still be judged against the real
    host:

    * a fabricated process is a child of :data:`_FAKE_INIT_PID`, never of real pid 1;
    * the reader's own PID is a PARENTLESS root. The driver is the root of the fabricated
      world, and handing it the fabricated init as a parent would let the descendant rule
      drop the very lines ``pid in mine`` is there to drop — which is how the first
      version of the self-PID test passed without pinning anything (review F1);
    * the real ``os.getpid()`` appears with its real command line whenever it is not
      itself one of the fabricated processes. ``preflight`` reads the output-directory
      lock through this same tree, and a lock whose ``/proc/<pid>/cmdline`` is missing is
      reported as stale rather than held — so without this entry ``output_dir_unlocked``
      could never refuse in any test that fabricates processes (review F3).
    """
    tree: dict[int, tuple[int, str]] = {_FAKE_INIT_PID: (0, "/sbin/init")}
    for pid, args in processes:
        tree[pid] = (0 if pid == self_pid else _FAKE_INIT_PID, args)
    if os.getpid() not in tree:
        tree[os.getpid()] = (0, _real_self_cmdline())
    if self_pid not in tree:
        tree[self_pid] = (0, "/usr/bin/python tools/tos_evidence_scan_measure.py run")
    return _fake_proc(root, tree)


# ---------------------------------------------------------------------------------------
# Fixtures: a fake host, and a miniature reference evidence file
# ---------------------------------------------------------------------------------------


def _meminfo(
    path: Path, *, available_gb: float, swap_free_gb: float, swap_total_gb: float = 8.0
) -> Path:
    """A ``/proc/meminfo`` in the real format (kB units, the real field spelling)."""
    path.write_text(
        "MemTotal:       22016000 kB\n"
        f"MemFree:        {int(available_gb * _GB / 1024)} kB\n"
        f"MemAvailable:   {int(available_gb * _GB / 1024)} kB\n"
        f"SwapTotal:      {int(swap_total_gb * _GB / 1024)} kB\n"
        f"SwapFree:       {int(swap_free_gb * _GB / 1024)} kB\n"
    )
    return path


def _reader(
    tmp_path: Path,
    *,
    available_gb: float = 12.0,
    swap_free_gb: float = 5.0,
    processes: Sequence[tuple[int, str]] = (),
    self_pid: int | None = None,
    proc_root: Path | None = None,
) -> Any:
    """A real :class:`HostReader` pointed at fake inputs.

    ``pgrep`` is replaced by a real process producing real stdout — the reader's parsing,
    self-exclusion and search-command filtering all run for real. Nothing is monkeypatched.

    ``processes`` is the whole fabrication: the ``pgrep`` table, the ``/proc`` tree and the
    reader's own identity are all derived from it, so they cannot disagree (#848). A reader
    with no fabricated process keeps the real ``/proc``, which is what the output-directory
    lock check needs for real PIDs. ``proc_root`` is overridable for one purpose only — so
    the regression test can point a fabrication back at the real ``/proc`` and show the
    failure this seam exists to prevent.
    """
    meminfo = _meminfo(
        tmp_path / f"meminfo-{available_gb}-{swap_free_gb}",
        available_gb=available_gb,
        swap_free_gb=swap_free_gb,
    )
    whoami = os.getpid() if self_pid is None else self_pid
    if not processes:
        return driver.HostReader(
            meminfo_path=meminfo,
            pgrep_argv=("/bin/true",),
            proc_root=Path("/proc") if proc_root is None else proc_root,
            self_pid=whoami,
        )
    # A faithful `pgrep -af`: a fixed process table, matched with the SAME extended regex
    # the real binary would apply. Echoing the lines back unconditionally would test the
    # reader's parsing while leaving the patterns themselves unexercised — and the patterns
    # are where review F3 found the bug.
    text = _proc_table(processes)
    stamp = abs(hash(text))
    table = tmp_path / f"proc-table-{stamp}"
    table.write_text(text)
    fake = tmp_path / f"fake-pgrep-{stamp}.sh"
    fake.write_text(f'#!/bin/sh\ngrep -E -- "$1" "{table}" || true\nexit 0\n')
    fake.chmod(0o755)
    return driver.HostReader(
        meminfo_path=meminfo,
        pgrep_argv=(str(fake),),
        proc_root=(
            _fake_proc_for(tmp_path / f"proc-{stamp}", processes, self_pid=whoami)
            if proc_root is None
            else proc_root
        ),
        self_pid=whoami,
    )


def _reader_that_reports_a_build_once(tmp_path: Path, *, gate: Path) -> Any:
    """A host that is healthy until ``gate`` exists and running a Gradle daemon from then
    on.

    Three watchdog tests need the same thing: an abort at a known point in the run rather
    than after some number of samples. Tying the daemon's appearance to a file the run
    itself creates keeps that deterministic.

    This one keeps the REAL ``/proc``, deliberately (review F4). These are the only tests
    that run a real bench child, and the sampler reads that child's ``status`` and ``io``
    through this same ``proc_root``; a fabricated tree would answer "no such process" for
    it and quietly stop exercising the per-child sampling path. Reading the real tree is
    safe here because the one process this reader invents carries a PID the kernel cannot
    assign, so the ancestry rules can never find anything under it.
    """
    daemon = _fake_pid(0)
    fake_pgrep = tmp_path / "fake-pgrep.sh"
    fake_pgrep.write_text(
        "#!/bin/sh\n"
        f'[ -f "{gate}" ] && echo "{daemon} /usr/bin/java GradleDaemon"\n'
        "exit 0\n"
    )
    fake_pgrep.chmod(0o755)
    return driver.HostReader(
        meminfo_path=_meminfo(tmp_path / "mi", available_gb=12.0, swap_free_gb=5.0),
        pgrep_argv=(str(fake_pgrep),),
    )


def _guard(**overrides):
    kwargs = {
        "min_available_gb": driver.DEFAULT_MIN_AVAILABLE_GB,
        "min_swap_free_gb": driver.DEFAULT_MIN_SWAP_FREE_GB,
        "abort_available_gb": driver.DEFAULT_ABORT_AVAILABLE_GB,
        "abort_swap_free_gb": driver.DEFAULT_ABORT_SWAP_FREE_GB,
        "watch_interval_s": 0.01,
        "poll_interval_s": 0.005,
        "term_grace_s": 0.5,
    }
    kwargs.update(overrides)
    return driver.GuardConfig.validated(**kwargs)


# ---------------------------------------------------------------------------------------
# Checkout fixtures — REAL git repositories, in each shape the guard has to refuse
# ---------------------------------------------------------------------------------------
#
# Real `git init`, not a stub binary: the guard asks git four questions (toplevel, HEAD,
# `status --porcelain`, `merge-base --is-ancestor`) and a fake would only prove the fake
# answers them. Each repo is two files and lives under `tmp_path`, so it is cheap and
# hermetic. `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` are pinned to /dev/null so the
# developer's own git config (hooks, templates, signing, `init.defaultBranch`) cannot
# change what these tests measure.

_GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_AUTHOR_NAME": "tos tests",
    "GIT_AUTHOR_EMAIL": "tos-tests@example.invalid",
    "GIT_COMMITTER_NAME": "tos tests",
    "GIT_COMMITTER_EMAIL": "tos-tests@example.invalid",
}


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=_GIT_ENV,
    )
    return completed.stdout.strip()


def _make_checkout(
    root: Path,
    *,
    detached: bool = True,
    dirty: bool = False,
    ancestor: bool = True,
    origin_main: bool = True,
    bench_ignored: bool = False,
) -> Path:
    """A git checkout holding stand-ins for the driver and the bench, in the asked shape.

    The two files only have to exist and be hashable — the guard reads git about the tree
    and sha256 about the bench, never the Python inside either.

    ``bench_ignored`` puts the bench in ``.gitignore``. That is the one shape in which a
    bench can change while ``git status --porcelain`` stays empty, which is why the digest
    is checked next to cleanliness rather than instead of it.
    """
    repo = root / "checkout"
    (repo / "tools").mkdir(parents=True)
    (repo / "tools" / "tos_evidence_scan_measure.py").write_text("# driver stand-in\n")
    (repo / "tools" / "tos_evidence_scan_bench.py").write_text("# bench stand-in\n")
    if bench_ignored:
        (repo / ".gitignore").write_text("tools/tos_evidence_scan_bench.py\n")
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
        env=_GIT_ENV,
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    if origin_main:
        _git(repo, "update-ref", "refs/remotes/origin/main", base)
    head = base
    if not ancestor:
        # One commit past origin/main: present in the tree, not in the published history.
        (repo / "tools" / "unmerged.txt").write_text("not on origin/main\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "unmerged")
        head = _git(repo, "rev-parse", "HEAD")
    if detached:
        _git(repo, "checkout", "-q", "--detach", head)
    if dirty:
        (repo / "tools" / "scratch.txt").write_text("uncommitted\n")
    return repo


def _checkout(repo: Path, *, enforced: bool = True, bench: Path | None = None):
    """A :class:`CheckoutGuard` over ``repo``, with its baseline already read."""
    return driver.CheckoutGuard(
        driver_path=repo / "tools" / "tos_evidence_scan_measure.py",
        bench_path=(
            bench
            if bench is not None
            else repo / "tools" / "tos_evidence_scan_bench.py"
        ),
        enforced=enforced,
    ).with_baseline()


#: One clean detached checkout for the whole session, AND one guard over it with its
#: baseline already read. Both are built once: the ~50 tests that merely need a passing
#: guard should not each pay for a `git init`, nor for the five `git` subprocesses
#: `with_baseline()` costs — the shared repo never changes under them (review F10). A
#: test that MOVES the tree builds its own repo and its own guard under its ``tmp_path``.
_SHARED: dict[str, Any] = {}


@pytest.fixture(scope="session", autouse=True)
def _shared_clean_checkout(tmp_path_factory):
    repo = _make_checkout(tmp_path_factory.mktemp("clean-checkout"))
    _SHARED["repo"] = repo
    _SHARED["guard"] = _checkout(repo)
    yield
    _SHARED.clear()


def _clean_checkout(*, enforced: bool = True):
    """The session guard, or a non-enforcing view of it. No git runs here."""
    guard = _SHARED["guard"]
    return guard if enforced else dataclasses.replace(guard, enforced=False)


def _write_reference(path: Path, *, hot_rows: int = 20) -> None:
    """A miniature stand-in for a real ``evidence.sqlite3`` — the same shape the bench's own
    test uses, so the two suites agree on what a reference looks like."""
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(bench._ENTRIES_TABLE_SQL)
        rows = []
        seq = 1
        for kind, count, payload in (
            ("TIME_HEALTH_SNAPSHOT", hot_rows, "x" * 200),
            ("EVENT_CONSUMED", 5, "y" * 50),
            ("RECOVERY_BARRIER", 1, "z" * 10),
        ):
            for _ in range(count):
                rows.append(
                    (
                        seq,
                        None,
                        kind,
                        kind,
                        None,
                        payload,
                        hashlib.sha256(str(seq).encode()).hexdigest(),
                        hashlib.sha256(f"c{seq}".encode()).hexdigest(),
                        1,
                        seq,
                    )
                )
                seq += 1
        conn.executemany(
            "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
        )
        conn.commit()
    finally:
        conn.close()


def _stub_bench(
    tmp_path: Path, main_body: str, name: str = "tos_evidence_scan_bench.py"
):
    """A stand-in for the bench: importable (the driver loads it for `profile_kinds`) and
    doing whatever a test needs when run as a child.

    Needed because the real bench cannot be made to fail or to run long on a tiny fixture,
    and because `synthetic_absent` now refuses the "pre-create the file" trick the F1 test
    used to make `build` fail.
    """
    path = tmp_path / name
    path.write_text(
        "import sys, time, os, pathlib\n"
        "from dataclasses import dataclass\n"
        "\n"
        "class BenchRefused(RuntimeError):\n"
        "    pass\n"
        "\n"
        "@dataclass(frozen=True)\n"
        "class KindProfile:\n"
        "    kind: str\n"
        "    record_class: str\n"
        "    rows: int\n"
        "    payload_bytes: int\n"
        "\n"
        "def profile_kinds(reference):\n"
        "    return (KindProfile('TIME_HEALTH_SNAPSHOT', 'X', 20, 4000),)\n"
        "\n"
        "if __name__ == '__main__':\n" + main_body
    )
    return path


def _preflight(
    tmp_path: Path,
    reader,
    *,
    guard=None,
    days: int = 1,
    expect_gb=None,
    steps=None,
    checkout=None,
):
    reference = tmp_path / "evidence.sqlite3"
    if not reference.exists():
        _write_reference(reference)
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / f"synth-{days}d.sqlite3"

    def estimator():
        return driver.estimate_synthetic_size(
            reference,
            days=days,
            session_hours=7.0,
            reference_minutes=15.0,
            boot_once_max_rows=1,
            bench=bench,
        )

    planned = driver.plan_steps(
        names=steps or list(driver.STEP_NAMES),
        python=sys.executable,
        bench_path=_BENCH_PATH,
        reference=reference,
        synthetic=synthetic,
        out_dir=out_dir,
        days=days,
        repeats=1,
        session_hours=7.0,
        reference_minutes=15.0,
        boot_once_max_rows=1,
        batch_rows=1000,
    )
    return driver.preflight(
        run_id="testrun",
        guard=guard or _guard(),
        checkout=checkout if checkout is not None else _clean_checkout(),
        reader=reader,
        out_dir=out_dir,
        days=days,
        estimator=estimator,
        expect_bytes=None if expect_gb is None else int(expect_gb * _GB),
        disk_headroom_ratio=driver.DEFAULT_DISK_HEADROOM_RATIO,
        index_growth_ratio=driver.DEFAULT_INDEX_GROWTH_RATIO,
        steps=planned,
        argv=["run", "--days", str(days)],
        synthetic=synthetic,
    )


def _failed(record) -> dict[str, str]:
    return {c.check: c.measured for c in record.checks if not c.ok}


def _abort_records(out_dir: Path, name: str) -> list[Path]:
    """Every ``ABORTED`` artifact for one ``<step>-<days>d``, sorted by name.

    Deliberately NOT a plain ``out_dir / f"ABORTED-{name}.json"``: the fixed name is the
    defect plan §7.1.23 registered — the 270-day campaign's second stop overwrote the
    first one's record in place. The glob matches the run-id form only, so a regression
    back to the fixed name reads as "no record" here rather than passing quietly.
    """
    return sorted(out_dir.glob(f"ABORTED-{name}.*.json"))


def _summary_outcome(out_dir: Path) -> str:
    """The `outcome` of the single run summary in ``out_dir``."""
    (path,) = list(out_dir.glob("run-*.summary.json"))
    outcome: str = json.loads(path.read_text())["outcome"]
    return outcome


def _abort_record(out_dir: Path, name: str) -> dict[str, Any]:
    """The single abort record for ``<step>-<days>d``, parsed."""
    found = _abort_records(out_dir, name)
    assert len(found) == 1, f"expected one abort record for {name}, found {found}"
    record: dict[str, Any] = json.loads(found[0].read_text())
    return record


# ---------------------------------------------------------------------------------------
# Preflight refusals — one per threshold
# ---------------------------------------------------------------------------------------


def test_preflight_passes_on_a_healthy_host_and_records_the_context(
    tmp_path: Path,
) -> None:
    record = _preflight(
        tmp_path, _reader(tmp_path, available_gb=12.0, swap_free_gb=5.0)
    )

    assert record.verdict == "ok"
    assert record.refusal is None
    assert {c.check for c in record.checks} == {
        "checkout_detached_and_clean",
        "matches_earlier_steps",
        "outputs_outside_the_checkout",
        "mem_available",
        "swap_free",
        "competing_build",
        "competing_measurement",
        "disk_free",
        "artifacts_absent",
        "output_dir_unlocked",
    }
    # The global rule asks for the top-RSS census as part of the check; it is recorded, not
    # gated, and a run must be readable afterwards next to what else was resident.
    assert record.top_rss
    assert record.watchdog_enabled is True
    # The tree is recorded whatever the verdict (plan §2 A1-c): the 180-day run had to be
    # reconstructed from a reflog afterwards because the driver wrote none of this.
    assert record.checkout["detached"] is True
    assert record.checkout["clean"] is True
    assert record.checkout["ancestor_of_origin_main"] is True
    assert len(str(record.checkout["repo_commit"])) == 40
    assert record.checkout["repo_path"]
    assert len(str(record.checkout["bench_sha256"])) == 64
    assert record.checkout["allow_shared_checkout"] is False


def test_preflight_refuses_when_mem_available_is_below_the_start_floor(
    tmp_path: Path,
) -> None:
    record = _preflight(tmp_path, _reader(tmp_path, available_gb=5.5, swap_free_gb=5.0))

    assert record.verdict == "refused"
    assert "mem_available" in _failed(record)
    assert "5.50 GB" in _failed(record)["mem_available"]
    assert "mem_available" in (record.refusal or "")


def test_preflight_refuses_when_swap_free_is_below_the_start_floor(
    tmp_path: Path,
) -> None:
    """Plan §7.1.7 deviation 11-b: this clause of the global rule was absent from the lost
    driver, and swap — not MemAvailable — is what hit zero in the §7.1.5 incident."""
    record = _preflight(
        tmp_path, _reader(tmp_path, available_gb=12.0, swap_free_gb=1.5)
    )

    assert record.verdict == "refused"
    failed = _failed(record)
    assert "swap_free" in failed
    assert "1.50 GB" in failed["swap_free"]
    # Memory alone would have let this run start — which is exactly how the hole survived.
    assert "mem_available" not in failed


def test_preflight_refuses_when_a_gradle_build_is_running(tmp_path: Path) -> None:
    daemon = _fake_pid(0)
    reader = _reader(
        tmp_path,
        processes=[
            (
                daemon,
                "/usr/lib/jvm/java-21-openjdk-amd64/bin/java -Xmx2g "
                "org.gradle.launcher.daemon.bootstrap.GradleDaemon 9.6.1",
            )
        ],
    )
    record = _preflight(tmp_path, reader)

    assert record.verdict == "refused"
    failed = _failed(record)
    assert "competing_build" in failed
    assert str(daemon) in failed["competing_build"]


def test_preflight_refuses_when_another_measurement_driver_is_running(
    tmp_path: Path,
) -> None:
    second_driver = _fake_pid(0)
    reader = _reader(tmp_path, processes=[(second_driver, _A_SECOND_DRIVER)])
    record = _preflight(tmp_path, reader)

    assert record.verdict == "refused"
    assert str(second_driver) in _failed(record)["competing_measurement"]


def _case_dir(tmp_path: Path, name: str, reference: Path) -> Path:
    """A fresh preflight directory that reuses one already-built reference DB."""
    case = tmp_path / name
    case.mkdir()
    (case / "evidence.sqlite3").write_bytes(reference.read_bytes())
    return case


def test_a_fabricated_competitor_is_read_from_the_fabricated_proc_not_the_runners(
    tmp_path: Path,
) -> None:
    """#848, at the mechanism: an invented PID must never be looked up in the real /proc.

    The test above went red on tos-firewall run 36997189121 with
    ``assert 'ok' == 'refused'`` — nothing about the code had changed, the runner had
    simply allocated the hardcoded ``5150`` to a live pytest descendant, so the driver
    dropped the only injected line and the refusal evaporated. Waiting for that collision
    again is not a test, so it is CONSTRUCTED here out of PIDs this process can name with
    certainty: its own parent (an ancestor, the branch the issue's reproduction forced by
    faking ``os.getpid()``) and a live child of its own (a descendant, and under pytest a
    pytest descendant too).

    Each is checked both ways round. Pointed at the real ``/proc`` the fabrication is
    dropped and the verdict is ``ok``: that half is the old failure, on demand, and it
    fails if the seam ever stops being the thing that saves the test. Pointed at the fake
    tree the line was fabricated in, it is a competitor and the run is refused.
    """
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    real = driver.HostReader()

    def both_ways(label: str, pid: int) -> None:
        processes = [(pid, _A_SECOND_DRIVER)]
        leaky = _case_dir(tmp_path, f"real-proc-{pid}", reference)
        assert (
            _preflight(
                leaky, _reader(leaky, processes=processes, proc_root=Path("/proc"))
            ).verdict
            == "ok"
        ), f"the shape of #848: the real /proc answers for {label}"

        fake = _case_dir(tmp_path, f"fake-proc-{pid}", reference)
        record = _preflight(fake, _reader(fake, processes=processes))

        assert record.verdict == "refused", label
        assert str(pid) in _failed(record)["competing_measurement"], label

    # The ancestor half needs an ancestor to exist. It does not when pytest is itself pid
    # 1 — the container case this module's fabricated init guards against — and asserting
    # `os.getppid()` is in the chain would then fail for a reason that is not the bug
    # (review F2). The descendant half below covers the same mechanism either way.
    parent = real._parent_pid(os.getpid())
    if parent is not None and parent > 0:
        assert parent in real._self_pid_chain(), "precondition: a real ancestor"
        both_ways("this test process's own parent", parent)

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
    try:
        assert real._is_descendant_of(
            child.pid, frozenset({os.getpid()})
        ), "precondition: a real descendant"
        both_ways("a live child of this test process", child.pid)
    finally:
        child.kill()
        child.wait()


def test_the_drivers_own_pid_is_never_read_as_a_competing_driver(
    tmp_path: Path,
) -> None:
    """The branch #848 tripped over, pinned as intended instead of left ambiguous.

    A driver must not refuse to run because it can see itself, so ``scan`` drops a line
    whose PID is in its own chain. The fabricated driver here has NO parent, which is what
    makes this test able to fail: ``pid in mine`` is then the only rule that can drop the
    line, and deleting that clause from ``HostReader.scan`` turns this red. The first
    version of this test parented the self PID to the fabricated init, so the descendant
    rule dropped the same line and the test would have stayed green with the branch gone
    (review F1) — the "guard that admits what it names" shape.
    """
    the_driver = _fake_pid(0)
    reader = _reader(
        tmp_path, processes=[(the_driver, _A_SECOND_DRIVER)], self_pid=the_driver
    )

    assert reader._self_pid_chain() == frozenset({the_driver}), "no other rule applies"
    assert _preflight(tmp_path, reader).verdict == "ok"


def test_a_fabricated_process_table_does_not_blind_the_output_directory_lock(
    tmp_path: Path,
) -> None:
    """Review F3. A fake ``/proc`` must not quietly answer "owner gone" for a real lock.

    ``preflight`` reads the output-directory lock through the SAME ``proc_root`` as the
    process rules, and :func:`read_lock` treats a lock whose ``/proc/<pid>/cmdline`` it
    cannot read as stale. A fabricated tree holding only the fabricated processes would
    therefore leave ``output_dir_unlocked`` unable to refuse in every test that fabricates
    a process table — a check that cannot fail, which is the thing this module exists to
    catch.
    """
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / driver.LOCK_NAME).write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "argv0": _real_self_cmdline().split(" ")[0],
                "run_id": "somebody-elses-run",
            }
        )
    )

    record = _preflight(
        tmp_path, _reader(tmp_path, processes=[(_fake_pid(0), _A_SECOND_DRIVER)])
    )

    assert record.verdict == "refused"
    failed = _failed(record)
    # Both, so that neither check can stand in for the other.
    assert "output_dir_unlocked" in failed
    assert "competing_measurement" in failed


def test_no_fabricated_pid_can_belong_to_a_live_process() -> None:
    """``_fake_pid`` is unassignable, not merely unlikely.

    Every fabricated tree reads better for it, and one reader depends on it outright:
    :func:`_reader_that_reports_a_build_once` reads the REAL ``/proc`` so that the
    per-child sampling path stays exercised, and only an unassignable PID keeps its
    invented Gradle daemon invisible there.
    """
    ceiling = int(Path("/proc/sys/kernel/pid_max").read_text().strip())
    fabricated = (_FAKE_INIT_PID, *(_fake_pid(n) for n in range(8)))

    assert min(fabricated) >= ceiling, "a fabricated PID must be unassignable"
    for pid in fabricated:
        assert not Path(f"/proc/{pid}").exists(), pid


def test_a_process_merely_searching_for_the_marker_is_not_a_competing_build(
    tmp_path: Path,
) -> None:
    """Both directions, because a filter that is too wide is the same bug as no filter.

    The live 2026-09-30 preflight matched another session's
    ``bash -c "... pgrep -f 'GradleWrapperMain|...'"``. That line must NOT count; a real
    ``java ... GradleDaemon`` line must.
    """
    searching = _reader(
        tmp_path,
        processes=[
            (
                _fake_pid(0),
                "/bin/bash -c eval "
                "'if ! pgrep -f GradleWrapperMain; then echo idle; fi'",
            )
        ],
    )
    assert _preflight(tmp_path, searching).verdict == "ok"

    building = _reader(
        tmp_path,
        processes=[
            (
                _fake_pid(1),
                "/usr/lib/jvm/java-21/bin/java "
                "worker.org.gradle.process.internal.worker.GradleWorkerMain",
            )
        ],
    )
    assert _preflight(tmp_path, building).verdict == "refused"


def test_preflight_refuses_when_the_disk_cannot_hold_the_synthetic_file(
    tmp_path: Path,
) -> None:
    record = _preflight(tmp_path, _reader(tmp_path), expect_gb=10_000_000.0)

    assert record.verdict == "refused"
    failed = _failed(record)
    assert "disk_free" in failed
    assert "free" in failed["disk_free"]


def test_preflight_refuses_when_a_step_artifact_already_exists(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    (out_dir / "before-1d.json").write_text("[]")

    record = _preflight(tmp_path, _reader(tmp_path))

    assert record.verdict == "refused"
    assert "before-1d.json" in _failed(record)["artifacts_absent"]


def test_preflight_writes_its_artifact_even_when_it_refuses(tmp_path: Path) -> None:
    """A refusal that leaves nothing behind is indistinguishable from never having checked —
    plan §7.1.2's complaint about a measurement whose guards existed only in session memory.
    """
    record = _preflight(tmp_path, _reader(tmp_path, available_gb=1.0, swap_free_gb=0.1))

    assert record.verdict == "refused"
    payload = json.loads((tmp_path / "out" / "preflight.json").read_text())
    assert payload["verdict"] == "refused"
    assert payload["refusal"]
    checks = {c["check"]: c for c in payload["checks"]}
    assert checks["mem_available"]["ok"] is False
    assert checks["swap_free"]["ok"] is False
    # Every refusal names the failing check AND the measured value.
    assert "1.00 GB" in checks["mem_available"]["measured"]
    assert "0.10 GB" in checks["swap_free"]["measured"]
    # The append-only history keeps an earlier refusal when a later run overwrites the .json.
    assert (tmp_path / "out" / "preflight.jsonl").read_text().count("\n") == 1


def test_meminfo_without_the_fields_the_guards_need_is_refused(tmp_path: Path) -> None:
    """Fail closed: a preflight that cannot read swap has not checked swap."""
    path = tmp_path / "partial-meminfo"
    path.write_text("MemTotal: 22016000 kB\nMemAvailable: 12000000 kB\n")
    reader = driver.HostReader(meminfo_path=path, pgrep_argv=("/bin/true",))

    with pytest.raises(driver.MeasureRefused, match="SwapFree"):
        reader.meminfo()


# ---------------------------------------------------------------------------------------
# Guard configuration
# ---------------------------------------------------------------------------------------


def test_an_abort_floor_above_the_start_floor_is_refused() -> None:
    """A guard must not admit what it names. With the abort floor above the start floor the
    watchdog would kill a run the preflight had just approved."""
    with pytest.raises(driver.MeasureRefused, match="abort-available-gb"):
        _guard(min_available_gb=4.0, abort_available_gb=6.0)

    with pytest.raises(driver.MeasureRefused, match="abort-swap-free-gb"):
        _guard(min_swap_free_gb=1.0, abort_swap_free_gb=2.0)


def test_the_defaults_are_the_operator_rule_not_a_local_invention() -> None:
    """The global rule (``~/.claude/CLAUDE.md``, 로컬 빌드 동시 실행 제한) is 6 GB available
    and 2 GB swap free. If a future edit relaxes either default, this fails."""
    assert driver.DEFAULT_MIN_AVAILABLE_GB == 6.0
    assert driver.DEFAULT_MIN_SWAP_FREE_GB == 2.0
    assert driver.DEFAULT_ABORT_AVAILABLE_GB == 4.0
    assert driver.DEFAULT_ABORT_SWAP_FREE_GB == 1.0
    guard = _guard()
    assert guard.abort_available_bytes < guard.min_available_bytes
    assert guard.abort_swap_free_bytes < guard.min_swap_free_bytes


# ---------------------------------------------------------------------------------------
# Size estimate — the drift guard on the duplicated scaling rule
# ---------------------------------------------------------------------------------------


def test_the_size_estimate_predicts_the_real_row_count_exactly(tmp_path: Path) -> None:
    """The driver reapplies the bench's replication rule to size the disk check. This builds
    a real synthetic file and compares, so a change to either copy shows up here instead of
    as a disk check that silently sizes the wrong thing."""
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    estimate = driver.estimate_synthetic_size(
        reference,
        days=2,
        session_hours=7.0,
        reference_minutes=15.0,
        boot_once_max_rows=1,
        bench=bench,
    )

    report = bench.build_synthetic(
        reference,
        tmp_path / "synth.sqlite3",
        days=2,
        session_hours=7.0,
        reference_minutes=15.0,
        boot_once_max_rows=1,
        batch_rows=500,
    )

    assert estimate.predicted_rows == report.rows
    assert estimate.recurring_repeats == report.recurring_repeats
    assert estimate.boot_repeats == report.boot_repeats
    # Bytes are an estimate, not an identity: the prediction scales payload by the
    # reference's own file/payload ratio. It must be the right order and on the safe side.
    assert estimate.predicted_file_bytes >= report.file_bytes * 0.5


def test_the_estimate_refuses_a_reference_the_bench_itself_refuses(
    tmp_path: Path,
) -> None:
    drifted = tmp_path / "drifted.sqlite3"
    conn = sqlite3.connect(str(drifted))
    conn.execute("CREATE TABLE entries (seq INTEGER PRIMARY KEY, kind TEXT)")
    conn.commit()
    conn.close()

    with pytest.raises(driver.MeasureRefused, match="reference unusable"):
        driver.estimate_synthetic_size(
            drifted,
            days=1,
            session_hours=7.0,
            reference_minutes=15.0,
            boot_once_max_rows=1,
            bench=bench,
        )


# ---------------------------------------------------------------------------------------
# Watchdog — it must actually kill a live child
# ---------------------------------------------------------------------------------------


def _sleep_step(tmp_path: Path, seconds: int = 30, *, name: str = "before"):
    # No return annotation: `driver` is loaded by path, so `driver.Step` is not a name
    # mypy can resolve — the same reason the bench's own suite leaves these unannotated.
    return driver.Step(
        name=name,
        argv=(sys.executable, "-c", f"import time; time.sleep({seconds})"),
        stdout_path=tmp_path / f"{name}.out",
        stderr_path=tmp_path / f"{name}.err",
    )


def _series(reader, samples: list[tuple[float, float]]):
    """A sampler that walks a scripted MemAvailable/SwapFree series and then holds the last
    value, so a test states exactly when the host goes bad."""
    calls = {"n": 0}

    def take(pid: int):
        index = min(calls["n"], len(samples) - 1)
        calls["n"] += 1
        available_gb, swap_gb = samples[index]
        return driver.HostSample(
            at_kst="2026-09-30T12:00:00.000+09:00",
            mem_available_bytes=int(available_gb * _GB),
            swap_free_bytes=int(swap_gb * _GB),
            swap_total_bytes=8 * _GB,
            child_peak_rss_bytes=reader.child_peak_rss_bytes(pid),
            child_io=reader.child_io(pid),
        )

    return take


def _healthy(reader=None):
    """A sampler for a host that stays fine, so a test about resource capture is not also a
    test of whatever else happens to be running on the machine."""
    return _series(reader or driver.HostReader(), [(12.0, 5.0)])


def test_the_watchdog_kills_the_child_when_memory_falls_and_writes_the_abort_artifact(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    step = _sleep_step(tmp_path, seconds=120)
    sampler = _series(driver.HostReader(), [(12.0, 5.0), (12.0, 5.0), (3.0, 5.0)])

    with pytest.raises(driver.MeasureAborted, match="MemAvailable 3.00 GB"):
        driver.run_step(
            step,
            guard=_guard(),
            checkout=_clean_checkout(),
            reader=driver.HostReader(),
            run_id="abortrun",
            days=90,
            out_dir=out_dir,
            log=lambda _m: None,
            sampler=sampler,
        )

    record = _abort_record(out_dir, "before-90d")
    assert record["check"] == "mem_available"
    assert "3.00 GB" in record["reason"]
    assert record["signal_sent"] == "SIGTERM"
    assert record["returncode"] != 0
    assert record["last_samples"], "the abort record must carry the samples it acted on"
    # Plan §7.1.2: the aborted 365-day pass left NO numbers (before-365d.time was 0 bytes),
    # so every figure cited for it had to be demoted to a hypothesis. A stopped step now
    # reports how far it got.
    partial = record["partial_resource"]
    assert partial["max_rss_bytes"] > 0
    assert partial["user_seconds"] >= 0.0
    assert "fs_inputs_blocks" in partial and "proc_io" in partial
    assert record["elapsed_seconds"] < 120, "the 120 s child did not actually die"
    # The series is on disk too, so a later plan section cites an artifact, not a session.
    lines = (out_dir / "watchdog.jsonl").read_text().strip().splitlines()
    assert len(lines) == len(record["last_samples"])
    assert json.loads(lines[0])["step"] == "before"


def test_the_watchdog_aborts_on_low_swap_alone(tmp_path: Path) -> None:
    """Deviation 11-b again, in-run this time: plenty of MemAvailable, no swap left."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    sampler = _series(driver.HostReader(), [(12.0, 5.0), (12.0, 0.2)])

    with pytest.raises(driver.MeasureAborted, match="SwapFree 0.20 GB"):
        driver.run_step(
            _sleep_step(tmp_path, seconds=120),
            guard=_guard(),
            checkout=_clean_checkout(),
            reader=driver.HostReader(),
            run_id="swaprun",
            days=30,
            out_dir=out_dir,
            log=lambda _m: None,
            sampler=sampler,
        )

    assert _abort_record(out_dir, "before-30d")["check"] == "swap_free"


def test_the_watchdog_aborts_when_a_competing_build_appears_mid_run(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    calls = {"n": 0}

    def sampler(pid: int):
        calls["n"] += 1
        competing = (
            ()
            if calls["n"] < 3
            else (
                driver.CompetingProcess(
                    pid=999, pattern="GradleDaemon", args="java GradleDaemon"
                ),
            )
        )
        return driver.HostSample(
            at_kst="2026-09-30T12:00:00.000+09:00",
            mem_available_bytes=12 * _GB,
            swap_free_bytes=5 * _GB,
            swap_total_bytes=8 * _GB,
            competing=competing,
        )

    with pytest.raises(driver.MeasureAborted, match="competing process appeared"):
        driver.run_step(
            _sleep_step(tmp_path, seconds=120),
            guard=_guard(),
            checkout=_clean_checkout(),
            reader=driver.HostReader(),
            run_id="cotenant",
            days=30,
            out_dir=out_dir,
            log=lambda _m: None,
            sampler=sampler,
        )

    assert _abort_record(out_dir, "before-30d")["check"] == "competing_build"


def test_a_child_that_ignores_sigterm_is_escalated_to_sigkill(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    ready = tmp_path / "handler-installed"
    step = driver.Step(
        name="build",
        argv=(
            sys.executable,
            "-c",
            "import pathlib, signal, time\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            f"pathlib.Path({str(ready)!r}).write_text('x')\n"
            "time.sleep(120)\n",
        ),
        stdout_path=tmp_path / "b.out",
        stderr_path=tmp_path / "b.err",
    )

    def sampler(pid: int):
        # Healthy until the child says its SIGTERM handler is installed. Without this the
        # abort can land during interpreter startup, the default disposition kills the
        # child, and the test would pass while proving nothing about escalation.
        starved = ready.exists()
        return driver.HostSample(
            at_kst="2026-09-30T12:00:00.000+09:00",
            mem_available_bytes=int((1.0 if starved else 12.0) * _GB),
            swap_free_bytes=5 * _GB,
            swap_total_bytes=8 * _GB,
        )

    with pytest.raises(driver.MeasureAborted):
        driver.run_step(
            step,
            guard=_guard(term_grace_s=0.3),
            checkout=_clean_checkout(),
            reader=driver.HostReader(),
            run_id="stubborn",
            days=30,
            out_dir=out_dir,
            log=lambda _m: None,
            sampler=sampler,
        )

    record = _abort_record(out_dir, "build-30d")
    assert record["escalated_to_sigkill"] is True
    assert record["returncode"] == -9


def test_the_watchdog_can_be_turned_off_but_the_run_says_so(tmp_path: Path) -> None:
    """``--no-watchdog`` exists; it must not be quiet about existing."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    guard = _guard(watchdog_enabled=False)
    sampler = _series(driver.HostReader(), [(0.1, 0.0)])

    result = driver.run_step(
        driver.Step(
            name="build",
            argv=(sys.executable, "-c", "pass"),
            stdout_path=tmp_path / "n.out",
            stderr_path=tmp_path / "n.err",
        ),
        guard=guard,
        checkout=_clean_checkout(),
        reader=driver.HostReader(),
        run_id="nowatch",
        days=1,
        out_dir=out_dir,
        log=lambda _m: None,
        sampler=sampler,
    )

    assert result.returncode == 0
    assert not _abort_records(out_dir, "build-1d")
    # The samples are still recorded, flagged as unguarded.
    row = json.loads((out_dir / "watchdog.jsonl").read_text().strip().splitlines()[0])
    assert row["watchdog_enabled"] is False


# ---------------------------------------------------------------------------------------
# Resource capture
# ---------------------------------------------------------------------------------------


def test_a_step_records_wall_clock_max_rss_and_the_children_io_counters(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    payload = tmp_path / "payload.bin"
    step = driver.Step(
        name="build",
        argv=(
            sys.executable,
            "-c",
            "import time\n"
            f"open({str(payload)!r}, 'wb').write(b'x' * (8 * 1024 * 1024))\n"
            "time.sleep(0.2)\n",
        ),
        stdout_path=tmp_path / "r.out",
        stderr_path=tmp_path / "r.err",
    )

    result = driver.run_step(
        step,
        guard=_guard(),
        checkout=_clean_checkout(),
        reader=driver.HostReader(),
        run_id="resource",
        days=1,
        out_dir=out_dir,
        log=lambda _m: None,
        sampler=_healthy(),
    )

    assert result.returncode == 0
    assert result.wall_seconds >= 0.2
    assert result.max_rss_bytes > 0
    assert result.user_seconds >= 0.0
    assert result.samples_taken >= 1

    # The GNU `time -v` field names the plan already cites must still be greppable.
    time_text = (out_dir / "build-1d.time").read_text()
    assert "Maximum resident set size (kbytes):" in time_text
    assert "File system inputs:" in time_text
    assert "Elapsed (wall clock) time" in time_text

    record = json.loads((out_dir / "build-1d.resource.json").read_text())
    assert record["fs_outputs_blocks"] >= 0
    assert "proc_io" in record
    if record["proc_io"]:
        # The physical/logical distinction plan §7.1.2 recorded as missing.
        assert "rchar" in record["proc_io"]
        assert "write_bytes" in record["proc_io"]
        assert record["proc_io_sample_age_seconds"] is not None


def test_a_failing_child_is_reported_with_its_exit_status(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = driver.run_step(
        driver.Step(
            name="build",
            argv=(sys.executable, "-c", "raise SystemExit(3)"),
            stdout_path=tmp_path / "f.out",
            stderr_path=tmp_path / "f.err",
        ),
        guard=_guard(),
        checkout=_clean_checkout(),
        reader=driver.HostReader(),
        run_id="failing",
        days=1,
        out_dir=out_dir,
        log=lambda _m: None,
        sampler=_healthy(),
    )

    assert result.returncode == 3
    assert "Exit status: 3" in (out_dir / "build-1d.time").read_text()


# ---------------------------------------------------------------------------------------
# Step planning and the end-to-end path
# ---------------------------------------------------------------------------------------


def test_the_planned_steps_are_the_bench_commands_in_order(tmp_path: Path) -> None:
    steps = driver.plan_steps(
        names=["after", "build", "before"],  # order of the argument must not matter
        python="/usr/bin/python3",
        bench_path=_BENCH_PATH,
        reference=tmp_path / "ref.sqlite3",
        synthetic=tmp_path / "s.sqlite3",
        out_dir=tmp_path,
        days=365,
        repeats=3,
        session_hours=7.0,
        reference_minutes=15.0,
        boot_once_max_rows=1,
        batch_rows=10000,
    )

    assert [s.name for s in steps] == ["build", "before", "after"]
    assert "build" in steps[0].argv and "--days" in steps[0].argv
    assert steps[0].stdout_path.name == "build-365d.json"
    # Only the `after` step creates the index; the bench has no separate index subcommand.
    assert "--create-index" not in steps[1].argv
    assert "--create-index" in steps[2].argv
    assert str(tmp_path / "after-365d.json") in steps[2].argv


def test_an_unknown_step_name_is_refused(tmp_path: Path) -> None:
    with pytest.raises(driver.MeasureRefused, match="unknown step"):
        driver.plan_steps(
            names=["build", "index"],
            python="/usr/bin/python3",
            bench_path=_BENCH_PATH,
            reference=tmp_path / "r",
            synthetic=tmp_path / "s",
            out_dir=tmp_path,
            days=1,
            repeats=1,
            session_hours=7.0,
            reference_minutes=15.0,
            boot_once_max_rows=1,
            batch_rows=10,
        )


def test_the_whole_driver_runs_build_before_and_after_end_to_end(
    tmp_path: Path,
) -> None:
    """A real, tiny measurement: three real bench children, the real preflight (against a
    fake host reader is not possible through the CLI, so the thresholds are lowered to what
    any host satisfies), and every artifact the plan will cite."""
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"

    rc = driver.main(
        [
            "run",
            "--reference",
            str(reference),
            "--synthetic",
            str(synthetic),
            "--out-dir",
            str(out_dir),
            "--days",
            "1",
            "--repeats",
            "1",
            "--batch-rows",
            "200",
            "--min-available-gb",
            "0",
            "--min-swap-free-gb",
            "0",
            "--abort-available-gb",
            "0",
            "--abort-swap-free-gb",
            "0",
            "--watch-interval-s",
            "0.05",
            "--poll-interval-s",
            "0.01",
            "--allow-shared-checkout",
            "--bench",
            str(_BENCH_PATH),
        ],
        reader=_reader(tmp_path),
    )

    assert rc == 0
    for name in ("build-1d.json", "before-1d.json", "after-1d.json"):
        assert (out_dir / name).is_file(), name
    for name in ("build", "before", "after"):
        assert (out_dir / f"{name}-1d.time").is_file()
        assert (out_dir / f"{name}-1d.resource.json").is_file()
    assert json.loads((out_dir / "preflight.json").read_text())["verdict"] == "ok"
    assert (out_dir / "watchdog.jsonl").read_text().strip()
    assert (out_dir / "measure-1d.log").read_text().count("##########") == 3

    build = json.loads((out_dir / "build-1d.json").read_text())
    assert build["days"] == 1 and build["rows"] > 0

    # The `after` pass really used the index — that is the whole point of the pair.
    after = json.loads((out_dir / "after-1d.json").read_text())
    plans = " ".join(line for m in after for line in m["plan"])
    assert "entries_kind_seq" in plans
    before = json.loads((out_dir / "before-1d.json").read_text())
    assert "entries_kind_seq" not in " ".join(
        line for m in before for line in m["plan"]
    )

    # Default is to remove the synthetic file so peak disk stays one file.
    assert not synthetic.exists()


def test_a_synthetic_file_the_run_did_not_create_is_never_deleted(
    tmp_path: Path,
) -> None:
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    synthetic.parent.mkdir(parents=True)

    # Build it first — `--steps build` leaves the pair unmeasured, so the driver keeps
    # the file on its own and no --keep-synthetic workaround is needed (review #853
    # finding 2) — then measure against it in a second invocation.
    assert (
        driver.main(
            [
                "run",
                "--reference",
                str(reference),
                "--synthetic",
                str(synthetic),
                "--out-dir",
                str(out_dir),
                "--days",
                "1",
                "--steps",
                "build",
                "--batch-rows",
                "200",
                "--min-available-gb",
                "0",
                "--min-swap-free-gb",
                "0",
                "--abort-available-gb",
                "0",
                "--abort-swap-free-gb",
                "0",
                "--watch-interval-s",
                "0.05",
                "--poll-interval-s",
                "0.01",
                "--allow-shared-checkout",
                "--bench",
                str(_BENCH_PATH),
            ],
            reader=_reader(tmp_path),
        )
        == 0
    )
    assert synthetic.exists()

    assert (
        driver.main(
            [
                "run",
                "--reference",
                str(reference),
                "--synthetic",
                str(synthetic),
                "--out-dir",
                str(out_dir),
                "--days",
                "1",
                "--steps",
                "before",
                "--repeats",
                "1",
                "--min-available-gb",
                "0",
                "--min-swap-free-gb",
                "0",
                "--abort-available-gb",
                "0",
                "--abort-swap-free-gb",
                "0",
                "--watch-interval-s",
                "0.05",
                "--poll-interval-s",
                "0.01",
                "--allow-shared-checkout",
                "--bench",
                str(_BENCH_PATH),
            ],
            reader=_reader(tmp_path),
        )
        == 0
    )
    assert synthetic.exists(), "a pre-existing synthetic file must survive the run"


def test_the_cli_reports_a_refusal_as_exit_one_and_starts_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"

    rc = driver.main(
        [
            "run",
            "--reference",
            str(reference),
            "--synthetic",
            str(synthetic),
            "--out-dir",
            str(out_dir),
            "--days",
            "1",
            "--expect-gb",
            "10000000",
            "--min-available-gb",
            "0",
            "--min-swap-free-gb",
            "0",
            "--abort-available-gb",
            "0",
            "--abort-swap-free-gb",
            "0",
            "--allow-shared-checkout",
            "--bench",
            str(_BENCH_PATH),
        ],
        reader=_reader(tmp_path),
    )

    assert rc == 1
    assert "disk_free" in capsys.readouterr().err
    assert not synthetic.exists()
    assert not (out_dir / "build-1d.json").exists()


def _import_roots(path: Path) -> set[str]:
    import ast

    tree = ast.parse(path.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_driver_is_stdlib_only_and_reaches_into_no_tos_package() -> None:
    """Two properties in one AST pass, both enforced elsewhere but cheap to keep local.

    ``tos``/``tos_runtime``: the import firewall's reverse rule (TOS-FW-R) forbids anything
    outside ``tos/`` from importing them, and ``tools/tos_firewall_check.py`` runs in CI.
    Stdlib-only: a guard that protects a host must not be defeatable by a dependency missing
    on that host.
    """
    roots = _import_roots(_MODULE_PATH)
    assert "tos" not in roots and "tos_runtime" not in roots
    assert roots <= set(sys.stdlib_module_names), roots - set(sys.stdlib_module_names)


def test_the_measure_pattern_does_not_match_this_test_process_itself() -> None:
    """Self-exclusion by PID chain, exercised against the real ``pgrep`` on the real host:
    this pytest process's command line contains the driver's module name (the test file is
    named after it), and it must not count as a competing measurement."""
    reader = driver.HostReader()
    found = reader.competing_processes(driver.COMPETING_MEASURE_PATTERN)
    assert os.getpid() not in {p.pid for p in found}


def test_an_aborted_run_keeps_the_synthetic_file_it_built(tmp_path: Path) -> None:
    """A watchdog abort must not throw the build away.

    The guard fires because the host is short of MEMORY; deleting a multi-gigabyte
    synthetic file does nothing for that and costs the operator the whole build (366 s at
    365 days, plan §7.1.2). The cheapest recovery is to rerun the remaining steps against
    the file that already exists, so the run keeps it and says where it is.
    """
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"

    # The `before` step's stdout file is created by posix_spawn the instant the child
    # starts, so gating the daemon on it lands the abort in `before`, after `build` has
    # finished and written the synthetic: the build really is complete and really is worth
    # preserving whenever this fires.
    reader = _reader_that_reports_a_build_once(tmp_path, gate=out_dir / "before-1d.out")

    rc = driver.main(
        [
            "run",
            "--reference",
            str(reference),
            "--synthetic",
            str(synthetic),
            "--out-dir",
            str(out_dir),
            "--days",
            "1",
            "--repeats",
            "1",
            "--batch-rows",
            "200",
            "--min-available-gb",
            "0",
            "--min-swap-free-gb",
            "0",
            "--abort-available-gb",
            "0",
            "--abort-swap-free-gb",
            "0",
            "--watch-interval-s",
            "0.05",
            "--poll-interval-s",
            "0.01",
            "--allow-shared-checkout",
            "--bench",
            str(_BENCH_PATH),
        ],
        reader=reader,
    )

    assert rc == 1
    # Whichever step the competing build lands in, the abort is recorded.
    (aborted,) = _abort_records(out_dir, "before-1d")
    assert aborted.name.startswith(
        "ABORTED-before-1d."
    ), "an abort must never be silent"
    record = json.loads(aborted.read_text())
    assert record["check"] == "competing_build"
    assert synthetic.exists(), "the aborted run deleted the build it had just paid for"

    # This reader keeps the REAL `/proc`, so the per-child sampling really ran (review
    # F4). Point it at a fabricated tree instead and both of these go empty — the live
    # bench child is simply not in it — which would retire the whole per-child read from
    # the only tests that exercise it against a real process.
    assert record["partial_resource"][
        "proc_io"
    ], "the child's /proc/<pid>/io never read"
    watchdog = [
        json.loads(line)
        for line in (out_dir / "watchdog.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert any(
        row.get("child_peak_rss_bytes") for row in watchdog
    ), "the child's VmHWM was never sampled"
    log = (out_dir / "measure-1d.log").read_text()
    assert "KEPT synthetic" in log
    assert "--steps before,after" in log, "the log must say how to resume"


def test_the_synthetic_disposition_says_the_right_thing_for_each_outcome(
    tmp_path: Path,
) -> None:
    """The three branches of the keep/delete decision, including the one the CLI test
    cannot reach deterministically (an abort DURING the build, which leaves a partial
    file that must not be advertised as resumable)."""
    path = tmp_path / "synth-365d.sqlite3"

    done = driver.decide_synthetic_disposition(
        path,
        remaining=[],
        size_bytes=53_230_000_000,
        created_by_this_run=True,
        before_measured=True,
        after_measured=True,
    )
    assert done.action == "delete"
    assert "53.23 GB" in done.message, "the one message that used to carry no size"

    partial = driver.decide_synthetic_disposition(
        path,
        remaining=["build", "before", "after"],
        size_bytes=7_000_000_000,
        created_by_this_run=True,
        before_measured=False,
        after_measured=False,
    )
    assert partial.action == "keep-partial"
    assert "INCOMPLETE" in partial.message
    assert "--steps" not in partial.message, "a partial file is not resumable"

    resumable = driver.decide_synthetic_disposition(
        path,
        remaining=["before", "after"],
        size_bytes=53_230_000_000,
        created_by_this_run=True,
        before_measured=False,
        after_measured=False,
    )
    assert resumable.action == "keep-resumable"
    assert "--steps before,after" in resumable.message
    assert "53.23 GB" in resumable.message

    # The two measured flags have no defaults: a caller that forgets them must not get a
    # decision that silently falls toward deletion.
    with pytest.raises(TypeError):
        driver.decide_synthetic_disposition(
            path, remaining=[], size_bytes=1, created_by_this_run=True
        )


# ---------------------------------------------------------------------------------------
# Review #826 findings — each with the scenario the reviewer named
# ---------------------------------------------------------------------------------------


def _cli(
    tmp_path: Path,
    *extra: str,
    reference: Path | None = None,
    out_dir: Path | None = None,
    synthetic: Path | None = None,
    reader=None,
):
    """Run the CLI with the floors lowered to what any host satisfies, so a test decides
    the outcome rather than whatever else is running on the machine."""
    reference = reference or (tmp_path / "evidence.sqlite3")
    if not reference.exists():
        _write_reference(reference)
    out_dir = out_dir or (tmp_path / "out")
    synthetic = synthetic or (tmp_path / "synth" / "synth-1d.sqlite3")
    return driver.main(
        [
            "run",
            "--reference",
            str(reference),
            "--synthetic",
            str(synthetic),
            "--out-dir",
            str(out_dir),
            "--days",
            "1",
            "--repeats",
            "1",
            "--batch-rows",
            "200",
            "--min-available-gb",
            "0",
            "--min-swap-free-gb",
            "0",
            "--abort-available-gb",
            "0",
            "--abort-swap-free-gb",
            "0",
            "--watch-interval-s",
            "0.05",
            "--poll-interval-s",
            "0.01",
            "--allow-shared-checkout",
            "--bench",
            str(_BENCH_PATH),
            *extra,
        ],
        reader=reader if reader is not None else _reader(tmp_path),
    )


def test_f1_a_failed_step_stops_the_run_keeps_the_file_and_exits_non_zero(
    tmp_path: Path,
) -> None:
    """F1. The first revision only looked at exceptions, so a child that merely exited
    non-zero counted as a completed step: the later steps ran against a DB that was never
    built, all three names landed in `completed`, the file was deleted and the process
    returned 0."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    failing = _stub_bench(
        tmp_path,
        "    sys.stderr.write('bench: refusing\\n')\n    raise SystemExit(1)\n",
    )

    rc = _cli(tmp_path, "--bench", str(failing), out_dir=out_dir, synthetic=synthetic)

    assert rc == 1
    # The failed step's own files are moved aside, reason and all.
    err = list(out_dir.glob("build-1d.*.aborted.err"))
    assert err and "refusing" in err[0].read_text()
    # The later steps must not have run.
    assert not (out_dir / "before-1d.json").exists()
    assert not (out_dir / "after-1d.json").exists()
    assert not (out_dir / "before-1d.resource.json").exists()
    assert "rc=1" in (out_dir / "measure-1d.log").read_text()


def test_f1_a_failed_step_keeps_a_synthetic_this_run_did_create(tmp_path: Path) -> None:
    """The other half of F1: when the failing step is not `build`, the build's own output
    must survive rather than be deleted as if the pair had finished."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    # Point `--repeats 0` at the measure steps: the bench refuses (`--repeats must be >= 1`)
    # so `before` exits 1 after `build` has succeeded.
    rc = _cli(tmp_path, "--repeats", "0", out_dir=out_dir, synthetic=synthetic)

    assert rc == 1
    assert (out_dir / "build-1d.json").is_file(), "the build really did run"
    assert not (out_dir / "after-1d.json").exists(), "after must not run"
    assert synthetic.exists(), "a failed run must not delete the build it paid for"
    assert "KEPT synthetic" in (out_dir / "measure-1d.log").read_text()


def test_f2_a_host_read_failure_is_retried_once_then_aborts_with_an_artifact(
    tmp_path: Path,
) -> None:
    """F2. A transient `pgrep` exit 2/3 raised MeasureRefused out of the sampler, which the
    BaseException path turned into a silent kill: child dead, no ABORTED artifact, and a
    message whose exception type says 'Nothing was started'."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    calls = {"n": 0}

    def sampler(pid: int):
        calls["n"] += 1
        if calls["n"] == 1:
            return driver.HostSample(
                at_kst="2026-10-01T12:00:00.000+09:00",
                mem_available_bytes=12 * _GB,
                swap_free_bytes=5 * _GB,
                swap_total_bytes=8 * _GB,
            )
        raise driver.MeasureRefused("pgrep exited 2: resource temporarily unavailable")

    with pytest.raises(driver.MeasureAborted, match="could not be read"):
        driver.run_step(
            _sleep_step(tmp_path, seconds=120),
            guard=_guard(host_read_retries=1),
            checkout=_clean_checkout(),
            reader=driver.HostReader(),
            run_id="hostread",
            days=90,
            out_dir=out_dir,
            log=lambda _m: None,
            sampler=sampler,
        )

    record = _abort_record(out_dir, "before-90d")
    assert record["check"] == "host_read"
    assert "pgrep exited 2" in record["reason"]
    # Retried once: the run survived the first failure and stopped on the second.
    assert calls["n"] == 3
    rows = [
        json.loads(line)
        for line in (out_dir / "watchdog.jsonl").read_text().splitlines()
    ]
    assert any(
        "host_read_error" in row for row in rows
    ), "the failure itself is recorded"


def test_f2_an_unexpected_driver_error_still_writes_an_abort_artifact(
    tmp_path: Path,
) -> None:
    """The general case of F2: any exception out of the loop must leave the same evidence,
    not the zero-artifact stop §7.1.2 had to demote to a hypothesis."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    def sampler(pid: int):
        raise OSError(28, "No space left on device")

    with pytest.raises(OSError):
        driver.run_step(
            _sleep_step(tmp_path, seconds=120),
            guard=_guard(),
            checkout=_clean_checkout(),
            reader=driver.HostReader(),
            run_id="enospc",
            days=365,
            out_dir=out_dir,
            log=lambda _m: None,
            sampler=sampler,
        )

    record = _abort_record(out_dir, "before-365d")
    assert record["check"] == "driver_error"
    assert "No space left on device" in record["reason"]


def test_f3_editing_or_testing_this_tool_is_not_a_competing_measurement(
    tmp_path: Path,
) -> None:
    """F3. The pattern was a bare filename substring, so `pytest tests/tools/
    test_tos_evidence_scan_measure.py`, `mypy tools/…`, `vim tools/…` and `git show
    main:tools/…` all counted — editing this tool during a multi-hour run killed the run.
    """
    innocent = [
        (_fake_pid(i), args)
        for i, args in enumerate(
            (
                "/usr/bin/python -m pytest tests/tools/test_tos_evidence_scan_measure.py -q",
                "/usr/bin/mypy tools/tos_evidence_scan_measure.py --ignore-missing-imports",
                "vim tools/tos_evidence_scan_measure.py",
                "git show main:tools/tos_evidence_scan_bench.py",
                "/usr/bin/black tools/tos_evidence_scan_measure.py",
            )
        )
    ]
    assert _preflight(tmp_path, _reader(tmp_path, processes=innocent)).verdict == "ok"


def test_f3_a_real_second_driver_invocation_is_still_caught(tmp_path: Path) -> None:
    """The other direction — the tightened pattern must not have tightened the guard away."""
    for i, args in enumerate(
        (
            "/usr/bin/python tools/tos_evidence_scan_measure.py run --days 365",
            "/usr/bin/python tools/tos_evidence_scan_bench.py build --days 90",
            "/usr/bin/python /opt/x/tos_evidence_scan_bench.py measure --db /tmp/s",
        )
    ):
        record = _preflight(
            tmp_path, _reader(tmp_path, processes=[(_fake_pid(i), args)])
        )
        assert record.verdict == "refused", args
        assert "competing_measurement" in _failed(record), args

    # `profile` reads a 5 MB file and `preflight` starts no child: neither competes, and
    # killing a six-hour run for one of them is a real loss (round-2 F2).
    for i, harmless in enumerate(
        (
            "/usr/bin/python tools/tos_evidence_scan_bench.py profile --reference /x",
            "/usr/bin/python tools/tos_evidence_scan_measure.py preflight --days 30",
        )
    ):
        assert (
            _preflight(
                tmp_path, _reader(tmp_path, processes=[(_fake_pid(3 + i), harmless)])
            ).verdict
            == "ok"
        ), harmless


def test_f3_the_pattern_matches_a_real_invocation_through_the_real_pgrep(
    tmp_path: Path,
) -> None:
    """The regex is evaluated by `pgrep`, not by Python, so both directions are checked
    against live processes and the real binary. `_pgrep` is used rather than `scan` because
    these children ARE descendants of pytest, which `scan` now deliberately excludes."""
    script = tmp_path / "tos_evidence_scan_measure.py"
    script.write_text("import time\ntime.sleep(20)\n")
    running = subprocess.Popen([sys.executable, str(script), "run", "--days", "365"])
    decoy = subprocess.Popen([sys.executable, str(script), "-q"])
    profiling = subprocess.Popen(
        [sys.executable, str(script), "profile", "--reference", "/x"]
    )
    try:
        time.sleep(1.0)
        found = {
            pid
            for pid, _ in driver.HostReader()._pgrep(driver.COMPETING_MEASURE_PATTERN)
        }
        assert running.pid in found, "a real invocation must be seen"
        assert decoy.pid not in found, "a bare mention of the file must not be"
        assert profiling.pid not in found, "a read-only profile is not a competitor"
    finally:
        for proc in (running, decoy, profiling):
            proc.kill()
            proc.wait()


def test_f2_the_test_suites_own_bench_children_cannot_kill_a_live_run(
    tmp_path: Path,
) -> None:
    """F2, the integration half. The suite spawns real `bench build`/`measure` children
    (the e2e tests do) and they match the measurement pattern. Here they are this
    process's own descendants, so the descendant rule covers them; the OTHER pytest's
    children are covered by `_has_pytest_ancestor`, tested separately below."""
    script = tmp_path / "tos_evidence_scan_bench.py"
    script.write_text("import time\ntime.sleep(20)\n")
    child = subprocess.Popen([sys.executable, str(script), "build", "--days", "1"])
    try:
        time.sleep(1.0)
        reader = driver.HostReader()
        raw = {pid for pid, _ in reader._pgrep(driver.COMPETING_MEASURE_PATTERN)}
        assert child.pid in raw, "pgrep really does see it — the exclusion is the point"
        filtered = {
            p.pid for p in reader.scan({"m": driver.COMPETING_MEASURE_PATTERN})["m"]
        }
        assert (
            child.pid not in filtered
        ), "a pytest's own child must not stop a live run"
    finally:
        child.kill()
        child.wait()


def test_f2_a_process_descended_from_another_pytest_is_excluded(tmp_path: Path) -> None:
    """F2, the rule itself, on a constructed process tree.

    The scenario the review names is a LIVE driver watching a colleague's test run: those
    bench children are not the driver's descendants, so only this rule keeps them from
    SIGTERMing a six-hour measurement. The suite cannot stage that with real processes —
    its own children are its descendants — so the tree is built by hand.
    """
    another_pytest = _fake_pid(0)
    its_bench_child = _fake_pid(1)
    a_login_shell = _fake_pid(2)
    a_real_second_run = _fake_pid(3)
    root = _fake_proc(
        tmp_path / "proc",
        {
            _FAKE_INIT_PID: (0, "/sbin/init"),
            another_pytest: (_FAKE_INIT_PID, "/usr/bin/python -m pytest tests/tools"),
            its_bench_child: (
                another_pytest,
                "/usr/bin/python tools/tos_evidence_scan_bench.py build",
            ),
            a_login_shell: (_FAKE_INIT_PID, "/bin/bash -l"),
            a_real_second_run: (
                a_login_shell,
                "/usr/bin/python tools/tos_evidence_scan_bench.py build",
            ),
        },
    )
    reader = driver.HostReader(proc_root=root)

    assert reader._has_pytest_ancestor(
        its_bench_child
    ), "a test run's child must be excluded"
    assert not reader._has_pytest_ancestor(
        a_real_second_run
    ), "a real second run must NOT be"


def test_f2_the_descendant_rule_is_live_in_scan_not_just_available(
    tmp_path: Path,
) -> None:
    """F2, the descendant rule exercised THROUGH `scan`, with no pytest in the picture.

    Under pytest every descendant of this process also has a pytest ancestor, so the two
    exclusions cover each other and removing either leaves the suite green — a guard that
    is never the reason for anything. Here the whole process tree is constructed:
    ``the_driver`` stands in for the driver (a plain shell, no pytest anywhere),
    ``its_bench_child`` is the child it spawned, and ``an_unrelated_run`` is a second run
    that must still be seen.
    """
    the_driver = _fake_pid(0)
    its_bench_child = _fake_pid(1)
    an_unrelated_run = _fake_pid(2)
    # The driver is a parentless root: give it the fabricated init as a parent and every
    # other fabricated process becomes its "descendant".
    tree = {
        _FAKE_INIT_PID: (0, "/sbin/init"),
        the_driver: (0, "/bin/bash -l"),
        its_bench_child: (
            the_driver,
            "/usr/bin/python tools/tos_evidence_scan_bench.py build --days 1",
        ),
        an_unrelated_run: (
            _FAKE_INIT_PID,
            "/usr/bin/python tools/tos_evidence_scan_bench.py build --days 90",
        ),
    }
    root = _fake_proc(tmp_path / "proc", tree)
    table = tmp_path / "table"
    # The visible half of the same tree — one source for both views (review F7).
    table.write_text(
        _proc_table(
            [(pid, tree[pid][1]) for pid in (its_bench_child, an_unrelated_run)]
        )
    )
    fake = tmp_path / "fake-pgrep.sh"
    fake.write_text(f'#!/bin/sh\ngrep -E -- "$1" "{table}" || true\nexit 0\n')
    fake.chmod(0o755)
    # `self_pid` is the driver's own identity seam — no reaching into the private memo.
    reader = driver.HostReader(
        proc_root=root, pgrep_argv=(str(fake),), self_pid=the_driver
    )

    found = {p.pid for p in reader.scan({"m": driver.COMPETING_MEASURE_PATTERN})["m"]}

    assert (
        its_bench_child not in found
    ), "the driver's own bench child is the work, not competition"
    assert an_unrelated_run in found, "an unrelated second run must still be caught"


def test_f2_the_drivers_own_child_and_grandchildren_are_not_competitors(
    tmp_path: Path,
) -> None:
    """The other exclusion: the bench child this driver spawned is the work being
    measured. Checked by identity on the real `/proc` ancestry, with this process standing
    in for the driver."""
    script = tmp_path / "tos_evidence_scan_bench.py"
    script.write_text("import time\ntime.sleep(20)\n")
    child = subprocess.Popen([sys.executable, str(script), "measure", "--db", "/x"])
    try:
        time.sleep(1.0)
        reader = driver.HostReader()
        assert reader._is_descendant_of(child.pid, frozenset({os.getpid()}))
        assert not reader._is_descendant_of(1, frozenset({os.getpid()}))
    finally:
        child.kill()
        child.wait()


def test_f9_a_search_command_glued_to_shell_syntax_is_still_a_search(
    tmp_path: Path,
) -> None:
    """F9. Splitting on whitespace after stripping single quotes left `$(pgrep`, `;pgrep`
    and `|grep` unrecognized, so a line that was plainly searching counted as a build.
    """
    for args in (
        "bash -c 'for p in $(pgrep -f GradleWorkerMain); do kill $p; done'",
        'sh -c "pgrep -f GradleDaemon|wc -l"',
        "bash -c 'ps aux;grep GradleWrapperMain'",
    ):
        assert driver._is_searching_for_the_pattern(args), args
    # And a path that merely contains the letters is not a search command.
    assert not driver._is_searching_for_the_pattern(
        "/opt/grepbuild/gradlew --daemon org.gradle.launcher.daemon.bootstrap.GradleDaemon"
    )


def test_r2_f7_a_build_whose_paths_end_in_a_search_command_name_is_not_hidden() -> None:
    """Round-2 F7, both cases the reviewer EXECUTED against the branch.

    `os.path.basename` was applied to every whitespace token, so a JVM argument like
    `-Dorg.gradle.appname=/home/u/rg` read as the command `rg` and the whole Gradle build
    was filed as "merely searching" — invisible to both the preflight and the watchdog.
    A command name only appears at a command position; a `key=/path` value never is one.
    """
    for hidden in (
        "java -Dorg.gradle.appname=/home/u/rg -cp x worker.GradleWorkerMain",
        "/usr/bin/java -Duser.dir=/srv/grep "
        "org.gradle.launcher.daemon.bootstrap.GradleDaemon 8.5",
        "/usr/lib/jvm/java-21/bin/java -cp /opt/pgrep/lib/x.jar "
        "worker.org.gradle.process.internal.worker.GradleWorkerMain",
    ):
        assert not driver._is_searching_for_the_pattern(hidden), hidden

    # The command positions themselves still classify.
    assert driver._command_position_tokens(
        "java -Dorg.gradle.appname=/home/u/rg -cp x worker.GradleWorkerMain"
    ) == ["java"]
    assert driver._command_position_tokens("FOO=/x/rg pgrep -f y") == ["pgrep"]


def test_f4_the_documented_resume_command_actually_gets_past_preflight(
    tmp_path: Path,
) -> None:
    """F4. The abort log said 'resume with --steps before,after'; the artifacts_absent
    check then refused that exact command, because the aborted step's own `.out`/`.err`
    (created by posix_spawn) were sitting there. The resume was advice nothing tested.
    """
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    aborting_reader = _reader_that_reports_a_build_once(
        tmp_path, gate=out_dir / "before-1d.out"
    )

    assert (
        _cli(tmp_path, out_dir=out_dir, synthetic=synthetic, reader=aborting_reader)
        == 1
    )
    log = (out_dir / "measure-1d.log").read_text()
    assert "--steps before,after" in log
    assert synthetic.exists()
    # The aborted step's output was moved aside, not deleted.
    assert list(out_dir.glob("before-1d.*.aborted.out")), "the output is preserved"
    assert not (out_dir / "before-1d.out").exists()

    # Now run the command the log told the operator to run. It must get past preflight.
    rc = _cli(tmp_path, "--steps", "before,after", out_dir=out_dir, synthetic=synthetic)

    assert rc == 0, "the documented resume must actually work"
    assert (out_dir / "before-1d.json").is_file()
    assert (out_dir / "after-1d.json").is_file()


def test_f5_a_resume_is_not_asked_for_the_space_its_build_already_spent(
    tmp_path: Path,
) -> None:
    """F5. disk_free always demanded predicted x headroom, so a measure-only rerun on the
    very disk that now holds the synthetic file was refused by the tool's own advice."""
    # The `build` case needs the file ABSENT (otherwise synthetic_absent refuses first),
    # so the two cases get their own directories.
    build_dir = tmp_path / "b"
    build_dir.mkdir()
    _write_reference(build_dir / "evidence.sqlite3")
    build = _preflight(build_dir, _reader(build_dir), steps=["build"])

    resume_dir = tmp_path / "r"
    resume_dir.mkdir()
    _write_reference(resume_dir / "evidence.sqlite3")
    synthetic = resume_dir / "synth" / "synth-1d.sqlite3"
    synthetic.parent.mkdir(parents=True)
    synthetic.write_bytes(b"x" * 4096)
    measure_only = _preflight(
        resume_dir, _reader(resume_dir), steps=["before", "after"]
    )

    build_check = next(c for c in build.checks if c.check == "disk_free")
    resume_check = next(c for c in measure_only.checks if c.check == "disk_free")
    assert build_check.evaluated and resume_check.evaluated
    assert "index-growth-ratio" in resume_check.source
    assert resume_check.floor_bytes is not None
    assert build_check.floor_bytes is not None
    assert resume_check.floor_bytes < build_check.floor_bytes
    # Only the index is new: ~1.8 % of the file on disk, not the whole predicted file.
    assert resume_check.floor_bytes <= int(
        4096 * driver.DEFAULT_INDEX_GROWTH_RATIO * driver.DEFAULT_DISK_HEADROOM_RATIO
    )


def test_f5_measure_only_without_a_synthetic_file_is_refused_up_front(
    tmp_path: Path,
) -> None:
    """The step selection has to be consistent with what is on disk: with `build` excluded
    nothing creates the file, so refusing now beats three children failing later."""
    record = _preflight(tmp_path, _reader(tmp_path), steps=["before", "after"])

    assert record.verdict == "refused"
    assert "synthetic_present" in _failed(record)


def test_f6_wall_clock_is_not_rounded_up_to_the_host_sample_interval(
    tmp_path: Path,
) -> None:
    """F6. wait4 was polled only after sleep(watch_interval_s), so a step that finished
    early was still reported as having run until the next sample: an 8 s step under a 5 s
    cadence read as 10 s at 80 % CPU, not comparable with the GNU `time -v` numbers."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    step = driver.Step(
        name="build",
        argv=(sys.executable, "-c", "import time; time.sleep(0.3)"),
        stdout_path=tmp_path / "w.out",
        stderr_path=tmp_path / "w.err",
    )

    result = driver.run_step(
        step,
        # A deliberately coarse host cadence next to a fine reap cadence.
        guard=_guard(watch_interval_s=5.0, poll_interval_s=0.02),
        checkout=_clean_checkout(),
        reader=driver.HostReader(),
        run_id="cadence",
        days=1,
        out_dir=out_dir,
        log=lambda _m: None,
        sampler=_healthy(),
    )

    assert 0.3 <= result.wall_seconds < 1.0, result.wall_seconds
    assert result.samples_taken == 1, "the host cadence is still 5 s"


def _wait_until_reapable(pid: int, timeout: float = 10.0) -> bool:
    """Block until ``pid`` is a zombie (exited, not yet reaped) or gone.

    A child writing "I am done" to a file and then exiting are two different instants, so
    a marker file cannot express "the child has already exited" — the first version of the
    F7 test used one and raced. The kernel's own ``Z`` state can.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
        except OSError:
            return True
        state = stat[stat.rindex(")") + 2]
        if state == "Z":
            return True
        time.sleep(0.01)
    return False


def test_f7_a_breach_that_coincides_with_the_child_exiting_is_not_an_abort(
    tmp_path: Path,
) -> None:
    """F7. A sample taken on a child that had already exited could produce an ABORTED
    artifact next to a complete `<step>-Nd.json`, and the next resume was then refused by
    artifacts_absent for a step that had in fact succeeded."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    step = driver.Step(
        name="build",
        argv=(sys.executable, "-c", "pass"),
        stdout_path=tmp_path / "r.out",
        stderr_path=tmp_path / "r.err",
    )
    seen = {"reaped": False}

    def sampler(pid: int):
        # Hold the sample until the child really has exited, then report a starved host:
        # exactly the interleaving the guard has to recognize as "already finished".
        seen["reaped"] = _wait_until_reapable(pid)
        return driver.HostSample(
            at_kst="2026-10-01T12:00:00.000+09:00",
            mem_available_bytes=int(0.5 * _GB),
            swap_free_bytes=5 * _GB,
            swap_total_bytes=8 * _GB,
        )

    result = driver.run_step(
        step,
        guard=_guard(),
        checkout=_clean_checkout(),
        reader=driver.HostReader(),
        run_id="race",
        days=1,
        out_dir=out_dir,
        log=lambda _m: None,
        sampler=sampler,
    )

    assert seen["reaped"], "the test did not reach the interleaving it is about"
    assert result.returncode == 0
    assert not _abort_records(out_dir, "build-1d")
    assert (out_dir / "build-1d.resource.json").is_file()


def test_f7_an_abort_records_the_exit_code_the_way_a_step_result_does(
    tmp_path: Path,
) -> None:
    """The raw wait status leaked into AbortRecord.returncode on the non-signalled branch:
    a child that had exited 1 was recorded as 256 while StepResult said 1."""
    assert driver._returncode(0) == 0
    assert driver._returncode(1 << 8) == 1, "exit 1 is 1, not 256"
    assert driver._returncode(9) == -9, "SIGKILL is -9"


def test_f8_lowering_the_start_floor_lowers_the_in_run_floor_with_it(
    tmp_path: Path,
) -> None:
    """F8. The help said `--min-swap-free-gb 0` opts out on a swapless host; the default
    abort floor of 1.0 then refused, citing a flag the operator had never typed."""
    guard = driver.GuardConfig.validated(min_available_gb=6.0, min_swap_free_gb=0.0)

    assert guard.abort_swap_free_bytes == 0
    assert guard.abort_available_bytes == int(driver.DEFAULT_ABORT_AVAILABLE_GB * _GB)
    assert any("abort_swap_free_gb derived" in d for d in guard.derivations)

    # An abort floor the operator DID type above the start floor is still a contradiction.
    with pytest.raises(driver.MeasureRefused, match="abort-swap-free-gb"):
        driver.GuardConfig.validated(
            min_available_gb=6.0, min_swap_free_gb=0.0, abort_swap_free_gb=1.0
        )


def test_f8_a_swapless_host_runs_end_to_end_with_one_flag(tmp_path: Path) -> None:
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    reader = driver.HostReader(
        meminfo_path=_meminfo(
            tmp_path / "swapless",
            available_gb=12.0,
            swap_free_gb=0.0,
            swap_total_gb=0.0,
        ),
        pgrep_argv=("/bin/true",),
    )
    rc = driver.main(
        [
            "run",
            "--reference",
            str(reference),
            "--synthetic",
            str(tmp_path / "synth" / "s.sqlite3"),
            "--out-dir",
            str(tmp_path / "out"),
            "--days",
            "1",
            "--repeats",
            "1",
            "--batch-rows",
            "200",
            "--min-available-gb",
            "0",
            # The one flag the help text names. No --abort-swap-free-gb.
            "--min-swap-free-gb",
            "0",
            "--watch-interval-s",
            "0.05",
            "--poll-interval-s",
            "0.01",
            "--allow-shared-checkout",
            "--bench",
            str(_BENCH_PATH),
        ],
        reader=reader,
    )

    assert rc == 0
    payload = json.loads((tmp_path / "out" / "preflight.json").read_text())
    assert payload["thresholds"]["abort_swap_free_gb"] == 0.0
    assert any("derived" in w for w in payload["warnings"])


def test_the_output_directory_lock_refuses_a_second_run_and_survives_a_kill(
    tmp_path: Path,
) -> None:
    """The lock is the exact half of F3 that a pattern cannot do: it says whether another
    run claimed THIS output directory. A lock whose owner is gone must not block forever —
    a SIGKILLed run cannot clean up after itself."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    live = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
    try:
        (out_dir / driver.LOCK_NAME).write_text(
            json.dumps({"pid": live.pid, "argv0": sys.executable, "run_id": "other"})
        )
        assert driver.read_lock(out_dir) is not None
        assert _preflight(tmp_path, _reader(tmp_path)).verdict == "refused"
    finally:
        live.kill()
        live.wait()

    # Owner gone: stale, and the next run proceeds.
    assert driver.read_lock(out_dir) is None
    assert _preflight(tmp_path, _reader(tmp_path)).verdict == "ok"


def test_the_lock_is_released_when_a_run_finishes(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    assert _cli(tmp_path, out_dir=out_dir) == 0
    assert not (out_dir / driver.LOCK_NAME).exists()


# ---------------------------------------------------------------------------------------
# Round-2 review findings
# ---------------------------------------------------------------------------------------


def test_r2_f1_sigterm_to_the_driver_kills_the_child_and_leaves_an_artifact(
    tmp_path: Path,
) -> None:
    """Round-2 F1. With no handler, SIGTERM to the driver (a closed tmux pane, `kill`,
    `timeout`, earlyoom picking the driver) exited the interpreter immediately: the abort
    path never ran, the bench child was ORPHANED and kept writing a 53 GB file with no
    watchdog, and no artifact was written."""
    out_dir = tmp_path / "out"
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    child_pid_file = tmp_path / "child.pid"
    slow = _stub_bench(
        tmp_path,
        f"    pathlib.Path({str(child_pid_file)!r}).write_text(str(os.getpid()))\n"
        "    time.sleep(120)\n",
    )
    meminfo = _meminfo(tmp_path / "mi", available_gb=12.0, swap_free_gb=5.0)

    proc = subprocess.Popen(
        [
            sys.executable,
            str(_MODULE_PATH),
            "run",
            "--reference",
            str(reference),
            "--synthetic",
            str(tmp_path / "synth" / "s.sqlite3"),
            "--out-dir",
            str(out_dir),
            "--days",
            "1",
            "--repeats",
            "1",
            "--min-available-gb",
            "0",
            "--min-swap-free-gb",
            "0",
            "--abort-available-gb",
            "0",
            "--abort-swap-free-gb",
            "0",
            "--watch-interval-s",
            "0.05",
            "--poll-interval-s",
            "0.01",
            "--term-grace-s",
            "1",
            # The stub bench lives under tmp_path, outside the checkout, and the real
            # checkout is a branch: both are exactly what the A1-c guard refuses, and
            # this test is about SIGTERM.
            "--allow-shared-checkout",
            "--bench",
            str(slow),
        ],
        # The real HostReader is used here (this is a real subprocess), so the fake
        # /proc/meminfo is handed over the only way a subprocess can take it: it cannot.
        # The floors are zeroed above instead, and the fake file is unused.
        env={**os.environ, "TOS_MEASURE_FAKE_MEMINFO": str(meminfo)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not child_pid_file.exists():
            time.sleep(0.05)
        assert child_pid_file.exists(), "the bench child never started"
        child_pid = int(child_pid_file.read_text())

        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    assert proc.returncode == 1, proc.stderr
    # The child is gone, not orphaned.
    assert not _pid_alive(child_pid), "the bench child outlived the signalled driver"
    record = _abort_record(out_dir, "build-1d")
    assert record["check"] == "driver_signalled"
    assert "SIGTERM" in record["reason"]
    # And the lock the run took is released.
    assert not (out_dir / driver.LOCK_NAME).exists()


def _pid_alive(pid: int) -> bool:
    """Alive AND not a zombie — a reaped-but-unwaited child still has a /proc entry."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return False
    return stat[stat.rindex(")") + 2] != "Z"


def test_r2_f3_a_build_onto_an_existing_synthetic_is_refused_before_anything_runs(
    tmp_path: Path,
) -> None:
    """Round-2 F3. The bench refuses to overwrite its `--out`, so this run was GUARANTEED
    to fail at step 1 — after preflight said ok, and after leaving four artifacts behind
    that then blocked the retry."""
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    synthetic.parent.mkdir(parents=True)
    synthetic.write_bytes(b"not a database")
    out_dir = tmp_path / "out"

    rc = _cli(tmp_path, out_dir=out_dir, synthetic=synthetic)

    assert rc == 1
    payload = json.loads((out_dir / "preflight.json").read_text())
    checks = {c["check"]: c for c in payload["checks"]}
    assert checks["synthetic_absent"]["ok"] is False
    # Nothing ran, so nothing was left behind to block the retry.
    assert not (out_dir / "build-1d.json").exists()
    assert not (out_dir / "build-1d.err").exists()
    assert not list(out_dir.glob("*.resource.json"))


def test_r2_f4_with_the_watchdog_off_a_host_read_failure_is_recorded_not_fatal(
    tmp_path: Path,
) -> None:
    """Round-2 F4. `--no-watchdog` turns the in-run guards off, but the `host_read` abort
    still fired and killed the child citing blind guards that were disabled."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    def sampler(pid: int):
        raise driver.MeasureRefused("pgrep exited 2")

    result = driver.run_step(
        driver.Step(
            name="build",
            argv=(sys.executable, "-c", "import time; time.sleep(0.3)"),
            stdout_path=tmp_path / "n.out",
            stderr_path=tmp_path / "n.err",
        ),
        guard=_guard(watchdog_enabled=False),
        checkout=_clean_checkout(),
        reader=driver.HostReader(),
        run_id="nowatch",
        days=1,
        out_dir=out_dir,
        log=lambda _m: None,
        sampler=sampler,
    )

    assert result.returncode == 0, "the child ran to completion"
    assert not _abort_records(out_dir, "build-1d")
    rows = [
        json.loads(line)
        for line in (out_dir / "watchdog.jsonl").read_text().splitlines()
    ]
    assert rows, "the failures are still recorded"
    assert all(row["fatal"] is False for row in rows if "host_read_error" in row)


def test_r2_f5_a_failed_step_cannot_have_its_resource_numbers_overwritten(
    tmp_path: Path,
) -> None:
    """Round-2 F5. `artifacts_absent` guarded `.out/.err/.json` only, while a failed step
    had already written `.time` and `.resource.json`; the rerun then replaced the failed
    pass's numbers with no trace."""
    step = driver.Step(
        name="before",
        argv=("x",),
        stdout_path=tmp_path / "before-90d.out",
        stderr_path=tmp_path / "before-90d.err",
    )
    names = {
        p.name for p in driver.step_artifact_paths(step, out_dir=tmp_path, days=90)
    }

    assert names == {
        "before-90d.out",
        "before-90d.err",
        "before-90d.json",
        "before-90d.time",
        "before-90d.resource.json",
    }

    for name in names:
        (tmp_path / name).write_text("x")
    moved = driver.move_step_artifacts_aside(
        step, out_dir=tmp_path, days=90, run_id="abc123"
    )
    assert len(moved) == 5
    assert all(".abc123.aborted" in m.name for m in moved)
    assert all(m.read_text() == "x" for m in moved), "moved, never deleted"
    assert not any((tmp_path / name).exists() for name in names)


def test_r2_f6_a_reader_failure_still_writes_the_preflight_record(
    tmp_path: Path,
) -> None:
    """Round-2 F6. `meminfo()` and `competing_processes()` raised out of `preflight()`
    before the record was written, so a host with no SwapFree line produced the very
    'refusal that leaves no artifact' this record exists to prevent."""
    partial = tmp_path / "partial-meminfo"
    partial.write_text("MemTotal: 22016000 kB\nMemAvailable: 12000000 kB\n")
    reader = driver.HostReader(meminfo_path=partial, pgrep_argv=("/bin/true",))

    record = _preflight(tmp_path, reader)

    assert record.verdict == "refused"
    payload = json.loads((tmp_path / "out" / "preflight.json").read_text())
    checks = {c["check"]: c for c in payload["checks"]}
    assert checks["swap_free"]["ok"] is False
    assert "SwapFree" in checks["swap_free"]["measured"]

    # Same for an unusable pgrep.
    broken = driver.HostReader(
        meminfo_path=_meminfo(tmp_path / "mi", available_gb=12.0, swap_free_gb=5.0),
        pgrep_argv=("/bin/sh", "-c", "exit 2", "--"),
    )
    record = _preflight(tmp_path, broken)
    assert record.verdict == "refused"
    payload = json.loads((tmp_path / "out" / "preflight.json").read_text())
    checks = {c["check"]: c for c in payload["checks"]}
    assert checks["competing_build"]["ok"] is False
    assert "exited 2" in checks["competing_build"]["measured"]


def test_r2_f8_the_run_log_is_appended_not_replaced(tmp_path: Path) -> None:
    """Round-2 F8. The documented resume (same --days, same --out-dir) overwrote the
    aborted run's log wholesale, including the ABORT line — the human-readable timeline
    the plan says it will cite instead of session memory."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    aborting = _reader_that_reports_a_build_once(
        tmp_path, gate=out_dir / "before-1d.out"
    )

    assert _cli(tmp_path, out_dir=out_dir, synthetic=synthetic, reader=aborting) == 1
    first = (out_dir / "measure-1d.log").read_text()
    assert "ABORT (before)" in first

    assert (
        _cli(tmp_path, "--steps", "before,after", out_dir=out_dir, synthetic=synthetic)
        == 0
    )
    second = (out_dir / "measure-1d.log").read_text()
    assert "ABORT (before)" in second, "the aborted run's timeline survived the resume"
    assert second.count("##### run ") == 2, "each run is headed by its own id"
    assert len(second) > len(first)


def test_r2_f10_a_measure_only_resume_needs_no_reference_at_all(
    tmp_path: Path,
) -> None:
    """Round-2 F10. The estimate (a GROUP BY over the whole reference) ran unconditionally
    before the memory checks and even for resumes that never use it, so `--reference` was
    mandatory for a run that does not read it."""
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    assert (
        _cli(
            tmp_path,
            "--steps",
            "build",
            "--keep-synthetic",
            out_dir=out_dir,
            synthetic=synthetic,
            reference=reference,
        )
        == 0
    )
    assert synthetic.exists()
    rc = driver.main(
        [
            "run",
            "--synthetic",
            str(synthetic),
            "--out-dir",
            str(out_dir),
            "--days",
            "1",
            "--steps",
            "before",
            "--repeats",
            "1",
            "--min-available-gb",
            "0",
            "--min-swap-free-gb",
            "0",
            "--abort-available-gb",
            "0",
            "--abort-swap-free-gb",
            "0",
            "--watch-interval-s",
            "0.05",
            "--poll-interval-s",
            "0.01",
            "--allow-shared-checkout",
            "--bench",
            str(_BENCH_PATH),
        ],
        reader=_reader(tmp_path),
    )

    assert rc == 0, "a measure-only resume must not require --reference"
    assert (out_dir / "before-1d.json").is_file()


def test_r2_f10_a_build_without_a_reference_is_refused_with_a_clear_reason(
    tmp_path: Path,
) -> None:
    rc = driver.main(
        [
            "run",
            "--synthetic",
            str(tmp_path / "s.sqlite3"),
            "--out-dir",
            str(tmp_path / "out"),
            "--days",
            "1",
            "--allow-shared-checkout",
            "--bench",
            str(_BENCH_PATH),
        ],
        reader=_reader(tmp_path),
    )
    assert rc == 1


def test_r2_f10_the_reference_is_not_scanned_when_the_host_already_failed(
    tmp_path: Path,
) -> None:
    """Sizing the run means scanning the reference. Doing that for a run that is not going
    to start is work on a host that is already in trouble — and the disk check says it was
    skipped rather than quietly passing."""
    record = _preflight(tmp_path, _reader(tmp_path, available_gb=1.0, swap_free_gb=0.1))

    assert record.verdict == "refused"
    disk = next(c for c in record.checks if c.check == "disk_free")
    assert disk.evaluated is False
    assert "mem_available" in disk.floor
    # Not evaluated is not a pass: it stays out of the refusal list but is in the record.
    assert "disk_free" not in (record.refusal or "")
    assert record.estimate is None


def test_every_check_is_evaluated_on_a_healthy_host(tmp_path: Path) -> None:
    """The guard on the guard: `evaluated=False` must only ever happen because something
    else already refused the run. If a healthy host could skip a check, the skip would be
    a silent pass."""
    record = _preflight(tmp_path, _reader(tmp_path))

    assert record.verdict == "ok"
    assert all(c.evaluated for c in record.checks)


# ---------------------------------------------------------------------------------------
# A1-c — the measurement runs from a detached worktree, and the tree may not move under it
# ---------------------------------------------------------------------------------------
#
# Plan §2 A1-c, registered by the §7.1.16 F6 disposition. The 365-day and 180-day
# measurements both ran from the shared checkout and the tree moved under both of them
# mid-run. Each test below names the shape that would have let that happen again.


def test_a1c_preflight_refuses_a_checkout_attached_to_a_branch(tmp_path: Path) -> None:
    """The shape both earlier runs had: a branch another lane can move under the run."""
    repo = _make_checkout(tmp_path, detached=False)
    record = _preflight(tmp_path, _reader(tmp_path), checkout=_checkout(repo))

    assert record.verdict == "refused"
    check = next(c for c in record.checks if c.check == "checkout_detached_and_clean")
    assert check.ok is False
    assert check.evaluated is True
    assert "on branch main" in check.measured
    assert "HEAD is attached to branch 'main'" in check.detail
    assert "checkout_detached_and_clean" in (record.refusal or "")
    assert record.checkout["detached"] is False


def test_a1c_preflight_refuses_a_dirty_checkout(tmp_path: Path) -> None:
    """Detached is not enough: an uncommitted edit means the bench that runs is not the
    bench any commit names."""
    repo = _make_checkout(tmp_path, dirty=True)
    record = _preflight(tmp_path, _reader(tmp_path), checkout=_checkout(repo))

    assert record.verdict == "refused"
    check = next(c for c in record.checks if c.check == "checkout_detached_and_clean")
    assert check.ok is False
    assert "DIRTY" in check.measured
    assert "the tree is dirty" in check.detail
    assert "scratch.txt" in check.detail
    assert record.checkout["clean"] is False


def test_a1c_preflight_refuses_a_head_that_is_not_an_ancestor_of_origin_main(
    tmp_path: Path,
) -> None:
    """Clean and detached, but at a commit that was never published: a measurement is
    evidence, and evidence is produced by merged code (#793)."""
    repo = _make_checkout(tmp_path, ancestor=False)
    record = _preflight(tmp_path, _reader(tmp_path), checkout=_checkout(repo))

    assert record.verdict == "refused"
    check = next(c for c in record.checks if c.check == "checkout_detached_and_clean")
    assert check.ok is False
    assert "NOT an ancestor of origin/main" in check.measured
    assert "is not an ancestor of origin/main" in check.detail
    assert record.checkout["ancestor_of_origin_main"] is False
    assert record.checkout["origin_main_present"] is True


def test_a1c_preflight_refuses_when_origin_main_is_absent_and_says_to_fetch(
    tmp_path: Path,
) -> None:
    """The driver does not fetch — a measurement must not reach the network, and a tool
    that moved a remote ref would be changing the answer to its own question. So a missing
    origin/main is a refusal that says what to run, not a pass."""
    repo = _make_checkout(tmp_path, origin_main=False)
    record = _preflight(tmp_path, _reader(tmp_path), checkout=_checkout(repo))

    assert record.verdict == "refused"
    check = next(c for c in record.checks if c.check == "checkout_detached_and_clean")
    assert check.ok is False
    assert "git fetch origin" in check.detail
    assert record.checkout["origin_main_present"] is False


def test_a1c_preflight_refuses_a_bench_from_outside_the_checkout(
    tmp_path: Path,
) -> None:
    """run_p_ca.sh's module-provenance check, in Python. --python is deliberately the
    SHARED checkout's venv, so the interpreter vouches for nothing; if --bench may point
    anywhere, the three git checks above vouch for code that never runs."""
    repo = _make_checkout(tmp_path)
    stranger = tmp_path / "elsewhere" / "tos_evidence_scan_bench.py"
    stranger.parent.mkdir()
    stranger.write_text("# a bench from some other tree\n")

    record = _preflight(
        tmp_path, _reader(tmp_path), checkout=_checkout(repo, bench=stranger)
    )

    assert record.verdict == "refused"
    check = next(c for c in record.checks if c.check == "checkout_detached_and_clean")
    assert check.ok is False
    assert "resolves OUTSIDE the checkout" in check.detail
    assert record.checkout["bench_in_repo"] is False
    # Recorded even so: the digest is how a reader finds out WHICH stranger it was.
    assert len(str(record.checkout["bench_sha256"])) == 64


def test_a1c_a_directory_outside_any_git_checkout_is_refused_not_assumed_fine(
    tmp_path: Path,
) -> None:
    """Fail closed. A question git cannot answer has not been answered."""
    loose = tmp_path / "loose"
    (loose / "tools").mkdir(parents=True)
    (loose / "tools" / "tos_evidence_scan_measure.py").write_text("# no repo here\n")
    (loose / "tools" / "tos_evidence_scan_bench.py").write_text("# nor here\n")

    record = _preflight(tmp_path, _reader(tmp_path), checkout=_checkout(loose))

    assert record.verdict == "refused"
    check = next(c for c in record.checks if c.check == "checkout_detached_and_clean")
    assert check.ok is False
    assert "not inside a git checkout" in check.measured


def test_a1c_a_missing_git_binary_is_refused_rather_than_skipped(
    tmp_path: Path,
) -> None:
    """The same fail-closed rule for the tool itself."""
    repo = _make_checkout(tmp_path)
    guard = driver.CheckoutGuard(
        driver_path=repo / "tools" / "tos_evidence_scan_measure.py",
        bench_path=repo / "tools" / "tos_evidence_scan_bench.py",
        git=(str(tmp_path / "no-such-git"),),
    ).with_baseline()

    assert guard.baseline.ok is False
    record = _preflight(tmp_path, _reader(tmp_path), checkout=guard)
    assert record.verdict == "refused"
    assert "checkout_detached_and_clean" in (record.refusal or "")


def test_a1c_the_refusal_names_every_reason_not_only_the_first(
    tmp_path: Path,
) -> None:
    """An operator who has to fix one refusal at a time learns about the dirty tree only
    after fixing the branch — the same rule the rest of this preflight already follows.
    """
    repo = _make_checkout(tmp_path, detached=False, dirty=True, ancestor=False)
    record = _preflight(tmp_path, _reader(tmp_path), checkout=_checkout(repo))

    check = next(c for c in record.checks if c.check == "checkout_detached_and_clean")
    assert "HEAD is attached" in check.detail
    assert "the tree is dirty" in check.detail
    assert "is not an ancestor of origin/main" in check.detail


def test_a1c_a_bad_checkout_stops_the_run_before_the_reference_is_scanned(
    tmp_path: Path,
) -> None:
    """Sizing the run means a GROUP BY over the whole reference. Doing that for a run that
    cannot start is work for nothing — the same reason the disk check is skipped when
    memory already failed (round-2 F10)."""
    repo = _make_checkout(tmp_path, detached=False)
    record = _preflight(tmp_path, _reader(tmp_path), checkout=_checkout(repo))

    assert record.estimate is None
    disk = next(c for c in record.checks if c.check == "disk_free")
    assert disk.evaluated is False
    assert "checkout_detached_and_clean" in disk.floor


def test_a1c_the_escape_hatch_records_the_warning_and_does_not_refuse(
    tmp_path: Path,
) -> None:
    """--allow-shared-checkout is needed by this suite and by a deliberate operator run.
    It turns the refusal off; it does not turn the RECORD off, so a run made with the
    hatch open cannot be mistaken for a clean one afterwards."""
    repo = _make_checkout(tmp_path, detached=False, dirty=True)
    (tmp_path / "synth.sqlite3").write_bytes(b"")  # nothing else may refuse this run
    record = driver.preflight(
        run_id="hatch",
        guard=_guard(),
        checkout=_checkout(repo, enforced=False),
        reader=_reader(tmp_path),
        out_dir=tmp_path / "out",
        days=1,
        estimator=None,
        expect_bytes=0,
        disk_headroom_ratio=1.0,
        index_growth_ratio=0.0,
        steps=(),
        argv=["run"],
        synthetic=tmp_path / "synth.sqlite3",
        warnings=[driver.ALLOW_SHARED_CHECKOUT_WARNING],
    )

    assert record.verdict == "ok"
    check = next(c for c in record.checks if c.check == "checkout_detached_and_clean")
    assert check.ok is False, "the facts are still measured honestly"
    assert check.evaluated is False, "and visibly not gating"
    assert "SKIPPED by --allow-shared-checkout" in check.floor
    assert record.checkout["allow_shared_checkout"] is True
    assert record.checkout["detached"] is False
    assert record.checkout["clean"] is False
    assert any("--allow-shared-checkout" in w for w in record.warnings)
    # And on disk, not only in the returned object.
    payload = json.loads((tmp_path / "out" / "preflight.json").read_text())
    assert payload["checkout"]["allow_shared_checkout"] is True
    assert any("--allow-shared-checkout" in w for w in payload["warnings"])


def test_a1c_the_cli_warns_on_stderr_when_the_hatch_is_open(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _cli(tmp_path)
    assert "--allow-shared-checkout" in capsys.readouterr().err


def test_a1c_the_guard_follows_the_drivers_own_file_not_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Production resolves the repo from ``__file__``, so running the driver from
    somewhere else does not point the guard at a different tree. ``preflight`` starts no
    child, and the verdict is left alone: on a developer branch it refuses, in CI's
    detached checkout it may not, and neither says anything about this property."""
    monkeypatch.chdir(tmp_path)
    out_dir = tmp_path / "out"
    driver.main(
        [
            "preflight",
            "--synthetic",
            str(tmp_path / "synth.sqlite3"),
            "--out-dir",
            str(out_dir),
            "--days",
            "1",
            "--steps",
            "before",
            "--min-available-gb",
            "0",
            "--min-swap-free-gb",
            "0",
        ],
        reader=_reader(tmp_path),
    )

    payload = json.loads((out_dir / "preflight.json").read_text())
    # Resolved on both sides: `git rev-parse --show-toplevel` answers with the path as
    # git knows it, which need not be the resolved one on a checkout reached through a
    # symlink. The property under test is "the driver's own tree", not its spelling.
    assert Path(str(payload["checkout"]["repo_path"])).resolve() == _REPO_ROOT
    assert payload["checkout"]["driver_path"] == str(_MODULE_PATH)
    assert payload["checkout"]["bench_path"] == str(_BENCH_PATH)
    assert payload["checkout"]["bench_in_repo"] is True


# -- the run-time guard: the property the SHA line could only document -------------------


def _trivial_step(tmp_path: Path, name: str = "before"):
    return driver.Step(
        name=name,
        argv=(sys.executable, "-c", "pass"),
        stdout_path=tmp_path / f"{name}.out",
        stderr_path=tmp_path / f"{name}.err",
    )


def _run_with(checkout, tmp_path: Path, *, out_dir: Path, name: str = "before"):
    return driver.run_step(
        _trivial_step(tmp_path, name),
        guard=_guard(),
        checkout=checkout,
        reader=driver.HostReader(),
        run_id="driftrun",
        days=7,
        out_dir=out_dir,
        log=lambda _m: None,
        sampler=_healthy(),
    )


def test_a1c_a_commit_that_moves_between_steps_aborts_before_the_child_starts(
    tmp_path: Path,
) -> None:
    """THE property. The preflight runs once; `before` and `after` do not — at 180 days
    they started 1 h 39 m apart. A SHA written into the artifact proves afterwards that
    the tree moved; this stops the second child from running at all."""
    repo = _make_checkout(tmp_path)
    checkout = _checkout(repo)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # Step one runs against the tree the preflight approved.
    first = _run_with(checkout, tmp_path, out_dir=out_dir, name="build")
    assert first.returncode == 0

    # …and then the tree moves, exactly as it did under both earlier measurements.
    moved_from = _git(repo, "rev-parse", "HEAD")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "a parallel lane lands something")
    moved_to = _git(repo, "rev-parse", "HEAD")
    assert moved_from != moved_to

    with pytest.raises(driver.MeasureAborted, match="HEAD moved from"):
        _run_with(checkout, tmp_path, out_dir=out_dir, name="before")

    record = _abort_record(out_dir, "before-7d")
    assert record["check"] == "checkout_drift"
    assert moved_from in record["reason"] and moved_to in record["reason"]
    # No child was started, and the record says so instead of printing a 0 that would read
    # as "the child exited cleanly".
    assert record["returncode"] is None
    assert record["partial_resource"] == {}
    assert record["signal_sent"].startswith("none")
    assert record["checkout"]["repo_commit"] == moved_to
    assert record["checkout"]["baseline_commit"] == moved_from
    assert not (tmp_path / "before.out").exists(), "the child must never have run"


def test_a1c_a_tree_that_goes_dirty_between_steps_aborts(tmp_path: Path) -> None:
    repo = _make_checkout(tmp_path)
    checkout = _checkout(repo)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert _run_with(checkout, tmp_path, out_dir=out_dir, name="build").returncode == 0

    (repo / "tools" / "edited-mid-run.txt").write_text("someone is working in here\n")

    with pytest.raises(driver.MeasureAborted, match="went dirty"):
        _run_with(checkout, tmp_path, out_dir=out_dir, name="after")
    record = _abort_record(out_dir, "after-7d")
    assert record["check"] == "checkout_drift"
    assert record["checkout"]["clean"] is False


def test_a1c_a_bench_edited_between_steps_aborts_even_with_a_clean_tree(
    tmp_path: Path,
) -> None:
    """Why the digest is checked next to cleanliness rather than behind it: an IGNORED
    bench can change while `git status --porcelain` stays empty and HEAD stays put. That
    is the one case where the two git answers are both "nothing moved" and the two passes
    were still measured with different benches."""
    repo = _make_checkout(tmp_path, bench_ignored=True)
    checkout = _checkout(repo)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    before_digest = checkout.baseline.bench_sha256
    assert _run_with(checkout, tmp_path, out_dir=out_dir, name="build").returncode == 0

    (repo / "tools" / "tos_evidence_scan_bench.py").write_text("# a different bench\n")
    assert (
        _git(repo, "status", "--porcelain") == ""
    ), "git sees nothing — that is the point"

    with pytest.raises(driver.MeasureAborted, match="the bench .* changed"):
        _run_with(checkout, tmp_path, out_dir=out_dir, name="after")
    record = _abort_record(out_dir, "after-7d")
    assert record["check"] == "checkout_drift"
    assert record["checkout"]["clean"] is True
    assert record["checkout"]["baseline_bench_sha256"] == before_digest
    assert record["checkout"]["bench_sha256"] != before_digest


def test_a1c_every_step_artifact_carries_the_commit_and_the_bench_digest(
    tmp_path: Path,
) -> None:
    """Requirement 3: a changed bench stays detectable even when the guard is bypassed,
    because each step's own artifact says which bench produced it."""
    repo = _make_checkout(tmp_path)
    checkout = _checkout(repo)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = _run_with(checkout, tmp_path, out_dir=out_dir, name="before")

    head = _git(repo, "rev-parse", "HEAD")
    digest = hashlib.sha256(
        (repo / "tools" / "tos_evidence_scan_bench.py").read_bytes()
    ).hexdigest()
    assert result.checkout["repo_commit"] == head
    assert result.checkout["bench_sha256"] == digest

    payload = json.loads((out_dir / "before-7d.resource.json").read_text())
    for key in (
        "repo_commit",
        "repo_path",
        "detached",
        "clean",
        "ancestor_of_origin_main",
    ):
        assert key in payload["checkout"], key
    assert payload["checkout"]["bench_sha256"] == digest

    # The .time file carries the same two facts as COMMENTS, so §7.1.2's grep for
    # `File system inputs` keeps working unchanged.
    timing = (out_dir / "before-7d.time").read_text()
    assert f"# repo_commit: {head}" in timing
    assert f"# bench sha256: {digest}" in timing
    assert "\tFile system inputs: " in timing


def test_a1c_with_the_hatch_open_drift_is_recorded_but_does_not_abort(
    tmp_path: Path,
) -> None:
    """The deliberate operator run: nothing is blocked, and the step artifact still shows
    the tree moved — baseline_commit next to repo_commit, in the file itself."""
    repo = _make_checkout(tmp_path)
    checkout = _checkout(repo, enforced=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    baseline = checkout.baseline.repo_commit
    _git(repo, "commit", "-q", "--allow-empty", "-m", "moved under an allowed run")

    result = _run_with(checkout, tmp_path, out_dir=out_dir, name="after")

    assert result.returncode == 0
    assert not _abort_records(out_dir, "after-7d")
    assert result.checkout["baseline_commit"] == baseline
    assert result.checkout["repo_commit"] != baseline
    assert result.checkout["allow_shared_checkout"] is True


def test_a1c_a_checkout_that_stays_put_is_not_an_abort(tmp_path: Path) -> None:
    """The other direction, because a guard that is too eager is the same bug as no guard:
    three steps in a row against an unmoving tree all run."""
    repo = _make_checkout(tmp_path)
    checkout = _checkout(repo)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    for name in ("build", "before", "after"):
        assert _run_with(checkout, tmp_path, out_dir=out_dir, name=name).returncode == 0
    assert not list(out_dir.glob("ABORTED-*"))


def test_a1c_a_state_that_errored_is_never_ok_however_good_the_rest_looks() -> None:
    """The fail-closed clause, given the concrete input it refuses.

    It needs its own test. Through :func:`read_checkout` the clause is MASKED: every
    error path returns before the four git answers are filled in, so they are all False
    and ``ok`` would already be False without it — deleting ``not self.error`` leaves the
    refusal tests above green. A clause nothing can fail is a clause that blocks nothing
    (`MEMORY.md`, "가드가 자기가 막는다고 말한 것을 허용한다"), so here is the state it
    exists for: a reader that learns the four answers and THEN fails.
    """
    state = driver.CheckoutState(
        at_kst="2026-10-02T12:00:00.000+09:00",
        repo_path="/somewhere",
        repo_commit="0" * 40,
        branch="HEAD",
        detached=True,
        clean=True,
        ancestor_of_origin_main=True,
        origin_main_present=True,
        origin_main_commit="0" * 40,
        dirty_sample="",
        driver_path="/somewhere/tools/tos_evidence_scan_measure.py",
        bench_path="/somewhere/tools/tos_evidence_scan_bench.py",
        bench_sha256="f" * 64,
        bench_in_repo=True,
        error="git exited 128 halfway through",
    )

    assert state.ok is False
    assert state.failures() == ("git exited 128 halfway through",)
    assert "unreadable" in state.summary()


# ---------------------------------------------------------------------------------------
# Review #838 findings — each with the scenario the reviewer named
# ---------------------------------------------------------------------------------------


def _resource_artifact(
    out_dir: Path, step: str, days: int, *, commit: str, digest: str
) -> Path:
    """A finished step's artifact as the driver writes it, with chosen provenance."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{step}-{days}d.resource.json"
    path.write_text(
        json.dumps(
            {"name": step, "checkout": {"repo_commit": commit, "bench_sha256": digest}}
        )
    )
    return path


def test_f1_a_resume_at_a_different_commit_is_refused(tmp_path: Path) -> None:
    """F1, the hole the in-process baseline could not see. `before` today and `after`
    next week are two PROCESSES: each is internally consistent, and together they are a
    pair measured with two different trees. Nothing read what the first one wrote down.
    """
    repo = _make_checkout(tmp_path)
    checkout = _checkout(repo)
    out_dir = tmp_path / "out"
    _resource_artifact(
        out_dir, "before", 1, commit="0" * 40, digest="1" * 64
    )  # measured at X / S1

    record = _preflight(tmp_path, _reader(tmp_path), checkout=checkout, steps=["after"])

    assert record.verdict == "refused"
    check = next(c for c in record.checks if c.check == "matches_earlier_steps")
    assert check.ok is False
    assert "before was measured at 000000000000" in check.detail
    assert "would not come from one tree" in check.detail
    assert "matches_earlier_steps" in (record.refusal or "")


def test_f1_a_resume_from_the_same_tree_is_allowed(tmp_path: Path) -> None:
    """The other direction: the documented resume must still work when nothing moved."""
    repo = _make_checkout(tmp_path)
    checkout = _checkout(repo)
    out_dir = tmp_path / "out"
    (tmp_path / "synth").mkdir()
    (tmp_path / "synth" / "synth-1d.sqlite3").write_bytes(b"")
    _resource_artifact(
        out_dir,
        "before",
        1,
        commit=checkout.baseline.repo_commit,
        digest=checkout.baseline.bench_sha256,
    )

    record = _preflight(tmp_path, _reader(tmp_path), checkout=checkout, steps=["after"])

    assert record.verdict == "ok", record.refusal
    check = next(c for c in record.checks if c.check == "matches_earlier_steps")
    assert check.ok is True
    assert "before at" in check.measured


def test_f1_a_resume_onto_an_artifact_with_no_provenance_is_refused(
    tmp_path: Path,
) -> None:
    """An artifact written before A1-c carries no `checkout` block. That is not a pass:
    "which tree measured this" is exactly the question, and the artifact cannot answer.
    """
    repo = _make_checkout(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    (out_dir / "before-1d.resource.json").write_text(json.dumps({"name": "before"}))

    record = _preflight(
        tmp_path, _reader(tmp_path), checkout=_checkout(repo), steps=["after"]
    )

    assert record.verdict == "refused"
    check = next(c for c in record.checks if c.check == "matches_earlier_steps")
    assert "records no checkout provenance" in check.detail
    assert "produced before A1-c" in check.detail


def test_f1_a_different_size_in_the_same_out_dir_is_not_compared(
    tmp_path: Path,
) -> None:
    """One output directory holds every size (the existing `a1/` does). A 365-day run
    months ago is a DIFFERENT measurement and may legitimately be at another commit —
    comparing it would refuse every real campaign."""
    repo = _make_checkout(tmp_path)
    out_dir = tmp_path / "out"
    _resource_artifact(out_dir, "before", 365, commit="9" * 40, digest="8" * 64)
    (tmp_path / "synth").mkdir()
    (tmp_path / "synth" / "synth-1d.sqlite3").write_bytes(b"")

    record = _preflight(
        tmp_path, _reader(tmp_path), checkout=_checkout(repo), steps=["after"]
    )

    assert record.verdict == "ok", record.refusal


def test_f2_an_untracked_file_hidden_by_the_operators_git_config_is_still_dirty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F2. `status.showUntrackedFiles = no` is a common personal setting, and under the
    plain `--porcelain` this shipped with it made an untracked bench INVISIBLE — the tree
    read clean and both the preflight and the per-step re-check passed."""
    repo = _make_checkout(tmp_path)
    (repo / "tools" / "stray_bench.py").write_text("# nobody committed me\n")
    config = tmp_path / "gitconfig"
    config.write_text("[status]\n\tshowUntrackedFiles = no\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))

    # The premise, measured rather than assumed: plain --porcelain really does hide it.
    plain = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert plain.stdout.strip() == "", "the config is not actually hiding anything"

    state = driver.read_checkout(
        driver_path=repo / "tools" / "tos_evidence_scan_measure.py",
        bench_path=repo / "tools" / "tos_evidence_scan_bench.py",
    )

    assert state.clean is False
    assert "stray_bench.py" in state.dirty_sample
    assert state.ok is False


def test_f2_a_clean_tree_is_still_clean_under_the_same_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both directions: a filter that calls everything dirty is the same bug as no
    filter."""
    repo = _make_checkout(tmp_path)
    config = tmp_path / "gitconfig"
    config.write_text("[status]\n\tshowUntrackedFiles = no\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))

    state = driver.read_checkout(
        driver_path=repo / "tools" / "tos_evidence_scan_measure.py",
        bench_path=repo / "tools" / "tos_evidence_scan_bench.py",
    )

    assert state.clean is True
    assert state.ok is True


def _fake_git(tmp_path: Path, body: str, name: str = "fake-git.sh") -> Path:
    path = tmp_path / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return path


def test_f4_a_git_that_never_answers_is_an_error_not_a_pass(tmp_path: Path) -> None:
    """F4. A `git status` behind somebody's index.lock used to stall the per-child
    re-check forever: no watchdog is watching the driver, and no artifact is written."""
    repo = _make_checkout(tmp_path)
    slow = _fake_git(tmp_path, "sleep 30\nexit 0\n")

    state = driver.read_checkout(
        driver_path=repo / "tools" / "tos_evidence_scan_measure.py",
        bench_path=repo / "tools" / "tos_evidence_scan_bench.py",
        git=(str(slow),),
        timeout_s=0.5,
    )

    assert state.ok is False
    assert "did not answer within 0.5 s" in state.error


def test_f4_a_hung_git_at_the_per_child_recheck_aborts_with_an_artifact(
    tmp_path: Path,
) -> None:
    """And the consequence that matters: it stops the run and says so in a file."""
    repo = _make_checkout(tmp_path)
    good = _checkout(repo)
    slow = _fake_git(tmp_path, "sleep 30\nexit 0\n")
    # Baseline from the real git, re-check through the hung one — the shape of a lock
    # taken by someone else after the run started.
    stalled = dataclasses.replace(good, git=(str(slow),), timeout_s=0.5)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with pytest.raises(driver.MeasureAborted, match="could not be re-read"):
        _run_with(stalled, tmp_path, out_dir=out_dir, name="after")

    record = _abort_record(out_dir, "after-7d")
    assert record["check"] == "checkout_drift"
    assert "did not answer within" in record["reason"]
    assert record["returncode"] is None


def test_f3_a_signal_during_the_pre_spawn_recheck_still_leaves_an_artifact(
    tmp_path: Path,
) -> None:
    """F3. The five git calls take real time and run hours into a measurement. A SIGTERM
    landing in the middle of them escaped with NO artifact — past the handler whose
    docstring says an abort is never silent, whatever caused it."""

    class SignalledCheckout:
        """The guard seam with a signal arriving where the five git calls would be.

        Duck-typed rather than a subclass: `run_step` asks a checkout for exactly
        `read`/`record`/`drift`, and `driver` is loaded by path so its classes are not
        names a type checker can subclass.
        """

        def read(self):
            raise driver.MeasureSignalled("received SIGTERM — terminating the child")

        def record(self, current):
            return {}

        def drift(self, current):
            return None

    guard = SignalledCheckout()
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with pytest.raises(driver.MeasureSignalled):
        _run_with(guard, tmp_path, out_dir=out_dir, name="after")

    record = _abort_record(out_dir, "after-7d")
    assert record["check"] == "driver_signalled"
    assert "SIGTERM" in record["reason"]
    assert record["returncode"] is None
    assert not (tmp_path / "after.out").exists(), "no child should have been started"


def test_f5_output_written_into_the_checkout_is_refused_up_front(
    tmp_path: Path,
) -> None:
    """F5. `--synthetic ./synth-365d.sqlite3` inside the worktree used to pass, then
    `build` spent six minutes and 53 GB, and only then did the `before` re-check abort
    the run blaming "someone working in the tree"."""
    repo = _make_checkout(tmp_path)
    inside = repo / "synth-1d.sqlite3"

    record = driver.preflight(
        run_id="f5",
        guard=_guard(),
        checkout=_checkout(repo),
        reader=_reader(tmp_path),
        out_dir=tmp_path / "out",
        days=1,
        estimator=None,
        expect_bytes=0,
        disk_headroom_ratio=1.0,
        index_growth_ratio=0.0,
        steps=(),
        argv=["run"],
        synthetic=inside,
    )

    assert record.verdict == "refused"
    check = next(c for c in record.checks if c.check == "outputs_outside_the_checkout")
    assert check.ok is False
    assert "--synthetic" in check.measured
    assert "NOT gitignored" in check.measured
    # And the stderr-bound refusal says it too, not only the stdout detail line (F8).
    assert "NOT gitignored" in (record.refusal or "")


def test_f5_a_gitignored_path_inside_the_checkout_is_allowed(tmp_path: Path) -> None:
    """Ignored is the one safe way to be inside: it cannot dirty the tree, and
    `git add -A` will not stage it."""
    repo = _make_checkout(tmp_path)
    (repo / ".gitignore").write_text("synth-*.sqlite3\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "ignore the synthetic")
    _git(repo, "checkout", "-q", "--detach", "HEAD")
    _git(
        repo, "update-ref", "refs/remotes/origin/main", _git(repo, "rev-parse", "HEAD")
    )
    inside = repo / "synth-1d.sqlite3"
    inside.write_bytes(b"")

    record = driver.preflight(
        run_id="f5ok",
        guard=_guard(),
        checkout=_checkout(repo),
        reader=_reader(tmp_path),
        out_dir=tmp_path / "out",
        days=1,
        estimator=None,
        expect_bytes=0,
        disk_headroom_ratio=1.0,
        index_growth_ratio=0.0,
        steps=(),
        argv=["run"],
        synthetic=inside,
    )

    check = next(c for c in record.checks if c.check == "outputs_outside_the_checkout")
    assert check.ok is True, check.measured
    assert record.verdict == "ok", record.refusal


def test_f5_the_output_check_is_not_released_by_the_shared_checkout_hatch(
    tmp_path: Path,
) -> None:
    """Unlike the rest of the guard. The hatch is a choice about where the CODE comes
    from, not a licence to drop a 53 GB file into the repository — the same line
    run_p_ca.sh draws around its own override."""
    repo = _make_checkout(tmp_path)

    record = driver.preflight(
        run_id="f5hatch",
        guard=_guard(),
        checkout=_checkout(repo, enforced=False),
        reader=_reader(tmp_path),
        out_dir=repo / "measure-out",
        days=1,
        estimator=None,
        expect_bytes=0,
        disk_headroom_ratio=1.0,
        index_growth_ratio=0.0,
        steps=(),
        argv=["run"],
        synthetic=tmp_path / "synth.sqlite3",
    )

    check = next(c for c in record.checks if c.check == "outputs_outside_the_checkout")
    assert check.evaluated is True
    assert check.ok is False
    assert "--out-dir" in check.measured
    assert record.verdict == "refused"


def test_f6_a_branch_created_between_steps_aborts_even_at_the_same_commit(
    tmp_path: Path,
) -> None:
    """F6. `git switch -c scratch` leaves the commit and the tree exactly as they were,
    so the first revision's three comparisons all passed — and the next child ran from a
    branch a parallel lane can advance, the very state the preflight refuses."""
    repo = _make_checkout(tmp_path)
    checkout = _checkout(repo)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert _run_with(checkout, tmp_path, out_dir=out_dir, name="build").returncode == 0

    _git(repo, "checkout", "-q", "-b", "scratch")
    assert _git(repo, "rev-parse", "HEAD") == checkout.baseline.repo_commit
    assert _git(repo, "status", "--porcelain") == ""

    with pytest.raises(driver.MeasureAborted, match="no longer satisfies"):
        _run_with(checkout, tmp_path, out_dir=out_dir, name="after")
    record = _abort_record(out_dir, "after-7d")
    assert record["checkout"]["detached"] is False
    assert "HEAD is attached to branch 'scratch'" in record["reason"]


def test_f6_origin_main_moving_away_between_steps_aborts(tmp_path: Path) -> None:
    """The other condition the first revision re-read and never compared."""
    repo = _make_checkout(tmp_path)
    checkout = _checkout(repo)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert _run_with(checkout, tmp_path, out_dir=out_dir, name="build").returncode == 0

    # A fetch lands while the measurement runs and origin/main diverges from HEAD.
    _git(repo, "checkout", "-q", "-B", "side", "HEAD")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "published elsewhere")
    _git(
        repo, "update-ref", "refs/remotes/origin/main", _git(repo, "rev-parse", "HEAD")
    )
    _git(repo, "checkout", "-q", "--detach", checkout.baseline.repo_commit)
    _git(repo, "branch", "-q", "-D", "side")
    assert _git(repo, "rev-parse", "HEAD") == checkout.baseline.repo_commit

    # HEAD is still an ancestor here, so this must NOT abort — the ancestor relation is
    # what the check cares about, not equality with origin/main.
    assert _run_with(checkout, tmp_path, out_dir=out_dir, name="before").returncode == 0

    # Now rewind origin/main behind HEAD: the ancestor relation really is broken.
    _git(repo, "update-ref", "refs/remotes/origin/main", "0" * 40)
    with pytest.raises(driver.MeasureAborted, match="no longer satisfies"):
        _run_with(checkout, tmp_path, out_dir=out_dir, name="after")


def test_f7_a_merge_base_that_fails_is_an_error_not_a_verdict(tmp_path: Path) -> None:
    """F7. Exit 0 is "ancestor" and 1 is "not"; 128 is git failing. Reporting it as
    "not an ancestor" tells the operator to merge code that is already merged."""
    repo = _make_checkout(tmp_path)
    broken = _fake_git(
        tmp_path,
        'for a in "$@"; do\n'
        '  if [ "$a" = "merge-base" ]; then\n'
        '    echo "fatal: bad object origin/main" >&2\n'
        "    exit 128\n"
        "  fi\n"
        "done\n"
        'exec git "$@"\n',
    )

    state = driver.read_checkout(
        driver_path=repo / "tools" / "tos_evidence_scan_measure.py",
        bench_path=repo / "tools" / "tos_evidence_scan_bench.py",
        git=(str(broken),),
    )

    assert state.ok is False
    assert "merge-base exited 128" in state.error
    assert "bad object" in state.error
    # And it must NOT claim the wrong cause.
    assert "is not an ancestor of origin/main" not in "; ".join(state.failures())


def test_f8_the_refusal_names_the_actionable_cause_not_only_the_summary(
    tmp_path: Path,
) -> None:
    """F8. `summary()` for a worktree with no origin/main reads perfectly healthy
    ("detached, clean"), so the operator saw a refusal whose text never said to fetch.
    """
    repo = _make_checkout(tmp_path, origin_main=False)

    record = _preflight(tmp_path, _reader(tmp_path), checkout=_checkout(repo))

    assert record.verdict == "refused"
    assert "git fetch origin" in (record.refusal or "")


def test_f8_the_cli_refusal_on_stderr_carries_the_cause(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The place the operator actually reads."""
    rc = _cli(tmp_path, "--expect-gb", "10000000")
    assert rc == 1
    err = capsys.readouterr().err
    assert "disk_free" in err
    assert "predicted" in err, "the refusal must carry the detail, not only the floor"


def test_f9_children_cannot_import_from_the_shared_checkout(tmp_path: Path) -> None:
    """F9. `--python` is the SHARED checkout's venv by design, and on this host that venv
    carries an editable-install `.pth` putting the shared tree on `sys.path`. Measured:
    `-I` alone does NOT remove it — a child run with `-I` still imported `tools.*` from
    the shared tree while every provenance field described the worktree. `-S` is what
    closes it, and `-I` closes PYTHONPATH and user-site next to it."""
    repo = _make_checkout(tmp_path)
    injected = tmp_path / "injected"
    (injected / "smuggled").mkdir(parents=True)
    (injected / "smuggled" / "__init__.py").write_text(
        "VALUE = 'from the other tree'\n"
    )
    report = tmp_path / "child-report.json"
    probe = _stub_bench(
        tmp_path,
        "    import json, sys\n"
        "    try:\n"
        "        import smuggled\n"
        "        smuggled_from = smuggled.__file__\n"
        "    except ImportError:\n"
        "        smuggled_from = None\n"
        f"    pathlib.Path({str(report)!r}).write_text(json.dumps({{\n"
        '        "isolated": sys.flags.isolated,\n'
        '        "no_site": sys.flags.no_site,\n'
        '        "smuggled_from": smuggled_from,\n'
        '        "sys_path": sys.path,\n'
        "    }))\n",
    )
    steps = driver.plan_steps(
        names=["build"],
        python=sys.executable,
        bench_path=probe,
        reference=tmp_path / "ref.sqlite3",
        synthetic=tmp_path / "s.sqlite3",
        out_dir=tmp_path,
        days=1,
        repeats=1,
        session_hours=7.0,
        reference_minutes=15.0,
        boot_once_max_rows=1,
        batch_rows=10,
    )
    assert steps[0].argv[1:3] == driver.CHILD_PYTHON_FLAGS

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    env_before = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = str(injected)
    try:
        result = driver.run_step(
            steps[0],
            guard=_guard(),
            checkout=_checkout(repo),
            reader=driver.HostReader(),
            run_id="isolation",
            days=1,
            out_dir=out_dir,
            log=lambda _m: None,
            sampler=_healthy(),
        )
    finally:
        if env_before is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = env_before

    assert result.returncode == 0, (tmp_path / "build.err").read_text()
    payload = json.loads(report.read_text())
    assert payload["isolated"] == 1
    assert payload["no_site"] == 1
    assert payload["smuggled_from"] is None, "PYTHONPATH reached the child"
    assert str(injected) not in payload["sys_path"]
    # And the artifact says which flags were in force, so the question is answerable
    # afterwards from the file rather than from this test.
    assert result.checkout["child_python_flags"] == list(driver.CHILD_PYTHON_FLAGS)


def test_f10_the_shared_guard_is_built_once_not_per_test() -> None:
    """F10. `_clean_checkout()` used to re-run `with_baseline()` — five git subprocesses
    — on every one of ~50 tests, over a repo that never changes."""
    first = _clean_checkout()
    second = _clean_checkout()

    assert first is second
    assert first.baseline is not None
    # The non-enforcing view is the same baseline, not a second read.
    assert _clean_checkout(enforced=False).baseline is first.baseline


# ---------------------------------------------------------------------------------------
# Plan §7.1.23 "답하지 못한 것" 3 and "계획에 바꾸는 것" 3 — the two follow-ups the
# 270-day measurement registered against this driver
# ---------------------------------------------------------------------------------------
#
# Both are about what a RESUME does to the previous attempt's evidence. The 270-day
# campaign stopped twice in one output directory and finished on the third run, and both
# defects only exist because that happened:
#
#   1. the abort record's name carried no run id, so the second stop silently overwrote
#      the first one's `reason` / `signal_sent` / `returncode` / `partial_resource`;
#   2. a resume that succeeds never says anything about the synthetic file, because the
#      driver only disposes of a file it built in the same run — so 36-53 GB sat on the
#      host with nothing in the log saying it was the operator's to remove.


def test_two_stops_in_one_output_directory_leave_two_abort_records(
    tmp_path: Path,
) -> None:
    """Plan §7.1.23: the 270-day run was stopped twice and only ONE record survived.

    `.out`/`.err` were moved aside under their run id (both pairs are still on the host),
    the JSON was not — so the plan had to cite the first stop's burned wall clock as "≥",
    reconstructed from `watchdog.jsonl`, and its `reason` / `signal_sent` / `returncode` /
    `partial_resource` are simply gone. Two stops, two records.
    """
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    aborting = _reader_that_reports_a_build_once(
        tmp_path, gate=out_dir / "before-1d.out"
    )

    # First stop: build succeeds, `before` is aborted by the competing build.
    assert _cli(tmp_path, out_dir=out_dir, synthetic=synthetic, reader=aborting) == 1
    # Second stop: the documented resume, aborted at the same place by the same host.
    assert (
        _cli(
            tmp_path,
            "--steps",
            "before,after",
            out_dir=out_dir,
            synthetic=synthetic,
            reader=aborting,
        )
        == 1
    )

    records = _abort_records(out_dir, "before-1d")
    assert len(records) == 2, (
        "the second stop overwrote the first one's record — "
        f"found {[p.name for p in records]}"
    )
    first, second = (json.loads(p.read_text()) for p in records)
    assert first["run_id"] != second["run_id"]
    # Each record is a whole record, not a pointer: the fields the plan lost are present
    # in BOTH.
    for record in (first, second):
        assert record["check"] == "competing_build"
        assert record["reason"]
        assert record["signal_sent"] == "SIGTERM"
        assert record["returncode"] is not None
        assert record["partial_resource"]["proc_io"]
    assert first != second

    # And the moved-aside streams of both attempts are still next to them, which is the
    # convention the JSON now follows.
    assert len(list(out_dir.glob("before-1d.*.aborted.out"))) == 2


def test_an_abort_record_names_the_run_that_wrote_it_in_the_file_and_inside(
    tmp_path: Path,
) -> None:
    """The run id in the name is the same run id the record already carried.

    A name that disagrees with the payload would be worse than the fixed name: it would
    look like per-run evidence while attributing it to the wrong run.
    """
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    aborting = _reader_that_reports_a_build_once(
        tmp_path, gate=out_dir / "before-1d.out"
    )

    assert _cli(tmp_path, out_dir=out_dir, synthetic=synthetic, reader=aborting) == 1

    (path,) = _abort_records(out_dir, "before-1d")
    record = json.loads(path.read_text())
    assert path.name == f"ABORTED-before-1d.{record['run_id']}.json"
    # The same run id is in the preflight record and in the watchdog series, so the three
    # can be joined without guessing.
    assert json.loads((out_dir / "preflight.json").read_text())["run_id"] == (
        record["run_id"]
    )
    watchdog = [
        json.loads(line)
        for line in (out_dir / "watchdog.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert {row["run_id"] for row in watchdog} == {record["run_id"]}


def test_the_preflight_accepts_an_output_directory_full_of_abort_records(
    tmp_path: Path,
) -> None:
    """`artifacts_absent` guards the STEP artifacts, and an abort record is not one.

    Written down because the run-id suffix changes those names: a check that started
    counting them would refuse every resume after the second stop — exactly the directory
    the 270-day measurement finished in.
    """
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    synthetic.parent.mkdir(parents=True)
    synthetic.write_bytes(b"x" * 4096)
    for run_id in ("e1a9dcb24f64", "9e41a6d809e6", "89841a926bd6"):
        (out_dir / f"ABORTED-before-1d.{run_id}.json").write_text(
            json.dumps({"run_id": run_id, "step": "before", "days": 1})
        )
    # The pre-run-id name too: a directory that predates this change still resumes.
    (out_dir / "ABORTED-before-1d.json").write_text(json.dumps({"step": "before"}))

    record = _preflight(tmp_path, _reader(tmp_path), steps=["before", "after"])

    assert record.verdict == "ok", _failed(record)
    assert (
        next(c for c in record.checks if c.check == "artifacts_absent").measured
        == "none present"
    )


def test_a_resume_that_finishes_says_the_synthetic_is_not_its_to_delete(
    tmp_path: Path,
) -> None:
    """Plan §7.1.23 "뒤처리": 40 GB (36-53 GB across the campaign) stayed on the host and
    the run that finished the measurement said nothing about it.

    The driver disposes only of a file it built in the same run — correct, and the reason
    the 180- and 270-day index sizes could be read at all — but silence is what made the
    deletion a step the operator had to remember on their own.
    """
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    assert _cli(tmp_path, "--steps", "build", out_dir=out_dir, synthetic=synthetic) == 0
    assert synthetic.exists(), "`--steps build` leaves the pair unmeasured, so it stays"
    assert (
        "keep-unmeasured"
        in json.loads(next(iter(out_dir.glob("run-1d.*.summary.json"))).read_text())[
            "synthetic"
        ]["action"]
    )

    assert (
        _cli(tmp_path, "--steps", "before,after", out_dir=out_dir, synthetic=synthetic)
        == 0
    )

    assert synthetic.exists(), "a file this run did not build must survive by default"
    log = (out_dir / "measure-1d.log").read_text()
    assert "KEPT synthetic" in log
    assert "not built by this run" in log
    assert f"rm {synthetic}" in log, "the log must carry the exact command"
    # Printed once where the decision is made and once in the closing summary, so a
    # scrollback that lost the middle of a three-hour run still ends with it.
    assert log.count(f"rm {synthetic}") >= 2


def test_a_resume_can_opt_into_deleting_the_synthetic_it_did_not_build(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    assert _cli(tmp_path, "--steps", "build", out_dir=out_dir, synthetic=synthetic) == 0

    assert (
        _cli(
            tmp_path,
            "--steps",
            "before,after",
            "--delete-synthetic-on-success",
            out_dir=out_dir,
            synthetic=synthetic,
        )
        == 0
    )

    assert not synthetic.exists()
    assert "removed synthetic" in (out_dir / "measure-1d.log").read_text()


def test_the_opt_in_delete_is_refused_when_the_pair_would_not_be_measured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--steps before --delete-synthetic-on-success` would throw the file away BETWEEN
    the two halves of the pair — every planned step ran, and `after` still needs it."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    synthetic.parent.mkdir(parents=True)
    synthetic.write_bytes(b"x" * 4096)

    rc = _cli(
        tmp_path,
        "--steps",
        "before",
        "--delete-synthetic-on-success",
        out_dir=out_dir,
        synthetic=synthetic,
    )

    assert rc == 1
    assert "--delete-synthetic-on-success" in capsys.readouterr().err
    assert synthetic.exists()
    assert not (out_dir / "before-1d.json").exists(), "nothing may have started"


def test_the_opt_in_delete_and_keep_synthetic_cannot_both_be_asked_for(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"

    rc = _cli(
        tmp_path,
        "--keep-synthetic",
        "--delete-synthetic-on-success",
        out_dir=out_dir,
        synthetic=synthetic,
    )

    assert rc == 1
    err = capsys.readouterr().err
    assert "--keep-synthetic" in err and "--delete-synthetic-on-success" in err
    assert not synthetic.exists(), "nothing may have been built"


def test_the_disposition_covers_the_resume_cases_the_plan_hit(tmp_path: Path) -> None:
    """The branches the CLI tests below reach, as the pure decision they come from."""
    path = tmp_path / "synth-270d.sqlite3"
    forty = 40_099_414_016  # the kept 270-day file, plan §7.1.23

    kept = driver.decide_synthetic_disposition(
        path,
        remaining=[],
        size_bytes=forty,
        created_by_this_run=False,
        before_measured=True,
        after_measured=True,
    )
    assert kept.action == "keep-not-ours"
    assert "not built by this run" in kept.message
    assert f"rm {path}" in kept.message
    assert "40.10 GB" in kept.message, "decimal GB, the base the plan is written in"

    deleted = driver.decide_synthetic_disposition(
        path,
        remaining=[],
        size_bytes=forty,
        created_by_this_run=False,
        before_measured=True,
        after_measured=True,
        delete_on_success=True,
    )
    assert deleted.action == "delete"

    # An unfinished resume is never deleted, whatever the flag says.
    aborted = driver.decide_synthetic_disposition(
        path,
        remaining=["after"],
        size_bytes=forty,
        created_by_this_run=False,
        before_measured=True,
        after_measured=False,
        delete_on_success=True,
    )
    assert aborted.action == "keep-resumable"
    assert "--steps after" in aborted.message


@pytest.mark.parametrize("created_by_this_run", [True, False])
@pytest.mark.parametrize(
    ("before_measured", "after_measured", "missing"),
    [(True, False, "after"), (False, True, "before"), (False, False, "before,after")],
)
def test_an_unmeasured_pair_is_never_deleted_on_either_branch(
    tmp_path: Path,
    created_by_this_run: bool,
    before_measured: bool,
    after_measured: bool,
    missing: str,
) -> None:
    """Review #853 findings 1 and 2, as one property on both branches.

    Finding 1: `--steps after --delete-synthetic-on-success` satisfied a POSITIONAL check
    ("is the string `after` in --steps") and deleted a pair whose `before` had never run.
    Finding 2: the created-by-this-run branch did not read the distinction at all, so
    `--steps build` deleted the file it had just spent hours building, with the bare
    message `removed synthetic <path>`.

    Both are the same invariant — a pair that is not measured is not finished with — and
    the flag must not be able to buy its way past it.
    """
    path = tmp_path / "synth-270d.sqlite3"
    for delete_on_success in (False, True):
        decision = driver.decide_synthetic_disposition(
            path,
            remaining=[],
            size_bytes=40_099_414_016,
            created_by_this_run=created_by_this_run,
            before_measured=before_measured,
            after_measured=after_measured,
            delete_on_success=delete_on_success,
        )
        assert decision.action == "keep-unmeasured", (
            f"deleted an unmeasured pair (missing {missing}, "
            f"created={created_by_this_run}, flag={delete_on_success})"
        )
        assert f"--steps {missing}" in decision.message
        assert "40.10 GB" in decision.message
        assert f"rm {path}" in decision.message


def test_keep_synthetic_is_answered_before_the_provenance_split(
    tmp_path: Path,
) -> None:
    """Review #853 finding 5. On a resume `--keep-synthetic` fell through to the
    not-ours branch, which recommends `--delete-synthetic-on-success` — the one flag the
    startup refusal rejects next to `--keep-synthetic`."""
    path = tmp_path / "synth-270d.sqlite3"

    decision = driver.decide_synthetic_disposition(
        path,
        remaining=[],
        size_bytes=40_099_414_016,
        created_by_this_run=False,
        before_measured=True,
        after_measured=True,
        keep_requested=True,
    )

    assert decision.action == "keep-requested"
    assert "--keep-synthetic" in decision.message
    assert (
        "--delete-synthetic-on-success" not in decision.message
    ), "recommended the flag that cannot be combined with the one that was passed"
    assert "not built by this run" in decision.message, "the provenance is still said"
    assert f"rm {path}" in decision.message


def test_the_rm_command_is_quoted_for_a_path_a_shell_would_split(
    tmp_path: Path,
) -> None:
    """Review #853 finding 6. `delete_command` is documented as paste-ready; an unquoted
    path with a space is a two-operand `rm` against a 26-53 GB clean-up."""
    path = tmp_path / "a dir with spaces" / "synth-270d.sqlite3"

    for decision in (
        driver.decide_synthetic_disposition(
            path,
            remaining=[],
            size_bytes=40_099_414_016,
            created_by_this_run=False,
            before_measured=True,
            after_measured=True,
        ),
        driver.decide_synthetic_disposition(
            path,
            remaining=["after"],
            size_bytes=40_099_414_016,
            created_by_this_run=True,
            before_measured=True,
            after_measured=False,
        ),
    ):
        assert f"rm {shlex.quote(str(path))}" in decision.message
        assert f"rm {path} " not in decision.message


def test_the_run_summary_records_the_disposition_for_the_plan_to_cite(
    tmp_path: Path,
) -> None:
    """A log line is for a human; the plan cites fields. The disposition is both."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    assert _cli(tmp_path, "--steps", "build", out_dir=out_dir, synthetic=synthetic) == 0
    assert (
        _cli(tmp_path, "--steps", "before,after", out_dir=out_dir, synthetic=synthetic)
        == 0
    )

    summaries = sorted(out_dir.glob("run-1d.*.summary.json"))
    assert len(summaries) == 2, "one per run, named by run id like every other artifact"
    resume = json.loads(summaries[-1].read_text())
    build_run = json.loads(summaries[0].read_text())
    if resume["steps_planned"] == ["build"]:  # glob order is by run id, not by time
        resume, build_run = build_run, resume

    assert resume["outcome"] == "ok"
    assert resume["steps_planned"] == ["before", "after"]
    assert resume["steps_completed"] == ["before", "after"]
    assert resume["steps_remaining"] == []
    assert f"run-1d.{resume['run_id']}.summary.json" in {p.name for p in summaries}
    blob = resume["synthetic"]
    assert blob["path"] == str(synthetic)
    assert blob["created_by_this_run"] is False
    assert blob["exists_after_the_run"] is True
    assert blob["action"] == "keep-not-ours"
    assert blob["delete_command"] == f"rm {synthetic}"
    assert blob["size_bytes"] == synthetic.stat().st_size

    assert build_run["synthetic"]["created_by_this_run"] is True
    assert build_run["synthetic"]["action"] == "keep-unmeasured"


def test_the_run_summary_is_written_when_the_run_is_aborted_too(
    tmp_path: Path,
) -> None:
    """The summary is most useful on the run that did NOT finish — it is where the abort
    record, the kept file and the resume command are named in one place."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    aborting = _reader_that_reports_a_build_once(
        tmp_path, gate=out_dir / "before-1d.out"
    )

    assert _cli(tmp_path, out_dir=out_dir, synthetic=synthetic, reader=aborting) == 1

    (summary_path,) = list(out_dir.glob("run-1d.*.summary.json"))
    summary = json.loads(summary_path.read_text())
    (abort_path,) = _abort_records(out_dir, "before-1d")
    assert summary["outcome"] == "aborted"
    assert summary["run_id"] == json.loads(abort_path.read_text())["run_id"]
    assert summary["steps_completed"] == ["build"]
    assert summary["steps_remaining"] == ["before", "after"]
    assert summary["abort_records"] == [abort_path.name]
    assert summary["synthetic"]["action"] == "keep-resumable"
    assert summary["synthetic"]["created_by_this_run"] is True


def test_the_summary_records_the_file_size_even_when_it_deletes_the_file(
    tmp_path: Path,
) -> None:
    """§7.1.15 "답하지 못한 것" 3 / §7.1.23 4, partially: the size after the last step.

    The size the plan wanted is the one AFTER `after` creates the index, and it was
    readable only off a synthetic file that happened to survive — the default run deletes
    it and recorded nothing. The number is read at disposition time, so it is in the
    summary whichever way the file goes.
    """
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"

    assert _cli(tmp_path, out_dir=out_dir, synthetic=synthetic) == 0

    assert not synthetic.exists(), "the default run still deletes what it built"
    (summary_path,) = list(out_dir.glob("run-1d.*.summary.json"))
    blob = json.loads(summary_path.read_text())["synthetic"]
    assert blob["action"] == "delete"
    assert blob["exists_after_the_run"] is False
    assert blob["delete_command"] is None
    assert isinstance(blob["size_bytes"], int) and blob["size_bytes"] > 0


# ---------------------------------------------------------------------------------------
# Independent review #853 findings — each with the scenario the reviewer reproduced
# ---------------------------------------------------------------------------------------


def test_f1_the_opt_in_delete_is_refused_when_before_was_never_measured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F1. `--steps after --delete-synthetic-on-success` on a pre-built file satisfied the
    positional check ("is `after` in --steps"), ran only `after`, and deleted the
    synthetic with `before` never measured — the exact case the refusal's own message said
    it existed to stop. `matches_earlier_steps` passes vacuously with no earlier artifact,
    so nothing else caught it."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    assert _cli(tmp_path, "--steps", "build", out_dir=out_dir, synthetic=synthetic) == 0
    assert synthetic.exists()
    capsys.readouterr()

    rc = _cli(
        tmp_path,
        "--steps",
        "after",
        "--delete-synthetic-on-success",
        out_dir=out_dir,
        synthetic=synthetic,
    )

    assert rc == 1
    err = capsys.readouterr().err
    assert "UNMEASURED" in err and "before" in err
    assert synthetic.exists(), "the unmeasured pair's file was deleted"
    assert not (out_dir / "after-1d.json").exists(), "nothing may have started"


def test_f1_the_opt_in_delete_is_allowed_once_before_is_on_disk_for_this_file(
    tmp_path: Path,
) -> None:
    """The other direction of F1: the property is "is this pass recorded", so a `before`
    that already ran in this directory against THIS file unlocks it."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    assert (
        _cli(tmp_path, "--steps", "build,before", out_dir=out_dir, synthetic=synthetic)
        == 0
    )
    assert (out_dir / "before-1d.resource.json").is_file()

    rc = _cli(
        tmp_path,
        "--steps",
        "after",
        "--delete-synthetic-on-success",
        out_dir=out_dir,
        synthetic=synthetic,
    )

    assert rc == 0
    assert not synthetic.exists(), "both halves are measured, so the opt-in applies"


def test_f1_a_recorded_before_that_measured_a_different_file_does_not_unlock_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An output directory can be reused. A `before-1d.resource.json` naming a different
    `--db` is evidence about a different file, and a positional "the artifact exists"
    check would be the same shape of defect F1 is."""
    out_dir = tmp_path / "out"
    other = tmp_path / "synth" / "synth-other.sqlite3"
    assert (
        _cli(tmp_path, "--steps", "build,before", out_dir=out_dir, synthetic=other) == 0
    )
    assert (out_dir / "before-1d.resource.json").is_file()

    wanted = tmp_path / "synth" / "synth-1d.sqlite3"
    wanted.write_bytes(other.read_bytes())
    capsys.readouterr()

    rc = _cli(
        tmp_path,
        "--steps",
        "after",
        "--delete-synthetic-on-success",
        out_dir=out_dir,
        synthetic=wanted,
    )

    assert rc == 1
    assert "names a different --db" in capsys.readouterr().err
    assert wanted.exists()


def test_f2_a_build_only_run_keeps_the_file_and_says_the_pair_is_unmeasured(
    tmp_path: Path,
) -> None:
    """F2. `run --steps build` (and `build,before`) deleted the file it had just spent
    hours building, with the bare message `removed synthetic <path>`."""
    for steps, missing in (("build", "before,after"), ("build,before", "after")):
        out_dir = tmp_path / f"out-{steps.replace(',', '-')}"
        synthetic = tmp_path / "synth" / f"synth-{steps.replace(',', '-')}.sqlite3"

        assert (
            _cli(tmp_path, "--steps", steps, out_dir=out_dir, synthetic=synthetic) == 0
        )

        assert synthetic.exists(), f"--steps {steps} deleted an unmeasured pair"
        log = (out_dir / "measure-1d.log").read_text()
        assert "KEPT synthetic" in log and f"--steps {missing}" in log
        blob = json.loads(
            next(iter(out_dir.glob("run-1d.*.summary.json"))).read_text()
        )["synthetic"]
        assert blob["action"] == "keep-unmeasured"
        assert blob["exists_after_the_run"] is True


def test_f3_an_unlink_that_fails_still_leaves_the_summary_log_and_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F3. The `stat()` and the bare `unlink()` ran on every run including aborts, outside
    any guard. An OSError there left the `finally` with an exception the outer handler
    does not name: it replaced the in-flight failure and skipped the summary, the closing
    lines, the `measure-<days>d.log` append — the ONLY write of the buffered log — and
    `release_lock`."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    real_unlink = Path.unlink

    def exploding_unlink(self: Path, *args: Any, **kwargs: Any) -> None:
        if self == synthetic:
            raise PermissionError(13, "Permission denied", str(self))
        real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", exploding_unlink)

    rc = _cli(tmp_path, out_dir=out_dir, synthetic=synthetic)

    assert rc == 0, "a clean-up that could not happen is not a failed measurement"
    assert synthetic.exists(), "the file really is still there"
    log = (out_dir / "measure-1d.log").read_text()
    assert "COULD NOT remove synthetic" in log
    assert "##### summary" in log, "the run log survived the failing unlink"
    blob = json.loads(next(iter(out_dir.glob("run-1d.*.summary.json"))).read_text())
    assert blob["synthetic"]["action"] == "delete-failed"
    assert "PermissionError" in blob["synthetic"]["message"]
    assert blob["synthetic"]["delete_command"] == f"rm {synthetic}"
    assert not (out_dir / driver.LOCK_NAME).exists(), "the lock was never released"


def test_f3_a_stat_that_fails_does_not_replace_the_runs_real_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other unguarded call. The run here is already failing; the `stat` must not
    overwrite why."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    real_stat = Path.stat

    def exploding_stat(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self == synthetic:
            raise OSError(5, "Input/output error", str(self))
        return real_stat(self, *args, **kwargs)

    # Armed only once the steps are over, so the preflight's own reads are untouched and
    # the failure lands exactly where the guard is. `--repeats 0` makes the bench refuse,
    # so `before` exits 1 after `build` succeeded.
    armed: list[bool] = []
    real_run_step = driver.run_step

    def arming_run_step(*args: Any, **kwargs: Any) -> Any:
        result = real_run_step(*args, **kwargs)
        armed.append(True)
        return result

    monkeypatch.setattr(driver, "run_step", arming_run_step)
    monkeypatch.setattr(
        Path,
        "stat",
        lambda self, *a, **k: (
            exploding_stat(self, *a, **k) if armed else real_stat(self, *a, **k)
        ),
    )
    rc = _cli(tmp_path, "--repeats", "0", out_dir=out_dir, synthetic=synthetic)

    assert rc == 1
    log = (out_dir / "measure-1d.log").read_text()
    assert "could not tell whether" in log or "could not stat" in log
    blob = json.loads(next(iter(out_dir.glob("run-1d.*.summary.json"))).read_text())
    assert blob["outcome"] == "step-failed", "the stat error replaced the real outcome"
    assert blob["synthetic"]["size_bytes"] is None
    assert (
        blob["synthetic"]["exists_after_the_run"] is None
    ), "an I/O error must not be recorded as 'the file is gone'"
    assert not (out_dir / driver.LOCK_NAME).exists()


def test_f4_a_preflight_refusal_writes_a_summary_and_an_argument_one_does_not(
    tmp_path: Path,
) -> None:
    """F4. `_run_outcome` said `"refused" is the preflight`, but every preflight refusal
    is raised before the inner `try` and wrote no summary at all — a documented artifact
    state that could not occur."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"

    assert (
        _cli(
            tmp_path,
            "--min-available-gb",
            "999999",
            out_dir=out_dir,
            synthetic=synthetic,
        )
        == 1
    )

    (summary_path,) = list(out_dir.glob("run-1d.*.summary.json"))
    summary = json.loads(summary_path.read_text())
    assert summary["outcome"] == "refused"
    assert "mem_available" in str(summary["refusal"])
    assert summary["steps_completed"] == []
    assert summary["synthetic"]["exists_after_the_run"] is False

    # An argument contradiction is refused before the output directory exists, so it
    # leaves nothing — like any argparse error, and the docstrings now say so.
    bare = tmp_path / "never-created"
    assert (
        _cli(
            tmp_path,
            "--keep-synthetic",
            "--delete-synthetic-on-success",
            out_dir=bare,
            synthetic=tmp_path / "synth" / "synth-x.sqlite3",
        )
        == 1
    )
    assert not bare.exists(), "a refused argument must not leave a directory behind"


def test_f4_the_outcome_names_which_of_the_four_stopped_the_run(
    tmp_path: Path,
) -> None:
    """Collapsing `step-failed` / `signalled` / `aborted` to one word survived the first
    revision's tests. Each is pinned here against the thing that produces it."""
    failed_dir = tmp_path / "failed"
    assert (
        _cli(
            tmp_path,
            "--repeats",
            "0",
            out_dir=failed_dir,
            synthetic=tmp_path / "synth" / "a.sqlite3",
        )
        == 1
    )
    assert _summary_outcome(failed_dir) == "step-failed"

    aborted_dir = tmp_path / "aborted"
    assert (
        _cli(
            tmp_path,
            out_dir=aborted_dir,
            synthetic=tmp_path / "synth" / "b.sqlite3",
            reader=_reader_that_reports_a_build_once(
                tmp_path, gate=aborted_dir / "before-1d.out"
            ),
        )
        == 1
    )
    assert _summary_outcome(aborted_dir) == "aborted"

    assert driver._run_outcome(driver.MeasureSignalled("SIGTERM")) == "signalled"
    assert driver._run_outcome(driver.MeasureRefused("no")) == "refused"
    assert driver._run_outcome(None) == "ok"
    assert driver._run_outcome(RuntimeError("x")).startswith("error (")


def test_f5_keep_synthetic_on_a_resume_is_recorded_and_recommends_nothing_it_refuses(
    tmp_path: Path,
) -> None:
    """F5, through the CLI: `--steps before,after --keep-synthetic` on a resume yielded
    `keep-not-ours` and told the operator to pass `--delete-synthetic-on-success`, which
    the startup refusal rejects next to `--keep-synthetic`; `--keep-synthetic` left no
    trace in the summary at all."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    assert _cli(tmp_path, "--steps", "build", out_dir=out_dir, synthetic=synthetic) == 0

    assert (
        _cli(
            tmp_path,
            "--steps",
            "before,after",
            "--keep-synthetic",
            out_dir=out_dir,
            synthetic=synthetic,
        )
        == 0
    )

    assert synthetic.exists()
    blob = json.loads(
        sorted(out_dir.glob("run-1d.*.summary.json"), key=lambda p: p.stat().st_mtime)[
            -1
        ].read_text()
    )["synthetic"]
    assert blob["action"] == "keep-requested"
    assert "--delete-synthetic-on-success" not in blob["message"]


def test_f6_the_rm_command_in_the_artifact_is_quoted(tmp_path: Path) -> None:
    """F6 through the CLI: `delete_command` is what the plan's clean-up paragraph pastes."""
    out_dir = tmp_path / "an out dir with spaces"
    synthetic = tmp_path / "synth dir" / "synth-1d.sqlite3"

    assert _cli(tmp_path, "--steps", "build", out_dir=out_dir, synthetic=synthetic) == 0

    blob = json.loads(next(iter(out_dir.glob("run-1d.*.summary.json"))).read_text())[
        "synthetic"
    ]
    assert blob["delete_command"] == f"rm {shlex.quote(str(synthetic))}"
    assert shlex.split(blob["delete_command"])[1:] == [str(synthetic)]


def test_the_opt_in_delete_is_refused_when_the_run_builds_the_file_itself(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Note d. The flag says RESUME; with `build` in --steps it was accepted as a no-op,
    which reads as asking for something it is not doing."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"

    rc = _cli(
        tmp_path, "--delete-synthetic-on-success", out_dir=out_dir, synthetic=synthetic
    )

    assert rc == 1
    assert "--steps includes build" in capsys.readouterr().err
    assert not out_dir.exists()


def test_the_synthetic_may_not_be_the_reference_itself(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Note h. The one file the driver must never build onto or delete is the real
    evidence store it is replicating. Checked on resolved paths, not strings."""
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    out_dir = tmp_path / "out"

    rc = _cli(
        tmp_path,
        reference=reference,
        out_dir=out_dir,
        synthetic=tmp_path / "." / "evidence.sqlite3",
    )

    assert rc == 1
    assert "--synthetic and --reference are the same file" in capsys.readouterr().err
    assert reference.exists() and not out_dir.exists()


@pytest.mark.serial
def test_a_stop_signal_during_the_end_of_run_bookkeeping_is_deferred_not_lost(
    tmp_path: Path,
) -> None:
    """Note g. The end-of-run block got longer in this revision, and every write in it is
    the only write of what it writes. A SIGTERM landing inside used to raise straight out
    of the `finally` and take the run log with it.

    Blocked, not ignored: the operator's stop request is still delivered, after the
    bookkeeping and after the handlers are restored.
    """
    previous = driver._install_signal_handlers()
    held = None
    try:
        held = driver._hold_stop_signals()
        assert held is not None, "this platform must be able to block SIGTERM"
        os.kill(os.getpid(), signal.SIGTERM)
        # Still running: the signal is pending, not delivered, so bookkeeping finishes.
        marker = tmp_path / "written-while-held"
        marker.write_text("the finally got to run")
        assert marker.read_text() == "the finally got to run"
        assert signal.SIGTERM in signal.sigpending()

        with pytest.raises(driver.MeasureSignalled):
            driver._release_stop_signals(held)
        held = None
    finally:
        if held is not None:  # pragma: no cover - only on an unexpected failure above
            driver._release_stop_signals(held)
        driver._restore_signal_handlers(previous)


def test_the_closing_summary_survives_a_summary_write_that_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `#####` lines sat in the `else` of the summary-write try, so one ENOSPC took
    both the artifact and the closing lines out of the run log — the one place a reader
    who lost the middle of a three-hour scrollback still looks."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"

    def refuse(*_args: Any, **_kwargs: Any) -> Path:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(driver, "write_run_summary", refuse)

    assert _cli(tmp_path, "--steps", "build", out_dir=out_dir, synthetic=synthetic) == 0

    log = (out_dir / "measure-1d.log").read_text()
    assert not list(out_dir.glob("run-1d.*.summary.json")), "the write really failed"
    assert "could not write the run summary" in log
    assert "##### summary (run " in log
    assert "##### synthetic: KEPT synthetic" in log


def test_the_end_of_run_bookkeeping_runs_with_stop_signals_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hold is wired into the `finally`, and the mask is put back before main returns.

    Without the second half a successful run would leave the caller's process unable to
    receive SIGTERM at all.
    """
    calls: list[str] = []
    real_hold = driver._hold_stop_signals
    real_release = driver._release_stop_signals

    def hold() -> Any:
        calls.append("hold")
        return real_hold()

    def release(previous: Any) -> None:
        calls.append("release")
        real_release(previous)

    monkeypatch.setattr(driver, "_hold_stop_signals", hold)
    monkeypatch.setattr(driver, "_release_stop_signals", release)

    assert (
        _cli(
            tmp_path,
            "--steps",
            "build",
            out_dir=tmp_path / "out",
            synthetic=tmp_path / "synth" / "synth-1d.sqlite3",
        )
        == 0
    )

    assert calls == ["hold", "release"], "the bookkeeping ran unprotected"
    assert signal.SIGTERM not in signal.pthread_sigmask(signal.SIG_BLOCK, [])


def test_a_file_that_vanishes_between_the_exists_and_the_stat_is_not_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second half of F3's guard: `exists()` then `stat()` is two syscalls, and the
    file can go between them (another cleanup, a filling disk). The `stat` raising there
    must not take the summary, the run log and the lock with it — and "I could not tell"
    must not be written down as "it is gone"."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    armed: list[bool] = []
    real_run_step = driver.run_step

    def arming_run_step(*args: Any, **kwargs: Any) -> Any:
        result = real_run_step(*args, **kwargs)
        armed.append(True)
        return result

    monkeypatch.setattr(driver, "run_step", arming_run_step)
    # The race, made deterministic: `exists()` says yes, and by the `stat()` it is gone.
    monkeypatch.setattr(
        driver, "_exists_or_unknown", lambda path: True if armed else path.exists()
    )
    real_stat = Path.stat

    def vanished_stat(self: Path, *a: Any, **k: Any) -> Any:
        if armed and self == synthetic:
            raise FileNotFoundError(2, "No such file or directory", str(self))
        return real_stat(self, *a, **k)

    monkeypatch.setattr(Path, "stat", vanished_stat)

    assert _cli(tmp_path, "--steps", "build", out_dir=out_dir, synthetic=synthetic) == 0

    log = (out_dir / "measure-1d.log").read_text()
    assert "could not stat the synthetic file" in log
    assert "##### summary" in log
    blob = json.loads(next(iter(out_dir.glob("run-1d.*.summary.json"))).read_text())
    assert blob["synthetic"]["size_bytes"] is None
    assert (
        blob["synthetic"]["exists_after_the_run"] is None
    ), "a stat that failed is 'cannot tell', not 'the file is gone'"
    assert (
        blob["synthetic"]["action"] is None
    ), "no disposition without a size to report"
    assert not (out_dir / driver.LOCK_NAME).exists()


def test_n1_an_argument_contradiction_writes_nothing_into_a_directory_that_exists(
    tmp_path: Path,
) -> None:
    """Round-2 N1. The claim "an argument contradiction is refused before anything is
    created and leaves nothing behind" was gated on `out_dir.exists()`, so it held only
    for the one input the first test used — a directory that was not there yet.

    `--delete-synthetic-on-success` is a RESUME flag, so by the time anyone passes it the
    output directory normally holds the earlier steps, and a contradiction was dropping a
    `refused` summary into it.
    """
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    assert _cli(tmp_path, "--steps", "build", out_dir=out_dir, synthetic=synthetic) == 0
    before = {p.name for p in out_dir.iterdir()}
    assert any(
        n.startswith("run-1d.") for n in before
    ), "the first run really wrote one"

    rc = _cli(
        tmp_path,
        "--steps",
        "before,after",
        "--keep-synthetic",
        "--delete-synthetic-on-success",
        out_dir=out_dir,
        synthetic=synthetic,
    )

    assert rc == 1
    assert {
        p.name for p in out_dir.iterdir()
    } == before, "a refused argument wrote into a directory it does not own"


def test_n2_a_refusal_raised_inside_the_run_carries_its_reason(tmp_path: Path) -> None:
    """Round-2 N2. `MeasureRefused` also comes from inside the run — `_spawn` cannot find
    the interpreter, the host reader gives up — and the summary was the only place that
    would say why, with `refusal: null`."""
    out_dir = tmp_path / "out"

    rc = _cli(
        tmp_path,
        "--python",
        "definitely-not-a-real-interpreter",
        out_dir=out_dir,
        synthetic=tmp_path / "synth" / "synth-1d.sqlite3",
    )

    assert rc == 1
    summary = json.loads(next(iter(out_dir.glob("run-1d.*.summary.json"))).read_text())
    assert summary["outcome"] == "refused"
    assert "definitely-not-a-real-interpreter" in str(summary["refusal"])
    assert summary["steps_completed"] == []


def test_n3_a_preflight_refusal_still_says_what_it_was_going_to_run(
    tmp_path: Path,
) -> None:
    """Round-2 N3. `plan_steps` has already run by the time the preflight refuses, so
    `steps_planned: []` said "nothing was planned" about a run with a full plan."""
    out_dir = tmp_path / "out"

    assert (
        _cli(
            tmp_path,
            "--min-available-gb",
            "999999",
            out_dir=out_dir,
            synthetic=tmp_path / "synth" / "synth-1d.sqlite3",
        )
        == 1
    )

    summary = json.loads(next(iter(out_dir.glob("run-1d.*.summary.json"))).read_text())
    assert summary["steps_planned"] == ["build", "before", "after"]
    assert summary["steps_remaining"] == ["build", "before", "after"]
    assert summary["steps_completed"] == []
