#!/usr/bin/env python3
"""CP-3 post-session B3 — run the §3.6 reconciliation when a tenant session stops.

Roadmap ``docs/plans/2026-10-22-tos-rescope-plan.md`` §2-1 is measured off
``<session>/b3/report/summary.json``: "장후 B3 대조에서 unresolved = 0, 설명 안
되는 divergence 0". Before this module no session had ever produced that file —
B3 was the six-command manual recipe in
``docs/runbooks/tos-paper-boot-history.md`` §7.2-d, and the status board printed
"B3 대조: 결과 없음" every day.

**This module re-implements none of that recipe's math.** It runs the same six
tools as subprocesses, in the same order, with the same flags:

1. ``session_inputs.py consumed-ids``  — what the runtime actually consumed
2. ``session_inputs.py live-decisions`` — the live decision records
3. ``produce_fields.py``                — B1a, over the producer's FROZEN frame
4. ``emit_legacy_decisions.py``         — B2, same window
5. ``cp3.runner``                       — B1b, with the session's RENDERED tree
6. ``diff_decisions.py``                — B3 itself, the only writer of summary.json

Why the rendered tree for step 5 and not a committed copy: both committed copies
refuse this journal (the harness copy pins backtest literals, the tenant copy
leaves the two coordinate slots at ``"TBD"``), so B1b has to read
``$TENANT_RENDER_OUT`` — which is why B3 must run BEFORE the session directory
is cleaned up. Running it here, inside the session, is the only point where that
tree is guaranteed to exist.

Fail-closed, and this is the whole design:

* ``b3/status.json`` is written with ``verdict: "running"`` BEFORE the first
  step and replaced atomically at the end, so a missing input, a step that
  refuses, a wall-clock overrun or a SIGKILL all leave a record that says so.
* The file this module writes NEVER carries a verdict about the comparison.
  ``unresolved`` lives in ``summary.json`` and only ``diff_decisions.py`` writes
  it, so "the step did not run" can never read as ``unresolved = 0``.
* A B3 failure is not a session failure. The runner logs this process's exit
  code and keeps its own (``tools/tos_cp3/runners/run_tenant_session.sh`` step
  14): the session's verdict is about the runtime and the producer, and a
  reconciliation that could not run says nothing about either.

Exit codes (the runner records them, nothing branches on them):
``0`` the comparison ran · ``2`` it did not (missing input, a step's refusal,
the budget) · ``3`` it was skipped (disabled, or a market B3 does not cover) ·
``4`` even ``status.json`` could not be written, which is the one case with no
record on disk.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

#: Repo root, put on ``sys.path`` for the same reason B1a/B2/B3 do it: an
#: editable install of another checkout must not answer ``tools.tos_cp3``.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

#: Default config location, relative to :data:`REPO_ROOT`.
CONFIG_REL = "config/tos_cp3_b3.yaml"

#: ``status.json``'s shape. The status board pins the versions it can read
#: (``tools/tos_cp3/status_board.py::B3_STATUS_SCHEMA_VERSIONS``), so a shape
#: change here is a two-file change, never a silent one.
STATUS_SCHEMA_VERSION = 1

KST = ZoneInfo("Asia/Seoul")

#: Where ``config/tos_cp3_b3.yaml::total_timeout_s`` comes from — a real
#: post-session run, not a picked number. Every field below is read off one
#: session's own ``b3/status.json`` (``steps[*].seconds``), so re-measuring is
#: reading that file again rather than trusting this block.
TOTAL_TIMEOUT_MEASUREMENT: dict[str, Any] = {
    "measured_at": "2026-10-29",
    # The 10-28 LONG session's own artifacts, with its durable leaf read from
    # the cold-backup generation taken after that session stopped (gen9,
    # 2026-10-28 18:20) — the leaf as B3 would have seen it in the session.
    "session": "long-20261028",
    "frame_days": 5,
    "evidence_sqlite3_bytes": 763744256,
    "steps_seconds": {
        "consumed-ids": 0.82,
        "live-decisions": 2.07,
        "b1a-fields": 6.80,
        "b2-legacy": 7.40,
        "b1b-tos": 8.41,
        "b3-report": 0.37,
    },
    "total_seconds": 25.9,
    # Why the budget is ~18x the measurement rather than a tight bound: the
    # frozen frame stays ~5 days (the producer seeds that many) but the durable
    # leaf GROWS every session, and `live-decisions` and `consumed-ids` scan it.
    # The budget is not a performance target — it exists so a wedged step
    # cannot hold the cron wrapper's flock into the next day.
    "budget_seconds": 480,
}


class PostSessionB3Error(RuntimeError):
    """An input this module cannot work from — recorded, never worked around."""


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class B3Config:
    """``config/tos_cp3_b3.yaml``, validated."""

    enabled: bool
    markets: tuple[str, ...]
    subdir: str
    legacy_strategy_yaml: str
    total_timeout_s: int


def load_config(path: Path) -> B3Config:
    """Read and validate the YAML config.

    Raises:
        PostSessionB3Error: the file is missing, is not a mapping, or any key is
            missing or the wrong type. Every value is required: a default here
            is a threshold that stops being config.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PostSessionB3Error(f"config not found: {path}") from exc
    except (OSError, yaml.YAMLError) as exc:
        raise PostSessionB3Error(f"config unreadable: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise PostSessionB3Error(f"config is not a mapping: {path}")

    def need(key: str, kind: type) -> Any:
        if key not in raw:
            raise PostSessionB3Error(f"config {path} has no {key!r}")
        value = raw[key]
        # `isinstance(True, int)` is True, so a bool would pass for an int and a
        # typo like `total_timeout_s: yes` would become a one-second budget.
        wrong_kind = not isinstance(value, kind)
        bool_mixup = isinstance(value, bool) != (kind is bool)
        if wrong_kind or bool_mixup:
            raise PostSessionB3Error(
                f"config {path}: {key!r} must be {kind.__name__}, got {value!r}"
            )
        return value

    markets = need("markets", list)
    if not markets or not all(isinstance(m, str) and m for m in markets):
        raise PostSessionB3Error(f"config {path}: 'markets' must be non-empty strings")
    total = need("total_timeout_s", int)
    if total <= 0:
        raise PostSessionB3Error(f"config {path}: 'total_timeout_s' must be positive")
    subdir = need("subdir", str)
    if not subdir or "/" in subdir or subdir.startswith("."):
        raise PostSessionB3Error(
            f"config {path}: 'subdir' must be a single plain directory name,"
            f" got {subdir!r}"
        )
    return B3Config(
        enabled=need("enabled", bool),
        markets=tuple(markets),
        subdir=subdir,
        legacy_strategy_yaml=need("legacy_strategy_yaml", str),
        total_timeout_s=total,
    )


# ---------------------------------------------------------------------------
# the window
# ---------------------------------------------------------------------------


def stitch_first_day(manifest: Path) -> str:
    """The earliest day in the producer's stitch manifest — B1a/B2's ``--start``.

    The runbook's recipe reads it from the same place ("stitch 의 첫 날 = the
    earliest segment day"), and the producer's own ``seed`` record agrees with
    it.

    Raises:
        PostSessionB3Error: the manifest is missing, unparseable, or carries no
            segment day. A guessed window is a comparison against the wrong
            bars.
    """
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PostSessionB3Error(f"stitch manifest not found: {manifest}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise PostSessionB3Error(
            f"stitch manifest unreadable: {manifest}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise PostSessionB3Error(f"stitch manifest is not an object: {manifest}")
    days: list[str] = []
    for segment in raw.get("segments") or ():
        if not isinstance(segment, dict):
            continue
        for day in segment.get("days") or ():
            if isinstance(day, str):
                days.append(day)
    if not days:
        raise PostSessionB3Error(
            f"stitch manifest {manifest} lists no segment day — no window to compare"
        )
    return min(days)


def _one_rendered_strategy(render_out: Path) -> Path:
    """The session's rendered Authored Strategy YAML (step 5's ``--strategy``).

    The direction is not read from a flag: a rendered tenant tree holds exactly
    one strategy file, ``setup_d_long`` or ``setup_d_short``, and taking the one
    that is there cannot disagree with the tree the session actually booted.

    Raises:
        PostSessionB3Error: zero or several candidates.
    """
    found = sorted((render_out / "strategies").glob("*.strategy.yaml"))
    if len(found) != 1:
        raise PostSessionB3Error(
            f"expected exactly one *.strategy.yaml under {render_out / 'strategies'},"
            f" found {[p.name for p in found]}"
        )
    return found[0]


# ---------------------------------------------------------------------------
# the steps
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Step:
    """One subprocess: the recipe's own command, as a list."""

    name: str
    argv: tuple[str, ...]
    extra_env: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Plan:
    """What :func:`run` will do, resolved from the session's own artifacts."""

    steps: tuple[Step, ...]
    b3_dir: Path
    window_start: str
    window_end: str
    summary_path: Path


def plan_steps(
    *,
    session_dir: Path,
    data_leaf: Path,
    producer_session_dir: Path,
    render_out: Path,
    instrument: str,
    session_day: str,
    config: B3Config,
    python: str,
    repo_root: Path = REPO_ROOT,
) -> Plan:
    """Resolve the six commands against this session's artifacts.

    Pure: it reads the stitch manifest and checks that every input exists, and
    writes nothing. Every path it refuses is named in the message, because the
    record this produces is the only thing an operator gets back.

    Raises:
        PostSessionB3Error: any input is missing, or the window cannot be read.
    """
    producer_log = producer_session_dir / "producer-log.jsonl"
    boot_snapshot = producer_session_dir / "boot-journal-snapshot.json"
    data_root = producer_session_dir / "market"
    manifest = data_root / "stitch.json"
    bindings = render_out / "strategy_bindings.yaml"
    legacy_strategy = repo_root / config.legacy_strategy_yaml

    missing = [
        str(path)
        for path in (producer_log, boot_snapshot, manifest, bindings, legacy_strategy)
        if not path.is_file()
    ]
    if not data_leaf.is_dir():
        missing.append(f"{data_leaf} (durable set leaf)")
    else:
        missing.extend(
            str(data_leaf / name)
            for name in ("marketfeed.sqlite3", "evidence.sqlite3", "inbox.sqlite3")
            if not (data_leaf / name).is_file()
        )
    if missing:
        raise PostSessionB3Error("input(s) missing: " + ", ".join(sorted(missing)))

    strategy = _one_rendered_strategy(render_out)
    window_start = stitch_first_day(manifest)
    if window_start > session_day:
        raise PostSessionB3Error(
            f"stitch manifest's first day {window_start} is after the session day"
            f" {session_day} — the frame does not cover this session"
        )

    b3 = session_dir / config.subdir
    tool = repo_root / "tools" / "tos_cp3"
    window = (
        "--symbol",
        instrument,
        "--start",
        window_start,
        "--end",
        session_day,
        "--strategy-yaml",
        str(legacy_strategy),
        "--stitch-manifest",
        str(manifest),
    )
    steps = (
        Step(
            "consumed-ids",
            (
                python,
                str(tool / "session_inputs.py"),
                "consumed-ids",
                "--data-dir",
                str(data_leaf),
                "--producer-log",
                str(producer_log),
                "--boot-snapshot",
                str(boot_snapshot),
                "--out",
                str(b3 / "consumed-ids.json"),
            ),
        ),
        Step(
            "live-decisions",
            (
                python,
                str(tool / "session_inputs.py"),
                "live-decisions",
                "--data-dir",
                str(data_leaf),
                # Same reason as step 1's: the durable leaf accumulates
                # sessions, and a store-wide live.jsonl makes step 6 refuse
                # (session_inputs.LiveScope has the measurement).
                "--boot-snapshot",
                str(boot_snapshot),
                "--out",
                str(b3 / "live"),
            ),
        ),
        Step(
            "b1a-fields",
            (
                python,
                str(tool / "produce_fields.py"),
                "--data-root",
                str(data_root),
                *window,
                "--out",
                str(b3 / "b1a"),
            ),
        ),
        Step(
            "b2-legacy",
            (
                python,
                str(tool / "emit_legacy_decisions.py"),
                "--data-root",
                str(data_root),
                *window,
                "--out",
                str(b3 / "b2"),
            ),
        ),
        Step(
            "b1b-tos",
            (
                python,
                "-m",
                "cp3.runner",
                "--fields",
                str(b3 / "b1a" / "fields.jsonl"),
                "--strategy",
                str(strategy),
                "--bindings",
                str(bindings),
                "--out",
                str(b3 / "b1b"),
            ),
            # B1b is the one step that imports the kernel. The three roots are
            # the runbook's, in its order: `cp3` lives in tos/runtime, and the
            # two src roots are what it imports.
            extra_env=(
                (
                    "PYTHONPATH",
                    os.pathsep.join(
                        (
                            str(repo_root / "tos" / "src"),
                            str(repo_root / "tos" / "runtime" / "src"),
                            str(repo_root / "tos" / "runtime"),
                        )
                    ),
                ),
            ),
        ),
        Step(
            "b3-report",
            (
                python,
                str(tool / "diff_decisions.py"),
                "--fields",
                str(b3 / "b1a" / "fields.jsonl"),
                "--legacy",
                str(b3 / "b2" / "decisions.jsonl"),
                "--tos",
                str(b3 / "b1b" / "trace.jsonl"),
                "--consumed-ids",
                str(b3 / "consumed-ids.json"),
                "--live",
                str(b3 / "live" / "live.jsonl"),
                "--out",
                str(b3 / "report"),
            ),
        ),
    )
    return Plan(
        steps=steps,
        b3_dir=b3,
        window_start=window_start,
        window_end=session_day,
        summary_path=b3 / "report" / "summary.json",
    )


# ---------------------------------------------------------------------------
# the record
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.datetime.now(tz=KST).isoformat(timespec="seconds")


@dataclass
class StatusWriter:
    """``b3/status.json``, replaced atomically on every write.

    Atomic because the one failure mode this record exists for is the process
    not getting to finish: a half-written JSON file reads as "unparseable", and
    the status board would then have to guess whether B3 ran.
    """

    path: Path
    payload: dict[str, Any] = field(default_factory=dict)

    def write(self, **updates: Any) -> None:
        self.payload.update(updates)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(
            json.dumps(self.payload, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, self.path)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


def _run_step(
    step: Step, *, log_dir: Path, cwd: Path, timeout_s: float
) -> tuple[int, float, Path]:
    """Run one step, capture its output to a file, and return (rc, seconds, log).

    ``rc`` is the process's own code, or ``124`` for a step the budget cut off —
    the code ``timeout(1)`` uses for the same thing, so a reader of the record
    does not need a second vocabulary.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{step.name}.log"
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        **dict(step.extra_env),
    }
    started = time.monotonic()
    with log_path.open("w", encoding="utf-8") as handle:
        handle.write(f"$ {' '.join(step.argv)}\n")
        handle.flush()
        try:
            completed = subprocess.run(
                step.argv,
                stdout=handle,
                stderr=subprocess.STDOUT,
                cwd=str(cwd),
                env=env,
                timeout=timeout_s,
                check=False,
            )
            rc = completed.returncode
        except subprocess.TimeoutExpired:
            handle.write(f"\n[post_session_b3] cut off after {timeout_s:.0f}s\n")
            rc = 124
        except OSError as exc:
            handle.write(f"\n[post_session_b3] could not start: {exc}\n")
            rc = 127
    return rc, time.monotonic() - started, log_path


def run(
    *,
    session_dir: Path,
    data_leaf: Path,
    producer_session_dir: Path,
    render_out: Path,
    instrument: str,
    session_day: str,
    market: str,
    config: B3Config,
    python: str,
    repo_root: Path = REPO_ROOT,
    step_runner: Any = _run_step,
) -> int:
    """Run the comparison and leave a record either way. Returns the exit code.

    ``step_runner`` is injected so the tests drive the whole sequence without
    six real subprocesses; production never passes it.
    """
    status = StatusWriter(session_dir / config.subdir / "status.json")
    status.payload.update(
        {
            "status_schema_version": STATUS_SCHEMA_VERSION,
            "session_day": session_day,
            "instrument": instrument,
            "market": market,
            "started_at": _now(),
            "ended_at": None,
            "stage": None,
            "steps": [],
            "window": None,
            "summary_json": None,
            "total_timeout_s": config.total_timeout_s,
        }
    )

    if not config.enabled:
        status.write(
            verdict="skipped",
            reason="config/tos_cp3_b3.yaml::enabled is false",
            ended_at=_now(),
        )
        return 3
    if market not in config.markets:
        status.write(
            verdict="skipped",
            reason=f"market {market!r} is not in config markets {list(config.markets)}",
            ended_at=_now(),
        )
        return 3

    try:
        plan = plan_steps(
            session_dir=session_dir,
            data_leaf=data_leaf,
            producer_session_dir=producer_session_dir,
            render_out=render_out,
            instrument=instrument,
            session_day=session_day,
            config=config,
            python=python,
            repo_root=repo_root,
        )
    except PostSessionB3Error as exc:
        status.write(verdict="failed", stage="inputs", reason=str(exc), ended_at=_now())
        return 2

    status.write(
        verdict="running",
        reason="",
        window={"start": plan.window_start, "end": plan.window_end},
    )

    deadline = time.monotonic() + config.total_timeout_s
    records: list[dict[str, Any]] = []
    for step in plan.steps:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            status.write(
                verdict="failed",
                stage=step.name,
                reason=(
                    f"the {config.total_timeout_s}s budget ran out before"
                    f" {step.name!r} started"
                ),
                ended_at=_now(),
            )
            return 2
        rc, seconds, log_path = step_runner(
            step,
            log_dir=plan.b3_dir / "logs",
            cwd=repo_root,
            timeout_s=remaining,
        )
        records.append(
            {
                "name": step.name,
                "rc": rc,
                "seconds": round(seconds, 3),
                "log": str(log_path),
            }
        )
        status.write(steps=list(records))
        if rc != 0:
            status.write(
                verdict="failed",
                stage=step.name,
                reason=f"{step.name} exited {rc} — see {log_path}",
                ended_at=_now(),
            )
            return 2

    if not plan.summary_path.is_file():
        status.write(
            verdict="failed",
            stage="b3-report",
            reason=(
                f"every step exited 0 but {plan.summary_path} is not there —"
                " nothing measures §2-1 without it"
            ),
            ended_at=_now(),
        )
        return 2

    status.write(
        verdict="ok",
        reason="",
        summary_json=str(plan.summary_path),
        ended_at=_now(),
    )
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools/tos_cp3/post_session_b3.py",
        description=(
            "CP-3 §3.6 B3 — run the post-session reconciliation from a tenant "
            "session's own artifacts and leave a record either way."
        ),
    )
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument(
        "--data-leaf",
        type=Path,
        required=True,
        help="the durable set leaf the runtime wrote (<data parent>/<instrument>)",
    )
    parser.add_argument("--producer-session-dir", type=Path, required=True)
    parser.add_argument(
        "--render-out",
        type=Path,
        required=True,
        help="the session's RENDERED tree — B1b's only loadable strategy copy",
    )
    parser.add_argument("--instrument", required=True)
    parser.add_argument(
        "--session-day", required=True, help="the session's KST day, YYYY-MM-DD"
    )
    parser.add_argument(
        "--market",
        required=True,
        help="the tree's market; B3 runs only for the markets the config lists",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="the interpreter the six tools run under (default: this one)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / CONFIG_REL,
        help=f"default {CONFIG_REL} in this checkout",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        datetime.date.fromisoformat(args.session_day)
    except ValueError:
        print(
            f"post_session_b3: --session-day {args.session_day!r} is not YYYY-MM-DD",
            file=sys.stderr,
        )
        return 4
    try:
        config = load_config(args.config)
    except PostSessionB3Error as exc:
        # No config, no subdir name, so nowhere to write the record — this is
        # the one path that leaves nothing on disk, and it says so.
        print(f"post_session_b3: {exc}", file=sys.stderr)
        return 4
    try:
        rc = run(
            session_dir=args.session_dir,
            data_leaf=args.data_leaf,
            producer_session_dir=args.producer_session_dir,
            render_out=args.render_out,
            instrument=args.instrument,
            session_day=args.session_day,
            market=args.market,
            config=config,
            python=args.python,
        )
    except OSError as exc:
        print(f"post_session_b3: cannot write the record: {exc}", file=sys.stderr)
        return 4
    status_path = args.session_dir / config.subdir / "status.json"
    print(f"post_session_b3: rc={rc} record={status_path}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
