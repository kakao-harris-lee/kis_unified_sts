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

import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path

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
    pgrep_output: str = "",
):
    """A real :class:`HostReader` pointed at fake inputs.

    ``pgrep`` is replaced by ``/bin/echo -n <output>``, which is a real process producing
    real stdout — the reader's parsing, self-exclusion and search-command filtering all run
    for real. Nothing is monkeypatched.
    """
    meminfo = _meminfo(
        tmp_path / f"meminfo-{available_gb}-{swap_free_gb}",
        available_gb=available_gb,
        swap_free_gb=swap_free_gb,
    )
    return driver.HostReader(
        meminfo_path=meminfo,
        pgrep_argv=(
            ("/bin/echo", "-n", pgrep_output) if pgrep_output else ("/bin/true",)
        ),
    )


def _guard(**overrides):
    kwargs = {
        "min_available_gb": driver.DEFAULT_MIN_AVAILABLE_GB,
        "min_swap_free_gb": driver.DEFAULT_MIN_SWAP_FREE_GB,
        "abort_available_gb": driver.DEFAULT_ABORT_AVAILABLE_GB,
        "abort_swap_free_gb": driver.DEFAULT_ABORT_SWAP_FREE_GB,
        "watch_interval_s": 0.01,
        "term_grace_s": 0.5,
    }
    kwargs.update(overrides)
    return driver.GuardConfig.validated(**kwargs)


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


def _preflight(
    tmp_path: Path, reader, *, guard=None, days: int = 1, expect_gb=None, steps=None
):
    reference = tmp_path / "evidence.sqlite3"
    if not reference.exists():
        _write_reference(reference)
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / f"synth-{days}d.sqlite3"
    estimate = driver.estimate_synthetic_size(
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
        reader=reader,
        out_dir=out_dir,
        days=days,
        estimate=estimate,
        expect_bytes=None if expect_gb is None else int(expect_gb * _GB),
        disk_headroom_ratio=driver.DEFAULT_DISK_HEADROOM_RATIO,
        steps=planned,
        argv=["run", "--days", str(days)],
        synthetic=synthetic,
    )


def _failed(record) -> dict[str, str]:
    return {c.check: c.measured for c in record.checks if not c.ok}


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
        "mem_available",
        "swap_free",
        "competing_build",
        "competing_measurement",
        "disk_free",
        "artifacts_absent",
    }
    # The global rule asks for the top-RSS census as part of the check; it is recorded, not
    # gated, and a run must be readable afterwards next to what else was resident.
    assert record.top_rss
    assert record.watchdog_enabled is True


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
    reader = _reader(
        tmp_path,
        pgrep_output=(
            "4242 /usr/lib/jvm/java-21-openjdk-amd64/bin/java -Xmx2g "
            "org.gradle.launcher.daemon.bootstrap.GradleDaemon 9.6.1\n"
        ),
    )
    record = _preflight(tmp_path, reader)

    assert record.verdict == "refused"
    failed = _failed(record)
    assert "competing_build" in failed
    assert "4242" in failed["competing_build"]


def test_preflight_refuses_when_another_measurement_driver_is_running(
    tmp_path: Path,
) -> None:
    reader = _reader(
        tmp_path,
        pgrep_output="5150 /usr/bin/python tools/tos_evidence_scan_measure.py run --days 90\n",
    )
    record = _preflight(tmp_path, reader)

    assert record.verdict == "refused"
    assert "5150" in _failed(record)["competing_measurement"]


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
        pgrep_output="777 /bin/bash -c eval 'if ! pgrep -f GradleWrapperMain; then echo idle; fi'\n",
    )
    assert _preflight(tmp_path, searching).verdict == "ok"

    building = _reader(
        tmp_path,
        pgrep_output="778 /usr/lib/jvm/java-21/bin/java worker.org.gradle.process.internal.worker.GradleWorkerMain\n",
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
            reader=driver.HostReader(),
            run_id="abortrun",
            days=90,
            out_dir=out_dir,
            log=lambda _m: None,
            sampler=sampler,
        )

    record = json.loads((out_dir / "ABORTED-before-90d.json").read_text())
    assert record["check"] == "mem_available"
    assert "3.00 GB" in record["reason"]
    assert record["signal_sent"] == "SIGTERM"
    assert record["returncode"] != 0
    assert record["last_samples"], "the abort record must carry the samples it acted on"
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
            reader=driver.HostReader(),
            run_id="swaprun",
            days=30,
            out_dir=out_dir,
            log=lambda _m: None,
            sampler=sampler,
        )

    assert (
        json.loads((out_dir / "ABORTED-before-30d.json").read_text())["check"]
        == "swap_free"
    )


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
            reader=driver.HostReader(),
            run_id="cotenant",
            days=30,
            out_dir=out_dir,
            log=lambda _m: None,
            sampler=sampler,
        )

    assert (
        json.loads((out_dir / "ABORTED-before-30d.json").read_text())["check"]
        == "competing_build"
    )


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
            reader=driver.HostReader(),
            run_id="stubborn",
            days=30,
            out_dir=out_dir,
            log=lambda _m: None,
            sampler=sampler,
        )

    record = json.loads((out_dir / "ABORTED-build-30d.json").read_text())
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
        reader=driver.HostReader(),
        run_id="nowatch",
        days=1,
        out_dir=out_dir,
        log=lambda _m: None,
        sampler=sampler,
    )

    assert result.returncode == 0
    assert not (out_dir / "ABORTED-build-1d.json").exists()
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

    # Build it first, keeping it, then measure against it in a second invocation.
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
                "--keep-synthetic",
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

    # A pgrep that reports a Gradle daemon exactly once the synthetic file exists — a
    # competing build appearing after the run started. Tying the trigger to the file
    # rather than to a call count makes the test deterministic: whenever it fires, there
    # really is a build on disk to preserve.
    fake_pgrep = tmp_path / "fake-pgrep.sh"
    fake_pgrep.write_text(
        "#!/bin/sh\n"
        f'[ -f "{synthetic}" ] && echo "4242 /usr/bin/java GradleDaemon"\n'
        "exit 0\n"
    )
    fake_pgrep.chmod(0o755)
    reader = driver.HostReader(
        meminfo_path=_meminfo(tmp_path / "mi", available_gb=12.0, swap_free_gb=5.0),
        pgrep_argv=(str(fake_pgrep),),
    )

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
            "--bench",
            str(_BENCH_PATH),
        ],
        reader=reader,
    )

    assert rc == 1
    # Whichever step the competing build lands in, the abort is recorded.
    aborted = sorted(out_dir.glob("ABORTED-*-1d.json"))
    assert aborted, "an abort must never be silent"
    assert json.loads(aborted[0].read_text())["check"] == "competing_build"
    assert synthetic.exists(), "the aborted run deleted the build it had just paid for"
    log = (out_dir / "measure-1d.log").read_text()
    assert "KEPT synthetic" in log
    assert "--steps" in log, "the log must say how to resume"
