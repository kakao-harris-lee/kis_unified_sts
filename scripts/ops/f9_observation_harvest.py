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

Evidence coverage
-----------------
The same trap has a second floor: a harvest that is *missing*, *empty*, or
*truncated* also renders "0" unless it is made to speak. So every service
carries, besides its status, an **evidence state** (did we get a file, was it
empty, did anything in it parse, did the ``docker logs`` capture fail?) and a
**coverage interval** (the span the surviving lines actually testify to).
``consumed`` — and therefore ``COMPLETE`` — requires coverage that brackets
the session. Absent evidence is never promoted to a benign status, and the
part of a session nothing testifies to is rendered as ``no evidence`` rather
than left to look like silence.

Observation freshness
---------------------
Coverage answers "did we look?", and it is granted by any timestamped line —
a startup banner will do. It cannot also answer "was it working?", and reading
it that way left the original defect open: a service whose only
proof-of-consumption was one line half an hour after the open, followed by
silence to the close, read ``consumed (COMPLETE)`` on the strength of two
banners. So a second, separate bound is measured: the gap from the open to the
first proof, between consecutive proofs, and from the last proof to the close
must each stay at or under ``observation_max_gap_seconds``.

Liveness — the separate claim
-----------------------------
``observed`` asks "did it CONSUME?". ``liveness`` asks "was it WATCHING?".
Those are different claims about different evidence and they are scored apart,
because merging them renders a consumer that polled 390 times and handled
nothing as ``consumed`` — the defect the ``observed``/``blind`` split closed,
returning through a new door.

Until PRs #765/#766/#776 there was no second claim to make. The idle loop
emitted nothing at any level, so a healthy quiet consumer and one that died at
the open left byte-identical records and a quiet day honestly read PARTIAL.
Now every stage poll feeds a ``stream_consumer_alive`` heartbeat and the
decision engine logs ``decision_engine_alive`` once per interval from a
``finally`` covering every exit path of a cycle.

So ``observation_max_gap_seconds`` changed job. It is no longer a **proxy** for
liveness — it is the **trigger** that makes the harvester demand a positive
liveness answer for a stretch of silence. A stretch the heartbeat vouches for
is ``idle_alive``, a *successful* observation of an empty stream; a stretch it
cannot is ``stale_observation``, exactly as before. A service configured with
no ``liveness`` patterns has nothing to offer and keeps the old behaviour.

Liveness is scored by **density, not by presence**: absence is the entire
signal — a stage in a read-failure loop emits *zero* heartbeats, and no regex
matches a line never written — so "the pattern appears somewhere" would let one
line certify seven silent hours. What is required is the number of lines the
configured cadence predicts, spread across the window. No field is parsed:
``polls=0`` is unrepresentable, because ``_LivenessHeartbeat.record_poll``
increments before the due-check, so a matched line already means the loop
turned.

Freshness exemptions
--------------------
``freshness_scored: false`` marks a service whose proof is not traffic-driven,
so that silence between two proofs says nothing about it. The producer used to
be one: its proof is the setup-evaluation INFO, emitted once per *state change*
(``shared/strategy/entry/setup_eval_publisher.py``). ``decision_engine_alive``
removed that premise, the exemption was lifted with it, and **no shipped
service sets the flag today.**

The machinery stays, keyed on the two facts rather than on a service name, so a
future throttled-proof service inherits the disclosure the day it is
configured — because **exempt from scoring is not exempt from disclosure**. A
day on which every service consumed but an exempt one went silent past the
bound is not a measurement and its row must not be able to pass for one: it
reads ``LIVENESS_UNVERIFIED``, names the stretch and quotes the reason, and its
counters ship qualified. Left out, the exemption walked the original defect
back in through the one service the bound could not cover — one 08:46
evaluation and six hours fifty-nine minutes of nothing rendered ``4/4 consumed
(COMPLETE)``, exit 0, counts bare.

Correlated lines
----------------
Some lines only mean what a *different* line about the same ``msg_id`` allows
them to mean, so two of them are read together (issue #767). A proof requires
``ack=true``: ``ack=false`` leaves the message pending and Redis redelivers the
same id, so a consumer making zero net progress used to renew its own freshness
forever. And a ``stream_message_dropped`` voids every line about the same
message, because ``services/futures_monitor/daemon.py`` deliberately ACKs a
poison record to keep going — leaving a ``stream_message_processed … ack=true``
that describes an ACK, not a fill. A consumer whose deliveries all fail this
way is ``no_progress``, never ``idle_alive``: idle means nothing arrived.

"The same message" is ``(stream, msg_id)``, not ``msg_id``. A Redis entry id is
unique per stream and not per server — the ``<ms>-<seq>`` counter lives on the
stream key — so two streams taking an entry in the same millisecond get
identical ids, and ``futures-monitor`` consumes two. Keyed on the id alone, a
dropped signal would strike a real fill.

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
from datetime import datetime, timedelta
from datetime import time as time_cls
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from shared.decision.context import (
    load_futures_close_from_config,
    load_futures_open_from_config,
)
from shared.strategy.market_time import is_trading_day_kst

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
#: Not a trading day: there was no session to observe. Distinct from
#: ``NOT_OBSERVED`` (a session happened and we cannot say what the surface saw)
#: so a weekend or holiday run does not raise a standing false alarm — the
#: runbook invokes this per session and exit-0-on-COMPLETE invites cron.
VERDICT_NO_SESSION = "NO_SESSION"
#: Every scored service consumed and covered the session — but at least one of
#: them **cannot prove it stayed alive**, because its proof is not traffic-driven
#: and it therefore carries ``freshness_scored: false`` (see the module
#: docstring). Exempt from *scoring* is not exempt from *disclosure*: without
#: this token a producer with one 08:46 evaluation and six hours fifty-nine
#: minutes of silence rendered ``4/4 consumed (COMPLETE)``, exit 0, counts bare
#: and ``counters.qualified: true`` — the same "one surviving line makes
#: ``consumed``" collapse the freshness bound closed for consumers, walked back
#: in through the one service the bound cannot cover.
#:
#: It exits 0, like ``COMPLETE``. A dead throttled emitter and a healthy one
#: leave identical records (that is precisely why no bound over them asserts
#: anything), and both real harvests show the healthy case: exiting 1 would
#: alarm on every trading day, which is the standing-alarm harm this script
#: exists to prevent. So the row says it loudly and the exit status stays quiet,
#: and the counts are never bare.
#:
#: **UNREACHABLE FROM THE SHIPPED CONFIG since 2026-09-23.** The only service
#: that ever set ``freshness_scored: false`` was ``futures-decision-engine``,
#: and PR #766's ``decision_engine_alive`` removed the premise for it, so the
#: exemption was lifted and nothing sets the flag. Nothing else reaches this
#: verdict — ``resolve_day`` gates it on ``liveness_unverified``, which is
#: ``not freshness_scored and not observation_is_fresh``, and
#: ``freshness_scored`` is True unless config says otherwise.
#:
#: Kept rather than deleted, and this is a judgement rather than an oversight:
#: the predicate is keyed on the two facts and never on a name, so the day a
#: service with a throttled proof is configured, its disclosure already exists
#: and is already tested. Deleting it would mean the next such service ships
#: with the same hole the 2026-09 round found, and re-deriving the reasoning
#: costs far more than the branch does.
VERDICT_LIVENESS_UNVERIFIED = "LIVENESS_UNVERIFIED"

#: Verdicts a per-session cron may treat as "nothing to escalate".
VERDICTS_EXIT_ZERO = (
    VERDICT_COMPLETE,
    VERDICT_NO_SESSION,
    VERDICT_LIVENESS_UNVERIFIED,
)

#: Per-service statuses.
STATUS_CONSUMED = "consumed"
STATUS_PARTIALLY_BLIND = "partially_blind"
STATUS_BLIND = "blind"
#: Observed, never blind — but the harvest does not span the session, so the
#: uncovered part is unknown rather than quiet. Never COMPLETE.
STATUS_PARTIAL_COVERAGE = "partial_coverage"
#: Observed, never blind, and the harvest spans the session — but a stretch of
#: it holds no proof of consumption AND no proof of liveness either. Coverage
#: says we watched; it cannot say the service was working, and nothing else
#: does. Never COMPLETE.
STATUS_STALE_OBSERVATION = "stale_observation"
#: Consumed nothing, and proved throughout that it was watching anyway. A
#: *successful* observation of an empty stream, not a failure: "nothing arrived,
#: and we know the consumer was there to see it" is a measurement, where before
#: the heartbeat it was indistinguishable from a dead daemon. COMPLETE-eligible.
STATUS_IDLE_ALIVE = "idle_alive"
#: Messages were delivered and none of them completed — ``ack=false`` on every
#: redelivery, or a handler that raised on every record. Alive, watching, and
#: getting nowhere. Deliberately NOT ``idle_alive``: idle means nothing arrived.
#: Never COMPLETE.
STATUS_NO_PROGRESS = "no_progress"
STATUS_NO_EVIDENCE = "no_evidence"

#: Statuses that imply the observation surface actually worked at some point —
#: it consumed, however partially. ``blind`` and ``no_evidence`` are absent on
#: purpose: they are what a *dead* surface and a *closed market* both look like.
#:
#: ``idle_alive`` is absent too, and that is the load-bearing omission. This set
#: answers "did anything HAPPEN?" for ``DayObservation.has_evidence``, which
#: overrides the calendar on a day both holiday sources call closed. The
#: daemons prove liveness every weekend — the loop has no trading-day gate — so
#: counting liveness here would make every Saturday read
#: ``**BUT THE HARVEST HOLDS EVIDENCE**`` and exit 1: the standing alarm
#: ``VERDICT_NO_SESSION`` exists to prevent. Liveness says the surface was
#: watching, which changes no fact about whether a session happened.
STATUSES_SURFACE_WORKED = (
    STATUS_CONSUMED,
    STATUS_PARTIALLY_BLIND,
    STATUS_PARTIAL_COVERAGE,
    STATUS_STALE_OBSERVATION,
)

#: What the observation surface doing its job looks like: it either consumed, or
#: proved it was watching while nothing arrived. These and only these are
#: COMPLETE-eligible.
STATUSES_OBSERVED_OK = (STATUS_CONSUMED, STATUS_IDLE_ALIVE)

#: What ``NOT_OBSERVED`` is the absence of. Wider than ``STATUSES_SURFACE_WORKED``
#: because it answers a different question — "did we learn anything about this
#: surface?" — and a proven-alive idle consumer taught us something. Narrower
#: than "any status", because ``blind`` and ``no_evidence`` taught us nothing.
STATUSES_OBSERVATION_LANDED = STATUSES_SURFACE_WORKED + (STATUS_IDLE_ALIVE,)

#: What the harvest itself yielded for a service. Only ``EVIDENCE_LINES`` is
#: ever eligible for a benign status: a missing, empty, unparseable or failed
#: harvest is a *harvest failure*, and "we did not look" must not read like
#: "there was nothing to see".
EVIDENCE_LINES = "lines"
EVIDENCE_NO_FILE = "no_file"
EVIDENCE_EMPTY = "empty"
EVIDENCE_UNPARSEABLE = "unparseable"
EVIDENCE_HARVEST_FAILED = "harvest_failed"

#: Why each non-``EVIDENCE_LINES`` state happened, in the row's own words.
EVIDENCE_REASONS = {
    EVIDENCE_NO_FILE: "no harvest file",
    EVIDENCE_EMPTY: "harvest file present but empty",
    EVIDENCE_UNPARSEABLE: "harvest file holds no timestamped line",
    EVIDENCE_HARVEST_FAILED: "docker logs capture failed",
}

#: The ``harvest_mode:`` vocabulary of config/f9_observation.yaml. ``since``
#: floors the capture at a KST clock time; ``tail`` keeps the N most recent
#: lines. Neither drops the tail — both end at the instant they run.
HARVEST_MODE_SINCE = "since"
HARVEST_MODE_TAIL = "tail"

#: The ``role:`` vocabulary of config/f9_observation.yaml. Only ``reference``
#: changes the verdict (it is excluded from scoring); the other two document
#: what each service is for a reader of the sidecar.
ROLE_PRODUCER = "producer"
ROLE_CONSUMER = "consumer"
ROLE_REFERENCE = "reference"

#: Both deployed log formats start with the same KST ``asctime``:
#: ``2026-09-18 09:47:37,466 WARNING shared.streaming.stage …`` (decoupled
#: daemons) and ``2026-09-18 08:45:00,004 - services.trading… - INFO - …``
#: (orchestrator). Continuation lines of a traceback carry no timestamp and are
#: therefore not evidence of anything.
_TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d{3}")

#: The ``<HHMMSS>`` KST stamp ``harvest_logs`` writes into every filename. It
#: dates the capture, which is the end of what the file testifies to.
_HARVEST_STAMP_RE = re.compile(r"\.(\d{6})\.log$")

#: Cells the script cannot derive (they need the runtime ledger and an operator
#: comparison). Named rather than left blank so an unfilled cell is obvious.
MANUAL_CELL = "(manual)"

#: Written instead of a ``.log`` when ``docker logs`` exits non-zero. Not a
#: ``.log`` on purpose: the verdict globs ``<service>.*.log`` and must never
#: read a daemon error message as if it were a service's own quiet output.
HARVEST_FAILED_SUFFIX = ".harvest-failed"


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
    #: Proof the service's loop TURNED, kept strictly apart from ``observed``,
    #: which is proof it CONSUMED. Two different claims: a consumer that polled
    #: 390 times and handled nothing is a successful observation of an empty
    #: stream, and merging the two groups would render it ``consumed``.
    #:
    #: Empty for a service with no heartbeat, and everything below degrades to
    #: the pre-heartbeat behaviour when it is — silence then has nothing to
    #: vouch for it, exactly as before.
    liveness: tuple[re.Pattern[str], ...] = ()
    #: Delivered and NOT completed (``ack=false``). Not scored on its own; it is
    #: what tells "alive and nothing arrived" from "alive, things arrived, and
    #: none of them got anywhere". Both are silent in ``observed``.
    stalled: tuple[re.Pattern[str], ...] = ()
    #: Lines that VOID every other line carrying the same ``msg_id``. One line
    #: about a message changing what another line about it meant is the whole
    #: mechanism of issue #767, and it closes both halves: a proof struck out of
    #: ``observed`` and a dropped record struck out of ``fills``.
    retracted_by: tuple[re.Pattern[str], ...] = ()
    #: Whether ``observation_max_gap_seconds`` is scored against this service's
    #: proofs. False for a service whose proof is emitted on state change rather
    #: than per message: silence then says nothing about liveness, so a bound
    #: over it asserts nothing. The reason belongs beside the service in
    #: ``config/f9_observation.yaml``, not in a branch here.
    freshness_scored: bool = True
    #: Why this service is exempt, in one clause, for the row to quote. Required
    #: when ``freshness_scored`` is false — the same rule ``harvest_tail``
    #: follows below, for the same reason: the exemption is disclosed in an
    #: operator-facing row, and a disclosure with no reason is a blank the
    #: reader has to go and reconstruct from config comments.
    freshness_unscored_reason: str = ""

    def __post_init__(self) -> None:
        if not self.freshness_scored and not self.freshness_unscored_reason.strip():
            raise ValueError(
                f"{self.name}: freshness_scored false needs a "
                "freshness_unscored_reason — the row discloses the exemption "
                "and quotes this"
            )
        if self.harvest_mode != HARVEST_MODE_TAIL:
            return
        # No default here on purpose. A default would be a *second* value: the
        # harvest capped at it while the truncation detector, which compares
        # line counts against `harvest_tail`, saw None and reported
        # `coverage_truncated: false` forever — a wrong fact in the audit
        # record. One value, from config, read by both (CLAUDE.md:
        # configuration-driven only).
        if self.harvest_tail is None:
            raise ValueError(
                f"{self.name}: harvest_mode '{HARVEST_MODE_TAIL}' needs an "
                "explicit harvest_tail — it is both the `docker logs --tail` "
                "cap and what truncation is detected against"
            )
        if self.harvest_tail <= 0:
            raise ValueError(
                f"{self.name}: harvest_tail must be positive, not "
                f"{self.harvest_tail} (`--tail 0` returns nothing)"
            )

    @property
    def tail_cap(self) -> int:
        """The ``--tail`` cap of a tail-harvested service."""
        if self.harvest_tail is None:
            raise ValueError(f"{self.name} is not harvested with --tail")
        return self.harvest_tail


@dataclass(frozen=True)
class ObservationConfig:
    report_root: Path
    container_prefix: str
    harvest_since: time_cls
    blind_run_merge_seconds: int
    #: Longest silence between two proofs of *consumption* before the harvester
    #: demands a positive liveness answer for that stretch. See the module
    #: docstring's "Observation freshness".
    observation_max_gap_seconds: int
    #: The cadence the emitters are configured to heartbeat at. Must equal
    #: ``config/streaming.yaml::consumer_stage.heartbeat_interval_seconds`` and
    #: ``config/decision_engine.yaml::liveness.log_interval_seconds``; a test
    #: reads all three real files and fails if they drift.
    liveness_expected_interval_seconds: int
    #: How many consecutive beats may go missing before the silence is scored.
    liveness_missed_beats_allowed: int
    #: How a message is IDENTIFIED in ``shared/streaming/stage.py``'s audit
    #: lines: a ``stream`` group and a ``msg_id`` group, because a Redis entry
    #: id is unique per stream and not per server. Drives
    #: :attr:`ServiceSpec.retracted_by`.
    message_key_pattern: re.Pattern[str]
    row_counters: tuple[str, ...]
    services: tuple[ServiceSpec, ...]
    point_in_time: Mapping[str, Any]

    @property
    def liveness_max_gap_seconds(self) -> int:
        """Longest stretch a heartbeat may leave unspoken before it is scored.

        Derived, never a third knob: the interval the emitters are configured
        at, times the beats allowed to go missing plus the one that is due. A
        separate number here could sit below the emitters' cadence and fail
        every healthy day, which is the false verdict the heartbeat exists to
        delete.
        """
        return self.liveness_expected_interval_seconds * (
            1 + self.liveness_missed_beats_allowed
        )


def _compile_all(patterns: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p) for p in patterns)


def anchored_report_root(value: str | Path, *, repo_root: Path = _REPO_ROOT) -> Path:
    """Resolve a report root the same way whether it came from YAML or ``--report-root``.

    The config value has always been repo-root-relative; ``--report-root`` used
    to resolve against the **current working directory**, so the same relative
    spelling meant two different trees depending on where the operator stood.
    Combined with ``main``'s ``mkdir(parents=True)``, a mistyped root produced a
    confident ``NOT OBSERVED - 0/4`` against zero input and then created the
    tree it had just judged, so a second run found its own sidecar there. One
    anchor for both.
    """
    path = Path(value)
    return (path if path.is_absolute() else repo_root / path).resolve()


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
                harvest_mode=str(entry.get("harvest_mode", HARVEST_MODE_SINCE)),
                # `is not None`, not truthiness: `harvest_tail: 0` is a mistake
                # worth naming (ServiceSpec refuses it), not a value to read as
                # "absent" and silently replace.
                harvest_tail=(
                    int(entry["harvest_tail"])
                    if entry.get("harvest_tail") is not None
                    else None
                ),
                observed=_compile_all(entry.get("observed", ())),
                blind=_compile_all(entry.get("blind", ())),
                counters=_parse_counters(entry.get("counters", {}) or {}),
                liveness=_compile_all(entry.get("liveness", ())),
                stalled=_compile_all(entry.get("stalled", ())),
                retracted_by=_compile_all(entry.get("retracted_by", ())),
                freshness_scored=bool(entry.get("freshness_scored", True)),
                freshness_unscored_reason=str(
                    entry.get("freshness_unscored_reason", "")
                ),
            )
        )

    hour, minute = (int(part) for part in str(root["harvest_since"]).split(":")[:2])

    return ObservationConfig(
        report_root=anchored_report_root(root["report_root"], repo_root=repo_root),
        container_prefix=str(root["container_prefix"]),
        harvest_since=time_cls(hour, minute),
        blind_run_merge_seconds=int(root["blind_run_merge_seconds"]),
        observation_max_gap_seconds=int(root["observation_max_gap_seconds"]),
        liveness_expected_interval_seconds=int(
            root["liveness_expected_interval_seconds"]
        ),
        liveness_missed_beats_allowed=int(root["liveness_missed_beats_allowed"]),
        message_key_pattern=re.compile(str(root["message_key_pattern"])),
        row_counters=tuple(str(name) for name in root["row_counters"]),
        services=tuple(services),
        point_in_time=dict(root.get("point_in_time", {}) or {}),
    )


def _read_schedule(schedule_path: Path) -> Mapping[str, Any]:
    """Load and validate ``market_schedule.yaml``, raising on anything wrong.

    ``load_futures_{open,close}_from_config`` deliberately never raise — they
    are called per tick and fall back to 08:45/15:45 after one WARNING. That is
    right for the runtime and wrong here: a mistyped ``--schedule`` would yield
    a hardcoded window and a verdict about a session that was never checked,
    while ``load_observation_config`` next to it fails closed. So the file is
    validated here first, and the loaders are still the ones that supply the
    value (no second parser to drift from the runtime).
    """
    document = yaml.safe_load(Path(schedule_path).read_text(encoding="utf-8")) or {}
    regular = document["market_schedule"]["futures"]["regular"]
    for field in ("open", "close"):
        hour_text, minute_text = str(regular[field]).strip().split(":")[:2]
        if not (0 <= int(hour_text) < 24 and 0 <= int(minute_text) < 60):
            raise ValueError(
                f"{schedule_path}::market_schedule.futures.regular.{field} "
                f"is not a valid HH:MM: {regular[field]!r}"
            )
    return document


def _validated_time(
    loader: Callable[[str], tuple[int, int]],
    schedule_path: Path,
    regular: Mapping[str, Any],
    field: str,
) -> tuple[int, int]:
    """The loader's value, refused if it is the silent fallback rather than the file."""
    hour_text, minute_text = str(regular[field]).strip().split(":")[:2]
    expected = (int(hour_text), int(minute_text))
    loaded = loader(str(schedule_path))
    if loaded != expected:
        # The loaders memoize per path, so a fallback cached by an earlier bad
        # read in this process would otherwise be served as if it were config.
        raise ValueError(
            f"{schedule_path}::market_schedule.futures.regular.{field} reads "
            f"{expected} but the runtime loader returned {loaded} — a cached "
            "fallback, not this file"
        )
    return loaded


def session_window(
    day: date_cls, *, schedule_path: Path = DEFAULT_SCHEDULE_PATH
) -> tuple[datetime, datetime]:
    """Return the KST futures session ``(open, close)`` for *day*.

    Reuses ``shared.decision.context``'s loader (PR #668) so the observation
    window is the same one the decision engine anchors ``minutes_since_open``
    to — a second parser here could drift from the runtime's idea of a session.
    """
    regular = _read_schedule(schedule_path)["market_schedule"]["futures"]["regular"]
    open_h, open_m = _validated_time(
        load_futures_open_from_config, schedule_path, regular, "open"
    )
    close_h, close_m = _validated_time(
        load_futures_close_from_config, schedule_path, regular, "close"
    )
    return (
        datetime.combine(day, time_cls(open_h, open_m), tzinfo=KST),
        datetime.combine(day, time_cls(close_h, close_m), tzinfo=KST),
    )


def is_session_day(
    day: date_cls, *, schedule_path: Path = DEFAULT_SCHEDULE_PATH
) -> bool:
    """Whether KRX traded on *day*, from both holiday sources this repo keeps.

    ``is_trading_day_kst`` (weekend + ``shared/calendar.py``'s KRX list) is the
    runtime's own answer and is used as-is. It is intersected with the
    ``holidays:`` block of the schedule file because that file carries
    substitute holidays the hardcoded list misses — 2026-08-17 and 2026-10-05
    among them — and a substitute holiday scored as a trading day is exactly
    the standing false alarm ``NO_SESSION`` exists to prevent.
    """
    if not is_trading_day_kst(datetime.combine(day, time_cls(12, 0), tzinfo=KST)):
        return False
    listed = _read_schedule(schedule_path).get("holidays") or ()
    return day not in {date_cls.fromisoformat(str(entry)) for entry in listed}


# ---------------------------------------------------------------------------
# Harvest
# ---------------------------------------------------------------------------

Runner = Callable[[Sequence[str]], "subprocess.CompletedProcess[bytes]"]


def _run_capture(command: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(list(command), capture_output=True, check=False)


@dataclass(frozen=True)
class HarvestOutcome:
    """Where one service's capture landed, and whether docker actually gave it."""

    name: str
    path: Path
    ok: bool
    returncode: int


def harvest_logs(
    config: ObservationConfig,
    day: date_cls,
    *,
    stamp: str,
    runner: Runner = _run_capture,
) -> dict[str, HarvestOutcome]:
    """Copy each configured container's log into the day's report directory.

    Never overwrites an existing harvest — every run writes fresh
    ``<service>.<HHMMSS KST>.log`` files, so harvesting before a mid-session
    redeploy and again at the close keeps both halves of the day.

    A non-zero ``docker logs`` exit writes ``<service>.<stamp>.harvest-failed``
    instead of a ``.log``: otherwise ``Error response from daemon: No such
    container`` lands in the evidence file and the run reports success, which
    is the "could not observe" rendered as "observed 0" this script exists to
    prevent. The marker is what the verdict reads; it can never be mistaken for
    a quiet log because it is not one.
    """
    out_dir = config.report_root / day.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, HarvestOutcome] = {}
    for spec in config.services:
        destination = out_dir / f"{spec.name}.{stamp}.log"
        failure_marker = out_dir / f"{spec.name}.{stamp}{HARVEST_FAILED_SUFFIX}"
        for existing in (destination, failure_marker):
            if existing.exists():
                raise FileExistsError(
                    f"{existing} already exists; harvests are never overwritten"
                )
        command = ["docker", "logs"]
        if spec.harvest_mode == HARVEST_MODE_TAIL:
            # `docker logs` without --tail (or with a large one) stops at the
            # broken record left by the 2026-09-09 host reboots. See the
            # runbook's --tail caveat.
            command += ["--tail", str(spec.tail_cap)]
        else:
            since = datetime.combine(day, config.harvest_since, tzinfo=KST)
            command += ["--since", since.isoformat()]
        command.append(f"{config.container_prefix}{spec.container}")

        completed = runner(command)
        # The daemons log through logging.basicConfig (stderr), so the runbook's
        # `2>&1` is the interesting half — keep both.
        payload = (completed.stdout or b"") + (completed.stderr or b"")
        ok = completed.returncode == 0
        target = destination if ok else failure_marker
        target.write_bytes(payload)
        written[spec.name] = HarvestOutcome(
            name=spec.name, path=target, ok=ok, returncode=completed.returncode
        )
    return written


# ---------------------------------------------------------------------------
# Evidence scan (durable — harvested files only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceObservation:
    name: str
    role: str
    status: str
    #: One of the ``EVIDENCE_*`` states — what the harvest yielded, kept apart
    #: from what the service did, so "we have no file" cannot be read as "the
    #: service was quiet".
    evidence: str
    observed_count: int
    first_observed: datetime | None
    last_observed: datetime | None
    blind_count: int
    blind_windows: tuple[tuple[datetime, datetime], ...]
    #: Spans the surviving lines testify to, merged across harvest files, and
    #: the part of the session none of them reach.
    coverage: tuple[tuple[datetime, datetime], ...]
    uncovered: tuple[tuple[datetime, datetime], ...]
    #: Stretches of the session the harvest *did* reach that hold no proof of
    #: consumption within ``observation_max_gap_seconds`` **and** no heartbeat
    #: to vouch for them. Kept apart from ``uncovered`` because they answer
    #: different questions: "we did not look" versus "we looked and it proved
    #: nothing".
    unobserved: tuple[tuple[datetime, datetime], ...]
    #: Stretches with no proof of consumption that the heartbeat DOES vouch
    #: for: nothing arrived and the loop was demonstrably turning.
    #:
    #: Consumed by the JSON sidecar (``idle_session_kst``) and by
    #: :func:`describe_service`'s ``idle_alive`` clause. **Not by the row an
    #: operator reads**, because :func:`render_consumers_cell` filters
    #: ``idle_alive`` out — an idle-alive service is a success, and the cell
    #: carries that in its tally. Said explicitly because the earlier wording
    #: claimed a reader "needs to see which hours were idle" without saying
    #: which reader, and the answer is: whoever opens the sidecar.
    idle_windows: tuple[tuple[datetime, datetime], ...]
    #: Heartbeat lines inside the session.
    liveness_count: int
    #: Whether this service has a ``liveness`` pattern group at all. Kept apart
    #: from ``liveness_count == 0``, which those two cases would otherwise
    #: collapse into one: "we asked and it never answered" is a defect, "we
    #: never asked" is a configuration fact, and a row that says the first when
    #: it means the second is the failure mode this whole file is about.
    liveness_scored: bool
    #: Deliveries that demonstrably made no progress: ``ack=false`` lines plus
    #: proofs struck by a ``retracted_by`` line naming the same message.
    no_progress_count: int
    #: How many DISTINCT messages those deliveries were about. The pair is what
    #: separates the two cases the count alone conflates: ``85 of 1`` is one
    #: record pinned in the PEL all session and never getting through, while
    #: ``85 of 85`` is a consumer refusing each message once and moving on. The
    #: first is a defect, the second can be ordinary back-pressure, and a row
    #: that renders them alike is the sort of collapse this file exists to
    #: prevent.
    no_progress_messages: int
    #: A harvest file that came back at its ``--tail`` cap: lines older than
    #: its first are gone, so coverage is unknown before ``coverage[0][0]``.
    coverage_truncated: bool
    counters: Mapping[str, int]
    files: tuple[str, ...]
    #: Whether ``unobserved`` was allowed to change this service's status. False
    #: for a service whose proof is not traffic-driven (see the module
    #: docstring); ``unobserved`` is still measured and recorded, as context.
    freshness_scored: bool = True
    #: Why, in one clause, for the row to quote. Empty when freshness is scored.
    freshness_unscored_reason: str = ""

    @property
    def covers_session(self) -> bool:
        """No part of the session is without evidence."""
        return not self.uncovered

    @property
    def observation_is_fresh(self) -> bool:
        """No stretch of the session went unaccounted for.

        "Accounted for" is proof of consumption within the bound, or — for a
        service that emits a heartbeat — proof it was alive across the silence.
        Informational, not a verdict input, when ``freshness_scored`` is False.
        """
        return not self.unobserved

    @property
    def liveness_unverified(self) -> bool:
        """Exempt from the freshness bound AND silent past it: nothing verified it.

        Keyed on the two facts, never on a name or a role, so a second exempt
        service inherits the disclosure the day it is configured.
        """
        return not self.freshness_scored and not self.observation_is_fresh


@dataclass(frozen=True)
class DayObservation:
    day: date_cls
    session_open: datetime
    session_close: datetime
    #: What the harvested evidence says, always — never overwritten by the
    #: calendar. See ``reported_verdict``.
    verdict: str
    #: Whether both of this repo's holiday sources call *day* a trading day.
    session_day: bool
    services: tuple[ServiceObservation, ...]
    counters: Mapping[str, int]
    point_in_time: Mapping[str, Any]

    @property
    def has_evidence(self) -> bool:
        """Any scored service's surface demonstrably *worked*, or a counter moved.

        Blindness is deliberately not evidence here. On a weekend the pipeline
        still runs — ``services/decision_engine/main.py``'s loop has no
        trading-day gate, ``context_provider()`` returns None and it publishes
        ``no_market_context`` per setup, while the indicator engine emits
        ``Indicator data stale …`` every minute — and both are ``blind``
        patterns. Counting them made every Saturday render
        ``**BUT THE HARVEST HOLDS EVIDENCE** … BLIND 08:45-15:45`` and exit 1: a
        standing alarm on a cron'd script, which is the one thing
        ``VERDICT_NO_SESSION`` exists to prevent, and a row an operator learns
        to stop reading.

        The narrower set keeps what the override was written for — 2026-08-17,
        four genuinely *consuming* services on a day both holiday sources called
        closed — and drops the weekend noise, because blindness on a day with no
        session changes no fact. It does mean a real trading day miscalendared
        as a holiday AND blind all session reads ``NO_SESSION``; that day's logs
        are byte-identical to a weekend's, so no rule over them could have told
        the two apart.
        """
        return any(
            service.status in STATUSES_SURFACE_WORKED
            for service in _scored(self.services)
        ) or any(self.counters.values())

    @property
    def reported_verdict(self) -> str:
        """The day's verdict, with ``NO_SESSION`` as a *qualifier*, not a replacement.

        ``NO_SESSION`` used to be written over the evidence-derived verdict
        after the scan, blanking the counts to ``n/a - no session`` and exiting
        0. Both holiday sources describe themselves as provisional
        (``shared/calendar.py``: ``예상 - 확정 시 업데이트 필요``), so one wrong
        entry silently unscored a real trading day — on a script whose whole
        purpose is making unscored days visible. A non-trading day that holds
        substantive evidence now keeps that evidence's verdict and says both
        things; only a non-trading day with nothing to report reads
        ``NO_SESSION``, where the override changes no fact.
        """
        if not self.session_day and not self.has_evidence:
            return VERDICT_NO_SESSION
        return self.verdict


def service_log_files(directory: Path, service: str) -> tuple[Path, ...]:
    """Every harvest of *service* in *directory*, oldest stamp first."""
    if not directory.is_dir():
        return ()
    return tuple(sorted(directory.glob(f"{service}.*.log")))


def service_failure_markers(directory: Path, service: str) -> tuple[Path, ...]:
    """Every failed ``docker logs`` capture of *service* in *directory*."""
    if not directory.is_dir():
        return ()
    return tuple(sorted(directory.glob(f"{service}.*{HARVEST_FAILED_SUFFIX}")))


@dataclass(frozen=True)
class FileEvidence:
    """One harvest file: what parsed out of it and what span it testifies to."""

    path: Path
    line_count: int
    lines: tuple[tuple[datetime, str], ...]
    #: When ``docker logs`` was run, read from the file's own ``<HHMMSS>``
    #: stamp. ``None`` when the name carries no stamp to read.
    harvested_at: datetime | None = None
    #: The floor the capture was asked for — ``--since``'s KST instant. ``None``
    #: for a ``--tail`` capture, which has no time floor at all.
    covers_from: datetime | None = None

    @property
    def span(self) -> tuple[datetime, datetime] | None:
        """The interval this file testifies to: its capture floor to its capture instant.

        Ending the span at the *last* line made ``COMPLETE`` depend on how
        chatty a service happened to be near 15:45: four consuming services
        whose files stopped 30 seconds short of the close read ``PARTIAL`` with
        ``no evidence 15:44-15:45``, while seven hours of interior silence read
        ``COMPLETE``. Same epistemic situation, opposite verdicts — and the
        quiet consumer hits the first one.

        ``docker logs`` returns everything up to the moment it runs in **both**
        harvest modes: ``--since`` floors the head, ``--tail N`` keeps the N
        most recent lines, and neither drops the tail. So silence after the last
        line is silence the harvest watched.

        The head is the same argument run backwards, but **only in ``since``
        mode**, where ``covers_from`` is a known floor: ``--since 08:00`` was
        asked for, so a first line at 08:45:05 means the service was quiet from
        08:00, not that the harvest missed those 45 minutes. Without this a
        healthy day whose first line landed five seconds after the open read
        ``PARTIAL — no evidence <=08:45``, and the real
        ``futures-risk-filter.113330.log`` (one line, 09:47) is that case.

        The cost is stated rather than hidden: a container recreated mid-morning
        returns only post-recreate lines, and anchoring at 08:00 credits
        coverage that did not exist. That hole is caught by the freshness bound
        instead — a recreate at 11:00 leaves a leading unproven window
        ``08:45-11:00`` — so head-hole detection moves from "any hole" to "holes
        larger than ``observation_max_gap_seconds``", the tolerance the design
        already accepts everywhere else, and it yields the truthful label.

        In ``tail`` mode the head stays at the first surviving line. Truncation
        there is by line *count*, not by time, so there is no floor to anchor
        at and a late head cannot be told from a quiet start.
        """
        if not self.lines:
            return None
        first, last = self.lines[0][0], self.lines[-1][0]
        if self.covers_from is not None:
            first = min(first, self.covers_from)
        if self.harvested_at is None:
            return (first, last)
        return (first, max(last, self.harvested_at))


def _parse_line(line: str) -> datetime | None:
    match = _TIMESTAMP_RE.match(line)
    if match is None:
        return None
    return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)


def harvest_stamp(
    path: Path, session_open: datetime, *, last_line: datetime | None = None
) -> datetime | None:
    """The KST instant *path* was harvested, from its ``<service>.<HHMMSS>.log`` name.

    The filename carries a clock but no date, and the directory that supplies
    one is the **session** date, not the capture date. A harvest run after
    midnight — ``reports/f9-gate1/2026-09-15/*.000135.log`` was captured
    2026-09-16 00:01 — therefore dated its own capture nine hours *before* the
    session it captured, ``max(last, harvested_at)`` discarded it, and the whole
    close-boundary rule went silently inert: byte-identical healthy evidence
    read ``4/4 consumed (COMPLETE)`` under a ``155000`` stamp and
    ``consumed, harvest does not span the session (no evidence 15:24-15:45)``
    under ``000500``, relabelling a wedged consumer as a harvest gap.

    The date is recovered from the file itself rather than from its mtime: these
    files are copied, archived and restored (the harvest tree is the only
    durable record of a session), and a plain ``cp`` resets every mtime to the
    copy instant while the name survives intact.

    Two facts pin the date. ``docker logs`` cannot return a line from the
    future, so the capture is at or after *last_line*; and a capture of this
    session cannot precede its open. So the stamp rolls to the next day only
    when it is **both** before the open and before the last line the file holds
    — which is the after-midnight case and nothing else. A stamp at or after the
    open stays on *day* whatever its lines say, so a line written in the second
    between computing the stamp and running ``docker logs`` cannot fling the
    capture instant 24 hours forward.
    """
    match = _HARVEST_STAMP_RE.search(path.name)
    if match is None:
        return None
    try:
        clock = datetime.strptime(match.group(1), "%H%M%S").time()
    except ValueError:
        return None
    stamped = datetime.combine(session_open.date(), clock, tzinfo=KST)
    if stamped >= session_open or last_line is None:
        return stamped
    while stamped < last_line:
        stamped += timedelta(days=1)
    return stamped


def read_file_evidence(
    path: Path,
    *,
    session_open: datetime | None = None,
    covers_from: datetime | None = None,
) -> FileEvidence:
    """Parse one harvest file, keeping its own line count and its own span.

    Per file rather than per service because coverage is a union of *files*: a
    mid-day harvest and a post-close harvest of a container recreated in
    between testify to two disjoint spans, and flattening them first would
    invent the hours between.

    *session_open* dates the file's ``<HHMMSS>`` stamp, so the span can reach
    the capture rather than the last line; *covers_from* is the ``--since``
    floor the capture was asked for, if any. See ``FileEvidence.span``.
    """
    raw = [
        line
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line
    ]
    parsed = [
        (moment, line) for line in raw if (moment := _parse_line(line)) is not None
    ]
    parsed.sort()
    return FileEvidence(
        path=path,
        line_count=len(raw),
        lines=tuple(parsed),
        harvested_at=(
            None
            if session_open is None
            else harvest_stamp(
                path, session_open, last_line=parsed[-1][0] if parsed else None
            )
        ),
        covers_from=covers_from,
    )


def _merge_intervals(
    intervals: Iterable[tuple[datetime, datetime]],
) -> tuple[tuple[datetime, datetime], ...]:
    """Union overlapping or touching ``(start, end)`` spans, earliest first."""
    ordered = sorted(intervals)
    if not ordered:
        return ()
    merged: list[list[datetime]] = [list(ordered[0])]
    for start, end in ordered[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return tuple((start, end) for start, end in merged)


def _uncovered(
    covered: Sequence[tuple[datetime, datetime]], start: datetime, end: datetime
) -> tuple[tuple[datetime, datetime], ...]:
    """The parts of ``[start, end]`` no interval in *covered* reaches."""
    gaps: list[tuple[datetime, datetime]] = []
    cursor = start
    for span_start, span_end in covered:
        if span_end < cursor or span_start > end:
            continue
        if span_start > cursor:
            gaps.append((cursor, span_start))
        cursor = max(cursor, span_end)
        if cursor >= end:
            break
    if cursor < end:
        gaps.append((cursor, end))
    return tuple(gaps)


def _stale_windows(
    observed: Sequence[datetime],
    start: datetime,
    end: datetime,
    max_gap_seconds: int,
) -> tuple[tuple[datetime, datetime], ...]:
    """Stretches of ``[start, end]`` with no proof of consumption in *observed*.

    Three gaps are bounded, not two: the open to the first proof as well as
    between consecutive proofs and the last proof to the close. A consumer that
    was dead all morning and woke at 15:40 is as unproven for the session as one
    that died at 08:46, and only the leading gap tells them apart from a healthy
    one.

    Sorted and clamped here rather than assumed of the caller. It happened to be
    safe — ``scan_service`` sorts and window-filters first — but out-of-order
    input silently produced bogus windows (``[15:00, 09:00]`` yields two) and a
    post-close moment produced a window ending after the close, and a function
    that renders operator-facing verdicts should not depend on a caller's habit
    for that.
    """
    gaps: list[tuple[datetime, datetime]] = []
    cursor = start
    for moment in (*sorted(m for m in observed if start <= m <= end), end):
        if (moment - cursor).total_seconds() > max_gap_seconds:
            gaps.append((cursor, moment))
        cursor = moment
    return tuple(gaps)


def _liveness_shortfall(
    liveness: Sequence[datetime],
    window: tuple[datetime, datetime],
    max_gap_seconds: int,
) -> tuple[tuple[datetime, datetime], ...]:
    """The parts of *window* the heartbeat does not vouch for.

    **Density, not presence.** A heartbeat every ``interval`` seconds predicts a
    known number of lines across a stretch, and the rule is that the predicted
    number really is there and really is spread out — implemented as "no
    sub-stretch longer than *max_gap_seconds* without one", which is the same
    claim localized. "The pattern appears somewhere in the window" would be
    satisfied by a single line and would certify the seven silent hours around
    it, which is the shape of every defect this file has had.

    The rule has to be about absence because absence is the whole signal: during
    the 2026-09-17 read-failure loop the stage spun 200 failed reads across 6.7
    heartbeat intervals and emitted **zero** heartbeats, and no regex matches a
    line that was never written.

    Counting a bare match is nevertheless safe, so no field is parsed: ``polls``
    cannot be 0, because ``_LivenessHeartbeat.record_poll``
    (``shared/streaming/stage.py``) increments it before the due-check. Every
    emitted line therefore stands for at least one completed poll.
    """
    return _stale_windows(liveness, window[0], window[1], max_gap_seconds)


def _dedupe_lines(
    evidence: Iterable[FileEvidence],
) -> list[tuple[datetime, str]]:
    """De-duplicate and time-order the timestamped lines across harvests.

    Two harvests of a container that was not recreated in between overlap; this
    is the runbook's ``cat … | sort -u``, which drops the shared lines while
    keeping genuine redeliveries (their timestamps differ).
    """
    unique: dict[str, datetime] = {}
    for item in evidence:
        for moment, line in item.lines:
            unique[line] = moment
    parsed = [(moment, line) for line, moment in unique.items()]
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


def _message_key(
    line: str, message_key_pattern: re.Pattern[str]
) -> tuple[str, str] | None:
    """Which message *line* is about: ``(stream, msg_id)``, or None.

    **The stream half is load-bearing.** A Redis entry id is unique per stream,
    not per server: the ``<ms>-<seq>`` sequence counter lives on the stream key,
    so two streams taking an entry in the same millisecond get byte-identical
    ids. Measured on a throwaway ``redis:7-alpine`` (2026-09-23): 200 XADDs
    alternating between two keys produced 200 identical ids — a 200/200
    collision, not a rare race.

    ``futures-monitor`` consumes two streams, so keying on ``msg_id`` alone
    would let a dropped *signal* void a legitimate *fill*. That strikes real
    evidence, and under-counting is the direction that looks safe while being
    wrong, which is why it gets a named function instead of an inline regex.
    """
    match = message_key_pattern.search(line)
    if match is None:
        return None
    groups = match.groupdict()
    return (groups.get("stream") or "", groups["msg_id"])


def _retracted_messages(
    spec: ServiceSpec,
    message_key_pattern: re.Pattern[str],
    lines: Sequence[tuple[datetime, str]],
) -> frozenset[tuple[str, str]]:
    """Messages some line declares void, whatever any other line says.

    The correlation issue #767 asked for, in one place because both halves it
    names are one mechanism. ``services/futures_monitor/daemon.py`` catches a
    raising handler, logs ``stream_message_dropped``, and returns True so the
    framework ACKs — deliberately, to preserve drop-and-continue. The stage then
    logs ``stream_message_processed … ack=true`` for that same message a moment
    later. Read alone, that second line says a fill was consumed; read together
    with the first, it says an ACK happened and nothing else did.

    Striking by identity rather than by position is what makes the order of the
    two lines irrelevant, which matters: the drop is logged inside the handler
    and the ACK after it returns today, but that is an implementation detail of
    the daemon, not a contract the harvester should depend on.
    """
    if not spec.retracted_by:
        return frozenset()
    retracted = set()
    for _, line in lines:
        if not any(pattern.search(line) for pattern in spec.retracted_by):
            continue
        key = _message_key(line, message_key_pattern)
        if key is not None:
            retracted.add(key)
    return frozenset(retracted)


def _strike_retracted(
    spec: ServiceSpec,
    message_key_pattern: re.Pattern[str],
    lines: Sequence[tuple[datetime, str]],
) -> tuple[list[tuple[datetime, str]], int]:
    """Drop every line a retraction voids, and say how many that was.

    Done once, before anything is classified, so no two measurements can read
    the same line and reach opposite conclusions about the same message — that
    disagreement is the bug, not the arithmetic.

    **The retraction lines themselves survive.** A ``stream_message_dropped``
    names the message it is voiding, so striking by identity alone would strike
    the declaration together with what it declares — and the ``dropped``
    counter, whose whole job is to say a poison record arrived, would read 0 on
    exactly the days it exists for. A line making a claim is evidence for that
    claim; only the lines it contradicts lose their meaning.
    """
    retracted = _retracted_messages(spec, message_key_pattern, lines)
    if not retracted:
        return list(lines), 0
    live: list[tuple[datetime, str]] = []
    struck = 0
    for moment, line in lines:
        if any(pattern.search(line) for pattern in spec.retracted_by):
            live.append((moment, line))
            continue
        if _message_key(line, message_key_pattern) in retracted:
            struck += 1
            continue
        live.append((moment, line))
    return live, struck


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


def _evidence_state(
    evidence: Sequence[FileEvidence], failure_markers: Sequence[Path]
) -> str:
    """Which ``EVIDENCE_*`` state this service's harvest is in."""
    if failure_markers:
        # A failed capture leaves a hole of unknown size; whatever else came
        # back cannot close it, so the service is ineligible for any benign
        # status even when a sibling harvest did succeed.
        return EVIDENCE_HARVEST_FAILED
    if not evidence:
        return EVIDENCE_NO_FILE
    if not any(item.line_count for item in evidence):
        return EVIDENCE_EMPTY
    if not any(item.lines for item in evidence):
        return EVIDENCE_UNPARSEABLE
    return EVIDENCE_LINES


def scan_service(
    spec: ServiceSpec,
    files: Sequence[Path],
    *,
    session_open: datetime,
    session_close: datetime,
    blind_run_merge_seconds: int,
    observation_max_gap_seconds: int,
    liveness_max_gap_seconds: int,
    message_key_pattern: re.Pattern[str],
    harvest_since: time_cls,
    failure_markers: Sequence[Path] = (),
) -> ServiceObservation:
    """Classify one service from its harvested logs.

    A line is blindness evidence before it is observation evidence: a setup
    rejected for ``no_market_context`` is the daemon saying it had no input,
    not a completed evaluation.

    Four things are measured, never merged:

    * **what the service did** inside the session window;
    * **how much of the session the harvest reaches** — a file that starts
      after the open (rotation, or a container recreated mid-day) cannot
      testify to the hours before its first line, and rotation drops the
      OLDEST lines, so it preferentially destroys early-session blindness;
    * **how fresh the proof of CONSUMPTION stayed** — coverage is granted by any
      timestamped line, a startup banner included, so it answers "did we look?"
      and cannot also answer "was it working?";
    * **whether the loop was TURNING across the silences** — the heartbeat, and
      the only one of the four that can tell an empty stream from a dead
      consumer. It is scored separately from consumption on purpose: folded
      into ``observed`` it would render a consumer that polled 390 times and
      handled nothing as ``consumed``.

    One surviving ``stream_message_processed`` therefore never proves the
    service consumed *for the session*: not beyond what the files cover, and
    not beyond the freshness bound either side of it — and, since the proof now
    requires ``ack=true``, not on the strength of a message it kept refusing.
    """
    covers_from = (
        datetime.combine(session_open.date(), harvest_since, tzinfo=KST)
        if spec.harvest_mode == HARVEST_MODE_SINCE
        else None
    )
    evidence = [
        read_file_evidence(path, session_open=session_open, covers_from=covers_from)
        for path in files
    ]
    state = _evidence_state(evidence, failure_markers)

    spans = [item.span for item in evidence]
    coverage = _merge_intervals(span for span in spans if span is not None)
    uncovered = _uncovered(coverage, session_open, session_close)
    truncated = any(
        spec.harvest_mode == HARVEST_MODE_TAIL and item.line_count >= spec.tail_cap
        for item in evidence
    )

    lines = [
        (moment, line)
        for moment, line in _dedupe_lines(evidence)
        if session_open <= moment <= session_close
    ]

    live_lines, struck = _strike_retracted(spec, message_key_pattern, lines)

    observed: list[datetime] = []
    blind: list[datetime] = []
    liveness: list[datetime] = []
    stalled = 0
    refused_messages: set[tuple[str, str]] = set()
    for moment, line in live_lines:
        if any(pattern.search(line) for pattern in spec.liveness):
            liveness.append(moment)
        elif any(pattern.search(line) for pattern in spec.blind):
            blind.append(moment)
        elif any(pattern.search(line) for pattern in spec.observed):
            observed.append(moment)
        elif any(pattern.search(line) for pattern in spec.stalled):
            stalled += 1
            key = _message_key(line, message_key_pattern)
            if key is not None:
                refused_messages.add(key)

    # The freshness bound now TRIGGERS the liveness question instead of
    # answering it: every stretch it flags is offered to the heartbeat, and only
    # what the heartbeat cannot vouch for survives as unproven. A service with no
    # `liveness` patterns has nothing to offer, so `_liveness_shortfall` returns
    # the whole window and the pre-heartbeat behaviour is unchanged for it.
    unaccounted = _stale_windows(
        observed, session_open, session_close, observation_max_gap_seconds
    )
    unobserved: list[tuple[datetime, datetime]] = []
    idle_windows: list[tuple[datetime, datetime]] = []
    for window in unaccounted:
        shortfall = _liveness_shortfall(liveness, window, liveness_max_gap_seconds)
        unobserved.extend(shortfall)
        if not shortfall:
            idle_windows.append(window)

    no_progress = stalled + struck

    if state != EVIDENCE_LINES:
        # Nothing was read, so nothing about this service was observed. Named
        # by `evidence`, never softened into a status that reads like quiet.
        status = STATUS_NO_EVIDENCE
    elif blind and observed:
        status = STATUS_PARTIALLY_BLIND
    elif blind:
        status = STATUS_BLIND
    elif not observed and not liveness and not no_progress:
        # Silent in every group. The pre-heartbeat case, and still the right
        # answer for it: a service that says nothing at all proves nothing.
        status = STATUS_NO_EVIDENCE
    elif uncovered:
        status = STATUS_PARTIAL_COVERAGE
    elif not observed and no_progress:
        # Alive, watching, and getting nowhere: messages arrived and none of
        # them completed. Deliberately not `idle_alive` — idle means nothing
        # arrived, and a wedged consumer inheriting the idle verdict is exactly
        # how the closed defect would come back.
        #
        # ABOVE `stale_observation`, which it used to sit under. A wedged
        # consumer on a pre-heartbeat image has no heartbeat to vouch for its
        # silence, so the stale branch caught it first and the delivery count
        # — the one fact that explains the day — never reached the row. Silence
        # is the symptom here and the refused deliveries are the cause, so the
        # status names the cause; `describe_service` still prints the unproven
        # window beside it, because both are true.
        status = STATUS_NO_PROGRESS
    elif unobserved and spec.freshness_scored:
        status = STATUS_STALE_OBSERVATION
    elif not observed:
        status = STATUS_IDLE_ALIVE
    else:
        status = STATUS_CONSUMED

    return ServiceObservation(
        name=spec.name,
        role=spec.role,
        status=status,
        freshness_scored=spec.freshness_scored,
        freshness_unscored_reason=spec.freshness_unscored_reason,
        evidence=state,
        observed_count=len(observed),
        first_observed=observed[0] if observed else None,
        last_observed=observed[-1] if observed else None,
        blind_count=len(blind),
        blind_windows=_merge_windows(blind, blind_run_merge_seconds),
        coverage=coverage,
        uncovered=uncovered,
        unobserved=tuple(unobserved),
        idle_windows=tuple(idle_windows),
        liveness_count=len(liveness),
        liveness_scored=bool(spec.liveness),
        no_progress_count=no_progress,
        # `struck` is counted as one message each: a retraction names exactly
        # one, and the set above only sees the `stalled` lines.
        no_progress_messages=len(refused_messages) + struck,
        coverage_truncated=truncated,
        counters={
            counter.name: _count(counter, live_lines) for counter in spec.counters
        },
        files=tuple(str(path) for path in (*files, *failure_markers)),
    )


def _scored(services: Iterable[ServiceObservation]) -> list[ServiceObservation]:
    return [s for s in services if s.role != ROLE_REFERENCE]


def resolve_day(
    services: Sequence[ServiceObservation],
) -> tuple[tuple[ServiceObservation, ...], str, dict[str, int]]:
    """Total the counters and verdict the day.

    There is deliberately **no "nothing was due" exemption** for a silent
    consumer. The version this replaced excused one whenever the producer was
    non-blind and published nothing, which failed two ways: the producer's
    status carried no span (a producer that stopped at 08:57 excused a consumer
    dead all day), and a consumer with no harvest file at all took the same
    exemption and rendered "4/4 observing" on zero bytes.

    Tightening the predicate was never going to be enough, because the evidence
    it needed did not exist. The healthy idle loop emitted nothing at any level:
    ``xreadgroup`` returns no messages, ``post_poll(count)``,
    ``asyncio.sleep(0)``, ``continue``, with no logging on that path. A healthy
    idle consumer and one that died at the open left byte-identical records, so
    the runbook's INERT-GATE CAVEAT applied to the observation surface itself —
    a quiet day is *exactly what you would observe* if the chain cannot fire —
    and a quiet day honestly read PARTIAL.

    **Both halves of that are now false, and they stopped being true one after
    the other.** PRs #765/#766/#776 added the emissions: every stage poll,
    idle ones included, feeds ``_LivenessHeartbeat``
    (``shared/streaming/stage.py``), and the decision engine's evaluation loop
    logs ``decision_engine_alive`` from a ``finally`` that covers every exit
    path of a cycle. That killed the premise. This function's rule — silence is
    silence, whatever caused it — kept the conclusion alive for one more step,
    because nothing read the new lines. ``config/f9_observation.yaml``'s
    ``liveness`` group and :func:`scan_service` now do, and a stretch the
    heartbeat vouches for is ``idle_alive``: a *successful* observation of an
    empty stream. So a quiet day reads COMPLETE again, on evidence rather than
    on an exemption.

    What did NOT change, because it never rested on the heartbeat: a service
    that says nothing at all is still ``no_evidence``, and a day holding one is
    still PARTIAL. Liveness is a claim a daemon has to *make*; absence of the
    claim is not the claim.

    And one thing got stricter rather than looser. ``observed`` now requires
    ``ack=true``, so a consumer redelivered the same ``msg_id`` forever — alive,
    polling, heartbeating, and making zero net progress — reads
    ``no_progress``, not ``idle_alive``. Idle means nothing arrived; that is the
    one reading a wedged consumer must never be able to borrow.
    """
    counters: dict[str, int] = {}
    for service in services:
        for name, value in service.counters.items():
            counters[name] = counters.get(name, 0) + value

    resolved = tuple(services)
    scored = _scored(resolved)
    observed_anywhere = any(s.status in STATUSES_OBSERVATION_LANDED for s in scored)
    if not scored or not observed_anywhere:
        verdict = VERDICT_NOT_OBSERVED
    elif not all(s.status in STATUSES_OBSERVED_OK for s in scored):
        verdict = VERDICT_PARTIAL
    elif any(s.liveness_unverified for s in scored):
        # Everything consumed and covered the session, but a service exempt from
        # the freshness bound went silent past it, and nothing scored that. The
        # day is not a measurement; the row must not be able to pass for one.
        # A verdict rather than a note on one cell, so the counts cell, the
        # sidecar's `counters.qualified` and the exit status all follow from one
        # predicate instead of three that can drift apart.
        verdict = VERDICT_LIVENESS_UNVERIFIED
    else:
        verdict = VERDICT_COMPLETE
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
            observation_max_gap_seconds=config.observation_max_gap_seconds,
            liveness_max_gap_seconds=config.liveness_max_gap_seconds,
            message_key_pattern=config.message_key_pattern,
            harvest_since=config.harvest_since,
            failure_markers=service_failure_markers(directory, spec.name),
        )
        for spec in config.services
    ]
    services, verdict, counters = resolve_day(scanned)
    return DayObservation(
        day=day,
        session_open=session_open,
        session_close=session_close,
        verdict=verdict,
        # Carried beside the verdict, never over it: see `reported_verdict`.
        session_day=is_session_day(day, schedule_path=schedule_path),
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
    """Render windows, leaving a single-observation one open at its start.

    A window whose start and end are the same timestamp rests on ONE line. The
    real 2026-09-18 risk-filter is the case: a single ``consumer group missing;
    recreated`` at 09:47 is evidence of a group that was gone over an *unknown
    window ending at* 09:47, not of a point event there. ``<=09:47`` says the
    end is known and the start is not; ``09:47`` would claim a duration the
    line cannot support.
    """
    parts = []
    for start, end in windows:
        parts.append(
            f"<={_hhmm(end)}"
            if _hhmm(start) == _hhmm(end)
            else f"{_hhmm(start)}-{_hhmm(end)}"
        )
    return ", ".join(parts)


#: How many ``unobserved`` windows a row spells out before it starts counting.
#: They are deliberately NOT run-merged the way blind timestamps are: a proof
#: separates each window from the next, and merging across it would render a
#: consumer that proved itself 13 times identically to one dead all session —
#: the exact collapse this script exists to prevent. So the row stays honest and
#: gets shorter instead.
_STALE_WINDOWS_SPELLED_OUT = 3


def _stale_text(service: ServiceObservation) -> str:
    """The unaccounted stretches, as a clause, or empty when there is none.

    "No proof of consumption **or liveness**" since the heartbeat landed, and
    the longer wording is the point: a stretch that reaches this clause is one
    the heartbeat was asked about and could not answer for, which is a stronger
    statement than the one the old wording made. A stretch it *did* answer for
    never gets here — it is idle, and idle is rendered as a success.
    """
    if not service.unobserved or not service.freshness_scored:
        return ""
    shown = _window_text(service.unobserved[:_STALE_WINDOWS_SPELLED_OUT])
    extra = len(service.unobserved) - _STALE_WINDOWS_SPELLED_OUT
    more = f" +{extra} more" if extra > 0 else ""
    proof = "consumption or liveness" if service.liveness_scored else "consumption"
    return f", no proof of {proof} {shown}{more}"


def describe_liveness(service: ServiceObservation) -> str:
    """One clause naming the stretch a freshness-exempt service went unverified.

    The stretch and the reason both, because either alone misleads: the window
    without the reason reads like a defect that was measured, and the reason
    without the window reads like a footnote about configuration rather than
    about this day.
    """
    windows = _window_text(service.unobserved[:_STALE_WINDOWS_SPELLED_OUT])
    extra = len(service.unobserved) - _STALE_WINDOWS_SPELLED_OUT
    more = f" +{extra} more" if extra > 0 else ""
    return (
        f"{service.name} liveness unverified {windows}{more} "
        f"({service.freshness_unscored_reason})"
    )


def _consumption_word(service: ServiceObservation) -> str:
    """ "consumed", but only when something really was.

    The word used to be a literal in three branches and it used to be safe
    there, because ``scan_service`` tested ``not observed -> no_evidence``
    ABOVE ``partial_coverage`` and ``stale_observation`` — so reaching either
    of them implied ``observed_count > 0``. The liveness work weakened that
    guard (a service that heartbeats but consumes nothing must get past it to
    be scored at all), and the prose did not follow: a container recreated at
    11:00 that emitted 286 heartbeats and zero evaluations rendered
    ``futures-decision-engine consumed, harvest does not span the session``.

    That is a *worse* form of the defect this module opens with — the earlier
    one let a count imply consumption, this one printed the word — so the verb
    is derived from the count rather than assumed alongside it.
    """
    return "consumed" if service.observed_count else "consumed nothing"


def _no_progress_text(service: ServiceObservation) -> str:
    """The refused deliveries, as a clause, for rows that are not about them.

    ``no_progress`` is a status only when NOTHING completed. A consumer with 85
    good ACKs beside 85 redeliveries of one pinned ``msg_id`` is ``consumed``,
    correctly — and rendered ``4/4 consumed (COMPLETE)`` with the 85 reaching
    only the sidecar, which is where the original defect kept everything it
    could not say out loud.

    The DISTINCT message count travels with it, because that is what separates
    the two readings: ``85 deliveries of 1 message`` is a record pinned in the
    PEL all session, while ``85 deliveries of 85 messages`` is a consumer
    refusing each once and moving on. Only the first is a defect, and no
    threshold is needed to tell them apart — the numbers do it.
    """
    if not service.no_progress_count or service.status == STATUS_NO_PROGRESS:
        return ""
    messages = service.no_progress_messages
    plural = "" if messages == 1 else "s"
    return (
        f", {service.no_progress_count} deliveries of {messages} message"
        f"{plural} made no progress"
    )


def describe_service(service: ServiceObservation) -> str:
    """One clause naming what a non-consuming service did, and when.

    The uncovered part of the session is always named. Ending a window at the
    last line the harvest happens to hold would render "blind 08:45-11:33" for
    a day whose monitor was in fact blind past 12:34 — the file simply stops.

    The unproven stretches are named on a blind row too. ``blind <=09:00`` on a
    monitor whose single proof was at 08:46 reads as an early hiccup; it was in
    fact unproven for the next six and three quarter hours, and that lived only
    in the sidecar. It is suppressed only when it would repeat the blind window
    verbatim, which is the fully-blind case where it adds nothing.

    **No branch here states a fact it has not read.** Every clause is derived
    from a field — the verb from ``observed_count``
    (:func:`_consumption_word`), the refusals from ``no_progress_count``, the
    windows from the interval lists — rather than implied by the status having
    been reached. Statuses are reordered as the scoring changes, and the round
    that added liveness proved the point: two branches kept a literal
    ``consumed`` that a status-ladder change had quietly made false.
    """
    if service.evidence != EVIDENCE_LINES:
        reason = EVIDENCE_REASONS[service.evidence]
        return f"{service.name} NO EVIDENCE ({reason})"

    gap = (
        f" (no evidence {_window_text(service.uncovered)})" if service.uncovered else ""
    )
    stale = _stale_text(service)
    refused = _no_progress_text(service)
    if service.status in (STATUS_BLIND, STATUS_PARTIALLY_BLIND):
        blind_text = _window_text(service.blind_windows)
        word = "BLIND" if service.status == STATUS_BLIND else "blind"
        if stale.endswith(blind_text):
            # Same window said twice; the blind spelling is the informative one.
            stale = ""
        return f"{service.name} {word} {blind_text}{stale}{gap}"
    if service.status == STATUS_PARTIAL_COVERAGE:
        # Which kind of hole it is decides what an operator does about it: a
        # `--tail` cap is a knob in config/f9_observation.yaml, while a log that
        # simply began late is a container that was recreated.
        cause = (
            " (head truncated by the --tail cap)" if service.coverage_truncated else ""
        )
        return (
            f"{service.name} {_consumption_word(service)}, harvest does not span "
            f"the session{cause}{refused}{stale}{gap}"
        )
    if service.status == STATUS_STALE_OBSERVATION:
        # The harvest spans the session; what it holds does not. Named as the
        # silence it is, not as the coverage hole it is not.
        return f"{service.name} {_consumption_word(service)}{refused}{stale}{gap}"
    if service.status == STATUS_NO_PROGRESS:
        # Never "silent where harvested" and never "idle": the log is full of
        # this service. Messages arrived, the loop kept turning, and not one of
        # them got through — which the ack-less proof pattern used to render as
        # a healthy consumer renewing its freshness on every redelivery.
        #
        # `stale` rides along: on a pre-heartbeat image nothing vouches for the
        # silence either, and both facts belong in the row. They do not
        # contradict — the deliveries say records arrived, `liveness` is a claim
        # the daemon has to make and this one made none.
        messages = service.no_progress_messages
        plural = "" if messages == 1 else "s"
        return (
            f"{service.name} NO PROGRESS ({service.no_progress_count} deliveries "
            f"of {messages} message{plural}, none completed){stale}{gap}"
        )
    if service.status == STATUS_NO_EVIDENCE:
        return f"{service.name} NO EVIDENCE (silent where harvested){gap}"
    if service.status == STATUS_IDLE_ALIVE:
        # `render_consumers_cell` filters this out — an idle-alive service is a
        # success, and the cell's tally is where it is counted. The branch is
        # here so that any OTHER caller gets the truth rather than the
        # fallthrough below, and it is the one rendering path `idle_windows`
        # has: the stretches are named, not just the beat count, because "alive
        # for 316 beats" does not say WHICH hours were quiet.
        windows = _window_text(service.idle_windows[:_STALE_WINDOWS_SPELLED_OUT])
        extra = len(service.idle_windows) - _STALE_WINDOWS_SPELLED_OUT
        more = f" +{extra} more" if extra > 0 else ""
        idle = f", idle {windows}{more}" if service.idle_windows else ""
        return (
            f"{service.name} idle (alive, {service.liveness_count} heartbeats)"
            f"{idle}{gap}"
        )
    # The fallthrough, reached by STATUS_CONSUMED and by any status added later.
    # It derives the verb too, so a new status cannot inherit a false one.
    return f"{service.name} {_consumption_word(service)}{refused}"


def render_consumers_cell(result: DayObservation) -> str:
    """The ``Consumers`` cell — consumers that demonstrably CONSUMED.

    Not "how many are running": see this module's docstring for the 09-17/09-18
    blind window that made the running count worthless.
    """
    scored = _scored(result.services)
    consumed = [s for s in scored if s.status == STATUS_CONSUMED]
    idle = [s for s in scored if s.status == STATUS_IDLE_ALIVE]
    # Consumption and liveness stay separately legible in the cell a human
    # reads, not only in the sidecar. "4/4 consumed" on a day where two
    # consumed and two were idle-but-alive would be a new conflation of exactly
    # the kind the `observed`/`liveness` split exists to prevent — both are
    # successful observations, and they are not the same observation. The
    # second clause is omitted when there is nothing idle, so the rows of a
    # fully-consuming day still read the way every earlier row in the runbook's
    # table does.
    tally = f"{len(consumed)}/{len(scored)} consumed"
    if idle:
        tally += f", {len(idle)}/{len(scored)} alive (idle)"

    # Refusals on a service whose STATUS is fine. 85 good ACKs beside 85
    # redeliveries of one pinned msg_id is `consumed` — correctly, it really did
    # consume — and rendered `4/4 consumed (COMPLETE)` with the 85 reaching only
    # the sidecar. A count nobody sees is the failure this file keeps meeting,
    # so it rides in the cell with the tally rather than waiting in the problems
    # list it can never join.
    refusals = "; ".join(
        f"{service.name}: {_no_progress_text(service).removeprefix(', ')}"
        for service in scored
        if service.status in STATUSES_OBSERVED_OK and service.no_progress_count
    )
    if refusals:
        tally += f" [{refusals}]"

    no_session = (
        ""
        if result.session_day
        else (f"(no session - {result.day.isoformat()} is not a trading day)")
    )
    if no_session and not result.has_evidence:
        return no_session
    if no_session:
        # A day both holiday sources call closed, holding real evidence. Say
        # both — one of the two is wrong and the row is where that shows.
        no_session += " **BUT THE HARVEST HOLDS EVIDENCE** - "

    if result.verdict == VERDICT_COMPLETE:
        return f"{no_session}{tally} (COMPLETE)"

    if result.verdict == VERDICT_LIVENESS_UNVERIFIED:
        # Every service is `consumed`, so the `problems` list below would be
        # empty. What is wrong with the day is a thing no status can carry.
        unverified = "; ".join(
            describe_liveness(s) for s in scored if s.liveness_unverified
        )
        return f"{no_session}{tally} ({VERDICT_LIVENESS_UNVERIFIED}): {unverified}"

    problems = "; ".join(
        describe_service(s) for s in scored if s.status not in STATUSES_OBSERVED_OK
    )
    marker = (
        "**NOT OBSERVED**"
        if result.verdict == VERDICT_NOT_OBSERVED
        else "**NOT COMPLETE**"
    )
    return f"{no_session}{marker} - {tally} ({result.verdict}): {problems}"


def render_counts_cell(result: DayObservation, row_counters: Sequence[str]) -> str:
    """The candidates -> final -> fills cell, qualified by the verdict.

    A bare "0 -> 0 -> 0" from a day whose observation surface was blind reads
    identically to a genuine quiet market. It never ships bare.

    ``LIVENESS_UNVERIFIED`` falls through to the same qualification, and must:
    the ``candidates`` counter comes from the very producer whose liveness is
    unverified, so its "0" is the "observed 0 / could not observe" collapse in
    its purest form.
    """
    counts = " -> ".join(str(result.counters.get(name, 0)) for name in row_counters)
    if not result.session_day:
        if not result.has_evidence:
            return "n/a - no session"
        # Measured against a session window that, per both holiday sources,
        # did not exist. Reported rather than discarded, and never bare.
        return (
            f"{counts} - UNQUALIFIED: {result.day.isoformat()} is not a trading "
            "day in either holiday source, yet the harvest holds evidence - "
            "check the calendar before reading these"
        )
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
    notes = f"observation={result.reported_verdict}"
    if not result.session_day and result.has_evidence:
        notes += "; not a trading day in either holiday source"
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
        "verdict": result.reported_verdict,
        "evidence_verdict": result.verdict,
        "session_day": result.session_day,
        "verdict_inputs": "durable: harvested log files only (Redis streams "
        "expire after 24h, so a past day is not reconstructible from Redis)",
        # The qualification travels WITH the values: a reader who copies
        # `counters` out of this JSON must not end up holding bare numbers from
        # a day whose observation surface could not see.
        "counters": {
            "qualified": result.reported_verdict == VERDICT_COMPLETE
            and result.session_day,
            "qualification": (
                "measured: the observation surface covered the session and "
                "proved it consumed throughout"
                if result.reported_verdict == VERDICT_COMPLETE and result.session_day
                else f"UNQUALIFIED: observation {result.reported_verdict}, these "
                "are a lower bound, not a measurement"
            ),
            "values": dict(result.counters),
        },
        "row": row,
        "services": [
            {
                "name": service.name,
                "role": service.role,
                "status": service.status,
                "evidence": service.evidence,
                "evidence_detail": EVIDENCE_REASONS.get(service.evidence, "parsed"),
                "coverage_kst": [
                    [start.isoformat(), end.isoformat()]
                    for start, end in service.coverage
                ],
                "uncovered_session_kst": [
                    [start.isoformat(), end.isoformat()]
                    for start, end in service.uncovered
                ],
                "unobserved_session_kst": [
                    [start.isoformat(), end.isoformat()]
                    for start, end in service.unobserved
                ],
                # Stretches with no consumption that the heartbeat vouched for.
                # Beside `unobserved`, never merged into it: the two are the
                # answers to the same question — what happened during the
                # silence — and the whole point is that they are different.
                "idle_session_kst": [
                    [start.isoformat(), end.isoformat()]
                    for start, end in service.idle_windows
                ],
                "liveness_count": service.liveness_count,
                "liveness_scored": service.liveness_scored,
                "no_progress_count": service.no_progress_count,
                "no_progress_messages": service.no_progress_messages,
                "covers_session": service.covers_session,
                "observation_is_fresh": service.observation_is_fresh,
                # False means `unobserved` above is context, not a verdict input
                # — see the module docstring's "Observation freshness".
                "freshness_scored": service.freshness_scored,
                "freshness_unscored_reason": service.freshness_unscored_reason,
                "liveness_unverified": service.liveness_unverified,
                "coverage_truncated": service.coverage_truncated,
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
        config = replace(config, report_root=anchored_report_root(args.report_root))
    today = datetime.now(KST).date()
    day = date_cls.fromisoformat(args.date) if args.date else today
    # Echoed always: every verdict below is *about this tree*, and a verdict
    # against the wrong tree used to be indistinguishable from a dead surface.
    print(f"[root] {config.report_root}", file=sys.stderr)

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

    day_directory = config.report_root / day.isoformat()
    if (
        not harvest
        and not day_directory.is_dir()
        and is_session_day(day, schedule_path=Path(args.schedule))
    ):
        # Refused rather than verdicted. `--no-harvest` means "read the files
        # already harvested"; with no directory holding them there is no input,
        # and the scan would have rendered a confident `NOT OBSERVED - 0/4`
        # against nothing — then `mkdir(parents=True)` below would create the
        # mistyped tree and file a sidecar in it, which a second run reads back
        # as its own evidence. A wrong --report-root and a dead observation
        # surface must not look alike.
        print(
            f"[error] no harvest directory for the {day} session at "
            f"{day_directory} — nothing to verdict. Check --report-root "
            "(relative paths anchor at the repo root, not the working "
            "directory) or harvest the day first.",
            file=sys.stderr,
        )
        return 2

    if harvest:
        stamp = datetime.now(KST).strftime("%H%M%S")
        for name, outcome in harvest_logs(config, day, stamp=stamp).items():
            failure = "" if outcome.ok else f" FAILED rc={outcome.returncode}"
            print(f"[harvest] {name} -> {outcome.path}{failure}", file=sys.stderr)

    point_in_time = {} if args.no_point_in_time else collect_point_in_time(config, day)
    result = observe_day(
        config, day, schedule_path=Path(args.schedule), point_in_time=point_in_time
    )

    # The sidecar lands beside the evidence it audits, and only there. The
    # refusal above is trading-day gated, so on a weekend a mistyped
    # --report-root used to sail past it and `mkdir(parents=True)` the typo
    # tree, leaving a sidecar in a directory nothing was ever harvested into.
    sidecar = (
        day_directory
        / f"observation-completeness.{datetime.now(KST).strftime('%H%M%S')}.json"
        if day_directory.is_dir()
        else None
    )
    row = render_row(result, config.row_counters, sidecar=sidecar)
    if sidecar is not None:
        sidecar.write_text(
            json.dumps(build_sidecar(result, row), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print(row)
    if sidecar is None:
        print(
            f"[sidecar] none — nothing was harvested into {day_directory}",
            file=sys.stderr,
        )
    else:
        print(f"[sidecar] {sidecar}", file=sys.stderr)
    # NO_SESSION and LIVENESS_UNVERIFIED exit 0 alongside COMPLETE: the runbook
    # invokes this per session and exit-0-on-COMPLETE invites cron, so a
    # standing weekend alarm — or a standing alarm on every day whose throttled
    # producer stayed quiet, which both real harvests show is every day — would
    # erode the signal this script exists to carry. Each of them says its piece
    # in the row instead. It is the *reported* verdict, so a non-trading day
    # holding incomplete evidence still exits 1 rather than being excused by the
    # calendar.
    return 0 if result.reported_verdict in VERDICTS_EXIT_ZERO else 1


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
