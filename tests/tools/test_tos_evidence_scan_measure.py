"""Tests for the evidence-scan measurement driver (growth plan §2 A1-b,"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import os
import re
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

_A_SECOND_DRIVER = "/usr/bin/python tools/tos_evidence_scan_measure.py run --days 90"


def _pid_ceiling() -> int:
    """The first number the kernel will not hand out as a PID."""
    try:
        return int(Path("/proc/sys/kernel/pid_max").read_text().strip())
    except (OSError, ValueError):  # pragma: no cover - every Linux has this file
        return 4 * 1024 * 1024


_FAKE_PID_BASE = _pid_ceiling()

_FAKE_INIT_PID = _FAKE_PID_BASE


def _fake_pid(n: int) -> int:
    """The ``n``-th PID (``n >= 0``) that no live process can hold."""
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
    """``pgrep -af`` text for these processes."""
    return "".join(f"{pid} {args}\n" for pid, args in processes)


def _fake_proc(root: Path, tree: dict[int, tuple[int, str]]) -> Path:
    """A `/proc` with just the two files the ancestry walk reads: `status` (PPid) and"""
    for pid, (ppid, cmdline) in tree.items():
        entry = root / str(pid)
        entry.mkdir(parents=True, exist_ok=True)
        (entry / "status").write_text(f"Name:\tx\nPPid:\t{ppid}\n")
        (entry / "cmdline").write_bytes(cmdline.replace(" ", "\0").encode())
    return root


def _fake_proc_for(
    root: Path, processes: Sequence[tuple[int, str]], *, self_pid: int
) -> Path:
    """The ``/proc`` that belongs with a fabricated ``pgrep`` table."""
    tree: dict[int, tuple[int, str]] = {_FAKE_INIT_PID: (0, "/sbin/init")}
    for pid, args in processes:
        tree[pid] = (0 if pid == self_pid else _FAKE_INIT_PID, args)
    if os.getpid() not in tree:
        tree[os.getpid()] = (0, _real_self_cmdline())
    if self_pid not in tree:
        tree[self_pid] = (0, "/usr/bin/python tools/tos_evidence_scan_measure.py run")
    return _fake_proc(root, tree)


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
    """A real :class:`HostReader` pointed at fake inputs."""
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
    """A host that is healthy until ``gate`` exists and running a Gradle daemon from then"""
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
    """A git checkout holding stand-ins for the driver and the bench, in the asked shape."""
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
    """A miniature stand-in for a real ``evidence.sqlite3`` — the same shape the bench's own"""
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
    """A stand-in for the bench: importable (the driver loads it for `profile_kinds`) and"""
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
    """Every ``ABORTED`` artifact for one ``<step>-<days>d``, sorted by name."""
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
    assert record.top_rss
    assert record.watchdog_enabled is True
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
    assert "5.50 GiB" in _failed(record)["mem_available"]
    assert "mem_available" in (record.refusal or "")


def test_preflight_refuses_when_swap_free_is_below_the_start_floor(
    tmp_path: Path,
) -> None:
    """Plan §7.1.7 deviation 11-b: this clause of the global rule was absent from the lost"""
    record = _preflight(
        tmp_path, _reader(tmp_path, available_gb=12.0, swap_free_gb=1.5)
    )

    assert record.verdict == "refused"
    failed = _failed(record)
    assert "swap_free" in failed
    assert "1.50 GiB" in failed["swap_free"]
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
    """#848, at the mechanism: an invented PID must never be looked up in the real /proc."""
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
    """The branch #848 tripped over, pinned as intended instead of left ambiguous."""
    the_driver = _fake_pid(0)
    reader = _reader(
        tmp_path, processes=[(the_driver, _A_SECOND_DRIVER)], self_pid=the_driver
    )

    assert reader._self_pid_chain() == frozenset({the_driver}), "no other rule applies"
    assert _preflight(tmp_path, reader).verdict == "ok"


def test_a_fabricated_process_table_does_not_blind_the_output_directory_lock(
    tmp_path: Path,
) -> None:
    """Review F3. A fake ``/proc`` must not quietly answer "owner gone" for a real lock."""
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
    assert "output_dir_unlocked" in failed
    assert "competing_measurement" in failed


def test_no_fabricated_pid_can_belong_to_a_live_process() -> None:
    """``_fake_pid`` is unassignable, not merely unlikely."""
    ceiling = int(Path("/proc/sys/kernel/pid_max").read_text().strip())
    fabricated = (_FAKE_INIT_PID, *(_fake_pid(n) for n in range(8)))

    assert min(fabricated) >= ceiling, "a fabricated PID must be unassignable"
    for pid in fabricated:
        assert not Path(f"/proc/{pid}").exists(), pid


def test_a_process_merely_searching_for_the_marker_is_not_a_competing_build(
    tmp_path: Path,
) -> None:
    """Both directions, because a filter that is too wide is the same bug as no filter."""
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
    """A refusal that leaves nothing behind is indistinguishable from never having checked —"""
    record = _preflight(tmp_path, _reader(tmp_path, available_gb=1.0, swap_free_gb=0.1))

    assert record.verdict == "refused"
    payload = json.loads((tmp_path / "out" / "preflight.json").read_text())
    assert payload["verdict"] == "refused"
    assert payload["refusal"]
    checks = {c["check"]: c for c in payload["checks"]}
    assert checks["mem_available"]["ok"] is False
    assert checks["swap_free"]["ok"] is False
    assert "1.00 GiB" in checks["mem_available"]["measured"]
    assert "0.10 GiB" in checks["swap_free"]["measured"]
    assert (tmp_path / "out" / "preflight.jsonl").read_text().count("\n") == 1


def test_meminfo_without_the_fields_the_guards_need_is_refused(tmp_path: Path) -> None:
    """Fail closed: a preflight that cannot read swap has not checked swap."""
    path = tmp_path / "partial-meminfo"
    path.write_text("MemTotal: 22016000 kB\nMemAvailable: 12000000 kB\n")
    reader = driver.HostReader(meminfo_path=path, pgrep_argv=("/bin/true",))

    with pytest.raises(driver.MeasureRefused, match="SwapFree"):
        reader.meminfo()


def test_an_abort_floor_above_the_start_floor_is_refused() -> None:
    """A guard must not admit what it names. With the abort floor above the start floor the"""
    with pytest.raises(driver.MeasureRefused, match="abort-available-gb"):
        _guard(min_available_gb=4.0, abort_available_gb=6.0)

    with pytest.raises(driver.MeasureRefused, match="abort-swap-free-gb"):
        _guard(min_swap_free_gb=1.0, abort_swap_free_gb=2.0)


def test_the_defaults_are_the_operator_rule_not_a_local_invention() -> None:
    """The global rule (``~/.claude/CLAUDE.md``, 로컬 빌드 동시 실행 제한) is 6 GB available"""
    assert driver.DEFAULT_MIN_AVAILABLE_GB == 6.0
    assert driver.DEFAULT_MIN_SWAP_FREE_GB == 2.0
    assert driver.DEFAULT_ABORT_AVAILABLE_GB == 4.0
    assert driver.DEFAULT_ABORT_SWAP_FREE_GB == 1.0
    guard = _guard()
    assert guard.abort_available_bytes < guard.min_available_bytes
    assert guard.abort_swap_free_bytes < guard.min_swap_free_bytes


def test_the_size_estimate_predicts_the_real_row_count_exactly(tmp_path: Path) -> None:
    """The driver reapplies the bench's replication rule to size the disk check. This builds"""
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


def _sleep_step(tmp_path: Path, seconds: int = 30, *, name: str = "before"):
    return driver.Step(
        name=name,
        argv=(sys.executable, "-c", f"import time; time.sleep({seconds})"),
        stdout_path=tmp_path / f"{name}.out",
        stderr_path=tmp_path / f"{name}.err",
    )


def _series(reader, samples: list[tuple[float, float]]):
    """A sampler that walks a scripted MemAvailable/SwapFree series and then holds the last"""
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
    """A sampler for a host that stays fine, so a test about resource capture is not also a"""
    return _series(reader or driver.HostReader(), [(12.0, 5.0)])


def test_the_watchdog_kills_the_child_when_memory_falls_and_writes_the_abort_artifact(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    step = _sleep_step(tmp_path, seconds=120)
    sampler = _series(driver.HostReader(), [(12.0, 5.0), (12.0, 5.0), (3.0, 5.0)])

    with pytest.raises(driver.MeasureAborted, match="MemAvailable 3.00 GiB"):
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
    assert "3.00 GiB" in record["reason"]
    assert record["signal_sent"] == "SIGTERM"
    assert record["returncode"] != 0
    assert record["last_samples"], "the abort record must carry the samples it acted on"
    partial = record["partial_resource"]
    assert partial["max_rss_bytes"] > 0
    assert partial["user_seconds"] >= 0.0
    assert "fs_inputs_blocks" in partial and "proc_io" in partial
    assert record["elapsed_seconds"] < 120, "the 120 s child did not actually die"
    lines = (out_dir / "watchdog.jsonl").read_text().strip().splitlines()
    assert len(lines) == len(record["last_samples"])
    assert json.loads(lines[0])["step"] == "before"


def test_the_watchdog_aborts_on_low_swap_alone(tmp_path: Path) -> None:
    """Deviation 11-b again, in-run this time: plenty of MemAvailable, no swap left."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    sampler = _series(driver.HostReader(), [(12.0, 5.0), (12.0, 0.2)])

    with pytest.raises(driver.MeasureAborted, match="SwapFree 0.20 GiB"):
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
    row = json.loads((out_dir / "watchdog.jsonl").read_text().strip().splitlines()[0])
    assert row["watchdog_enabled"] is False


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

    time_text = (out_dir / "build-1d.time").read_text()
    assert "Maximum resident set size (kbytes):" in time_text
    assert "File system inputs:" in time_text
    assert "Elapsed (wall clock) time" in time_text

    record = json.loads((out_dir / "build-1d.resource.json").read_text())
    assert record["fs_outputs_blocks"] >= 0
    assert "proc_io" in record
    if record["proc_io"]:
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


def test_the_planned_steps_are_the_bench_commands_in_order(tmp_path: Path) -> None:
    steps = driver.plan_steps(
        names=["after", "build", "before"],
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
    """A real, tiny measurement: three real bench children, the real preflight (against a"""
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

    after = json.loads((out_dir / "after-1d.json").read_text())
    plans = " ".join(line for m in after for line in m["plan"])
    assert "entries_kind_seq" in plans
    before = json.loads((out_dir / "before-1d.json").read_text())
    assert "entries_kind_seq" not in " ".join(
        line for m in before for line in m["plan"]
    )

    assert not synthetic.exists()


def test_a_synthetic_file_the_run_did_not_create_is_never_deleted(
    tmp_path: Path,
) -> None:
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    synthetic.parent.mkdir(parents=True)

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
    """Two properties in one AST pass, both enforced elsewhere but cheap to keep local."""
    roots = _import_roots(_MODULE_PATH)
    assert "tos" not in roots and "tos_runtime" not in roots
    assert roots <= set(sys.stdlib_module_names), roots - set(sys.stdlib_module_names)


def test_the_measure_pattern_does_not_match_this_test_process_itself() -> None:
    """Self-exclusion by PID chain, exercised against the real ``pgrep`` on the real host:"""
    reader = driver.HostReader()
    found = reader.competing_processes(driver.COMPETING_MEASURE_PATTERN)
    assert os.getpid() not in {p.pid for p in found}


def test_an_aborted_run_keeps_the_synthetic_file_it_built(tmp_path: Path) -> None:
    """A watchdog abort must not throw the build away."""
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"

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
    (aborted,) = _abort_records(out_dir, "before-1d")
    assert aborted.name.startswith(
        "ABORTED-before-1d."
    ), "an abort must never be silent"
    record = json.loads(aborted.read_text())
    assert record["check"] == "competing_build"
    assert synthetic.exists(), "the aborted run deleted the build it had just paid for"

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
    """The three branches of the keep/delete decision, including the one the CLI test"""
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

    with pytest.raises(TypeError):
        driver.decide_synthetic_disposition(
            path, remaining=[], size_bytes=1, created_by_this_run=True
        )


def _cli(
    tmp_path: Path,
    *extra: str,
    reference: Path | None = None,
    out_dir: Path | None = None,
    synthetic: Path | None = None,
    reader=None,
):
    """Run the CLI with the floors lowered to what any host satisfies, so a test decides"""
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
    """F1. The first revision only looked at exceptions, so a child that merely exited"""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    failing = _stub_bench(
        tmp_path,
        "    sys.stderr.write('bench: refusing\\n')\n    raise SystemExit(1)\n",
    )

    rc = _cli(tmp_path, "--bench", str(failing), out_dir=out_dir, synthetic=synthetic)

    assert rc == 1
    err = list(out_dir.glob("build-1d.*.aborted.err"))
    assert err and "refusing" in err[0].read_text()
    assert not (out_dir / "before-1d.json").exists()
    assert not (out_dir / "after-1d.json").exists()
    assert not (out_dir / "before-1d.resource.json").exists()
    assert "rc=1" in (out_dir / "measure-1d.log").read_text()


def test_f1_a_failed_step_keeps_a_synthetic_this_run_did_create(tmp_path: Path) -> None:
    """The other half of F1: when the failing step is not `build`, the build's own output"""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    rc = _cli(tmp_path, "--repeats", "0", out_dir=out_dir, synthetic=synthetic)

    assert rc == 1
    assert (out_dir / "build-1d.json").is_file(), "the build really did run"
    assert not (out_dir / "after-1d.json").exists(), "after must not run"
    assert synthetic.exists(), "a failed run must not delete the build it paid for"
    assert "KEPT synthetic" in (out_dir / "measure-1d.log").read_text()


def test_f2_a_host_read_failure_is_retried_once_then_aborts_with_an_artifact(
    tmp_path: Path,
) -> None:
    """F2. A transient `pgrep` exit 2/3 raised MeasureRefused out of the sampler, which the"""
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
    """The general case of F2: any exception out of the loop must leave the same evidence,"""
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
    """F3. The pattern was a bare filename substring, so `pytest tests/tools/"""
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
    """The regex is evaluated by `pgrep`, not by Python, so both directions are checked"""
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
    """F2, the integration half. The suite spawns real `bench build`/`measure` children"""
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
    """F2, the rule itself, on a constructed process tree."""
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
    """F2, the descendant rule exercised THROUGH `scan`, with no pytest in the picture."""
    the_driver = _fake_pid(0)
    its_bench_child = _fake_pid(1)
    an_unrelated_run = _fake_pid(2)
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
    table.write_text(
        _proc_table(
            [(pid, tree[pid][1]) for pid in (its_bench_child, an_unrelated_run)]
        )
    )
    fake = tmp_path / "fake-pgrep.sh"
    fake.write_text(f'#!/bin/sh\ngrep -E -- "$1" "{table}" || true\nexit 0\n')
    fake.chmod(0o755)
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
    """The other exclusion: the bench child this driver spawned is the work being"""
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
    """F9. Splitting on whitespace after stripping single quotes left `$(pgrep`, `;pgrep`"""
    for args in (
        "bash -c 'for p in $(pgrep -f GradleWorkerMain); do kill $p; done'",
        'sh -c "pgrep -f GradleDaemon|wc -l"',
        "bash -c 'ps aux;grep GradleWrapperMain'",
    ):
        assert driver._is_searching_for_the_pattern(args), args
    assert not driver._is_searching_for_the_pattern(
        "/opt/grepbuild/gradlew --daemon org.gradle.launcher.daemon.bootstrap.GradleDaemon"
    )


def test_r2_f7_a_build_whose_paths_end_in_a_search_command_name_is_not_hidden() -> None:
    """Round-2 F7, both cases the reviewer EXECUTED against the branch."""
    for hidden in (
        "java -Dorg.gradle.appname=/home/u/rg -cp x worker.GradleWorkerMain",
        "/usr/bin/java -Duser.dir=/srv/grep "
        "org.gradle.launcher.daemon.bootstrap.GradleDaemon 8.5",
        "/usr/lib/jvm/java-21/bin/java -cp /opt/pgrep/lib/x.jar "
        "worker.org.gradle.process.internal.worker.GradleWorkerMain",
    ):
        assert not driver._is_searching_for_the_pattern(hidden), hidden

    assert driver._command_position_tokens(
        "java -Dorg.gradle.appname=/home/u/rg -cp x worker.GradleWorkerMain"
    ) == ["java"]
    assert driver._command_position_tokens("FOO=/x/rg pgrep -f y") == ["pgrep"]


def test_f4_the_documented_resume_command_actually_gets_past_preflight(
    tmp_path: Path,
) -> None:
    """F4. The abort log said 'resume with --steps before,after'; the artifacts_absent"""
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
    assert list(out_dir.glob("before-1d.*.aborted.out")), "the output is preserved"
    assert not (out_dir / "before-1d.out").exists()

    rc = _cli(tmp_path, "--steps", "before,after", out_dir=out_dir, synthetic=synthetic)

    assert rc == 0, "the documented resume must actually work"
    assert (out_dir / "before-1d.json").is_file()
    assert (out_dir / "after-1d.json").is_file()


def test_f5_a_resume_is_not_asked_for_the_space_its_build_already_spent(
    tmp_path: Path,
) -> None:
    """F5. disk_free always demanded predicted x headroom, so a measure-only rerun on the"""
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
    assert resume_check.floor_bytes <= int(
        4096 * driver.DEFAULT_INDEX_GROWTH_RATIO * driver.DEFAULT_DISK_HEADROOM_RATIO
    )


def test_f5_measure_only_without_a_synthetic_file_is_refused_up_front(
    tmp_path: Path,
) -> None:
    """The step selection has to be consistent with what is on disk: with `build` excluded"""
    record = _preflight(tmp_path, _reader(tmp_path), steps=["before", "after"])

    assert record.verdict == "refused"
    assert "synthetic_present" in _failed(record)


def test_f6_wall_clock_is_not_rounded_up_to_the_host_sample_interval(
    tmp_path: Path,
) -> None:
    """F6. wait4 was polled only after sleep(watch_interval_s), so a step that finished"""
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
    """Block until ``pid`` is a zombie (exited, not yet reaped) or gone."""
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
    """F7. A sample taken on a child that had already exited could produce an ABORTED"""
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
    """The raw wait status leaked into AbortRecord.returncode on the non-signalled branch:"""
    assert driver._returncode(0) == 0
    assert driver._returncode(1 << 8) == 1, "exit 1 is 1, not 256"
    assert driver._returncode(9) == -9, "SIGKILL is -9"


def test_f8_lowering_the_start_floor_lowers_the_in_run_floor_with_it(
    tmp_path: Path,
) -> None:
    """F8. The help said `--min-swap-free-gb 0` opts out on a swapless host; the default"""
    guard = driver.GuardConfig.validated(min_available_gb=6.0, min_swap_free_gb=0.0)

    assert guard.abort_swap_free_bytes == 0
    assert guard.abort_available_bytes == int(driver.DEFAULT_ABORT_AVAILABLE_GB * _GB)
    assert any("abort_swap_free_gb derived" in d for d in guard.derivations)

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


def _await_exec(pid: int, argv0: str, *, timeout_s: float = 10.0) -> None:
    """Block until ``/proc/<pid>/cmdline`` shows the image ``pid`` exec'd."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            cmdline = (
                Path(f"/proc/{pid}/cmdline")
                .read_bytes()
                .replace(b"\0", b" ")
                .decode("utf-8", "replace")
            )
        except OSError:
            cmdline = ""
        if argv0 in cmdline:
            return
        time.sleep(0.01)
    raise AssertionError(f"pid {pid} never exec'd {argv0!r} within {timeout_s}s")


def test_the_output_directory_lock_refuses_a_second_run_and_survives_a_kill(
    tmp_path: Path,
) -> None:
    """The lock is the exact half of F3 that a pattern cannot do: it says whether another"""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    live = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
    try:
        _await_exec(live.pid, sys.executable)
        (out_dir / driver.LOCK_NAME).write_text(
            json.dumps({"pid": live.pid, "argv0": sys.executable, "run_id": "other"})
        )
        assert driver.read_lock(out_dir) is not None
        assert _preflight(tmp_path, _reader(tmp_path)).verdict == "refused"
    finally:
        live.kill()
        live.wait()

    assert driver.read_lock(out_dir) is None
    assert _preflight(tmp_path, _reader(tmp_path)).verdict == "ok"


def test_the_lock_is_released_when_a_run_finishes(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    assert _cli(tmp_path, out_dir=out_dir) == 0
    assert not (out_dir / driver.LOCK_NAME).exists()


def test_r2_f1_sigterm_to_the_driver_kills_the_child_and_leaves_an_artifact(
    tmp_path: Path,
) -> None:
    """Round-2 F1. With no handler, SIGTERM to the driver (a closed tmux pane, `kill`,"""
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
            "--allow-shared-checkout",
            "--bench",
            str(slow),
        ],
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
    assert not _pid_alive(child_pid), "the bench child outlived the signalled driver"
    record = _abort_record(out_dir, "build-1d")
    assert record["check"] == "driver_signalled"
    assert "SIGTERM" in record["reason"]
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
    """Round-2 F3. The bench refuses to overwrite its `--out`, so this run was GUARANTEED"""
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
    assert not (out_dir / "build-1d.json").exists()
    assert not (out_dir / "build-1d.err").exists()
    assert not list(out_dir.glob("*.resource.json"))


def test_r2_f4_with_the_watchdog_off_a_host_read_failure_is_recorded_not_fatal(
    tmp_path: Path,
) -> None:
    """Round-2 F4. `--no-watchdog` turns the in-run guards off, but the `host_read` abort"""
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
    """Round-2 F5. `artifacts_absent` guarded `.out/.err/.json` only, while a failed step"""
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
    """Round-2 F6. `meminfo()` and `competing_processes()` raised out of `preflight()`"""
    partial = tmp_path / "partial-meminfo"
    partial.write_text("MemTotal: 22016000 kB\nMemAvailable: 12000000 kB\n")
    reader = driver.HostReader(meminfo_path=partial, pgrep_argv=("/bin/true",))

    record = _preflight(tmp_path, reader)

    assert record.verdict == "refused"
    payload = json.loads((tmp_path / "out" / "preflight.json").read_text())
    checks = {c["check"]: c for c in payload["checks"]}
    assert checks["swap_free"]["ok"] is False
    assert "SwapFree" in checks["swap_free"]["measured"]

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
    """Round-2 F8. The documented resume (same --days, same --out-dir) overwrote the"""
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
    """Round-2 F10. The estimate (a GROUP BY over the whole reference) ran unconditionally"""
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
    """Sizing the run means scanning the reference. Doing that for a run that is not going"""
    record = _preflight(tmp_path, _reader(tmp_path, available_gb=1.0, swap_free_gb=0.1))

    assert record.verdict == "refused"
    disk = next(c for c in record.checks if c.check == "disk_free")
    assert disk.evaluated is False
    assert "mem_available" in disk.floor
    assert "disk_free" not in (record.refusal or "")
    assert record.estimate is None


def test_every_check_is_evaluated_on_a_healthy_host(tmp_path: Path) -> None:
    """The guard on the guard: `evaluated=False` must only ever happen because something"""
    record = _preflight(tmp_path, _reader(tmp_path))

    assert record.verdict == "ok"
    assert all(c.evaluated for c in record.checks)


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
    """Detached is not enough: an uncommitted edit means the bench that runs is not the"""
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
    """Clean and detached, but at a commit that was never published: a measurement is"""
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
    """The driver does not fetch — a measurement must not reach the network, and a tool"""
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
    """run_p_ca.sh's module-provenance check, in Python. --python is deliberately the"""
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
    """An operator who has to fix one refusal at a time learns about the dirty tree only"""
    repo = _make_checkout(tmp_path, detached=False, dirty=True, ancestor=False)
    record = _preflight(tmp_path, _reader(tmp_path), checkout=_checkout(repo))

    check = next(c for c in record.checks if c.check == "checkout_detached_and_clean")
    assert "HEAD is attached" in check.detail
    assert "the tree is dirty" in check.detail
    assert "is not an ancestor of origin/main" in check.detail


def test_a1c_a_bad_checkout_stops_the_run_before_the_reference_is_scanned(
    tmp_path: Path,
) -> None:
    """Sizing the run means a GROUP BY over the whole reference. Doing that for a run that"""
    repo = _make_checkout(tmp_path, detached=False)
    record = _preflight(tmp_path, _reader(tmp_path), checkout=_checkout(repo))

    assert record.estimate is None
    disk = next(c for c in record.checks if c.check == "disk_free")
    assert disk.evaluated is False
    assert "checkout_detached_and_clean" in disk.floor


def test_a1c_the_escape_hatch_records_the_warning_and_does_not_refuse(
    tmp_path: Path,
) -> None:
    """--allow-shared-checkout is needed by this suite and by a deliberate operator run."""
    repo = _make_checkout(tmp_path, detached=False, dirty=True)
    (tmp_path / "synth.sqlite3").write_bytes(b"")
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
    """Production resolves the repo from ``__file__``, so running the driver from"""
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
    assert Path(str(payload["checkout"]["repo_path"])).resolve() == _REPO_ROOT
    assert payload["checkout"]["driver_path"] == str(_MODULE_PATH)
    assert payload["checkout"]["bench_path"] == str(_BENCH_PATH)
    assert payload["checkout"]["bench_in_repo"] is True


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
    """THE property. The preflight runs once; `before` and `after` do not — at 180 days"""
    repo = _make_checkout(tmp_path)
    checkout = _checkout(repo)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    first = _run_with(checkout, tmp_path, out_dir=out_dir, name="build")
    assert first.returncode == 0

    moved_from = _git(repo, "rev-parse", "HEAD")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "a parallel lane lands something")
    moved_to = _git(repo, "rev-parse", "HEAD")
    assert moved_from != moved_to

    with pytest.raises(driver.MeasureAborted, match="HEAD moved from"):
        _run_with(checkout, tmp_path, out_dir=out_dir, name="before")

    record = _abort_record(out_dir, "before-7d")
    assert record["check"] == "checkout_drift"
    assert moved_from in record["reason"] and moved_to in record["reason"]
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
    """Why the digest is checked next to cleanliness rather than behind it: an IGNORED"""
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
    """Requirement 3: a changed bench stays detectable even when the guard is bypassed,"""
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

    timing = (out_dir / "before-7d.time").read_text()
    assert f"# repo_commit: {head}" in timing
    assert f"# bench sha256: {digest}" in timing
    assert "\tFile system inputs: " in timing


def test_a1c_with_the_hatch_open_drift_is_recorded_but_does_not_abort(
    tmp_path: Path,
) -> None:
    """The deliberate operator run: nothing is blocked, and the step artifact still shows"""
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
    """The other direction, because a guard that is too eager is the same bug as no guard:"""
    repo = _make_checkout(tmp_path)
    checkout = _checkout(repo)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    for name in ("build", "before", "after"):
        assert _run_with(checkout, tmp_path, out_dir=out_dir, name=name).returncode == 0
    assert not list(out_dir.glob("ABORTED-*"))


def test_a1c_a_state_that_errored_is_never_ok_however_good_the_rest_looks() -> None:
    """The fail-closed clause, given the concrete input it refuses."""
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
    """F1, the hole the in-process baseline could not see. `before` today and `after`"""
    repo = _make_checkout(tmp_path)
    checkout = _checkout(repo)
    out_dir = tmp_path / "out"
    _resource_artifact(out_dir, "before", 1, commit="0" * 40, digest="1" * 64)

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
    """An artifact written before A1-c carries no `checkout` block. That is not a pass:"""
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
    """One output directory holds every size (the existing `a1/` does). A 365-day run"""
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
    """F2. `status.showUntrackedFiles = no` is a common personal setting, and under the"""
    repo = _make_checkout(tmp_path)
    (repo / "tools" / "stray_bench.py").write_text("# nobody committed me\n")
    config = tmp_path / "gitconfig"
    config.write_text("[status]\n\tshowUntrackedFiles = no\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))

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
    """Both directions: a filter that calls everything dirty is the same bug as no"""
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
    """F4. A `git status` behind somebody's index.lock used to stall the per-child"""
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
    """F3. The five git calls take real time and run hours into a measurement. A SIGTERM"""

    class SignalledCheckout:
        """The guard seam with a signal arriving where the five git calls would be."""

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
    """F5. `--synthetic ./synth-365d.sqlite3` inside the worktree used to pass, then"""
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
    assert "NOT gitignored" in (record.refusal or "")


def test_f5_a_gitignored_path_inside_the_checkout_is_allowed(tmp_path: Path) -> None:
    """Ignored is the one safe way to be inside: it cannot dirty the tree, and"""
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
    """Unlike the rest of the guard. The hatch is a choice about where the CODE comes"""
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
    """F6. `git switch -c scratch` leaves the commit and the tree exactly as they were,"""
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

    _git(repo, "checkout", "-q", "-B", "side", "HEAD")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "published elsewhere")
    _git(
        repo, "update-ref", "refs/remotes/origin/main", _git(repo, "rev-parse", "HEAD")
    )
    _git(repo, "checkout", "-q", "--detach", checkout.baseline.repo_commit)
    _git(repo, "branch", "-q", "-D", "side")
    assert _git(repo, "rev-parse", "HEAD") == checkout.baseline.repo_commit

    assert _run_with(checkout, tmp_path, out_dir=out_dir, name="before").returncode == 0

    _git(repo, "update-ref", "refs/remotes/origin/main", "0" * 40)
    with pytest.raises(driver.MeasureAborted, match="no longer satisfies"):
        _run_with(checkout, tmp_path, out_dir=out_dir, name="after")


def test_f7_a_merge_base_that_fails_is_an_error_not_a_verdict(tmp_path: Path) -> None:
    """F7. Exit 0 is "ancestor" and 1 is "not"; 128 is git failing. Reporting it as"""
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
    assert "is not an ancestor of origin/main" not in "; ".join(state.failures())


def test_f8_the_refusal_names_the_actionable_cause_not_only_the_summary(
    tmp_path: Path,
) -> None:
    """F8. `summary()` for a worktree with no origin/main reads perfectly healthy"""
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
    """F9. `--python` is the SHARED checkout's venv by design, and on this host that venv"""
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
    assert result.checkout["child_python_flags"] == list(driver.CHILD_PYTHON_FLAGS)


def test_f10_the_shared_guard_is_built_once_not_per_test() -> None:
    """F10. `_clean_checkout()` used to re-run `with_baseline()` — five git subprocesses"""
    first = _clean_checkout()
    second = _clean_checkout()

    assert first is second
    assert first.baseline is not None
    assert _clean_checkout(enforced=False).baseline is first.baseline


def test_two_stops_in_one_output_directory_leave_two_abort_records(
    tmp_path: Path,
) -> None:
    """Plan §7.1.23: the 270-day run was stopped twice and only ONE record survived."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    aborting = _reader_that_reports_a_build_once(
        tmp_path, gate=out_dir / "before-1d.out"
    )

    assert _cli(tmp_path, out_dir=out_dir, synthetic=synthetic, reader=aborting) == 1
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
    for record in (first, second):
        assert record["check"] == "competing_build"
        assert record["reason"]
        assert record["signal_sent"] == "SIGTERM"
        assert record["returncode"] is not None
        assert record["partial_resource"]["proc_io"]
    assert first != second

    assert len(list(out_dir.glob("before-1d.*.aborted.out"))) == 2


def test_an_abort_record_names_the_run_that_wrote_it_in_the_file_and_inside(
    tmp_path: Path,
) -> None:
    """The run id in the name is the same run id the record already carried."""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    aborting = _reader_that_reports_a_build_once(
        tmp_path, gate=out_dir / "before-1d.out"
    )

    assert _cli(tmp_path, out_dir=out_dir, synthetic=synthetic, reader=aborting) == 1

    (path,) = _abort_records(out_dir, "before-1d")
    record = json.loads(path.read_text())
    assert path.name == f"ABORTED-before-1d.{record['run_id']}.json"
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
    """`artifacts_absent` guards the STEP artifacts, and an abort record is not one."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    synthetic.parent.mkdir(parents=True)
    synthetic.write_bytes(b"x" * 4096)
    for run_id in ("e1a9dcb24f64", "9e41a6d809e6", "89841a926bd6"):
        (out_dir / f"ABORTED-before-1d.{run_id}.json").write_text(
            json.dumps({"run_id": run_id, "step": "before", "days": 1})
        )
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
    """Plan §7.1.23 "뒤처리": 40 GB (36-53 GB across the campaign) stayed on the host and"""
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
    """`--steps before --delete-synthetic-on-success` would throw the file away BETWEEN"""
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
    forty = 40_099_414_016

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
    """Review #853 findings 1 and 2, as one property on both branches."""
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
    """Review #853 finding 5. On a resume `--keep-synthetic` fell through to the"""
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
    """Review #853 finding 6. `delete_command` is documented as paste-ready; an unquoted"""
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
    if resume["steps_planned"] == ["build"]:
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
    """The summary is most useful on the run that did NOT finish — it is where the abort"""
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
    """§7.1.15 "답하지 못한 것" 3 / §7.1.23 4, partially: the size after the last step."""
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


def test_f1_the_opt_in_delete_is_refused_when_before_was_never_measured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F1. `--steps after --delete-synthetic-on-success` on a pre-built file satisfied the"""
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
    """The other direction of F1: the property is "is this pass recorded", so a `before`"""
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
    """An output directory can be reused. A `before-1d.resource.json` naming a different"""
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
    """F2. `run --steps build` (and `build,before`) deleted the file it had just spent"""
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
    """F3. The `stat()` and the bare `unlink()` ran on every run including aborts, outside"""
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
    """The other unguarded call. The run here is already failing; the `stat` must not"""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    real_stat = Path.stat

    def exploding_stat(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self == synthetic:
            raise OSError(5, "Input/output error", str(self))
        return real_stat(self, *args, **kwargs)

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
    """F4. `_run_outcome` said `"refused" is the preflight`, but every preflight refusal"""
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
    """Collapsing `step-failed` / `signalled` / `aborted` to one word survived the first"""
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
    """F5, through the CLI: `--steps before,after --keep-synthetic` on a resume yielded"""
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
    """Note d. The flag says RESUME; with `build` in --steps it was accepted as a no-op,"""
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
    """Note h. The one file the driver must never build onto or delete is the real"""
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
    """Note g. The end-of-run block got longer in this revision, and every write in it is"""
    previous = driver._install_signal_handlers()
    held = None
    try:
        held = driver._hold_stop_signals()
        assert held is not None, "this platform must be able to block SIGTERM"
        os.kill(os.getpid(), signal.SIGTERM)
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
    """The `#####` lines sat in the `else` of the summary-write try, so one ENOSPC took"""
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
    """The hold is wired into the `finally`, and the mask is put back before main returns."""
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
    """The second half of F3's guard: `exists()` then `stat()` is two syscalls, and the"""
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    armed: list[bool] = []
    real_run_step = driver.run_step

    def arming_run_step(*args: Any, **kwargs: Any) -> Any:
        result = real_run_step(*args, **kwargs)
        armed.append(True)
        return result

    monkeypatch.setattr(driver, "run_step", arming_run_step)
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
    """Round-2 N1. The claim "an argument contradiction is refused before anything is"""
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
    """Round-2 N2. `MeasureRefused` also comes from inside the run — `_spawn` cannot find"""
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
    """Round-2 N3. `plan_steps` has already run by the time the preflight refuses, so"""
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


_UNIT_TOKEN = re.compile(r"(\d+\.\d+)\s*(GiB|GB|MiB|MB|KiB|kB)\b")

_UNIT_BASE = {
    "GiB": 1024**3,
    "GB": 10**9,
    "MiB": 1024**2,
    "MB": 10**6,
    "KiB": 1024,
    "kB": 1000,
}


def _unit_tokens(text: str) -> list[tuple[float, str]]:
    return [(float(number), unit) for number, unit in _UNIT_TOKEN.findall(text)]


def _bases_disagree(raw: int, unit: str, *, places: int = 2) -> bool:
    """True when `raw` prints different digits in the binary and decimal base of `unit`,"""
    exponent = {"K": 1, "M": 2, "G": 3}[unit[0].upper()]
    binary = f"{raw / 1024**exponent:.{places}f}"
    decimal = f"{raw / 1000**exponent:.{places}f}"
    return binary != decimal


def test_every_byte_quantity_in_the_preflight_record_names_its_own_base(
    tmp_path: Path,
) -> None:
    """Every `measured`/`floor`/`detail` in the record is computed with `_GB`, so every"""
    record = _preflight(
        tmp_path, _reader(tmp_path, available_gb=12.0, swap_free_gb=5.0), days=365
    )
    assert record.verdict == "ok", _failed(record)

    carrying_units: set[tuple[str, str]] = set()
    checked_against_bytes: set[tuple[str, str]] = set()
    for check in record.checks:
        for field_name in ("measured", "floor", "detail"):
            text = getattr(check, field_name)
            for number, unit in _unit_tokens(text):
                carrying_units.add((check.check, field_name))
                assert unit == "GiB", (
                    f"{check.check}.{field_name} says {number} {unit}; it is computed "
                    "with _GB = 1024**3, so the only honest token is GiB"
                )
            raw = getattr(check, f"{field_name}_bytes")
            if raw is None:
                continue
            tokens = _unit_tokens(text)
            assert len(tokens) == 1, f"{check.check}.{field_name} = {text!r}"
            number, unit = tokens[0]
            assert _bases_disagree(raw, unit), (
                f"{check.check}.{field_name} is {raw} bytes, which prints the same "
                f"digits in both bases — this assertion would pass either way"
            )
            assert number == round(raw / _UNIT_BASE[unit], 2), (
                f"{check.check}.{field_name} prints {number} {unit} for {raw} bytes, "
                f"which is {raw / _UNIT_BASE[unit]:.2f} {unit}"
            )
            checked_against_bytes.add((check.check, field_name))

    assert carrying_units == {
        ("mem_available", "measured"),
        ("mem_available", "floor"),
        ("swap_free", "measured"),
        ("swap_free", "floor"),
        ("swap_free", "detail"),
        ("disk_free", "measured"),
        ("disk_free", "floor"),
        ("disk_free", "detail"),
    }, carrying_units
    assert checked_against_bytes == carrying_units, (
        "every byte-valued string in the record must carry its bytes: "
        f"{carrying_units - checked_against_bytes} do not"
    )
    measured = {c.check: c.measured for c in record.checks}
    assert measured["mem_available"] == "12.00 GiB"
    assert measured["swap_free"] == "5.00 GiB"


@pytest.mark.parametrize(
    ("expected_check", "prefix", "available_bytes", "swap_bytes", "floor_attribute"),
    [
        ("mem_available", "MemAvailable", 3 * _GB, 5 * _GB, "abort_available_bytes"),
        ("swap_free", "SwapFree", 12 * _GB, _GB // 4, "abort_swap_free_bytes"),
    ],
)
def test_the_watchdog_abort_reason_names_its_own_base(
    expected_check: str,
    prefix: str,
    available_bytes: int,
    swap_bytes: int,
    floor_attribute: str,
) -> None:
    """Both branches of `in_run_breach` that print a byte quantity — the strings"""
    guard = _guard()
    sample = driver.HostSample(
        at_kst="2026-10-03T12:00:00.000+09:00",
        mem_available_bytes=available_bytes,
        swap_free_bytes=swap_bytes,
        swap_total_bytes=8 * _GB,
    )

    breach = guard.in_run_breach(sample)
    assert breach is not None
    check, reason = breach
    assert check == expected_check
    assert reason.startswith(prefix + " ")
    assert "is below the in-run floor" in reason

    measured_bytes = (
        available_bytes if expected_check == "mem_available" else swap_bytes
    )
    tokens = _unit_tokens(reason)
    assert len(tokens) == 2, reason
    for (number, unit), raw in zip(
        tokens, (measured_bytes, getattr(guard, floor_attribute))
    ):
        assert unit == "GiB", reason
        assert _bases_disagree(raw, unit), f"{raw} bytes prints alike in both bases"
        assert number == round(raw / _UNIT_BASE[unit], 2), reason


def test_the_step_log_line_names_its_own_base(tmp_path: Path) -> None:
    """The per-step completion line prints peak RSS as `bytes / 1024**2`, which it used to"""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    lines: list[str] = []

    result = driver.run_step(
        driver.Step(
            name="build",
            argv=(sys.executable, "-c", "x = bytearray(40 * 1024 * 1024); del x"),
            stdout_path=tmp_path / "log.out",
            stderr_path=tmp_path / "log.err",
        ),
        guard=_guard(),
        checkout=_clean_checkout(),
        reader=driver.HostReader(),
        run_id="logrun",
        days=1,
        out_dir=out_dir,
        log=lines.append,
        sampler=_healthy(),
    )

    assert result.returncode == 0
    (line,) = [one for one in lines if "maxrss=" in one]
    tokens = _unit_tokens(line)
    assert len(tokens) == 1, line
    number, unit = tokens[0]
    assert unit == "MiB", line
    assert _bases_disagree(result.max_rss_bytes, unit, places=1), (
        f"the child peaked at {result.max_rss_bytes} bytes, which prints the same "
        "digits as MiB and MB at one decimal — allocate more in the child"
    )
    assert number == round(result.max_rss_bytes / _UNIT_BASE[unit], 1), line


def test_the_cli_help_does_not_label_a_gib_default_as_gb(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--help` prints the in-run swap default, and the flags are read in GiB. The flag"""
    monkeypatch.setenv("COLUMNS", "120")
    with pytest.raises(SystemExit):
        driver.main(["run", "--help"])
    out = capsys.readouterr().out

    assert "1.0 GiB" in out, "the printed in-run swap default"
    units = {unit for _n, unit in _unit_tokens(out)}
    assert units == {"GiB"}, units
    for flag in ("--min-available-gb", "--min-swap-free-gb", "--expect-gb"):
        assert flag in out


def test_the_anti_trivial_guard_is_asked_at_the_precision_the_assertion_uses() -> None:
    """`_bases_disagree` is what keeps the other tests from passing on a degenerate input,"""
    half_mib = 1024 * 1024 // 2

    assert _bases_disagree(half_mib, "MiB")
    assert not _bases_disagree(half_mib, "MiB", places=1)
    assert _bases_disagree(10 * half_mib, "MiB", places=1)
    assert _bases_disagree(half_mib, "MB") is _bases_disagree(half_mib, "MiB")


def test_a_file_size_in_a_disposition_message_stays_decimal() -> None:
    """The other half of the rule, pinned from the other side. Disposition messages are"""
    assert driver._decimal_gb(40 * 1024**3) == "42.95 GB"
    assert driver._decimal_gb(40_000_000_000) == "40.00 GB"
