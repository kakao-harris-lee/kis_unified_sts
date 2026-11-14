#!/usr/bin/env python3
"""CP-3 §3.6 — the two session-derived inputs read from the durable stores."""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sqlite3
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tos_cp3 import TOS_CP3_VERSION  # noqa: E402

SOURCE_ID = f"tos-cp3-session-inputs/{TOS_CP3_VERSION}"

SCHEMA_VERSION = 3

MARKETFEED_FILE_NAME = "marketfeed.sqlite3"
EVIDENCE_FILE_NAME = "evidence.sqlite3"
INBOX_FILE_NAME = "inbox.sqlite3"

#: own value into ``PRAGMA user_version``. Pinned rather than read-and-
PINNED_MARKETFEED_SCHEMA_VERSION = 1
PINNED_EVIDENCE_SCHEMA_VERSION = 2
PINNED_INBOX_SCHEMA_VERSION = 1

DECISION_TICK_EVENT_KIND = "DECISION_TICK"

TICK_CAPSULE_PATH: tuple[str, ...] = ("decision_tick", "capsule", "capsule_id")
TICK_SNAPSHOT_PATH: tuple[str, ...] = (
    "decision_tick",
    "capsule",
    "critical_input_snapshot",
    "snapshot_id",
)

TICK_VALUE_VIEW_PATH: tuple[str, ...] = ("decision_tick", "value_view")

INBOX_HANDLING_STARTED_COLUMN = "handling_started_evidence_seq"
INBOX_CONSUMED_COLUMN = "consumed_evidence_seq"

SNAPSHOT_FIELD_EVALUATIONS_KEY = "field_evaluations"
SNAPSHOT_OBSERVATIONS_KEY = "observations"
FIELD_EVALUATION_STATE_KEY = "state"
FIELD_EVALUATION_FIELD_REF_KEY = "field_ref"
OBSERVATION_FIELD_STATE_KEY = "field_state"

PREIMAGE_ENTRIES_KEY = "entries"
PREIMAGE_ENTRY_KEY_KEY = "key"
PREIMAGE_ENTRY_VALUE_KEY = "value"

STALE_FIELD_STATE = "STALE"
VALID_FIELD_STATE = "VALID"
UNKNOWN_FIELD_STATE = "UNKNOWN"

CAUSE_PRESENT_REFUSED = "present_value_refused"
CAUSE_ABSENT_FROM_PAYLOAD = "absent_from_payload"
CAUSE_UNPROJECTABLE = "unprojectable"

EVIDENCE_PAYLOAD_KEY = "payload"

DECISION_KINDS: tuple[str, ...] = (
    "DECISION_OUTCOME_EMITTED",
    "DECISION_WITHHELD",
    "DECISION_DEGRADED",
    "COORDINATOR_PRECONDITION_REFUSED",
)

FLOW_KINDS: tuple[str, ...] = (
    "FLOW_STEP_ADMITTED",
    "FLOW_HALTED",
    "ATTEMPT_REQUEST_CREATED",
    "SEND_HANDED_OFF",
    "EGRESS_RESULT_CONSUMED",
    "RESULT_UNMATCHED",
)

CAPACITY_DENIAL_HALT_REASON = "AT_MOST_ONE_EXPOSURE_HELD"

OUTCOME_TYPE_TO_KIND: Mapping[str, str] = {"NoActionOutcome": "NO_ACTION"}

PROPOSAL_KIND = "PROPOSAL"

NO_OUTCOME_KIND = "NO_OUTCOME"

PRODUCER_DISPOSITION_STAGES: tuple[str, ...] = (
    "published",
    "skipped_behind",
    "late_completed",
    "missing_no_successor",
    "no_raw_row_for_minute",
    "omitted_unusable",
    "produce_error",
    "clock_regression",
)

REASON_PRE_BOOT = "pre_boot"

REASON_UNCONSUMED_AFTER_BOOT = "published_not_consumed"

REASON_PUBLISHED_AFTER_CLOSE = "published_after_session_close"

REASON_UNEXPLAINED = "unexplained"


class SessionInputsError(RuntimeError):
    """A refusal. Nothing is written when one is raised."""


def _connect_ro(path: Path, *, label: str, pinned_version: int) -> sqlite3.Connection:
    """Open *path* read-only and refuse a store shape this was not written for."""
    if not path.is_file():
        raise SessionInputsError(
            f"{label} store not found: {path}. A session that never ticked "
            "writes no marketfeed store at all (runbook tos-paper-boot-history.md §4), "
            "which is a different fact from an empty one"
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    except sqlite3.Error as exc:  # pragma: no cover - a corrupt file
        conn.close()
        raise SessionInputsError(f"{label} store {path} is unreadable: {exc}") from exc
    if version != pinned_version:
        conn.close()
        raise SessionInputsError(
            f"{label} store {path} declares PRAGMA user_version={version}, this "
            f"extractor is pinned to {pinned_version}. A different version means "
            "the tables changed shape, and these queries would answer a question "
            "about a store that no longer exists"
        )
    return conn


def sha256_file(path: Path) -> str:
    """Streaming sha256 of a file — the stores can be large."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_ref(path: Path | None) -> dict[str, Any] | None:
    """``{path, sha256}`` for a file that was read, or ``None``."""
    if path is None:
        return None
    return {"path": str(path), "sha256": sha256_file(path)}


@dataclass(frozen=True)
class Snapshot:
    """One issued snapshot and the single observation it covered."""

    snapshot_id: str
    instrument: str
    as_of_ms: int
    raw_event_id: str
    field_evaluations: tuple[tuple[str, str], ...] = ()
    observation_states: tuple[str, ...] = ()
    payload_tokens: Mapping[str, Any] = field(default_factory=dict)

    @property
    def field_states(self) -> tuple[str, ...]:
        """Just the states, in stored order."""
        return tuple(state for _ref, state in self.field_evaluations)


def _projectable(token: Any) -> bool:
    """Would ``tos.marketfeed.value.project_scalar`` admit this token?"""
    return isinstance(token, (bool, int, str))


def _snapshot_states(
    snapshot_json: str, *, snapshot_id: str
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """The durable FieldStates inside one ``snapshots.snapshot_json``."""
    document = json.loads(snapshot_json)
    if not isinstance(document, dict):
        raise SessionInputsError(
            f"snapshot {snapshot_id}: snapshot_json is "
            f"{type(document).__name__}, not an object — the store writes "
            "CriticalInputSnapshot.model_dump_json(), so a row shaped "
            "otherwise was not written by SqliteSnapshotStore"
        )

    def entries_of(key: str) -> list[Any]:
        entries = document.get(key)
        if entries is None:
            return []
        if not isinstance(entries, list):
            raise SessionInputsError(
                f"snapshot {snapshot_id}: {key} is {type(entries).__name__}, "
                "not a list"
            )
        return entries

    def string_at(entry: Any, key: str, *, where: str) -> str:
        if not isinstance(entry, dict) or not isinstance(entry.get(key), str):
            raise SessionInputsError(
                f"snapshot {snapshot_id}: {where} carries no string {key!r}. "
                "Counting it as 'not a finding' is the silent undercount M5's "
                "first number exists to prevent"
            )
        return str(entry[key])

    evaluations = tuple(
        (
            string_at(
                entry,
                FIELD_EVALUATION_FIELD_REF_KEY,
                where=f"{SNAPSHOT_FIELD_EVALUATIONS_KEY}[{index}]",
            ),
            string_at(
                entry,
                FIELD_EVALUATION_STATE_KEY,
                where=f"{SNAPSHOT_FIELD_EVALUATIONS_KEY}[{index}]",
            ),
        )
        for index, entry in enumerate(entries_of(SNAPSHOT_FIELD_EVALUATIONS_KEY))
    )
    observations = tuple(
        string_at(
            entry,
            OBSERVATION_FIELD_STATE_KEY,
            where=f"{SNAPSHOT_OBSERVATIONS_KEY}[{index}]",
        )
        for index, entry in enumerate(entries_of(SNAPSHOT_OBSERVATIONS_KEY))
    )
    return evaluations, observations


def _preimage_tokens(preimage_json: str, *, snapshot_id: str) -> dict[str, Any]:
    """The tokens one ``preimages.preimage_json`` attested, by key."""
    document = json.loads(preimage_json)
    entries = document.get(PREIMAGE_ENTRIES_KEY) if isinstance(document, dict) else None
    if not isinstance(entries, list):
        raise SessionInputsError(
            f"snapshot {snapshot_id}: preimage_json has no "
            f"{PREIMAGE_ENTRIES_KEY!r} list — the store writes "
            "RawPayloadPreimage.model_dump_json(), and without its tokens an "
            "UNKNOWN field cannot be told from an absent one"
        )
    tokens: dict[str, Any] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not isinstance(
            entry.get(PREIMAGE_ENTRY_KEY_KEY), str
        ):
            raise SessionInputsError(
                f"snapshot {snapshot_id}: "
                f"{PREIMAGE_ENTRIES_KEY}[{index}] carries no string "
                f"{PREIMAGE_ENTRY_KEY_KEY!r}"
            )
        tokens[str(entry[PREIMAGE_ENTRY_KEY_KEY])] = entry.get(PREIMAGE_ENTRY_VALUE_KEY)
    return tokens


def read_snapshots(data_dir: Path) -> tuple[Snapshot, ...]:
    """Every issued snapshot of the session, in issue order, with its id."""
    conn = _connect_ro(
        data_dir / MARKETFEED_FILE_NAME,
        label="marketfeed",
        pinned_version=PINNED_MARKETFEED_SCHEMA_VERSION,
    )
    try:
        rows = list(
            conn.execute(
                "SELECT snapshot_id, instrument, as_of_ms, snapshot_json "
                "FROM snapshots ORDER BY rowid"
            )
        )
        preimages: dict[str, list[tuple[str, str]]] = {}
        for snapshot_id, raw_event_id, preimage_json in conn.execute(
            "SELECT snapshot_id, raw_event_id, preimage_json FROM preimages"
        ):
            preimages.setdefault(str(snapshot_id), []).append(
                (str(raw_event_id), str(preimage_json))
            )
    finally:
        conn.close()

    snapshots: list[Snapshot] = []
    for snapshot_id, instrument, as_of_ms, snapshot_json in rows:
        covered = preimages.get(str(snapshot_id), [])
        if len(covered) != 1:
            raise SessionInputsError(
                f"snapshot {snapshot_id} covers {len(covered)} preimage row(s), "
                "expected exactly 1. One journal line is one observation and one "
                "snapshot (marketfeed/journal.py's own line shape), so another "
                "count means this session was not produced by ③ or the preimages "
                "were lost — either way the id this decision was about is not "
                "decidable here"
            )
        evaluations, observation_states = _snapshot_states(
            str(snapshot_json), snapshot_id=str(snapshot_id)
        )
        raw_event_id, preimage_json = covered[0]
        snapshots.append(
            Snapshot(
                snapshot_id=str(snapshot_id),
                instrument=str(instrument),
                as_of_ms=int(as_of_ms),
                raw_event_id=raw_event_id,
                field_evaluations=evaluations,
                observation_states=observation_states,
                payload_tokens=_preimage_tokens(
                    preimage_json, snapshot_id=str(snapshot_id)
                ),
            )
        )
    return tuple(snapshots)


def _assert_one_instrument(snapshots: Sequence[Snapshot]) -> str:
    instruments = sorted({snapshot.instrument for snapshot in snapshots})
    if len(instruments) != 1:
        raise SessionInputsError(
            f"the session's snapshots name {instruments} — a tenant session is "
            "one instrument (the runner derives the contract month once and "
            "gives render, data dir and producer the same value), so more than "
            "one means two deployments wrote into one durable set"
        )
    return instruments[0]


def _iter_json_lines(path: Path, *, label: str) -> Iterator[dict[str, Any]]:
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SessionInputsError(
                f"{label} line {index} is not JSON: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise SessionInputsError(f"{label} line {index} is not an object")
        yield payload


@dataclass(frozen=True)
class ProducerLogFacts:
    """What one pass over the producer's own log says about its bars."""

    dispositions: dict[str, str]
    published_as_of_ms: dict[str, int]
    session_close: _dt.time | None


PRODUCER_SEED_STAGE = "seed"
PRODUCER_SESSION_WINDOW_KEY = "session_window"


def _parse_session_close(value: Any) -> _dt.time | None:
    """The END of a ``"<start>..<end>"`` window, or ``None`` if unreadable."""
    if not isinstance(value, str) or ".." not in value:
        return None
    try:
        return _dt.time.fromisoformat(value.rsplit("..", 1)[1])
    except ValueError:
        return None


def producer_log_facts(producer_log: Path) -> ProducerLogFacts:
    """One pass over the producer log — see :class:`ProducerLogFacts`."""
    disposed: dict[str, str] = {}
    published_as_of_ms: dict[str, int] = {}
    session_close: _dt.time | None = None
    for payload in _iter_json_lines(producer_log, label="producer log"):
        stage = payload.get("stage")
        if stage == PRODUCER_SEED_STAGE and session_close is None:
            session_close = _parse_session_close(
                payload.get(PRODUCER_SESSION_WINDOW_KEY)
            )
            continue
        raw_event_id = payload.get("raw_event_id")
        if not isinstance(raw_event_id, str) or stage not in (
            PRODUCER_DISPOSITION_STAGES
        ):
            continue
        if disposed.get(raw_event_id) == "published":
            continue
        disposed[raw_event_id] = str(stage)
        if stage == "published":
            as_of_ms = payload.get("as_of_ms")
            if isinstance(as_of_ms, int) and not isinstance(as_of_ms, bool):
                published_as_of_ms[raw_event_id] = as_of_ms
    return ProducerLogFacts(
        dispositions=disposed,
        published_as_of_ms=published_as_of_ms,
        session_close=session_close,
    )


def read_boot_snapshot(path: Path) -> frozenset[str]:
    """The ids already in the journal when the runtime booted (runner step 9b)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    ids = payload.get("pre_boot_raw_event_ids") if isinstance(payload, dict) else None
    if not isinstance(ids, list) or not all(isinstance(value, str) for value in ids):
        raise SessionInputsError(
            f"{path} carries no pre_boot_raw_event_ids list — that key is the "
            "runner's record of what was already in the journal at boot, and "
            "without it a pre-boot line is indistinguishable from a line the "
            "runtime failed to consume"
        )
    return frozenset(ids)


_RAW_EVENT_ID_SEPARATOR = ":1m:"
_RAW_EVENT_ID_STAMP_FORMAT = "%Y%m%dT%H%M%S%z"

_KST = ZoneInfo("Asia/Seoul")


def _published_after_close(
    raw_event_id: str, as_of_ms: int | None, session_close: _dt.time | None
) -> bool:
    """Was this bar's line STAMPED at or after its own session's close?"""
    if as_of_ms is None or session_close is None:
        return False
    try:
        bar = _dt.datetime.strptime(
            raw_event_id.split(_RAW_EVENT_ID_SEPARATOR, 1)[1],
            _RAW_EVENT_ID_STAMP_FORMAT,
        )
    except (IndexError, ValueError):
        return False
    close = _dt.datetime.combine(bar.date(), session_close, tzinfo=bar.tzinfo)
    return as_of_ms >= int(close.timestamp() * 1000)


def unpaired_reasons(
    *,
    consumed: frozenset[str],
    dispositions: Mapping[str, str],
    pre_boot: frozenset[str],
    published_as_of_ms: Mapping[str, int] | None = None,
    session_close: _dt.time | None = None,
) -> dict[str, str]:
    """Why each produced-but-unconsumed bar has no live counterpart."""
    stamps = published_as_of_ms or {}
    reasons: dict[str, str] = {}
    for raw_event_id, stage in dispositions.items():
        if raw_event_id in consumed:
            continue
        if stage != "published":
            reasons[raw_event_id] = stage
        elif raw_event_id in pre_boot:
            reasons[raw_event_id] = REASON_PRE_BOOT
        elif _published_after_close(
            raw_event_id, stamps.get(raw_event_id), session_close
        ):
            reasons[raw_event_id] = REASON_PUBLISHED_AFTER_CLOSE
        else:
            reasons[raw_event_id] = REASON_UNCONSUMED_AFTER_BOOT
    return reasons


def session_day_of(raw_event_id: str) -> str | None:
    """The **KST** ``YYYYMMDD`` a bar id belongs to, or ``None`` when the id is malformed."""
    try:
        stamp = raw_event_id.split(_RAW_EVENT_ID_SEPARATOR, 1)[1]
        parsed = _dt.datetime.strptime(stamp, _RAW_EVENT_ID_STAMP_FORMAT)
    except (IndexError, ValueError):
        return None
    return parsed.astimezone(_KST).strftime("%Y%m%d")


def derive_session_day(
    snapshots: Sequence[Snapshot], pre_boot: frozenset[str] = frozenset()
) -> str | None:
    """The session day these snapshots were measured for."""
    consumed_days = {
        day
        for day in (session_day_of(snapshot.raw_event_id) for snapshot in snapshots)
        if day is not None
    }
    newest_consumed = max(consumed_days) if consumed_days else None
    boot_days = {
        day for day in (session_day_of(bar) for bar in pre_boot) if day is not None
    }
    if not boot_days:
        return newest_consumed
    if len(boot_days) > 1:
        raise SessionInputsError(
            "the boot snapshot's pre_boot_raw_event_ids span more than one KST day "
            f"({sorted(boot_days)}) — one boot cannot belong to two sessions, so the "
            "snapshot and the store are not from the same run"
        )
    session_day = boot_days.pop()
    if newest_consumed is not None and newest_consumed != session_day:
        raise SessionInputsError(
            f"the boot snapshot is for KST day {session_day} but the newest consumed bar in "
            f"the store is from {newest_consumed} — the two are not from the same session "
            "(a session that died before consuming anything reads the PREVIOUS session's "
            "numbers as its own). Point --boot-snapshot at this store's own session."
        )
    return session_day


@dataclass(frozen=True)
class SessionScope:
    """One session's slice of an accumulating durable leaf (:func:`scope_to_session_day`)."""

    session_day: str | None
    days_present: tuple[str, ...]
    all_days_total: int


def scope_to_session_day(
    snapshots: Sequence[Snapshot], pre_boot: frozenset[str]
) -> tuple[list[Snapshot], SessionScope]:
    """Cut ``snapshots`` down to the one session this document is about."""
    unparseable = sorted(
        snapshot.raw_event_id
        for snapshot in snapshots
        if session_day_of(snapshot.raw_event_id) is None
    )
    if unparseable:
        raise SessionInputsError(
            f"{len(unparseable)} consumed raw_event_id(s) carry no readable "
            f"'{_RAW_EVENT_ID_SEPARATOR}<stamp>' day and so cannot be scoped to a session: "
            f"{unparseable[:5]}{' …' if len(unparseable) > 5 else ''}. Refusing to report "
            "counts that would silently omit them."
        )
    session_day = derive_session_day(snapshots, pre_boot)
    days_present = tuple(
        sorted(
            {
                day
                for day in (session_day_of(s.raw_event_id) for s in snapshots)
                if day is not None
            }
        )
    )
    scoped = [
        snapshot
        for snapshot in snapshots
        if session_day is None or session_day_of(snapshot.raw_event_id) == session_day
    ]
    return scoped, SessionScope(
        session_day=session_day,
        days_present=days_present,
        all_days_total=len(snapshots),
    )


def consumed_field_states(
    *,
    snapshots: Sequence[Snapshot],
    pre_boot: frozenset[str],
    scope: SessionScope,
) -> dict[str, Any]:
    """M5's first count: lines the issuer HELD a value for and refused anyway."""
    post_boot_refused: list[str] = []
    pre_boot_refused: list[str] = []
    by_cause: dict[str, dict[str, int]] = {
        CAUSE_PRESENT_REFUSED: {"post_boot": 0, "pre_boot": 0},
        CAUSE_ABSENT_FROM_PAYLOAD: {"post_boot": 0, "pre_boot": 0},
        CAUSE_UNPROJECTABLE: {"post_boot": 0, "pre_boot": 0},
    }
    by_state: dict[str, dict[str, int]] = {}
    observation_by_state: dict[str, dict[str, int]] = {}
    without_evaluations = 0
    in_session = list(snapshots)
    for snapshot in in_session:
        where = "pre_boot" if snapshot.raw_event_id in pre_boot else "post_boot"
        if not snapshot.field_evaluations:
            without_evaluations += 1
        causes: set[str] = set()
        states: set[str] = set()
        for field_ref, state in snapshot.field_evaluations:
            if state == VALID_FIELD_STATE:
                continue
            if state != UNKNOWN_FIELD_STATE:
                states.add(state)
                continue
            if field_ref not in snapshot.payload_tokens:
                causes.add(CAUSE_ABSENT_FROM_PAYLOAD)
            elif _projectable(snapshot.payload_tokens[field_ref]):
                causes.add(CAUSE_PRESENT_REFUSED)
            else:
                causes.add(CAUSE_UNPROJECTABLE)
        for cause in sorted(causes):
            by_cause[cause][where] += 1
        if CAUSE_PRESENT_REFUSED in causes:
            (pre_boot_refused if where == "pre_boot" else post_boot_refused).append(
                snapshot.raw_event_id
            )
        for state in sorted(states):
            bucket = by_state.setdefault(state, {"post_boot": 0, "pre_boot": 0})
            bucket[where] += 1
        for state in sorted(set(snapshot.observation_states)):
            if state == VALID_FIELD_STATE:
                continue
            bucket = observation_by_state.setdefault(
                state, {"post_boot": 0, "pre_boot": 0}
            )
            bucket[where] += 1
    return {
        "m5_post_boot_consumed_ids_with_a_present_value_refused_as_unknown": len(
            post_boot_refused
        ),
        "definition": (
            "consumed raw_event_ids with at least one field_evaluations[*] in "
            "state UNKNOWN whose field_ref is a key of that snapshot's "
            "preimages.preimage_json AND whose token is projectable "
            "(bool/int/str; a float is refused by the kernel's own "
            "project_scalar) — i.e. the issuer held a usable value and refused "
            "it on age or on an unestablished clock. Counted once per id, "
            "excluding ids the runner's boot-journal snapshot lists as pre-boot "
            "(plan §5 M5 excludes those from both of its counts). Read as "
            "'stale, or evaluation clock unknown': an upper bound on STALE. "
            "The persisted FieldState is never STALE — "
            "tos_runtime.marketfeed.snapshot._derive_field_state writes "
            "UNKNOWN and keeps the reason in memory only"
        ),
        "session_day": scope.session_day,
        "days_present": list(scope.days_present),
        "counts": {
            "consumed_ids": len(in_session),
            "consumed_ids_all_days": scope.all_days_total,
            "pre_boot_consumed_ids": sum(
                1 for snapshot in in_session if snapshot.raw_event_id in pre_boot
            ),
            "post_boot_consumed_ids": sum(
                1 for snapshot in in_session if snapshot.raw_event_id not in pre_boot
            ),
            "consumed_ids_without_field_evaluations": without_evaluations,
        },
        "unknown_field_causes": {
            cause: dict(counts) for cause, counts in sorted(by_cause.items())
        },
        "post_boot_raw_event_ids_with_a_present_value_refused_as_unknown": sorted(
            post_boot_refused
        ),
        "pre_boot_raw_event_ids_with_a_present_value_refused_as_unknown": sorted(
            pre_boot_refused
        ),
        "other_field_evaluation_states": {
            state: dict(counts) for state, counts in sorted(by_state.items())
        },
        "observation_field_states_not_valid": {
            state: dict(counts)
            for state, counts in sorted(observation_by_state.items())
        },
        "note": (
            "ids per cause, not fields per cause: one id with three refused "
            "fields counts once, and an id with two different causes counts "
            "once under each. other_field_evaluation_states carries every "
            "non-VALID, non-UNKNOWN state by name — STALE among them, which "
            "today's issuer never writes (it writes UNKNOWN with the reason "
            "in memory), so a non-zero STALE there means the issuer changed "
            "and this block's definition must be revisited. The observation "
            "surface is reported apart because "
            "tos.marketfeed.value.value_field_state takes the WORST of the "
            "observation's admission state, its own field_state and the "
            "matching field evaluations, so neither stands for the other"
        ),
    }


def consumed_value_view_counts(
    *, data_dir: Path, by_snapshot: Mapping[str, str]
) -> dict[str, Any]:
    """What the RESOLVER did on each consumed tick — reported beside M5, not as it."""
    ticks = read_decision_ticks(data_dir)
    counts = {"no_view": 0, "empty_view": 0, "values_admitted": 0}
    with_values: list[str] = []
    for tick in ticks:
        raw_event_id = by_snapshot.get(tick.snapshot_id)
        if tick.admitted_values is None:
            counts["no_view"] += 1
        elif tick.admitted_values == 0:
            counts["empty_view"] += 1
        else:
            counts["values_admitted"] += 1
            if raw_event_id is not None:
                with_values.append(raw_event_id)
    return {
        "counts": counts,
        "raw_event_ids_with_admitted_values": sorted(with_values),
        "note": (
            "per admitted DECISION_TICK, the shape of the resolver's "
            "value_view: empty_view = 'the binding resolved and nothing was "
            "admissible', no_view = the resolver published none at all. "
            "NOT M5's first number — an empty view has ten possible reasons "
            "and the store does not say which; M5's first number is "
            "consumed_field_states"
            ".m5_post_boot_consumed_ids_with_a_present_value_refused_as_unknown"
        ),
    }


def build_consumed_ids_document(
    *,
    data_dir: Path,
    producer_log: Path | None = None,
    boot_snapshot: Path | None = None,
) -> dict[str, Any]:
    """The ``consumed-ids`` document: the id filter plus the reason map."""
    if boot_snapshot is None:
        raise SessionInputsError(
            "consumed-ids needs the runner's boot-journal snapshot "
            "(--boot-snapshot): the document always carries M5's counts, and "
            "plan §5 M5 excludes pre-boot lines from them. Without it every "
            "pre-boot line is counted as a post-boot one — silently, in the "
            "number the criterion is read off. 'No pre-boot lines' is an "
            "empty pre_boot_raw_event_ids list, not a missing file"
        )
    snapshots: Sequence[Snapshot] = read_snapshots(data_dir)
    if not snapshots:
        raise SessionInputsError(
            f"{data_dir / MARKETFEED_FILE_NAME} holds no snapshots — the runtime "
            "consumed nothing, so an id filter built from it would silently "
            "empty every comparison"
        )
    pre_boot = read_boot_snapshot(boot_snapshot)
    snapshots, scope = scope_to_session_day(snapshots, pre_boot)
    if not snapshots:
        raise SessionInputsError(
            f"the store holds {scope.all_days_total} snapshot(s) but none for KST day "
            f"{scope.session_day} (days present: {list(scope.days_present)}) — the boot "
            "snapshot and this store are not from the same session"
        )
    instrument = _assert_one_instrument(snapshots)
    consumed = frozenset(snapshot.raw_event_id for snapshot in snapshots)
    facts = (
        producer_log_facts(producer_log)
        if producer_log is not None
        else ProducerLogFacts(
            dispositions={}, published_as_of_ms={}, session_close=None
        )
    )
    dispositions = facts.dispositions
    reasons = unpaired_reasons(
        consumed=consumed,
        dispositions=dispositions,
        pre_boot=pre_boot,
        published_as_of_ms=facts.published_as_of_ms,
        session_close=facts.session_close,
    )
    reason_counts: dict[str, int] = {}
    for reason in reasons.values():
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "kind": "consumed_raw_event_ids",
        "instrument": instrument,
        "generated_from": {
            "data_dir": str(data_dir),
            "marketfeed_sqlite3": _file_ref(data_dir / MARKETFEED_FILE_NAME),
            "marketfeed_schema_version": PINNED_MARKETFEED_SCHEMA_VERSION,
            "producer_log": _file_ref(producer_log),
            "boot_snapshot": _file_ref(boot_snapshot),
            "producer_session_close": (
                facts.session_close.isoformat() if facts.session_close else None
            ),
        },
        "session_day": scope.session_day,
        "days_present": list(scope.days_present),
        "counts": {
            "snapshots": len(snapshots),
            "snapshots_all_days": scope.all_days_total,
            "consumed_raw_event_ids": len(consumed),
            "producer_disposed_bars": len(dispositions),
            "unpaired": len(reasons),
            "pre_boot_lines_at_boot": len(pre_boot),
        },
        "raw_event_ids": sorted(consumed),
        "pre_boot_raw_event_ids": sorted(pre_boot),
        "unpaired_reasons": dict(sorted(reasons.items())),
        "unpaired_reason_counts": dict(sorted(reason_counts.items())),
        "consumed_field_states": consumed_field_states(
            snapshots=snapshots, pre_boot=pre_boot, scope=scope
        ),
        "consumed_value_view": consumed_value_view_counts(
            data_dir=data_dir,
            by_snapshot={
                snapshot.snapshot_id: snapshot.raw_event_id for snapshot in snapshots
            },
        ),
    }


@dataclass(frozen=True)
class DecisionBlock:
    """One tick's engine records: the decision, then its commitment flow."""

    seq: int
    kind: str
    payload: dict[str, Any]
    flow: tuple[tuple[str, dict[str, Any]], ...]

    @property
    def capsule_id(self) -> str | None:
        """The capsule this decision consumed, when the record names one."""
        value = self.payload.get("capsule_id")
        return None if value is None else str(value)


def _evidence_record(payload_json: str, *, seq: int, kind: str) -> dict[str, Any]:
    """The engine record inside one ``entries.payload_json``."""
    outer = json.loads(payload_json)
    if not isinstance(outer, dict) or EVIDENCE_PAYLOAD_KEY not in outer:
        raise SessionInputsError(
            f"evidence seq {seq} ({kind}): payload_json has no "
            f"{EVIDENCE_PAYLOAD_KEY!r} key. Every entry the store writes is "
            '{"payload": <record>, "masked_keys": [...]} — a row shaped '
            "otherwise was not written by SqliteEvidenceStore, and reading it "
            "as the record itself would find every field absent and report an "
            "emitted outcome as an empty one"
        )
    record = outer[EVIDENCE_PAYLOAD_KEY]
    if not isinstance(record, dict):
        raise SessionInputsError(
            f"evidence seq {seq} ({kind}): payload is {type(record).__name__}, "
            "not an object"
        )
    return record


def read_decision_blocks(data_dir: Path) -> tuple[DecisionBlock, ...]:
    """Group the session's engine records into one block per decision pass."""
    conn = _connect_ro(
        data_dir / EVIDENCE_FILE_NAME,
        label="evidence",
        pinned_version=PINNED_EVIDENCE_SCHEMA_VERSION,
    )
    wanted = (*DECISION_KINDS, *FLOW_KINDS)
    placeholders = ",".join("?" * len(wanted))
    try:
        rows = list(
            conn.execute(
                "SELECT seq, kind, payload_json FROM entries "
                f"WHERE kind IN ({placeholders}) ORDER BY seq",
                wanted,
            )
        )
    finally:
        conn.close()

    blocks: list[DecisionBlock] = []
    current: dict[str, Any] | None = None
    flow: list[tuple[str, dict[str, Any]]] = []
    for seq, kind, payload_json in rows:
        payload = _evidence_record(payload_json, seq=int(seq), kind=str(kind))
        if kind in DECISION_KINDS:
            if current is not None:
                blocks.append(
                    DecisionBlock(
                        seq=current["seq"],
                        kind=current["kind"],
                        payload=current["payload"],
                        flow=tuple(flow),
                    )
                )
            current, flow = {"seq": int(seq), "kind": str(kind), "payload": payload}, []
            continue
        if current is None:
            raise SessionInputsError(
                f"evidence seq {seq} is a {kind} record with no decision record "
                "before it — a commitment-flow record belongs to the decision "
                "that started it, and attributing it to the next one would put "
                "one tick's flow on another tick's bar"
            )
        flow.append((str(kind), payload))
    if current is not None:
        blocks.append(
            DecisionBlock(
                seq=current["seq"],
                kind=current["kind"],
                payload=current["payload"],
                flow=tuple(flow),
            )
        )
    return tuple(blocks)


def _live_outcome_kind(block: DecisionBlock) -> str:
    """The token for one live decision block."""
    if block.kind != "DECISION_OUTCOME_EMITTED":
        return NO_OUTCOME_KIND
    outcome_type = block.payload.get("outcome_type")
    if outcome_type is None:
        raise SessionInputsError(
            f"evidence seq {block.seq}: an emitted-outcome record with no "
            "outcome_type. Every DECISION_OUTCOME_EMITTED record the pipeline "
            "writes carries one, so this row is not one of them (a wrapper "
            "read as the record looks exactly like this — see "
            f"{EVIDENCE_PAYLOAD_KEY!r})"
        )
    return OUTCOME_TYPE_TO_KIND.get(str(outcome_type), PROPOSAL_KIND)


def _flow_halt(block: DecisionBlock) -> tuple[str | None, str | None]:
    """This block's first ``FLOW_HALTED`` row as ``(halt_reason, step)``."""
    for kind, payload in block.flow:
        if kind == "FLOW_HALTED":
            reason = payload.get("halt_reason")
            step = payload.get("step")
            return (
                None if reason is None else str(reason),
                None if step is None else str(step),
            )
    return None, None


@dataclass(frozen=True)
class DecisionTick:
    """One admitted ``DECISION_TICK`` event: the KEY from a decision to a bar."""

    seq: int
    capsule_id: str
    snapshot_id: str
    admitted_values: int | None
    handling_started_evidence_seq: int | None = None
    consumed_evidence_seq: int | None = None

    def brackets(self, evidence_seq: int) -> bool:
        """Does this tick's durable handling window contain ``evidence_seq``?"""
        if self.handling_started_evidence_seq is None:
            return False
        if evidence_seq <= self.handling_started_evidence_seq:
            return False
        return (
            self.consumed_evidence_seq is None
            or evidence_seq <= self.consumed_evidence_seq
        )


def _dig(payload: Mapping[str, Any], path: Sequence[str]) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            return None
        value = value[key]
    return value


def read_decision_ticks(data_dir: Path) -> tuple[DecisionTick, ...]:
    """Every admitted market tick, in admission order, with its two ids."""
    conn = _connect_ro(
        data_dir / INBOX_FILE_NAME,
        label="inbox",
        pinned_version=PINNED_INBOX_SCHEMA_VERSION,
    )
    try:
        rows = list(
            conn.execute(
                "SELECT seq, payload_json, "
                f"{INBOX_HANDLING_STARTED_COLUMN}, {INBOX_CONSUMED_COLUMN} "
                "FROM events WHERE kind = ? ORDER BY seq",
                (DECISION_TICK_EVENT_KIND,),
            )
        )
    finally:
        conn.close()

    ticks: list[DecisionTick] = []
    seen: dict[str, int] = {}
    for seq, payload_json, handling_started, consumed in rows:
        payload = json.loads(payload_json)
        capsule_id = _dig(payload, TICK_CAPSULE_PATH)
        snapshot_id = _dig(payload, TICK_SNAPSHOT_PATH)
        if not isinstance(capsule_id, str) or not isinstance(snapshot_id, str):
            raise SessionInputsError(
                f"inbox seq {seq}: a {DECISION_TICK_EVENT_KIND} event with no "
                f"{'.'.join(TICK_CAPSULE_PATH)} / {'.'.join(TICK_SNAPSHOT_PATH)}. "
                "Those two are what tie a tick to its bar — the receipt "
                "bracket says WHICH tick a record belongs to, and these say "
                "which bar that tick was about; without them the chain ends "
                "at the tick"
            )
        if capsule_id in seen:
            raise SessionInputsError(
                f"inbox seq {seq}: capsule {capsule_id!r} was already admitted "
                f"at seq {seen[capsule_id]} — a capsule id that names two ticks "
                "cannot attribute a decision to one of them"
            )
        seen[capsule_id] = int(seq)
        view = _dig(payload, TICK_VALUE_VIEW_PATH)
        values = None if view is None else _dig(view, ("values",))
        ticks.append(
            DecisionTick(
                seq=int(seq),
                capsule_id=capsule_id,
                snapshot_id=snapshot_id,
                admitted_values=None if values is None else len(values),
                handling_started_evidence_seq=(
                    None if handling_started is None else int(handling_started)
                ),
                consumed_evidence_seq=None if consumed is None else int(consumed),
            )
        )
    return tuple(ticks)


def _attribute(
    blocks: Sequence[DecisionBlock], ticks: Sequence[DecisionTick]
) -> list[tuple[DecisionBlock, DecisionTick, str]]:
    """Pair each decision with the tick it was about, by durable key only."""
    by_capsule = {tick.capsule_id: (index, tick) for index, tick in enumerate(ticks)}
    assigned: dict[int, tuple[int, str]] = {}
    used: dict[int, int] = {}

    for position, block in enumerate(blocks):
        capsule_id = block.capsule_id
        if capsule_id is None:
            continue
        found = by_capsule.get(capsule_id)
        if found is None:
            raise SessionInputsError(
                f"evidence seq {block.seq}: capsule {capsule_id!r} is not one "
                "the inbox admitted. The decision and the tick stores "
                "disagree about what this session processed"
            )
        index, tick = found
        if tick.handling_started_evidence_seq is None:
            raise SessionInputsError(
                f"evidence seq {block.seq}: capsule {capsule_id!r} names inbox "
                f"seq {tick.seq}, whose {INBOX_HANDLING_STARTED_COLUMN} is "
                "NULL — the driver writes that stamp before it can write any "
                "decision record, so a decision quoting this capsule and a "
                "row that never started handling cannot both be true"
            )
        if not tick.brackets(block.seq):
            raise SessionInputsError(
                f"evidence seq {block.seq}: capsule {capsule_id!r} names inbox "
                f"seq {tick.seq}, whose handling window is "
                f"({tick.handling_started_evidence_seq}, "
                f"{tick.consumed_evidence_seq}] — the record is outside it. "
                "The capsule key and the driver's own receipts disagree about "
                "which event wrote this record"
            )
        if index in used:
            raise SessionInputsError(
                f"evidence seq {block.seq} and seq {used[index]} both attribute "
                f"to inbox seq {tick.seq} — one tick, two decisions"
            )
        used[index] = block.seq
        assigned[position] = (index, "capsule_id")

    for position, block in enumerate(blocks):
        if position in assigned:
            continue
        holders = [
            index for index, tick in enumerate(ticks) if tick.brackets(block.seq)
        ]
        if not holders:
            raise SessionInputsError(
                f"evidence seq {block.seq}: a {block.kind} record carries no "
                "capsule id and lies in NO admitted tick's handling window "
                f"({INBOX_HANDLING_STARTED_COLUMN} < seq <= "
                f"{INBOX_CONSUMED_COLUMN}). The driver writes a decision "
                "record only between those two receipts, so there is no event "
                "this record can belong to"
            )
        if len(holders) > 1:
            windows = ", ".join(
                f"inbox seq {ticks[index].seq} "
                f"({ticks[index].handling_started_evidence_seq}, "
                f"{ticks[index].consumed_evidence_seq}]"
                for index in holders
            )
            raise SessionInputsError(
                f"evidence seq {block.seq}: a {block.kind} record carries no "
                f"capsule id and lies in {len(holders)} handling windows "
                f"[{windows}]. Overlapping windows mean an event was left "
                "unconsumed while another ran — the bar this record was about "
                "is not decidable from the receipts"
            )
        index = holders[0]
        if index in used:
            raise SessionInputsError(
                f"evidence seq {block.seq} and seq {used[index]} both attribute "
                f"to inbox seq {ticks[index].seq} — one tick, two decisions"
            )
        used[index] = block.seq
        assigned[position] = (index, "evidence_seq_range")

    return [
        (block, ticks[assigned[position][0]], assigned[position][1])
        for position, block in enumerate(blocks)
    ]


@dataclass(frozen=True)
class LiveScope:
    """``live.jsonl``'s slice of an accumulating leaf (:func:`scope_live_decisions`)."""

    session_day: str | None
    days_present: tuple[str, ...]
    records_all_days: int
    ticks_all_days: int
    ticks_with_no_resolvable_day: int


def scope_live_decisions(
    records: Sequence[Mapping[str, Any]],
    *,
    ticks: Sequence[DecisionTick],
    snapshots: Sequence[Snapshot],
    pre_boot: frozenset[str],
) -> tuple[list[dict[str, Any]], int, LiveScope]:
    """Cut live records and the tick count down to the one session day."""
    unparseable = sorted(
        str(record["raw_event_id"])
        for record in records
        if session_day_of(str(record["raw_event_id"])) is None
    )
    if unparseable:
        raise SessionInputsError(
            f"{len(unparseable)} live decision(s) name a raw_event_id with no readable "
            f"'{_RAW_EVENT_ID_SEPARATOR}<stamp>' day and so cannot be scoped to a "
            f"session: {unparseable[:5]}{' …' if len(unparseable) > 5 else ''}. Refusing "
            "to write a file that would silently omit them."
        )
    session_day = derive_session_day(snapshots, pre_boot)
    day_of_snapshot = {
        snapshot.snapshot_id: session_day_of(snapshot.raw_event_id)
        for snapshot in snapshots
    }
    days_present = tuple(
        sorted({day for day in day_of_snapshot.values() if day is not None})
    )
    scoped = [
        dict(record)
        for record in records
        if session_day is None
        or session_day_of(str(record["raw_event_id"])) == session_day
    ]
    for index, record in enumerate(scoped):
        record["bar_index"] = index
    scoped_ticks = [
        tick
        for tick in ticks
        if session_day is None or day_of_snapshot.get(tick.snapshot_id) == session_day
    ]
    return (
        scoped,
        len(scoped_ticks),
        LiveScope(
            session_day=session_day,
            days_present=days_present,
            records_all_days=len(records),
            ticks_all_days=len(ticks),
            ticks_with_no_resolvable_day=sum(
                1 for tick in ticks if day_of_snapshot.get(tick.snapshot_id) is None
            ),
        ),
    )


def live_decision_records(data_dir: Path) -> list[dict[str, Any]]:
    """One record per live decision, in B1b's trace shape."""
    blocks = read_decision_blocks(data_dir)
    ticks = read_decision_ticks(data_dir)
    snapshots = read_snapshots(data_dir)
    _assert_one_instrument(snapshots)
    by_snapshot = {snapshot.snapshot_id: snapshot for snapshot in snapshots}
    records: list[dict[str, Any]] = []
    for index, (block, tick, how) in enumerate(_attribute(blocks, ticks)):
        snapshot = by_snapshot.get(tick.snapshot_id)
        if snapshot is None:
            raise SessionInputsError(
                f"inbox seq {tick.seq} names snapshot {tick.snapshot_id!r}, which "
                "the marketfeed store does not hold. The tick was admitted and "
                "its snapshot is gone, so the bar it was about is not knowable"
            )
        flow_halt, flow_halt_step = _flow_halt(block)
        records.append(
            {
                "raw_event_id": snapshot.raw_event_id,
                "as_of_ms": snapshot.as_of_ms,
                "bar_index": index,
                "outcome_kind": _live_outcome_kind(block),
                "rule_id": None,
                "pipeline_halt_reason": block.payload.get("halt_reason"),
                "flow_halt_reason": flow_halt,
                "flow_halt_step": flow_halt_step,
                "capacity_denied": flow_halt == CAPACITY_DENIAL_HALT_REASON,
                "handed_off": any(kind == "SEND_HANDED_OFF" for kind, _ in block.flow),
                "attributed_by": how,
                "evidence_seq": block.seq,
                "evidence_kind": block.kind,
                "inbox_seq": tick.seq,
                "snapshot_id": snapshot.snapshot_id,
                "outcome_digest": block.payload.get("outcome_digest"),
                "capsule_id": block.capsule_id,
            }
        )
    return records


def build_live_lineage(
    *,
    data_dir: Path,
    records: Sequence[Mapping[str, Any]],
    payload: bytes,
    ticks: int,
    scope: LiveScope,
) -> dict[str, Any]:
    """The sidecar B3 reads beside ``live.jsonl``."""
    kinds: dict[str, int] = {}
    attribution: dict[str, int] = {}
    for record in records:
        kind = str(record["outcome_kind"])
        kinds[kind] = kinds.get(kind, 0) + 1
        how = str(record["attributed_by"])
        attribution[how] = attribution.get(how, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "kind": "live_decisions",
        "generated_from": {
            "data_dir": str(data_dir),
            "evidence_sqlite3": _file_ref(data_dir / EVIDENCE_FILE_NAME),
            "evidence_schema_version": PINNED_EVIDENCE_SCHEMA_VERSION,
            "marketfeed_sqlite3": _file_ref(data_dir / MARKETFEED_FILE_NAME),
            "marketfeed_schema_version": PINNED_MARKETFEED_SCHEMA_VERSION,
            "inbox_sqlite3": _file_ref(data_dir / INBOX_FILE_NAME),
            "inbox_schema_version": PINNED_INBOX_SCHEMA_VERSION,
        },
        "join": {
            "method": "capsule_id_keyed_with_evidence_seq_range_for_unkeyed",
            "key": (
                "decision.capsule_id -> inbox DECISION_TICK "
                "decision_tick.capsule.capsule_id -> "
                "critical_input_snapshot.snapshot_id -> preimages.raw_event_id"
            ),
            "unkeyed": (
                "a DECISION_WITHHELD or COORDINATOR_PRECONDITION_REFUSED record "
                "names no capsule (the pipeline never reached a signature), so "
                "it is attributed to the UNIQUE admitted tick whose durable "
                "handling window contains its evidence seq: inbox "
                "handling_started_evidence_seq < seq <= consumed_evidence_seq, "
                "the bracket the single-threaded driver writes around each "
                "event. Nothing is attributed by position; the attributed_by "
                "field on every record says which of the two keys was used"
            ),
            "cross_check_keyed": (
                "every capsule-keyed record is also checked against its own "
                "tick's window — a record outside it is a refusal, not a "
                "preference for one of the two durable keys"
            ),
            "guard": (
                "a capsule the inbox never admitted, a keyed record outside "
                "its tick's window or whose tick never started handling, an "
                "unkeyed record in no window or in more than one, two "
                "decisions on one tick, a tick whose snapshot the marketfeed "
                "store does not hold, one instrument, exactly one preimage row "
                "per snapshot — each is a refusal"
            ),
            "cross_check": (
                "admitted ticks vs decisions is REPORTED, not refused: a tick "
                "queued and never run (a held runtime) leaves a real, keyed "
                "answer for every decision that did run"
            ),
            "rule_id": (
                "always null: B1b resolves it from the emitted outcome's "
                "rationale, which the durable evidence record does not carry"
            ),
            "as_of_ms": (
                "the snapshot's write stamp, NOT B1a's bar label — the two are "
                "different quantities and B3 does not compare them"
            ),
        },
        "output": {
            "live_jsonl_sha256": hashlib.sha256(payload).hexdigest(),
            "live_jsonl_lines": len(records),
        },
        "session_scope": {
            "session_day": scope.session_day,
            "days_present": list(scope.days_present),
            "live_jsonl_lines_all_days": scope.records_all_days,
            "admitted_decision_ticks_all_days": scope.ticks_all_days,
            "admitted_decision_ticks_with_no_resolvable_day": (
                scope.ticks_with_no_resolvable_day
            ),
        },
        "counts": {
            "outcome_kinds": dict(sorted(kinds.items())),
            "attributed_by": dict(sorted(attribution.items())),
            "admitted_decision_ticks": ticks,
            "ticks_without_a_decision": ticks - len(records),
        },
    }


def render_jsonl(records: Sequence[Mapping[str, Any]]) -> bytes:
    """One canonical JSON object per line — stable bytes for a digest."""
    return "".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        for record in records
    ).encode("utf-8")


def render_json(document: Mapping[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools/tos_cp3/session_inputs.py",
        description=(
            "CP-3 §3.6 — extract B3's two session-derived inputs from a tenant "
            "session's durable stores (read-only, no tos import)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    consumed = sub.add_parser(
        "consumed-ids",
        help="the raw_event_id set the runtime consumed, plus the unpaired reasons",
    )
    consumed.add_argument("--data-dir", type=Path, required=True)
    consumed.add_argument(
        "--producer-log",
        type=Path,
        default=None,
        help=(
            "the producer's own producer-log.jsonl; without it the document "
            "carries no unpaired reasons at all rather than guessed ones"
        ),
    )
    consumed.add_argument(
        "--boot-snapshot",
        type=Path,
        required=True,
        help=(
            "the runner's boot-journal-snapshot.json. REQUIRED: without it a "
            "pre-boot line cannot be told from one the runtime failed to "
            "consume, and both of M5's counts exclude pre-boot lines — so an "
            "omitted flag would silently move every pre-boot line into the "
            "numbers the criterion is read off"
        ),
    )
    consumed.add_argument("--out", type=Path, required=True)

    live = sub.add_parser(
        "live-decisions",
        help="one record per live decision, shaped like B1b's offline trace",
    )
    live.add_argument("--data-dir", type=Path, required=True)
    live.add_argument(
        "--boot-snapshot",
        type=Path,
        required=True,
        help=(
            "the runner's boot-journal-snapshot.json. REQUIRED for the same "
            "reason consumed-ids requires it: the durable leaf accumulates "
            "sessions, and a store-wide live.jsonl makes B3 refuse ('live "
            "decision(s) name bars that are not compared') because the offline "
            "three cover one session's frozen frame. See LiveScope"
        ),
    )
    live.add_argument(
        "--out",
        type=Path,
        required=True,
        help="a directory; live.jsonl and lineage.json are written into it",
    )
    return parser


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def main(argv: list[str] | None = None) -> int:
    """CLI. Exit codes: ``0`` ok, ``2`` refusal."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "consumed-ids":
            document = build_consumed_ids_document(
                data_dir=args.data_dir,
                producer_log=args.producer_log,
                boot_snapshot=args.boot_snapshot,
            )
            _write(args.out, render_json(document))
            print(
                f"consumed-ids: {document['counts']['consumed_raw_event_ids']} id(s), "
                f"{document['counts']['unpaired']} unpaired -> {args.out}"
            )
            return 0
        records, ticks, scope = scope_live_decisions(
            live_decision_records(args.data_dir),
            ticks=read_decision_ticks(args.data_dir),
            snapshots=read_snapshots(args.data_dir),
            pre_boot=read_boot_snapshot(args.boot_snapshot),
        )
        payload = render_jsonl(records)
        lineage = build_live_lineage(
            data_dir=args.data_dir,
            records=records,
            payload=payload,
            ticks=ticks,
            scope=scope,
        )
        _write(args.out / "live.jsonl", payload)
        _write(args.out / "lineage.json", render_json(lineage))
        print(
            f"live-decisions: {len(records)} record(s) of {scope.records_all_days} "
            f"in the leaf, session day {scope.session_day} "
            f"({lineage['counts']['attributed_by']}) -> {args.out}"
        )
        return 0
    except SessionInputsError as exc:
        print(f"session_inputs: REFUSED — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI tests
    raise SystemExit(main())
