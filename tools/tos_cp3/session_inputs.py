#!/usr/bin/env python3
"""CP-3 §3.6 — the two session-derived inputs B3 did not have.

Plan ``docs/plans/2026-10-10-tos-cp3-live-field-producer-plan.md`` §3.6, PR-3
row. Before this module B3 (:mod:`tools.tos_cp3.diff_decisions`) read three
offline artifacts — B1a's fields, B2's legacy outcomes, B1b's offline trace —
and therefore answered only "did the offline replay agree with the legacy
rule". It could not see the live session at all: not which bars the runtime
actually consumed, and not what the runtime decided on them. This module reads
the session's own durable stores and produces those two inputs:

``consumed-ids``
    The ``raw_event_id`` set the runtime really consumed, from the session
    ``marketfeed.sqlite3``'s ``preimages(snapshot_id, raw_event_id)`` table —
    one row per observation each issued snapshot covers. Given the producer's
    own log (and the runner's boot snapshot), it also says, for every bar the
    offline stream has and the runtime did NOT consume, WHY: the plan's
    pre-boot / ``skipped_behind`` / ``produce_error`` / ``omitted_unusable``
    reasons, each from the producer's own label rather than from a guess here.

``live-decisions``
    One record per live decision, shaped like B1b's offline trace line, from
    the session ``evidence.sqlite3``'s ``entries`` table — tied to its bar
    through the session ``inbox.sqlite3`` (below).

**Read-only, and no ``tos`` import.** The firewall is bidirectional —
``tools/`` is in its reverse scan (``tools/tos_firewall_check.py`` TOS-FW-R) —
so all three stores are opened as plain sqlite files in ``mode=ro``, and the
runtime literals this needs (three file names, three schema versions, the
field paths inside two stored payloads) are MIRRORED here with the constant
each mirrors named beside it. A mirrored literal that drifts is caught rather
than assumed: every read pins ``PRAGMA user_version`` against the mirrored
version, and the committed hinge
``tos/runtime/tests/fixtures/cp3-session-store-reads.json`` carries the exact
``payload_json`` bytes the REAL stores write — produced and checked on the
runtime side, replayed as input on this one.

**How a live decision is tied to its bar.** By KEY, through three durable
rows:

1. the decision record names the capsule it consumed (``capsule_id``, copied
   off the recorded input signature in ``tos/src/tos/engine/pipeline.py``);
2. the inbox event that carried that tick names the same capsule and the
   snapshot it bound (``decision_tick.capsule.capsule_id`` and
   ``…capsule.critical_input_snapshot.snapshot_id``) — the driver admits every
   event durably before processing it
   (``tos_runtime.engine.driver.EngineDriver.enqueue_and_run``);
3. ``preimages`` maps that snapshot to the bar's ``raw_event_id``.

A ``DECISION_WITHHELD`` or ``COORDINATOR_PRECONDITION_REFUSED`` record names
no capsule — the pipeline never reached a signature — so those, and only
those, take the next tick no keyed decision claimed. Every record says which
of the two it was in its ``attributed_by`` field.

The first cut paired by POSITION (the k-th decision with the k-th snapshot)
because the evidence record carries no bar id. That is an inference the stores
can contradict silently: one tick queued and drained later shifts every later
record onto the wrong bar with the counts still matching. The key cannot
shift, so the count comparison is now a REPORTED cross-check rather than the
thing the attribution rests on.

**What is still refused, not guessed**: a capsule the inbox never admitted,
two decisions on one tick, an unkeyed decision with no tick left, a tick whose
snapshot the marketfeed store does not hold, two instruments in one session,
and a snapshot without exactly one preimage row.

Usage::

    .venv/bin/python tools/tos_cp3/session_inputs.py consumed-ids \\
        --data-dir   /path/session/data/A05611 \\
        --producer-log /path/session/producer-log.jsonl \\
        --boot-snapshot /path/session/boot-journal-snapshot.json \\
        --out        /path/session/b3-inputs/consumed-ids.json

    .venv/bin/python tools/tos_cp3/session_inputs.py live-decisions \\
        --data-dir /path/session/data/A05611 \\
        --out      /path/session/b3-inputs/live

``live-decisions`` writes a directory holding ``live.jsonl`` and the
``lineage.json`` sidecar B3 auto-discovers beside an artifact, the same layout
B1a, B2 and B1b use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Repo root of the checkout this file belongs to, at the FRONT of
#: ``sys.path`` for the same reason B1a/B2/B3 do it: an editable install of
#: another checkout must not shadow this worktree's ``tools/``.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tos_cp3 import TOS_CP3_VERSION  # noqa: E402

#: Stable identity stamped on every document this module writes.
SOURCE_ID = f"tos-cp3-session-inputs/{TOS_CP3_VERSION}"

#: Document schema version — bumped when a produced document changes shape, so
#: a consumer reads "shaped differently" rather than "values differ".
SCHEMA_VERSION = 1

#: Mirrors ``tos_runtime.marketfeed.store.MARKETFEED_FILE_NAME`` and
#: ``tos_runtime.operations.backup_set.EVIDENCE_FILE_NAME``. Mirrored, not
#: imported: the firewall forbids importing either from here.
MARKETFEED_FILE_NAME = "marketfeed.sqlite3"
EVIDENCE_FILE_NAME = "evidence.sqlite3"
#: Mirrors ``tos_runtime.operations.backup_set.INBOX_FILE_NAME``. The durable
#: event queue is what carries the KEYED link from a decision to its bar
#: (:func:`read_decision_ticks`).
INBOX_FILE_NAME = "inbox.sqlite3"

#: Mirrors ``tos_runtime.marketfeed.store.MARKETFEED_SCHEMA_VERSION``,
#: ``tos_runtime.evidence.store.EVIDENCE_SCHEMA_VERSION`` and
#: ``tos_runtime.engine.inbox.INBOX_SCHEMA_VERSION`` — each store stamps its
#: own value into ``PRAGMA user_version``. Pinned rather than read-and-
#: accepted: a bumped version means the tables changed shape, and reading a new
#: shape with these queries would answer a question about a store that no
#: longer exists (the migration note is runbook ``tos-paper-boot.md`` §4-A).
PINNED_MARKETFEED_SCHEMA_VERSION = 1
PINNED_EVIDENCE_SCHEMA_VERSION = 2
PINNED_INBOX_SCHEMA_VERSION = 1

#: The ``kind`` the inbox stores for a market tick
#: (``tos.engine.EventKind.DECISION_TICK``).
DECISION_TICK_EVENT_KIND = "DECISION_TICK"

#: Where the capsule id and the snapshot id live inside one inbox event's
#: ``payload_json`` (``EngineEvent.model_dump(mode="json")``:
#: ``decision_tick`` is the ``DecisionTickPayload``, whose ``capsule`` is the
#: issued ``DecisionContextCapsule`` and whose ``critical_input_snapshot`` is
#: the ``SnapshotRef`` the capsule binds).
TICK_CAPSULE_PATH: tuple[str, ...] = ("decision_tick", "capsule", "capsule_id")
TICK_SNAPSHOT_PATH: tuple[str, ...] = (
    "decision_tick",
    "capsule",
    "critical_input_snapshot",
    "snapshot_id",
)

#: The resolved Critical Input value surface for that tick
#: (``DecisionTickPayload.value_view``). ``null`` means the resolver published
#: no view at all; a view with ``values: []`` is the defined "the binding
#: resolved and nothing was admissible" outcome
#: (``tos.dsl.context_value.ContextValueView``'s own ∅-both-ways note), which
#: at this tenant's ``max_age_ms`` of 800 is what a STALE line looks like from
#: the durable side (plan §5 M5; runbook §7.2-c's structural argument).
TICK_VALUE_VIEW_PATH: tuple[str, ...] = ("decision_tick", "value_view")

#: The evidence store wraps every record: ``payload_json`` is
#: ``{"payload": <the scrubbed record>, "masked_keys": [...]}``
#: (``tos_runtime.evidence.store.SqliteEvidenceStore._append_with_scheme``), so
#: the record's own fields are one level down. Reading the outer object instead
#: finds ``outcome_type``/``capsule_id`` absent and silently turns every
#: emitted no-action into an unmappable outcome — the first cut did exactly
#: that, and its tests missed it because they wrote flat rows (Claude lane
#: BLOCKER B1, 2026-10-14). The committed fixture in
#: ``tos/runtime/tests/fixtures/cp3-session-store-reads.json`` now carries
#: bytes the REAL store wrote, and both sides check against them.
EVIDENCE_PAYLOAD_KEY = "payload"

#: The engine evidence kinds that TERMINATE one decision pass — exactly one of
#: these is recorded per ``DECISION_TICK`` (``tos.engine.vocabulary
#: .EvidenceKind``; ``pipeline.py`` records ``DECISION_OUTCOME_EMITTED`` or
#: ``DECISION_WITHHELD``, ``core.py`` the withheld pre-dispatch case, and the
#: Coordinator gate its own refusal). They delimit the per-tick blocks.
DECISION_KINDS: tuple[str, ...] = (
    "DECISION_OUTCOME_EMITTED",
    "DECISION_WITHHELD",
    "DECISION_DEGRADED",
    "COORDINATOR_PRECONDITION_REFUSED",
)

#: The commitment-flow kinds that may follow a decision inside the same tick
#: block. Anything else in ``entries`` (boot records, backup observations, key
#: rotations, non-trade dispositions) is not part of a decision and is ignored
#: by name rather than by position.
FLOW_KINDS: tuple[str, ...] = (
    "FLOW_STEP_ADMITTED",
    "FLOW_HALTED",
    "ATTEMPT_REQUEST_CREATED",
    "SEND_HANDED_OFF",
    "EGRESS_RESULT_CONSUMED",
    "RESULT_UNMATCHED",
)

#: ``tos.engine.vocabulary.HaltReason.AT_MOST_ONE_EXPOSURE_HELD`` — the one
#: flow halt B1b calls ``capacity_denied`` (``tos/runtime/cp3/replay.py``'s own
#: ``denied = flow_halt is HaltReason.AT_MOST_ONE_EXPOSURE_HELD``).
CAPACITY_DENIAL_HALT_REASON = "AT_MOST_ONE_EXPOSURE_HELD"

#: ``outcome_type`` (the emitted outcome's class name) -> the token this side
#: reports. ``NoActionOutcome`` is exactly B1b's ``NO_ACTION``; every other
#: emitted outcome is a Proposal, and whether that is B1b's ACTION or its FLAT
#: turns on the proposal's ``position_effect``, which NO durable record carries
#: — measured, not assumed: ``position_effect`` does not occur anywhere in
#: ``tos/src/tos/engine/*.py``, so neither the decision record nor any
#: commitment-flow record stores it.
#:
#: So the live side says :data:`PROPOSAL_KIND` — "an outcome was emitted and it
#: was not a no-action" — instead of refusing the whole document over one bar
#: (Claude lane MEDIUM M3) or guessing which of the two it was. B3 treats it as
#: a KIND-ONLY match against an offline ACTION or FLAT and counts those bars
#: separately, so the half that is known is used and the half that is not is
#: visible.
OUTCOME_TYPE_TO_KIND: Mapping[str, str] = {"NoActionOutcome": "NO_ACTION"}

#: An emitted Proposal whose ACTION/FLAT half the durable record cannot say.
PROPOSAL_KIND = "PROPOSAL"

#: A tick that ended without an emitted outcome is not one of B1b's three
#: decision kinds, and B1b itself refuses to call it a fourth
#: (``replay.py::_attribute_rule``'s ``NO_OUTCOME``). The live side records the
#: same token so the two sides disagree visibly rather than silently.
NO_OUTCOME_KIND = "NO_OUTCOME"

#: Producer log stages that DISPOSE of a bar, newest-wins, with ``published``
#: overriding everything: a bar can miss its own boundary
#: (``missing_no_successor``) and complete later (``late_completed``), so the
#: last dispositive stage is the one that describes how the session left it.
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

#: The reason recorded for a bar the producer DID publish, the runtime did not
#: consume, and the runner's boot snapshot shows was already in the journal
#: when the runtime booted. Plan §5 M5: those lines are structurally
#: unconsumable (the scheduler takes only the newest observation of a poll), so
#: they are excluded from the two M5 counts and recorded under their own name.
REASON_PRE_BOOT = "pre_boot"

#: A line the producer published AFTER boot that the runtime never consumed.
#: This is the M5 defect shape and gets its own name — never folded into a
#: benign reason, which is the whole point of counting by reason.
REASON_UNCONSUMED_AFTER_BOOT = "published_not_consumed"

#: An offline bar with no producer-log disposition at all. Not refused: a B3
#: run whose producer log is missing or truncated still has something to say,
#: and a silent drop is what the reason counts exist to prevent.
REASON_UNEXPLAINED = "unexplained"


class SessionInputsError(RuntimeError):
    """A refusal. Nothing is written when one is raised."""


# ---------------------------------------------------------------------------
# sqlite, read-only
# ---------------------------------------------------------------------------


def _connect_ro(path: Path, *, label: str, pinned_version: int) -> sqlite3.Connection:
    """Open *path* read-only and refuse a store shape this was not written for."""
    if not path.is_file():
        raise SessionInputsError(
            f"{label} store not found: {path}. A session that never ticked "
            "writes no marketfeed store at all (runbook tos-paper-boot.md §4), "
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


# ---------------------------------------------------------------------------
# The marketfeed side: snapshots and the ids they covered
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Snapshot:
    """One issued snapshot and the single observation it covered."""

    snapshot_id: str
    instrument: str
    as_of_ms: int
    raw_event_id: str


def read_snapshots(data_dir: Path) -> tuple[Snapshot, ...]:
    """Every issued snapshot of the session, in issue order, with its id.

    Issue order is ``rowid`` order: ``snapshots`` has a TEXT primary key, so
    sqlite keeps its own rowid and that is insertion order. Ordering by
    ``as_of_ms`` instead would reorder two snapshots that share a stamp, and
    the ordered pairing below depends on this being the order the scheduler
    wrote them in.

    Raises:
        SessionInputsError: A snapshot covers no preimage row, or more than
            one. Both break the pairing: the first is the restore-path failure
            the store's own docstring describes (a snapshot id in hand, every
            value UNKNOWN), the second means a snapshot covered several
            observations and "the bar this decision was about" is not a
            question with one answer.
    """
    conn = _connect_ro(
        data_dir / MARKETFEED_FILE_NAME,
        label="marketfeed",
        pinned_version=PINNED_MARKETFEED_SCHEMA_VERSION,
    )
    try:
        rows = list(
            conn.execute(
                "SELECT snapshot_id, instrument, as_of_ms FROM snapshots ORDER BY rowid"
            )
        )
        preimages: dict[str, list[str]] = {}
        for snapshot_id, raw_event_id in conn.execute(
            "SELECT snapshot_id, raw_event_id FROM preimages"
        ):
            preimages.setdefault(str(snapshot_id), []).append(str(raw_event_id))
    finally:
        conn.close()

    snapshots: list[Snapshot] = []
    for snapshot_id, instrument, as_of_ms in rows:
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
        snapshots.append(
            Snapshot(
                snapshot_id=str(snapshot_id),
                instrument=str(instrument),
                as_of_ms=int(as_of_ms),
                raw_event_id=covered[0],
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


# ---------------------------------------------------------------------------
# The producer side: why a bar was never consumed
# ---------------------------------------------------------------------------


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


def producer_dispositions(producer_log: Path) -> dict[str, str]:
    """``raw_event_id -> the stage that disposed of that bar``.

    ``published`` wins over everything; otherwise the LAST dispositive stage
    wins, because a bar can miss its own boundary and complete afterwards. Only
    events carrying a ``raw_event_id`` are read — the producer stamps one on
    every per-bar event with B1a's own deriver, so nothing here reconstructs a
    join key (plan §3.6).
    """
    disposed: dict[str, str] = {}
    for payload in _iter_json_lines(producer_log, label="producer log"):
        stage = payload.get("stage")
        raw_event_id = payload.get("raw_event_id")
        if not isinstance(raw_event_id, str) or stage not in (
            PRODUCER_DISPOSITION_STAGES
        ):
            continue
        if disposed.get(raw_event_id) == "published":
            continue
        disposed[raw_event_id] = str(stage)
    return disposed


def read_boot_snapshot(path: Path) -> frozenset[str]:
    """The ids already in the journal when the runtime booted (runner step 9b).

    Raises:
        SessionInputsError: The file does not carry the runner's own
            ``pre_boot_raw_event_ids`` list. An empty list is a legitimate
            value only if the runner wrote one; a MISSING key is a different
            file, and reading it as "no pre-boot lines" would move every
            pre-boot line into :data:`REASON_UNCONSUMED_AFTER_BOOT` — turning
            the structurally-expected case into the defect shape.
    """
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


def unpaired_reasons(
    *,
    consumed: frozenset[str],
    dispositions: Mapping[str, str],
    pre_boot: frozenset[str],
) -> dict[str, str]:
    """Why each produced-but-unconsumed bar has no live counterpart."""
    reasons: dict[str, str] = {}
    for raw_event_id, stage in dispositions.items():
        if raw_event_id in consumed:
            continue
        if stage == "published":
            reasons[raw_event_id] = (
                REASON_PRE_BOOT
                if raw_event_id in pre_boot
                else REASON_UNCONSUMED_AFTER_BOOT
            )
        else:
            reasons[raw_event_id] = stage
    return reasons


def consumed_value_view_counts(
    *, data_dir: Path, by_snapshot: Mapping[str, str]
) -> dict[str, Any]:
    """M5's first count: how the runtime's values stood when it consumed a line.

    Plan §5 M5 asks for "lines consumed STALE". The durable side can answer it,
    and this is exactly how far it can: every admitted tick carries the
    resolver's ``value_view``, and that view is either absent (no view
    published), explicitly empty (resolved, nothing admissible) or populated.
    At this tenant's ``max_age_ms`` of 800 an empty view is what a stale line
    produces — the runbook §7.2-c argument — but the view records "nothing was
    admissible", not "stale", so the key is named for what the store says and
    the note carries the inference.

    The ids with admitted values are listed rather than the ones without: at
    genesis the second list is expected to be every line, and a list of
    everything is not a finding.
    """
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
            "value_view. empty_view = 'the binding resolved and nothing was "
            "admissible', which at max_age_ms 800 is the STALE shape (runbook "
            "§7.2-c); no_view = the resolver published none at all. Neither "
            "key claims the word 'stale' — the store does not record it — so "
            "M5's first count is empty_view + no_view with that reading stated"
        ),
    }


def build_consumed_ids_document(
    *,
    data_dir: Path,
    producer_log: Path | None = None,
    boot_snapshot: Path | None = None,
) -> dict[str, Any]:
    """The ``consumed-ids`` document: the id filter plus the reason map."""
    snapshots = read_snapshots(data_dir)
    if not snapshots:
        raise SessionInputsError(
            f"{data_dir / MARKETFEED_FILE_NAME} holds no snapshots — the runtime "
            "consumed nothing, so an id filter built from it would silently "
            "empty every comparison"
        )
    instrument = _assert_one_instrument(snapshots)
    consumed = frozenset(snapshot.raw_event_id for snapshot in snapshots)
    dispositions = (
        producer_dispositions(producer_log) if producer_log is not None else {}
    )
    pre_boot = (
        read_boot_snapshot(boot_snapshot)
        if boot_snapshot is not None
        else (frozenset())
    )
    reasons = unpaired_reasons(
        consumed=consumed, dispositions=dispositions, pre_boot=pre_boot
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
        },
        "counts": {
            "snapshots": len(snapshots),
            "consumed_raw_event_ids": len(consumed),
            "producer_disposed_bars": len(dispositions),
            "unpaired": len(reasons),
            "pre_boot_lines_at_boot": len(pre_boot),
        },
        "raw_event_ids": sorted(consumed),
        "unpaired_reasons": dict(sorted(reasons.items())),
        "unpaired_reason_counts": dict(sorted(reason_counts.items())),
        "consumed_value_view": consumed_value_view_counts(
            data_dir=data_dir,
            by_snapshot={
                snapshot.snapshot_id: snapshot.raw_event_id for snapshot in snapshots
            },
        ),
    }


# ---------------------------------------------------------------------------
# The evidence side: what the live runtime decided
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionBlock:
    """One tick's engine records: the decision, then its commitment flow."""

    seq: int
    kind: str
    payload: dict[str, Any]
    flow: tuple[tuple[str, dict[str, Any]], ...]

    @property
    def capsule_id(self) -> str | None:
        """The capsule this decision consumed, when the record names one.

        ``DECISION_OUTCOME_EMITTED`` carries it (``pipeline.py`` copies it off
        the recorded input signature); ``DECISION_WITHHELD`` and the
        Coordinator's refusal do not — the pipeline never reached a signature.
        That is why the attribution below is keyed where a key exists and
        positional only where one cannot exist.
        """
        value = self.payload.get("capsule_id")
        return None if value is None else str(value)


def _evidence_record(payload_json: str, *, seq: int, kind: str) -> dict[str, Any]:
    """The engine record inside one ``entries.payload_json``.

    The store wraps it: ``{"payload": …, "masked_keys": […]}``
    (:data:`EVIDENCE_PAYLOAD_KEY`). Reading the wrapper as if it were the
    record finds every field absent and says so nowhere — the BLOCKER this
    refusal replaces. An entry without the wrapper is a store this extractor
    was not written for, and that is a refusal, not a fallback.
    """
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
    """Group the session's engine records into one block per decision pass.

    A block opens at a :data:`DECISION_KINDS` record and runs to the next one;
    the :data:`FLOW_KINDS` records between them are that decision's commitment
    flow, which is the order the engine writes them in (the proposal is
    recorded before the flow it starts).

    Raises:
        SessionInputsError: A flow record appears before any decision record.
            Nothing it could belong to has been seen, so attributing it to the
            NEXT decision would attach one tick's send to another tick's bar.
    """
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
    """The token for one live decision block.

    ``NO_OUTCOME`` for a pass that emitted nothing, ``NO_ACTION`` for an
    emitted no-action, and :data:`PROPOSAL_KIND` for any other emitted outcome
    — the durable record says an outcome was emitted and cannot say whether it
    was B1b's ACTION or its FLAT, so this names exactly that much. Refusing
    instead (the first cut) threw away the whole document over one bar; naming
    ACTION or FLAT would be this module deciding what the engine decided.
    """
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


def _flow_halt_reason(block: DecisionBlock) -> str | None:
    for kind, payload in block.flow:
        if kind == "FLOW_HALTED":
            reason = payload.get("halt_reason")
            return None if reason is None else str(reason)
    return None


@dataclass(frozen=True)
class DecisionTick:
    """One admitted ``DECISION_TICK`` event: the KEY from a decision to a bar."""

    seq: int
    capsule_id: str
    snapshot_id: str
    #: How many Critical Input values the resolver ADMITTED for this tick, or
    #: ``None`` when it published no view at all (plan §5 M5 — see
    #: :func:`consumed_value_view_counts`).
    admitted_values: int | None


def _dig(payload: Mapping[str, Any], path: Sequence[str]) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            return None
        value = value[key]
    return value


def read_decision_ticks(data_dir: Path) -> tuple[DecisionTick, ...]:
    """Every admitted market tick, in admission order, with its two ids.

    This is the link the evidence store does not carry. The scheduler issues a
    snapshot, binds it into a capsule and hands the engine ONE
    ``DECISION_TICK`` event (``marketfeed/scheduler.py::tick_once``); the
    driver admits that event durably before processing it
    (``engine/driver.py::enqueue_and_run`` -> ``SqliteEventInbox.enqueue``),
    and the stored ``payload_json`` is the whole event — capsule id and
    ``SnapshotRef`` included. So ``decision.capsule_id -> tick.snapshot_id ->
    preimages.raw_event_id`` is a keyed join over durable rows, and the
    ordered pairing the first cut used is needed only where no key can exist.

    Raises:
        SessionInputsError: A tick event carries no capsule or snapshot id, or
            two ticks share one capsule id. Both make the key useless, and a
            key that is sometimes ambiguous is not a key.
    """
    conn = _connect_ro(
        data_dir / INBOX_FILE_NAME,
        label="inbox",
        pinned_version=PINNED_INBOX_SCHEMA_VERSION,
    )
    try:
        rows = list(
            conn.execute(
                "SELECT seq, payload_json FROM events WHERE kind = ? ORDER BY seq",
                (DECISION_TICK_EVENT_KIND,),
            )
        )
    finally:
        conn.close()

    ticks: list[DecisionTick] = []
    seen: dict[str, int] = {}
    for seq, payload_json in rows:
        payload = json.loads(payload_json)
        capsule_id = _dig(payload, TICK_CAPSULE_PATH)
        snapshot_id = _dig(payload, TICK_SNAPSHOT_PATH)
        if not isinstance(capsule_id, str) or not isinstance(snapshot_id, str):
            raise SessionInputsError(
                f"inbox seq {seq}: a {DECISION_TICK_EVENT_KIND} event with no "
                f"{'.'.join(TICK_CAPSULE_PATH)} / {'.'.join(TICK_SNAPSHOT_PATH)}. "
                "Those two are what tie a decision to its bar; without them "
                "this extractor would be back to guessing by position"
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
            )
        )
    return tuple(ticks)


def _attribute(
    blocks: Sequence[DecisionBlock], ticks: Sequence[DecisionTick]
) -> list[tuple[DecisionBlock, DecisionTick, str]]:
    """Pair each decision with the tick it was about: by key, else by position.

    ``DECISION_OUTCOME_EMITTED`` names its capsule, so that pairing is a
    lookup and survives a shifted sequence. ``DECISION_WITHHELD`` and the
    Coordinator's refusal name none — the pipeline never reached a signature —
    so those take the next tick no keyed decision has claimed, and the
    strictly-increasing check below is what stops a silent shift from moving
    them onto someone else's bar.

    Raises:
        SessionInputsError: a decision names a capsule the inbox never
            admitted; two decisions land on one tick; or an unkeyed decision
            has no tick left to take.
    """
    by_capsule = {tick.capsule_id: (index, tick) for index, tick in enumerate(ticks)}
    assigned: dict[int, tuple[int, str]] = {}  # block position -> (tick index, how)
    used: dict[int, int] = {}  # tick index -> evidence seq

    # Pass 1 — every decision that names a capsule, by key. Keyed first and in
    # their own pass, so an unkeyed record earlier in the file cannot take a
    # tick that a later keyed record names: the fallback must only ever see
    # ticks no key claims.
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
        if index in used:
            raise SessionInputsError(
                f"evidence seq {block.seq} and seq {used[index]} both attribute "
                f"to inbox seq {tick.seq} — one tick, two decisions"
            )
        used[index] = block.seq
        assigned[position] = (index, "capsule_id")

    # Pass 2 — the rest, in file order, onto the ticks left over in theirs.
    spare = iter(index for index in range(len(ticks)) if index not in used)
    for position, block in enumerate(blocks):
        if position in assigned:
            continue
        index = next(spare, -1)
        if index < 0:
            raise SessionInputsError(
                f"evidence seq {block.seq}: a {block.kind} record carries no "
                "capsule id and every admitted tick already has a decision. "
                "There is no bar left for it, and attributing it to one "
                "anyway would be inventing the attribution this join exists "
                "to avoid"
            )
        used[index] = block.seq
        assigned[position] = (index, "position")

    return [
        (block, ticks[assigned[position][0]], assigned[position][1])
        for position, block in enumerate(blocks)
    ]


def live_decision_records(data_dir: Path) -> list[dict[str, Any]]:
    """One record per live decision, in B1b's trace shape.

    The keys B3 reads from a trace line — ``raw_event_id``, ``as_of_ms``,
    ``outcome_kind``, ``rule_id``, ``capacity_denied`` — are all present, and
    each record also says HOW it was attributed (``attributed_by``), because
    "by key" and "by position" are not the same claim.

    ``rule_id`` is always ``null`` and says so in the sidecar: B1b resolves it
    from the emitted outcome's ``rationale`` through the authored policy's rule
    index, and the rationale is on the in-memory outcome, not in the durable
    record. B3's live comparison therefore compares the decision KIND and the
    capacity denial, never the rule id.

    ``as_of_ms`` is the snapshot's — the WRITE stamp the producer put on the
    journal line — and is deliberately not comparable to B1a's label-derived
    ``as_of_ms``; B3 does not compare them.
    """
    snapshots = read_snapshots(data_dir)
    _assert_one_instrument(snapshots)
    by_snapshot = {snapshot.snapshot_id: snapshot for snapshot in snapshots}
    ticks = read_decision_ticks(data_dir)
    blocks = read_decision_blocks(data_dir)
    records: list[dict[str, Any]] = []
    for index, (block, tick, how) in enumerate(_attribute(blocks, ticks)):
        snapshot = by_snapshot.get(tick.snapshot_id)
        if snapshot is None:
            raise SessionInputsError(
                f"inbox seq {tick.seq} names snapshot {tick.snapshot_id!r}, which "
                "the marketfeed store does not hold. The tick was admitted and "
                "its snapshot is gone, so the bar it was about is not knowable"
            )
        flow_halt = _flow_halt_reason(block)
        records.append(
            {
                "raw_event_id": snapshot.raw_event_id,
                "as_of_ms": snapshot.as_of_ms,
                "bar_index": index,
                "outcome_kind": _live_outcome_kind(block),
                "rule_id": None,
                "pipeline_halt_reason": block.payload.get("halt_reason"),
                "flow_halt_reason": flow_halt,
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
            "method": "capsule_id_keyed_with_positional_fallback",
            "key": (
                "decision.capsule_id -> inbox DECISION_TICK "
                "decision_tick.capsule.capsule_id -> "
                "critical_input_snapshot.snapshot_id -> preimages.raw_event_id"
            ),
            "fallback": (
                "a DECISION_WITHHELD or COORDINATOR_PRECONDITION_REFUSED record "
                "names no capsule (the pipeline never reached a signature), so "
                "it takes the next tick no keyed decision claimed; the "
                "attributed_by field on every record says which of the two it "
                "was"
            ),
            "guard": (
                "a capsule the inbox never admitted, two decisions on one tick, "
                "an unkeyed decision with no tick left, a tick whose snapshot "
                "the marketfeed store does not hold, one instrument, exactly "
                "one preimage row per snapshot — each is a refusal"
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
        "counts": {
            "outcome_kinds": dict(sorted(kinds.items())),
            "attributed_by": dict(sorted(attribution.items())),
            "admitted_decision_ticks": ticks,
            "ticks_without_a_decision": ticks - len(records),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


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
        default=None,
        help=(
            "the runner's boot-journal-snapshot.json; without it a pre-boot "
            "line cannot be told from one the runtime failed to consume"
        ),
    )
    consumed.add_argument("--out", type=Path, required=True)

    live = sub.add_parser(
        "live-decisions",
        help="one record per live decision, shaped like B1b's offline trace",
    )
    live.add_argument("--data-dir", type=Path, required=True)
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
        records = live_decision_records(args.data_dir)
        payload = render_jsonl(records)
        lineage = build_live_lineage(
            data_dir=args.data_dir,
            records=records,
            payload=payload,
            ticks=len(read_decision_ticks(args.data_dir)),
        )
        _write(args.out / "live.jsonl", payload)
        _write(args.out / "lineage.json", render_json(lineage))
        print(
            f"live-decisions: {len(records)} record(s) "
            f"({lineage['counts']['attributed_by']}) -> {args.out}"
        )
        return 0
    except SessionInputsError as exc:
        print(f"session_inputs: REFUSED — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI tests
    raise SystemExit(main())
