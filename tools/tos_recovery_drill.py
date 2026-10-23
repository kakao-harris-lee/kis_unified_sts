#!/usr/bin/env python3
"""kill -9 recovery drill — TOS rescope plan §2 sentence 3 («죽어도 중복 없음»), milestone M3.

For each crash point (전송 직전 ``BEFORE_SEND`` · 전송 직후 ``AFTER_SEND`` · 결과 수신 직후
``AFTER_RESULT``) and each round, this script:

1. starts ``python -m tests.recovery._kill9_child crash <root> <point>`` (a SYNTHETIC-transport
   paper runtime in a fresh directory) and waits until the child says it is parked at the point;
2. sends it ``SIGKILL`` (a real ``kill -9`` from outside the process);
3. restarts the runtime twice from the same files (``... _kill9_child reboot``);
4. judges the round from files only — the venue ledger the synthetic venue fsyncs one line per
   received order into, the reservation snapshot the child fsynced at the park point, and the
   two reboot reports.

A round passes when: the child died of SIGKILL at the right point; the venue saw exactly the
orders it should have by then (0 before the send, 1 after) and **no new order after either
restart**; each restart held the recovery barrier (not ready, no driver, both offered events
refused, zero transport calls, the interrupted event listed as possibly live, no authority
granted); and capacity was not released — every reservation keeps the state it had at the
crash, through both restarts.

Lives in ``tools/`` because the drill needs ``subprocess`` + ``os.kill``, which the tos
firewall forbids under ``tos/``. It does not import ``tos``/``tos_runtime`` (reverse firewall):
it only starts the child module by name with ``cwd=tos/runtime``.

Usage::

    python tools/tos_recovery_drill.py                  # 3 points x 3 rounds = 9 drills
    python tools/tos_recovery_drill.py --rounds 1 --json out.json --workdir /tmp/drill

Exit 0 only when every drill passes.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import signal
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "tos" / "runtime"
CHILD_MODULE = "tests.recovery._kill9_child"

POINTS = ("BEFORE_SEND", "AFTER_SEND", "AFTER_RESULT")
#: Orders the venue must have received by the time the child parks at each point.
EXPECTED_VENUE_LINES_AT_KILL = {"BEFORE_SEND": 0, "AFTER_SEND": 1, "AFTER_RESULT": 1}
VENUE_LEDGER_NAME = "venue_ledger.jsonl"
PARK_SNAPSHOT_NAME = "park_snapshot.json"
REBOOTS_PER_DRILL = 2
RELEASED_STATE = "RELEASED"


@dataclass
class DrillResult:
    point: str
    round: int
    passed: bool = False
    failures: list[str] = field(default_factory=list)
    killed_by_sigkill: bool = False
    venue_orders_at_kill: int = -1
    venue_orders_after_restarts: int = -1
    duplicate_sends: int = -1
    reservations_at_crash: dict[str, str] = field(default_factory=dict)
    reboots: list[dict[str, Any]] = field(default_factory=list)
    seconds: float = 0.0


def _child_env() -> dict[str, str]:
    # Minimal, explicit environment: no .env, no credentials, no proxy settings reach the child.
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": os.pathsep.join(("src", os.path.join("..", "src"))),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
    }


def _read_ledger(root: Path) -> list[dict[str, Any]]:
    path = root / VENUE_LEDGER_NAME
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line]


def _crash(
    python: str, root: Path, point: str, timeout: float, log: Path
) -> tuple[bool, str]:
    """Start the crash child, wait for ``AT <point>``, SIGKILL it. Returns (killed, detail)."""
    with log.open("wb") as err:
        child = subprocess.Popen(
            [python, "-m", CHILD_MODULE, "crash", str(root), point],
            cwd=RUNTIME_DIR,
            env=_child_env(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=err,
        )
        assert child.stdout is not None
        deadline = time.monotonic() + timeout
        line = b""
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([child.stdout], [], [], 0.5)
                if not ready:
                    if child.poll() is not None:
                        break
                    continue
                line = child.stdout.readline()
                if not line:
                    break
                if line.strip() == f"AT {point}".encode():
                    os.kill(child.pid, signal.SIGKILL)
                    child.wait(timeout=timeout)
                    return (
                        child.returncode == -signal.SIGKILL,
                        f"returncode={child.returncode}",
                    )
                if line.strip() == b"NO_PARK":
                    break
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
        return (
            False,
            f"never parked at {point} (last line {line!r}, returncode={child.returncode})",
        )


def _reboot(
    python: str, root: Path, index: int, timeout: float, log: Path
) -> dict[str, Any]:
    result_path = root.parent / f"{root.name}.reboot{index}.json"
    try:
        with log.open("ab") as err:
            completed = subprocess.run(
                [python, "-m", CHILD_MODULE, "reboot", str(root), str(result_path)],
                cwd=RUNTIME_DIR,
                env=_child_env(),
                stdin=subprocess.DEVNULL,
                stdout=err,
                stderr=err,
                timeout=timeout,
                check=False,
            )
    except subprocess.TimeoutExpired:
        # run() already killed the child; report it as a failed reboot so the table still prints.
        return {"error": f"reboot {index} timed out after {timeout}s; see {log}"}
    if completed.returncode != 0 or not result_path.exists():
        return {"error": f"reboot {index} exited {completed.returncode}; see {log}"}
    report: dict[str, Any] = json.loads(result_path.read_text("utf-8"))
    return report


def judge(
    point: str,
    killed: bool,
    ledger_at_kill: list[dict[str, Any]],
    ledger_after: list[dict[str, Any]],
    snapshot: dict[str, Any] | None,
    reboots: list[dict[str, Any]],
) -> list[str]:
    """Every reason this drill fails; empty means it passed. Pure — unit-tested on its own."""
    failures: list[str] = []
    if not killed:
        failures.append("child was not killed by SIGKILL at the park point")
    expected = EXPECTED_VENUE_LINES_AT_KILL[point]
    if len(ledger_at_kill) != expected:
        failures.append(
            f"venue had {len(ledger_at_kill)} order(s) at kill, expected {expected}"
        )
    if len(ledger_after) != len(ledger_at_kill):
        failures.append(
            f"venue received {len(ledger_after) - len(ledger_at_kill)} order(s) after restart"
        )
    repeated = [
        a for a, n in Counter(r["attempt_id"] for r in ledger_after).items() if n > 1
    ]
    if repeated:
        failures.append(f"attempt(s) sent more than once: {repeated}")
    if snapshot is None or snapshot.get("point") != point:
        failures.append("no park snapshot for this point")
        crash_reservations: dict[str, str] = {}
    else:
        crash_reservations = snapshot["reservations"]
        if not crash_reservations:
            failures.append("no reservation was held at the crash point")
    if len(reboots) != REBOOTS_PER_DRILL:
        failures.append(
            f"{len(reboots)} reboot report(s), expected {REBOOTS_PER_DRILL}"
        )
    for index, report in enumerate(reboots, start=1):
        tag = f"reboot {index}"
        if "error" in report:
            failures.append(f"{tag}: {report['error']}")
            continue
        if report["ready"] is not False or report["readiness_verdict"] != "NOT_READY":
            failures.append(
                f"{tag}: barrier did not hold ({report['readiness_verdict']})"
            )
        if report["driver_wired"]:
            failures.append(f"{tag}: a driver was wired")
        if report["run_once_refused"] != [True, True]:
            failures.append(f"{tag}: offered events were not all refused")
        if report["reboot_transport_requests"] != 0:
            failures.append(
                f"{tag}: transport called {report['reboot_transport_requests']}x"
            )
        interrupted = set(report["interrupted_event_ids"])
        if not interrupted:
            failures.append(f"{tag}: no interrupted event found in the inbox")
        if not interrupted <= set(report["possibly_live_event_ids"]):
            failures.append(
                f"{tag}: an interrupted event is not counted as possibly live"
            )
        if any((report["authority_effect"] or {"missing": True}).values()):
            failures.append(f"{tag}: recovery verdict grants authority")
        for key in ("reservations_at_boot", "reservations_after_refusals"):
            held = report[key]
            if held != crash_reservations:
                failures.append(f"{tag}: {key} {held} != at crash {crash_reservations}")
            if RELEASED_STATE in held.values():
                failures.append(f"{tag}: capacity released ({key})")
    return failures


def run_drill(
    python: str, workdir: Path, point: str, round_no: int, timeout: float
) -> DrillResult:
    started = time.monotonic()
    root = workdir / f"{point.lower()}-r{round_no}"
    root.mkdir(parents=True)
    log = workdir / f"{root.name}.log"
    result = DrillResult(point=point, round=round_no)
    killed, detail = _crash(python, root, point, timeout, log)
    result.killed_by_sigkill = killed
    ledger_at_kill = _read_ledger(root)
    snapshot_path = root / PARK_SNAPSHOT_NAME
    snapshot = (
        json.loads(snapshot_path.read_text("utf-8")) if snapshot_path.exists() else None
    )
    reboots = (
        [
            _reboot(python, root, i, timeout, log)
            for i in range(1, REBOOTS_PER_DRILL + 1)
        ]
        if killed
        else []
    )
    ledger_after = _read_ledger(root)
    result.failures = judge(
        point, killed, ledger_at_kill, ledger_after, snapshot, reboots
    )
    if not killed:
        result.failures.insert(0, detail)
    result.passed = not result.failures
    result.venue_orders_at_kill = len(ledger_at_kill)
    result.venue_orders_after_restarts = len(ledger_after)
    result.duplicate_sends = sum(
        n - 1 for n in Counter(r["attempt_id"] for r in ledger_after).values()
    ) + max(0, len(ledger_after) - len(ledger_at_kill))
    result.reservations_at_crash = (snapshot or {}).get("reservations", {})
    result.reboots = reboots
    result.seconds = round(time.monotonic() - started, 2)
    return result


def _table(results: list[DrillResult]) -> str:
    rows = [
        "| point | round | SIGKILL | venue orders at kill → after 2 restarts | duplicates "
        "| barrier held (2/2) | capacity at crash = after | result |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        held = sum(
            1
            for b in r.reboots
            if "error" not in b and b["ready"] is False and not b["driver_wired"]
        )
        capacity = ", ".join(
            f"{k}={v}" for k, v in sorted(r.reservations_at_crash.items())
        )
        rows.append(
            f"| {r.point} | {r.round} | {'yes' if r.killed_by_sigkill else 'NO'} "
            f"| {r.venue_orders_at_kill} → {r.venue_orders_after_restarts} "
            f"| {r.duplicate_sends} | {held}/{REBOOTS_PER_DRILL} "
            f"| {capacity or '-'} | {'PASS' if r.passed else 'FAIL'} ({r.seconds}s) |"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--points", nargs="+", choices=POINTS, default=list(POINTS))
    parser.add_argument("--workdir", type=Path, default=None)
    parser.add_argument(
        "--json", type=Path, default=None, help="write per-drill results here"
    )
    parser.add_argument(
        "--timeout", type=float, default=120.0, help="seconds per child"
    )
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)

    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="tos-recovery-drill-"))
    workdir.mkdir(parents=True, exist_ok=True)
    results = [
        run_drill(args.python, workdir, point, round_no, args.timeout)
        for point in args.points
        for round_no in range(1, args.rounds + 1)
    ]
    passed = sum(r.passed for r in results)
    duplicates = sum(max(r.duplicate_sends, 0) for r in results)
    summary = (
        f"recovery drill: {passed}/{len(results)} passed, duplicate sends {duplicates} "
        f"(workdir {workdir})"
    )
    print(_table(results))
    print()
    print(summary)
    for r in results:
        for failure in r.failures:
            print(f"FAIL {r.point} r{r.round}: {failure}")
    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "passed": passed,
                    "total": len(results),
                    "duplicate_sends": duplicates,
                    "drills": [r.__dict__ for r in results],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fh:
            fh.write(f"## {summary}\n\n{_table(results)}\n")
    return 0 if passed == len(results) and results else 1


if __name__ == "__main__":
    sys.exit(main())
