#!/usr/bin/env python3
"""Harvest an F-9 Gate 1 shadow session and verdict whether it was observed.

Two halves, run after the close:

1. **Harvest** — copy each service's container log to
   ``reports/f9-gate1/<KST date>/<service>.<HHMMSS>.log``. Never overwrites: a
   mid-day harvest and a post-close harvest both survive as separate files, and
   the verdict reads all of them. This is the half the runbook used to carry as
   inline bash (``docs/runbooks/futures-pipeline-cutover-f9.md``), including its
   ``--tail 900`` caveat for the decision-engine.

2. **Verdict** — decide, per consumer, whether it *demonstrably observed*
   during the session, and emit a day-level completeness verdict.

Why the second half exists
--------------------------
The runbook's observation-log ``Consumers`` column used to record how many
consumers were **running**. That is the wrong measurement and it failed
silently: from 2026-09-17 00:00 to 2026-09-18 12:34 both monitor daemons were
up with ``RestartCount=0`` while consuming nothing (a vanished-stream NOGROUP
loop, fixed in PRs #739/#741). A row written on either day would have said "4"
and been wrong, and a reader would have taken two days of "no signals" for a
quiet market rather than for a dead instrument.

The runbook already states this trap one level down, in its INERT-GATE CAVEAT:
*"No volatility or spread rejections in N trading days is not evidence those
controls work — it is exactly what you would observe if they are unable to
fire."* Nobody applied it to the observation surface itself. This script does:
**"observed 0" and "could not observe" never occupy the same cell.**

Durable vs point-in-time
------------------------
Redis streams carry a 24h TTL and their entries vanish, so the verdict for a
past day is derived **only** from the harvested log files. Live Redis and
``docker inspect`` state is collected for context, labelled ``point_in_time``
in the JSON sidecar, and never feeds the verdict.

Usage::

    python scripts/ops/f9_observation_harvest.py                  # today, harvest + verdict
    python scripts/ops/f9_observation_harvest.py --date 2026-09-18  # past day, verdict only
    python scripts/ops/f9_observation_harvest.py --no-harvest       # verdict from existing files
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date as date_cls
from datetime import datetime
from datetime import time as time_cls
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from shared.decision.context import (
    load_futures_close_from_config,
    load_futures_open_from_config,
)

# This project is KST-native (Korea); all time math uses Asia/Seoul, not UTC.
KST = ZoneInfo("Asia/Seoul")

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = _REPO_ROOT / "config" / "f9_observation.yaml"
DEFAULT_SCHEDULE_PATH = _REPO_ROOT / "config" / "market_schedule.yaml"

#: Day-level verdicts. Deliberately three words rather than a boolean: the
#: failure this file prevents is a reader collapsing "observed nothing" into
#: "could not observe", so the token names the *observation*, not the outcome.
VERDICT_COMPLETE = "COMPLETE"
VERDICT_PARTIAL = "PARTIAL"
VERDICT_NOT_OBSERVED = "NOT_OBSERVED"

#: Per-service statuses.
STATUS_CONSUMED = "consumed"
STATUS_PARTIALLY_BLIND = "partially_blind"
STATUS_BLIND = "blind"
STATUS_IDLE_NO_TRAFFIC = "idle_no_traffic"
STATUS_NO_EVIDENCE = "no_evidence"

ROLE_PRODUCER = "producer"
ROLE_CONSUMER = "consumer"
ROLE_REFERENCE = "reference"

#: Both deployed log formats start with the same KST ``asctime``:
#: ``2026-09-18 09:47:37,466 WARNING shared.streaming.stage …`` (decoupled
#: daemons) and ``2026-09-18 08:45:00,004 - services.trading… - INFO - …``
#: (orchestrator). Continuation lines of a traceback carry no timestamp and are
#: therefore not evidence of anything.
_TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d{3}")

#: Cells the script cannot derive (they need the runtime ledger and an operator
#: comparison). Named rather than left blank so an unfilled cell is obvious.
MANUAL_CELL = "(manual)"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CounterSpec:
    """A named count extracted from one service's session lines."""

    name: str
    pattern: re.Pattern[str]
    keep_last_per_key: bool = False
    count_state: str | None = None


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    container: str
    role: str
    harvest_mode: str
    harvest_tail: int | None
    observed: tuple[re.Pattern[str], ...]
    blind: tuple[re.Pattern[str], ...]
    counters: tuple[CounterSpec, ...]


@dataclass(frozen=True)
class ObservationConfig:
    report_root: Path
    container_prefix: str
    harvest_since: time_cls
    blind_run_merge_seconds: int
    row_counters: tuple[str, ...]
    services: tuple[ServiceSpec, ...]
    point_in_time: Mapping[str, Any]


def _compile_all(patterns: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p) for p in patterns)


def _parse_counters(raw: Mapping[str, Any]) -> tuple[CounterSpec, ...]:
    specs = []
    for name, body in raw.items():
        specs.append(
            CounterSpec(
                name=name,
                pattern=re.compile(str(body["pattern"])),
                keep_last_per_key=bool(body.get("keep_last_per_key", False)),
                count_state=body.get("count_state"),
            )
        )
    return tuple(specs)


def load_observation_config(
    path: Path = DEFAULT_CONFIG_PATH, *, repo_root: Path = _REPO_ROOT
) -> ObservationConfig:
    """Load ``config/f9_observation.yaml``.

    Raises rather than falling back to defaults: a harvest that silently
    targeted the wrong containers would produce exactly the false-confidence
    row this script exists to prevent.
    """
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    root = document["f9_observation"]

    services = []
    for entry in root["services"]:
        services.append(
            ServiceSpec(
                name=str(entry["name"]),
                container=str(entry["container"]),
                role=str(entry["role"]),
                harvest_mode=str(entry.get("harvest_mode", "since")),
                harvest_tail=(
                    int(entry["harvest_tail"]) if entry.get("harvest_tail") else None
                ),
                observed=_compile_all(entry.get("observed", ())),
                blind=_compile_all(entry.get("blind", ())),
                counters=_parse_counters(entry.get("counters", {}) or {}),
            )
        )

    hour, minute = (int(part) for part in str(root["harvest_since"]).split(":")[:2])
    report_root = Path(root["report_root"])
    if not report_root.is_absolute():
        report_root = repo_root / report_root

    return ObservationConfig(
        report_root=report_root,
        container_prefix=str(root["container_prefix"]),
        harvest_since=time_cls(hour, minute),
        blind_run_merge_seconds=int(root["blind_run_merge_seconds"]),
        row_counters=tuple(str(name) for name in root["row_counters"]),
        services=tuple(services),
        point_in_time=dict(root.get("point_in_time", {}) or {}),
    )


def session_window(
    day: date_cls, *, schedule_path: Path = DEFAULT_SCHEDULE_PATH
) -> tuple[datetime, datetime]:
    """Return the KST futures session ``(open, close)`` for *day*.

    Reuses ``shared.decision.context``'s loader (PR #668) so the observation
    window is the same one the decision engine anchors ``minutes_since_open``
    to — a second parser here could drift from the runtime's idea of a session.
    """
    open_h, open_m = load_futures_open_from_config(str(schedule_path))
    close_h, close_m = load_futures_close_from_config(str(schedule_path))
    return (
        datetime.combine(day, time_cls(open_h, open_m), tzinfo=KST),
        datetime.combine(day, time_cls(close_h, close_m), tzinfo=KST),
    )


# ---------------------------------------------------------------------------
# Harvest
# ---------------------------------------------------------------------------

Runner = Callable[[Sequence[str]], "subprocess.CompletedProcess[bytes]"]


def _run_capture(command: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(list(command), capture_output=True, check=False)


def harvest_logs(
    config: ObservationConfig,
    day: date_cls,
    *,
    stamp: str,
    runner: Runner = _run_capture,
) -> dict[str, Path]:
    """Copy each configured container's log into the day's report directory.

    Never overwrites an existing harvest — every run writes fresh
    ``<service>.<HHMMSS KST>.log`` files, so harvesting before a mid-session
    redeploy and again at the close keeps both halves of the day.
    """
    out_dir = config.report_root / day.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    for spec in config.services:
        destination = out_dir / f"{spec.name}.{stamp}.log"
        if destination.exists():
            raise FileExistsError(
                f"{destination} already exists; harvests are never overwritten"
            )
        command = ["docker", "logs"]
        if spec.harvest_mode == "tail":
            # `docker logs` without --tail (or with a large one) stops at the
            # broken record left by the 2026-09-09 host reboots. See the
            # runbook's --tail caveat.
            command += ["--tail", str(spec.harvest_tail or 900)]
        else:
            since = datetime.combine(day, config.harvest_since, tzinfo=KST)
            command += ["--since", since.isoformat()]
        command.append(f"{config.container_prefix}{spec.container}")

        completed = runner(command)
        # The daemons log through logging.basicConfig (stderr), so the runbook's
        # `2>&1` is the interesting half — keep both.
        destination.write_bytes((completed.stdout or b"") + (completed.stderr or b""))
        written[spec.name] = destination
    return written


# ---------------------------------------------------------------------------
# Evidence scan (durable — harvested files only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceObservation:
    name: str
    role: str
    status: str
    observed_count: int
    first_observed: datetime | None
    last_observed: datetime | None
    blind_count: int
    blind_windows: tuple[tuple[datetime, datetime], ...]
    counters: Mapping[str, int]
    files: tuple[str, ...]


@dataclass(frozen=True)
class DayObservation:
    day: date_cls
    session_open: datetime
    session_close: datetime
    verdict: str
    services: tuple[ServiceObservation, ...]
    counters: Mapping[str, int]
    point_in_time: Mapping[str, Any]


def service_log_files(directory: Path, service: str) -> tuple[Path, ...]:
    """Every harvest of *service* in *directory*, oldest stamp first."""
    if not directory.is_dir():
        return ()
    return tuple(sorted(directory.glob(f"{service}.*.log")))


def _read_timestamped_lines(paths: Iterable[Path]) -> list[tuple[datetime, str]]:
    """De-duplicate and time-order the timestamped lines across harvests.

    Two harvests of a container that was not recreated in between overlap; this
    is the runbook's ``cat … | sort -u``, which drops the shared lines while
    keeping genuine redeliveries (their timestamps differ).
    """
    unique: set[str] = set()
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        unique.update(line for line in text.splitlines() if line)

    parsed: list[tuple[datetime, str]] = []
    for line in unique:
        match = _TIMESTAMP_RE.match(line)
        if match is None:
            continue
        moment = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=KST
        )
        parsed.append((moment, line))
    parsed.sort()
    return parsed


def _merge_windows(
    moments: Sequence[datetime], merge_gap_seconds: int
) -> tuple[tuple[datetime, datetime], ...]:
    """Collapse a run of timestamps into ``(start, end)`` windows."""
    if not moments:
        return ()
    windows: list[list[datetime]] = [[moments[0], moments[0]]]
    for moment in moments[1:]:
        if (moment - windows[-1][1]).total_seconds() <= merge_gap_seconds:
            windows[-1][1] = moment
        else:
            windows.append([moment, moment])
    return tuple((start, end) for start, end in windows)


def _count(spec: CounterSpec, lines: Sequence[tuple[datetime, str]]) -> int:
    if not spec.keep_last_per_key:
        return sum(1 for _, line in lines if spec.pattern.search(line))

    # Keep the LAST match per key (lines are time-ordered) and count the ones
    # whose state matches — the runbook's de-duplication rule for redelivered
    # candidates, which log a fresh verdict under the same msg_id.
    last_state: dict[str, str] = {}
    for _, line in lines:
        match = spec.pattern.search(line)
        if match is None:
            continue
        groups = match.groupdict()
        last_state[groups.get("key", "")] = groups.get("state", "")
    return sum(1 for state in last_state.values() if state == spec.count_state)


def scan_service(
    spec: ServiceSpec,
    files: Sequence[Path],
    *,
    session_open: datetime,
    session_close: datetime,
    blind_run_merge_seconds: int,
) -> ServiceObservation:
    """Classify one service from its harvested logs.

    A line is blindness evidence before it is observation evidence: a setup
    rejected for ``no_market_context`` is the daemon saying it had no input,
    not a completed evaluation.
    """
    lines = [
        (moment, line)
        for moment, line in _read_timestamped_lines(files)
        if session_open <= moment <= session_close
    ]

    observed: list[datetime] = []
    blind: list[datetime] = []
    for moment, line in lines:
        if any(pattern.search(line) for pattern in spec.blind):
            blind.append(moment)
        elif any(pattern.search(line) for pattern in spec.observed):
            observed.append(moment)

    if blind and observed:
        status = STATUS_PARTIALLY_BLIND
    elif blind:
        status = STATUS_BLIND
    elif observed:
        status = STATUS_CONSUMED
    else:
        # Undecidable from this service alone: "healthy but nothing arrived"
        # and "silently dead" look identical here. resolve_day() decides,
        # using whether anything was due for it at all.
        status = STATUS_NO_EVIDENCE

    return ServiceObservation(
        name=spec.name,
        role=spec.role,
        status=status,
        observed_count=len(observed),
        first_observed=observed[0] if observed else None,
        last_observed=observed[-1] if observed else None,
        blind_count=len(blind),
        blind_windows=_merge_windows(blind, blind_run_merge_seconds),
        counters={counter.name: _count(counter, lines) for counter in spec.counters},
        files=tuple(str(path) for path in files),
    )


def _scored(services: Iterable[ServiceObservation]) -> list[ServiceObservation]:
    return [s for s in services if s.role != ROLE_REFERENCE]


def resolve_day(
    services: Sequence[ServiceObservation],
) -> tuple[tuple[ServiceObservation, ...], str, dict[str, int]]:
    """Resolve the undecidable services, then verdict the day."""
    counters: dict[str, int] = {}
    for service in services:
        for name, value in service.counters.items():
            counters[name] = counters.get(name, 0) + value

    producers = [s for s in services if s.role == ROLE_PRODUCER]
    # "Nothing was due" is only credible when every PRODUCER demonstrably
    # observed for the whole session AND produced nothing. A producer that was
    # blind for part of the day cannot tell us whether candidates were missed,
    # so a silent consumer downstream of it stays undecidable.
    nothing_was_due = bool(producers) and all(
        service.status == STATUS_CONSUMED and not any(service.counters.values())
        for service in producers
    )

    resolved = tuple(
        (
            replace(service, status=STATUS_IDLE_NO_TRAFFIC)
            if (
                service.status == STATUS_NO_EVIDENCE
                and service.role == ROLE_CONSUMER
                and nothing_was_due
            )
            else service
        )
        for service in services
    )

    scored = _scored(resolved)
    observed_anywhere = any(
        s.status in (STATUS_CONSUMED, STATUS_PARTIALLY_BLIND) for s in scored
    )
    if not scored or not observed_anywhere:
        verdict = VERDICT_NOT_OBSERVED
    elif all(s.status in (STATUS_CONSUMED, STATUS_IDLE_NO_TRAFFIC) for s in scored):
        verdict = VERDICT_COMPLETE
    else:
        verdict = VERDICT_PARTIAL
    return resolved, verdict, counters


def observe_day(
    config: ObservationConfig,
    day: date_cls,
    *,
    schedule_path: Path = DEFAULT_SCHEDULE_PATH,
    point_in_time: Mapping[str, Any] | None = None,
) -> DayObservation:
    """Verdict *day* from the harvested files under the configured report root."""
    session_open, session_close = session_window(day, schedule_path=schedule_path)
    directory = config.report_root / day.isoformat()

    scanned = [
        scan_service(
            spec,
            service_log_files(directory, spec.name),
            session_open=session_open,
            session_close=session_close,
            blind_run_merge_seconds=config.blind_run_merge_seconds,
        )
        for spec in config.services
    ]
    services, verdict, counters = resolve_day(scanned)
    return DayObservation(
        day=day,
        session_open=session_open,
        session_close=session_close,
        verdict=verdict,
        services=services,
        counters=counters,
        point_in_time=dict(point_in_time or {}),
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _hhmm(moment: datetime) -> str:
    return moment.astimezone(KST).strftime("%H:%M")


def _window_text(windows: Sequence[tuple[datetime, datetime]]) -> str:
    parts = []
    for start, end in windows:
        parts.append(
            _hhmm(start)
            if _hhmm(start) == _hhmm(end)
            else f"{_hhmm(start)}-{_hhmm(end)}"
        )
    return ", ".join(parts)


def describe_service(service: ServiceObservation) -> str:
    """One clause naming what a non-consuming service did, and when."""
    if service.status == STATUS_BLIND:
        return f"{service.name} BLIND {_window_text(service.blind_windows)}"
    if service.status == STATUS_PARTIALLY_BLIND:
        return f"{service.name} blind {_window_text(service.blind_windows)}"
    if service.status == STATUS_IDLE_NO_TRAFFIC:
        return f"{service.name} idle (nothing was due)"
    if service.status == STATUS_NO_EVIDENCE:
        return f"{service.name} NO EVIDENCE (could not observe)"
    return f"{service.name} consumed"


def render_consumers_cell(result: DayObservation) -> str:
    """The ``Consumers`` cell — consumers that demonstrably CONSUMED.

    Not "how many are running": see this module's docstring for the 09-17/09-18
    blind window that made the running count worthless.
    """
    scored = _scored(result.services)
    consumed = [s for s in scored if s.status == STATUS_CONSUMED]
    idle = [s for s in scored if s.status == STATUS_IDLE_NO_TRAFFIC]
    tally = f"{len(consumed)}/{len(scored)} consumed"
    if result.verdict == VERDICT_COMPLETE:
        if not idle:
            return f"{tally} (COMPLETE)"
        # A genuine quiet market: the producer observed the whole session and
        # emitted nothing, so the downstream consumers had nothing to consume.
        # Spelled out rather than folded into the consumed count, which would
        # claim proof these consumers never produced.
        return (
            f"{len(consumed) + len(idle)}/{len(scored)} observing "
            f"({len(consumed)} consumed, {len(idle)} idle - nothing was due) "
            "(COMPLETE)"
        )

    problems = "; ".join(
        describe_service(s) for s in scored if s.status != STATUS_CONSUMED
    )
    marker = (
        "**NOT OBSERVED**"
        if result.verdict == VERDICT_NOT_OBSERVED
        else "**NOT COMPLETE**"
    )
    return f"{marker} - {tally} ({result.verdict}): {problems}"


def render_counts_cell(result: DayObservation, row_counters: Sequence[str]) -> str:
    """The candidates -> final -> fills cell, qualified by the verdict.

    A bare "0 -> 0 -> 0" from a day whose observation surface was blind reads
    identically to a genuine quiet market. It never ships bare.
    """
    counts = " -> ".join(str(result.counters.get(name, 0)) for name in row_counters)
    if result.verdict == VERDICT_COMPLETE:
        return counts
    return (
        f"{counts} - UNQUALIFIED: observation {result.verdict}, "
        "these are a lower bound, not a measurement"
    )


def render_row(
    result: DayObservation, row_counters: Sequence[str], sidecar: Path | None = None
) -> str:
    """The markdown row for the runbook's Shadow observation log table."""
    notes = f"observation={result.verdict}"
    if sidecar is not None:
        notes += f"; evidence {sidecar}"
    return " | ".join(
        (
            "",
            result.day.isoformat(),
            render_consumers_cell(result),
            render_counts_cell(result, row_counters),
            MANUAL_CELL,
            MANUAL_CELL,
            notes,
            "",
        )
    ).strip()


def build_sidecar(result: DayObservation, row: str) -> dict[str, Any]:
    """Per-consumer detail, so a later reader can audit the verdict."""
    return {
        "day": result.day.isoformat(),
        "session_open_kst": result.session_open.isoformat(),
        "session_close_kst": result.session_close.isoformat(),
        "verdict": result.verdict,
        "verdict_inputs": "durable: harvested log files only (Redis streams "
        "expire after 24h, so a past day is not reconstructible from Redis)",
        "counters": dict(result.counters),
        "counters_qualified": result.verdict == VERDICT_COMPLETE,
        "row": row,
        "services": [
            {
                "name": service.name,
                "role": service.role,
                "status": service.status,
                "observed_count": service.observed_count,
                "first_observed_kst": (
                    service.first_observed.isoformat()
                    if service.first_observed
                    else None
                ),
                "last_observed_kst": (
                    service.last_observed.isoformat() if service.last_observed else None
                ),
                "blind_count": service.blind_count,
                "blind_windows_kst": [
                    [start.isoformat(), end.isoformat()]
                    for start, end in service.blind_windows
                ],
                "counters": dict(service.counters),
                "evidence_files": list(service.files),
            }
            for service in result.services
        ],
        "point_in_time": dict(result.point_in_time),
    }


# ---------------------------------------------------------------------------
# Point-in-time context (never an input to the verdict)
# ---------------------------------------------------------------------------


def collect_point_in_time(
    config: ObservationConfig,
    day: date_cls,
    *,
    runner: Runner = _run_capture,
) -> dict[str, Any]:
    """Best-effort live state. Failures are recorded, never raised."""
    settings = config.point_in_time
    snapshot: dict[str, Any] = {
        "collected_at_kst": datetime.now(KST).isoformat(),
        "caveat": "point-in-time only; Redis stream entries expire after 24h "
        "and container state is now, not during the session. Not an input to "
        "the verdict.",
        "containers": {},
        "redis": {},
    }

    for spec in config.services:
        name = f"{config.container_prefix}{spec.container}"
        completed = runner(
            [
                "docker",
                "inspect",
                "--format",
                "{{.RestartCount}}|{{.State.StartedAt}}|{{.State.Status}}",
                name,
            ]
        )
        text = (completed.stdout or b"").decode("utf-8", "replace").strip()
        if completed.returncode != 0 or "|" not in text:
            snapshot["containers"][spec.name] = {"error": "docker inspect failed"}
            continue
        restarts, started_at, state = text.split("|", 2)
        snapshot["containers"][spec.name] = {
            "restart_count": restarts,
            "started_at": started_at,
            "state": state,
        }

    try:
        import redis as redis_lib
    except ImportError:  # pragma: no cover - redis is a runtime dependency
        snapshot["redis"] = {"error": "redis package unavailable"}
        return snapshot

    url = os.environ.get(
        str(settings.get("redis_url_env", "REDIS_URL")),
        str(settings.get("redis_url_default", "redis://localhost:6379/1")),
    )
    try:
        client = redis_lib.Redis.from_url(url, decode_responses=True)
        client.ping()
    except Exception as exc:  # noqa: BLE001 - context only
        snapshot["redis"] = {"error": f"{type(exc).__name__}: {exc}"}
        return snapshot

    groups: dict[str, Any] = {}
    for entry in settings.get("consumer_groups", ()) or ():
        stream, group = str(entry["stream"]), str(entry["group"])
        try:
            found = [g for g in client.xinfo_groups(stream) if g.get("name") == group]
            groups[f"{stream}::{group}"] = found[0] if found else {"error": "no group"}
        except Exception as exc:  # noqa: BLE001 - context only
            groups[f"{stream}::{group}"] = {"error": f"{type(exc).__name__}: {exc}"}
    snapshot["redis"]["consumer_groups"] = groups

    tick_stream = str(settings.get("tick_stream", "raw_data"))
    try:
        tail = client.xrevrange(tick_stream, count=1)
        snapshot["redis"]["tick_stream"] = {
            "stream": tick_stream,
            "last_entry_id": tail[0][0] if tail else None,
        }
    except Exception as exc:  # noqa: BLE001 - context only
        snapshot["redis"]["tick_stream"] = {"error": f"{type(exc).__name__}: {exc}"}

    symbol = _symbol_from_harvest(config, day, str(settings.get("symbol_pattern", "")))
    if symbol:
        key = str(settings.get("daily_reference_key", "")).format(symbol=symbol)
        try:
            snapshot["redis"]["daily_reference"] = {"key": key, **client.hgetall(key)}
        except Exception as exc:  # noqa: BLE001 - context only
            snapshot["redis"]["daily_reference"] = {
                "key": key,
                "error": f"{type(exc).__name__}: {exc}",
            }
    return snapshot


def _symbol_from_harvest(
    config: ObservationConfig, day: date_cls, pattern: str
) -> str | None:
    """Last trading symbol named in the day's harvested logs."""
    if not pattern:
        return None
    compiled = re.compile(pattern)
    directory = config.report_root / day.isoformat()
    for spec in reversed(config.services):
        for path in reversed(service_log_files(directory, spec.name)):
            for line in reversed(
                path.read_text(encoding="utf-8", errors="replace").splitlines()
            ):
                match = compiled.search(line)
                if match:
                    return match.group(1)
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--date",
        default=None,
        help="KST trading date (YYYY-MM-DD). Defaults to today KST.",
    )
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG_PATH), help="Observation config path."
    )
    parser.add_argument(
        "--schedule",
        default=str(DEFAULT_SCHEDULE_PATH),
        help="market_schedule.yaml supplying the session window.",
    )
    parser.add_argument(
        "--report-root",
        default=None,
        help="Harvest root, overriding the configured reports/f9-gate1.",
    )
    parser.add_argument(
        "--no-harvest",
        action="store_true",
        help="Verdict from already-harvested files; do not touch docker.",
    )
    parser.add_argument(
        "--no-point-in-time",
        action="store_true",
        help="Skip the live docker/Redis context block.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    config = load_observation_config(Path(args.config))
    if args.report_root:
        config = replace(config, report_root=Path(args.report_root).resolve())
    today = datetime.now(KST).date()
    day = date_cls.fromisoformat(args.date) if args.date else today

    harvest = not args.no_harvest
    if harvest and day != today:
        # `docker logs` only ever returns the CURRENT container buffer, so
        # "harvesting" a past date would file today's lines under that date.
        print(
            f"[harvest] {day} is not today ({today}) — reading the existing "
            "harvest instead of running docker logs",
            file=sys.stderr,
        )
        harvest = False

    if harvest:
        stamp = datetime.now(KST).strftime("%H%M%S")
        for name, path in harvest_logs(config, day, stamp=stamp).items():
            print(f"[harvest] {name} -> {path}", file=sys.stderr)

    point_in_time = {} if args.no_point_in_time else collect_point_in_time(config, day)
    result = observe_day(
        config, day, schedule_path=Path(args.schedule), point_in_time=point_in_time
    )

    out_dir = config.report_root / day.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    sidecar = out_dir / (
        f"observation-completeness.{datetime.now(KST).strftime('%H%M%S')}.json"
    )
    row = render_row(result, config.row_counters, sidecar=sidecar)
    sidecar.write_text(
        json.dumps(build_sidecar(result, row), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(row)
    print(f"[sidecar] {sidecar}", file=sys.stderr)
    return 0 if result.verdict == VERDICT_COMPLETE else 1


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
