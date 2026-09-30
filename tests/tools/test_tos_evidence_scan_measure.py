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
import subprocess
import sys
import time
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
    if not pgrep_output:
        return driver.HostReader(meminfo_path=meminfo, pgrep_argv=("/bin/true",))
    # A faithful `pgrep -af`: a fixed process table, matched with the SAME extended regex
    # the real binary would apply. Echoing the lines back unconditionally would test the
    # reader's parsing while leaving the patterns themselves unexercised — and the patterns
    # are where review F3 found the bug.
    table = tmp_path / f"proc-table-{abs(hash(pgrep_output))}"
    table.write_text(pgrep_output)
    fake = tmp_path / f"fake-pgrep-{abs(hash(pgrep_output))}.sh"
    fake.write_text(f'#!/bin/sh\ngrep -E -- "$1" "{table}" || true\nexit 0\n')
    fake.chmod(0o755)
    return driver.HostReader(meminfo_path=meminfo, pgrep_argv=(str(fake),))


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
        index_growth_ratio=driver.DEFAULT_INDEX_GROWTH_RATIO,
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
        "output_dir_unlocked",
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
            "--poll-interval-s",
            "0.01",
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
                "--poll-interval-s",
                "0.01",
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
                "--poll-interval-s",
                "0.01",
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

    # A pgrep that reports a Gradle daemon exactly once the `before` step's stdout file
    # exists — that file is created by posix_spawn the instant the child starts, so the
    # trigger lands in `before`, after `build` has finished and written the synthetic.
    # Tying it to a file rather than to a call count keeps the test deterministic: the
    # build really is complete and really is worth preserving whenever this fires.
    fake_pgrep = tmp_path / "fake-pgrep.sh"
    fake_pgrep.write_text(
        "#!/bin/sh\n"
        f'[ -f "{out_dir / "before-1d.out"}" ] && echo "4242 /usr/bin/java GradleDaemon"\n'
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
            "--poll-interval-s",
            "0.01",
            "--bench",
            str(_BENCH_PATH),
        ],
        reader=reader,
    )

    assert rc == 1
    # Whichever step the competing build lands in, the abort is recorded.
    aborted = sorted(out_dir.glob("ABORTED-*-1d.json"))
    assert aborted, "an abort must never be silent"
    assert aborted[0].name == "ABORTED-before-1d.json"
    assert json.loads(aborted[0].read_text())["check"] == "competing_build"
    assert synthetic.exists(), "the aborted run deleted the build it had just paid for"
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

    done = driver.decide_synthetic_disposition(path, remaining=[], size_bytes=53 * _GB)
    assert done.action == "delete"

    partial = driver.decide_synthetic_disposition(
        path, remaining=["build", "before", "after"], size_bytes=7 * _GB
    )
    assert partial.action == "keep-partial"
    assert "INCOMPLETE" in partial.message
    assert "--steps" not in partial.message, "a partial file is not resumable"

    resumable = driver.decide_synthetic_disposition(
        path, remaining=["before", "after"], size_bytes=53 * _GB
    )
    assert resumable.action == "keep-resumable"
    assert "--steps before,after" in resumable.message
    assert "53.00 GB" in resumable.message


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
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    synthetic.parent.mkdir(parents=True)
    # A pre-existing --synthetic is the reviewer's own scenario: the bench's `build`
    # refuses to overwrite it and exits 1.
    synthetic.write_text("not a database")
    out_dir = tmp_path / "out"

    rc = _cli(tmp_path, out_dir=out_dir, synthetic=synthetic)

    assert rc == 1
    assert (out_dir / "build-1d.err").read_text().strip(), "the child's reason is kept"
    # The later steps must not have run.
    assert not (out_dir / "before-1d.json").exists()
    assert not (out_dir / "after-1d.json").exists()
    assert not (out_dir / "before-1d.resource.json").exists()
    # And the file is still there (this run did not create it, so it was never ours).
    assert synthetic.exists()
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
            reader=driver.HostReader(),
            run_id="hostread",
            days=90,
            out_dir=out_dir,
            log=lambda _m: None,
            sampler=sampler,
        )

    record = json.loads((out_dir / "ABORTED-before-90d.json").read_text())
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
            reader=driver.HostReader(),
            run_id="enospc",
            days=365,
            out_dir=out_dir,
            log=lambda _m: None,
            sampler=sampler,
        )

    record = json.loads((out_dir / "ABORTED-before-365d.json").read_text())
    assert record["check"] == "driver_error"
    assert "No space left on device" in record["reason"]


def test_f3_editing_or_testing_this_tool_is_not_a_competing_measurement(
    tmp_path: Path,
) -> None:
    """F3. The pattern was a bare filename substring, so `pytest tests/tools/
    test_tos_evidence_scan_measure.py`, `mypy tools/…`, `vim tools/…` and `git show
    main:tools/…` all counted — editing this tool during a multi-hour run killed the run.
    """
    innocent = "\n".join(
        (
            "101 /usr/bin/python -m pytest tests/tools/test_tos_evidence_scan_measure.py -q",
            "102 /usr/bin/mypy tools/tos_evidence_scan_measure.py --ignore-missing-imports",
            "103 vim tools/tos_evidence_scan_measure.py",
            "104 git show main:tools/tos_evidence_scan_bench.py",
            "105 /usr/bin/black tools/tos_evidence_scan_measure.py",
        )
    )
    assert (
        _preflight(tmp_path, _reader(tmp_path, pgrep_output=innocent + "\n")).verdict
        == "ok"
    )


def test_f3_a_real_second_driver_invocation_is_still_caught(tmp_path: Path) -> None:
    """The other direction — the tightened pattern must not have tightened the guard away."""
    for line in (
        "201 /usr/bin/python tools/tos_evidence_scan_measure.py run --days 365",
        "202 /usr/bin/python tools/tos_evidence_scan_bench.py build --days 90",
        "203 /usr/bin/python /opt/x/tos_evidence_scan_measure.py preflight --days 30",
    ):
        record = _preflight(tmp_path, _reader(tmp_path, pgrep_output=line + "\n"))
        assert record.verdict == "refused", line
        assert "competing_measurement" in _failed(record), line


def test_f3_the_pattern_matches_a_real_invocation_through_the_real_pgrep(
    tmp_path: Path,
) -> None:
    """The regex is only ever evaluated by `pgrep`, not by Python, so the two cases are
    checked against a live process and the real binary."""
    script = tmp_path / "tos_evidence_scan_measure.py"
    script.write_text("import time\ntime.sleep(20)\n")
    running = subprocess.Popen([sys.executable, str(script), "run", "--days", "365"])
    decoy = subprocess.Popen([sys.executable, str(script), "-q"])
    try:
        time.sleep(1.0)
        found = {
            p.pid
            for p in driver.HostReader().competing_processes(
                driver.COMPETING_MEASURE_PATTERN
            )
        }
        assert running.pid in found, "a real invocation must be seen"
        assert decoy.pid not in found, "a bare mention of the file must not be"
    finally:
        for proc in (running, decoy):
            proc.kill()
            proc.wait()


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


def test_f4_the_documented_resume_command_actually_gets_past_preflight(
    tmp_path: Path,
) -> None:
    """F4. The abort log said 'resume with --steps before,after'; the artifacts_absent
    check then refused that exact command, because the aborted step's own `.out`/`.err`
    (created by posix_spawn) were sitting there. The resume was advice nothing tested.
    """
    out_dir = tmp_path / "out"
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    gate = out_dir / "before-1d.out"
    fake_pgrep = tmp_path / "fake-pgrep.sh"
    fake_pgrep.write_text(
        "#!/bin/sh\n"
        f'[ -f "{gate}" ] && echo "4242 /usr/bin/java GradleDaemon"\n'
        "exit 0\n"
    )
    fake_pgrep.chmod(0o755)
    aborting_reader = driver.HostReader(
        meminfo_path=_meminfo(tmp_path / "mi", available_gb=12.0, swap_free_gb=5.0),
        pgrep_argv=(str(fake_pgrep),),
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
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    synthetic = tmp_path / "synth" / "synth-1d.sqlite3"
    synthetic.parent.mkdir(parents=True)
    synthetic.write_bytes(b"x" * 4096)

    build = _preflight(tmp_path, _reader(tmp_path), steps=["build"])
    measure_only = _preflight(tmp_path, _reader(tmp_path), steps=["before", "after"])

    build_check = next(c for c in build.checks if c.check == "disk_free")
    resume_check = next(c for c in measure_only.checks if c.check == "disk_free")
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
        reader=driver.HostReader(),
        run_id="race",
        days=1,
        out_dir=out_dir,
        log=lambda _m: None,
        sampler=sampler,
    )

    assert seen["reaped"], "the test did not reach the interleaving it is about"
    assert result.returncode == 0
    assert not (out_dir / "ABORTED-build-1d.json").exists()
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
