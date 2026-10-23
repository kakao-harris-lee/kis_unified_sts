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
    own log (and the runner's boot snapshot, which is REQUIRED), it also says,
    for every bar the offline stream has and the runtime did NOT consume,
    WHY: the plan's pre-boot / ``skipped_behind`` / ``produce_error`` /
    ``omitted_unusable`` reasons, each from the producer's own label rather
    than from a guess here. It also carries plan §5 M5's first number, read
    from each consumed snapshot's own field evaluations against its preimage
    (:func:`consumed_field_states`) — NOT from a count of the persisted word
    ``STALE``, which today's issuer never writes.

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
no capsule — the pipeline never reached a signature — so those are tied by the
OTHER durable key the driver writes: the bracket of receipts around each
event. ``EngineDriver._process_next`` appends ``EVENT_HANDLING_STARTED``,
stamps its ``seq`` onto the inbox row, runs the handler (which writes this
tick's decision records), appends ``EVENT_CONSUMED`` and stamps that ``seq``
too; the loop is single-threaded and refuses re-entry. So a capsule-less
record belongs to the unique tick whose ``(handling_started, consumed]``
window contains its evidence ``seq`` — and a keyed record is cross-checked
against that same window. Every record says which key attributed it in its
``attributed_by`` field (``capsule_id`` / ``evidence_seq_range``).

The first two cuts paired capsule-less records by POSITION (the k-th decision
with the k-th unclaimed tick). That is an inference the stores can contradict
silently: one tick queued and never run shifts every later unkeyed record onto
the wrong bar with the counts still matching and nothing refused (Claude lane
MEDIUM R1, 2026-10-14). Position is now used nowhere.

**What is still refused, not guessed**: a capsule the inbox never admitted, a
keyed record outside its own tick's window, a capsule-less record in no
window or in more than one, two decisions on one tick, a tick whose snapshot
the marketfeed store does not hold, two instruments in one session, and a
snapshot without exactly one preimage row.

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
import datetime as _dt
import hashlib
import json
import sqlite3
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
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
#:
#: 2 (2026-10-14, Claude lane MEDIUM R1/R2 + BLOCKER R2′): ``consumed-ids``
#: gained the ``consumed_field_states`` block that M5's first number now comes
#: from (whose own key was renamed from ``…_with_a_stale_field_evaluation`` to
#: ``…_with_a_present_value_refused_as_unknown`` within this same unreleased
#: version — the first spelling never shipped), and ``consumed-ids`` now
#: refuses without a boot snapshot; the live ``lineage.json``'s ``join``
#: renamed its positional fallback to the ``evidence_seq_range`` key
#: (``attributed_by`` values changed with it). Both
#: documents are read by B3 (:mod:`tools.tos_cp3.diff_decisions`) only through
#: keys that did not move, so a 1-shaped document still compares — the bump is
#: so a reader of an old artifact knows which shape it is.
#:
#: 3 (2026-10-15): ``consumed-ids`` gained ``generated_from
#: .producer_session_close`` and, with it, the
#: :data:`REASON_PUBLISHED_AFTER_CLOSE` reason. The key is what makes a zero
#: in that reason READABLE — without it, "no bar was published after the
#: close" and "the producer log carried no seed record, so the question was
#: never asked" are the same document.
SCHEMA_VERSION = 3

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
#: longer exists (the migration note is runbook ``tos-paper-boot-history.md`` §4-A).
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
#: (``tos.dsl.context_value.ContextValueView``'s own ∅-both-ways note).
#:
#: It is NOT the STALE count. ``tos.marketfeed.value._admit_one`` drops a
#: candidate for nine other reasons as well (``OBSERVATION_AMBIGUOUS``,
#: ``OBSERVATION_NOT_FOUND``, ``PAYLOAD_DIGEST_ABSENT``, ``AS_OF_ABSENT``,
#: ``DIGEST_MISMATCH``, ``VALUE_NOT_IN_PAYLOAD``, ``NON_DETERMINISTIC_NUMERIC``,
#: ``LINEAGE_NOT_REPRODUCIBLE``, ``WILDCARD_FIELD_KEY``), and its one
#: state-shaped reason — ``FIELD_STATE_NOT_VALID`` — folds every non-VALID
#: field state together. So an empty view says "nothing was admissible", never
#: "stale": M5's first number is read from the snapshot's own field
#: evaluations against its preimage (:func:`consumed_field_states`), and this
#: surface is reported beside it as what the RESOLVER did (Claude lane MEDIUM
#: R2 / BLOCKER R2′).
TICK_VALUE_VIEW_PATH: tuple[str, ...] = ("decision_tick", "value_view")

#: The two receipt stamps an inbox row carries, written by
#: ``tos_runtime.engine.inbox.SqliteEventInbox.mark_handling_started`` and
#: ``…mark_consumed``. The driver's loop
#: (``tos_runtime.engine.driver.EngineDriver._process_next``) appends the
#: ``EVENT_HANDLING_STARTED`` evidence entry and stamps its ``seq`` here,
#: THEN calls ``core.handle`` (which appends this tick's decision and
#: commitment-flow entries), THEN appends ``EVENT_CONSUMED`` and stamps that
#: ``seq`` here. The loop is single-threaded and refuses re-entry (its own
#: ``_draining`` guard), so one tick's decision entries are exactly the ones
#: whose evidence ``seq`` lies in ``(handling_started, consumed]`` — the
#: durable bracket :func:`_attribute` attributes by.
INBOX_HANDLING_STARTED_COLUMN = "handling_started_evidence_seq"
INBOX_CONSUMED_COLUMN = "consumed_evidence_seq"

#: Inside one ``snapshots.snapshot_json`` (``CriticalInputSnapshot
#: .model_dump_json()``): the two places a durable FieldState is written.
#: ``tos.marketfeed.value.value_field_state`` takes the WORST of the
#: observation's admission state, the observation's own ``field_state`` and
#: every ``field_evaluations`` entry naming the field — so both are read here
#: and reported apart, rather than one of them silently standing for both.
SNAPSHOT_FIELD_EVALUATIONS_KEY = "field_evaluations"
SNAPSHOT_OBSERVATIONS_KEY = "observations"
FIELD_EVALUATION_STATE_KEY = "state"
FIELD_EVALUATION_FIELD_REF_KEY = "field_ref"
OBSERVATION_FIELD_STATE_KEY = "field_state"

#: Inside one ``preimages.preimage_json`` (``RawPayloadPreimage
#: .model_dump_json()``): the tokens the snapshot's observation attested.
#: Measured on the real store's bytes (hinge ``marketfeed_snapshots``):
#: ``{"entries":[{"key":"close","value":451250}, …]}``. This is what makes
#: "the issuer HAD this value and refused it" decidable from the durable side
#: (:func:`consumed_field_states`).
PREIMAGE_ENTRIES_KEY = "entries"
PREIMAGE_ENTRY_KEY_KEY = "key"
PREIMAGE_ENTRY_VALUE_KEY = "value"

#: ``tos.capsule.field_evaluation.FieldState`` members, as the model dumps
#: them. VALID is the one state that is not a finding; UNKNOWN is the one the
#: real issuer writes for an over-age field.
#:
#: ⚠ **STALE is never written by today's issuer.**
#: ``tos_runtime.marketfeed.snapshot._derive_field_state`` returns
#: ``(FieldState.UNKNOWN, "stale")`` for ``now_ms - as_of_ms >
#: spec.max_age_ms``, and the reason string lives only on the in-memory
#: ``IssuedSnapshot.field_reports`` — the persisted ``FieldEvaluation`` carries
#: the state alone. Measured on the real issuer (hinge
#: ``marketfeed_snapshots.stale_by_age``, policy ``max_age_ms`` 5000, issued at
#: ``as_of + 5001``): persisted states ``['UNKNOWN', 'UNKNOWN']``. So a count
#: of persisted ``STALE`` reads 0 on every real session however stale it was —
#: the defect this constant's first use had (Claude lane BLOCKER R2′,
#: 2026-10-14). STALE is still reported if it ever appears, under
#: ``other_field_evaluation_states``, which is where a future issuer change
#: would show up.
STALE_FIELD_STATE = "STALE"
VALID_FIELD_STATE = "VALID"
UNKNOWN_FIELD_STATE = "UNKNOWN"

#: The three causes this side can tell apart for one UNKNOWN field evaluation,
#: from the durable bytes alone. ``_derive_field_state`` has exactly four, in
#: this order: ``absent_from_payload`` (the key is not in the preimage),
#: ``now_ms_unknown`` (no trustworthy clock), ``stale`` (over ``max_age_ms``)
#: and ``unprojectable`` (``project_scalar`` refuses the token).
#:
#: Presence separates the first; projectability separates the last; the two in
#: the middle are exactly the ones where the issuer HELD a usable value and
#: refused it, and they are the ones plan §5 M5 asks about. They are reported
#: together because no durable byte distinguishes them (the reason is not
#: persisted) — see :data:`CAUSE_PRESENT_REFUSED`'s use.
CAUSE_PRESENT_REFUSED = "present_value_refused"
CAUSE_ABSENT_FROM_PAYLOAD = "absent_from_payload"
CAUSE_UNPROJECTABLE = "unprojectable"

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

#: A line the producer published at or after the session CLOSE. Structurally
#: unconsumable, the same way :data:`REASON_PRE_BOOT` is, and for a reason at
#: the other end of the day: the runtime's scheduler answers
#: ``SKIPPED_SESSION_CLOSED`` for every pass whose session context is not open
#: (``tos_runtime.marketfeed.scheduler.decide_tick``'s FIRST clause), so a bar
#: that only exists after the close can never be ticked.
#:
#: The session's own last bar is exactly that bar, by construction and not by
#: accident: it is complete only once the minute after it has elapsed
#: (``live_producer/calendar.py::SessionWindow.end_boundary`` — "the 15:45 bar
#: covers 15:45:00-15:45:59, so 15:46:00 is the session end time has elapsed"),
#: so the producer publishes it one minute past the close, every day. Counted
#: as :data:`REASON_UNCONSUMED_AFTER_BOOT` it put a permanent 1 in the number
#: plan §5 M5 requires to be 0 (measured on the 2026-10-15 LONG genesis
#: session: ``published_not_consumed: 1``, the 15:45 bar).
#:
#: ⚠ Decided from the PUBLISH stamp against the close, never from the bar's
#: label and never from a literal 15:45: a bar published at 15:44:59 that the
#: runtime did not consume is a real miss and keeps the defect name.
REASON_PUBLISHED_AFTER_CLOSE = "published_after_session_close"

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
    #: ``(field_ref, state)`` per ``field_evaluations`` entry, in stored order
    #: (plan §5 M5 — :func:`consumed_field_states`). Empty when the snapshot
    #: carries no evaluations at all, which is itself counted rather than read
    #: as VALID. The ``field_ref`` is load-bearing: it is the key looked up in
    #: :attr:`payload_tokens` to tell WHY a field is UNKNOWN.
    field_evaluations: tuple[tuple[str, str], ...] = ()
    #: ``observations[*].field_state`` as stored. The kernel's VALID gate takes
    #: the worst of this and the matching evaluations, so a non-VALID here is
    #: a degraded line too — counted apart, never folded in.
    observation_states: tuple[str, ...] = ()
    #: The tokens this snapshot's one preimage attested, by key
    #: (``preimages.preimage_json``). Empty when the row carries none.
    payload_tokens: Mapping[str, Any] = field(default_factory=dict)

    @property
    def field_states(self) -> tuple[str, ...]:
        """Just the states, in stored order."""
        return tuple(state for _ref, state in self.field_evaluations)


def _projectable(token: Any) -> bool:
    """Would ``tos.marketfeed.value.project_scalar`` admit this token?

    MIRRORED, not imported — the firewall is bidirectional. The kernel rule is
    three admitted shapes and one refusal: ``bool``, ``int`` and ``str``
    project; a ``float`` is refused (``NON_DETERMINISTIC_NUMERIC``), including
    an integral-valued one, because the decimal → float projection rule is not
    ratified. Anything else a JSON token could be (``null``, a list, an
    object) is not a scalar the kernel would take either.

    The hinge's ``unprojectable`` snapshot carries a real float token the real
    issuer refused, so this mirror is checked against the issuer's own verdict
    rather than against this file's reading of it.

    A ``null`` token would be the one place this could disagree with the
    issuer (which reads an absent LOOKUP as "absent from payload"), and it
    cannot occur: ``PreimageEntry`` cannot carry ``None`` — the kernel's own
    ``RawPayloadPreimage.lookup`` docstring relies on exactly that to make its
    ``None`` unambiguous.
    """
    return isinstance(token, (bool, int, str))


def _snapshot_states(
    snapshot_json: str, *, snapshot_id: str
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """The durable FieldStates inside one ``snapshots.snapshot_json``.

    Returns:
        ``(field evaluations as (field_ref, state), observation
        field_states)``, each in stored order.

    Raises:
        SessionInputsError: the stored JSON is not an object, or an entry in
            either list is not an object / carries a non-string state (or, for
            a field evaluation, no string ``field_ref``). A missing state
            would otherwise be counted as "not a finding" — the quiet
            undercount M5 exists to prevent — and a missing ``field_ref``
            would make its cause undecidable while still looking answered. A
            snapshot with NO ``field_evaluations`` is not refused: that is a
            real shape (nothing was evaluated) and gets its own count.
    """
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
    """The tokens one ``preimages.preimage_json`` attested, by key.

    Raises:
        SessionInputsError: the row is not a ``RawPayloadPreimage`` dump — no
            ``entries`` list, or an entry without a string ``key``. Read
            permissively, a field would look ABSENT from the payload (its key
            not found) when the payload is simply unreadable here, and
            "absent" is the one UNKNOWN cause M5 excludes.
    """
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
    """Every issued snapshot of the session, in issue order, with its id.

    Issue order is ``rowid`` order: ``snapshots`` has a TEXT primary key, so
    sqlite keeps its own rowid and that is insertion order. Nothing is
    attributed by that order — the attribution is keyed
    (:func:`_attribute`) — but it is the order the session happened in, so
    the ``bar_index`` on each live record and the ids listed in every count
    below read in it rather than in sqlite's scan order.

    Each snapshot also carries the FieldStates it recorded
    (:func:`_snapshot_states`) AND the tokens its preimage attested
    (:func:`_preimage_tokens`) — plan §5 M5's first number is the two read
    together, because the state alone does not say why it is not VALID.

    Raises:
        SessionInputsError: A snapshot covers no preimage row, or more than
            one. Both break the join: the first is the restore-path failure
            the store's own docstring describes (a snapshot id in hand, every
            value UNKNOWN), the second means a snapshot covered several
            observations and "the bar this decision was about" is not a
            question with one answer. Or its ``snapshot_json`` /
            ``preimage_json`` is not a readable dump of what the store writes
            (:func:`_snapshot_states`, :func:`_preimage_tokens`).
    """
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


@dataclass(frozen=True)
class ProducerLogFacts:
    """What one pass over the producer's own log says about its bars.

    Three facts, read together because they come from the same file and the
    reason map needs all three:

    * ``dispositions`` — ``raw_event_id -> the stage that disposed of it``;
    * ``published_as_of_ms`` — the journal stamp the ``published`` event
      recorded, i.e. WHEN the line became visible to the runtime. Not the
      bar's label: the two differ by at least the boundary's own grace, and
      the close question is about the stamp;
    * ``session_close`` — the end of the session window the producer SEEDED
      with, off its ``seed`` record's ``session_window`` (``08:45:00..15:45:00``
      on 2026-10-15). Read from the record rather than written here: the
      producer takes it from the tenant calendar the runtime also loads
      (``live_producer/calendar.py``'s module docstring is explicit that a
      hardcoded 15:45 would be a second source of truth), and ``None`` when
      the log carries no seed record, which keeps every reason it would have
      refined exactly as it was.
    """

    dispositions: dict[str, str]
    published_as_of_ms: dict[str, int]
    session_close: _dt.time | None


#: The producer's ``seed`` log stage and the key on it that carries the
#: session window, as ``live_producer/seed_lineage.py`` writes them:
#: ``"<start>..<end>"`` of ``datetime.time.isoformat()``.
#:
#: ⚠ **The assumption this rests on, written down (PR #904 review round 1 LOW
#: 4).** That window is ONE phase of one session id — the producer is
#: configured with exactly one (``calendar_session_id`` plus
#: ``calendar_session_phase``, today ``krx-index-futures`` / ``CONTINUOUS``)
#: and logs that phase's end. The runtime reads the same calendar file, but
#: nothing here checks that it reads the same PHASE. If the runtime's session
#: context were ever open past the producer's phase end — a tenant tree that
#: adds an evening phase, or a runtime configured for a different session id —
#: then a bar published after the producer's close could still have been
#: ticked, and calling it :data:`REASON_PUBLISHED_AFTER_CLOSE` would EXCUSE a
#: real miss. The excuse is therefore only as narrow as "one phase, the same
#: one on both sides". If a second phase is ever configured, this reason has
#: to read the runtime's own session facts instead of the producer's log.
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
    """One pass over the producer log — see :class:`ProducerLogFacts`.

    ``published`` wins over everything; otherwise the LAST dispositive stage
    wins, because a bar can miss its own boundary and complete afterwards. Only
    events carrying a ``raw_event_id`` are read — the producer stamps one on
    every per-bar event with B1a's own deriver, so nothing here reconstructs a
    join key (plan §3.6).
    """
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


#: The timeframe token :func:`tools.tos_cp3.produce_fields.derive_raw_event_id`
#: puts between the symbol and the stamp, and the stamp's own format. Split on
#: here rather than re-derived: the key is the producer's, and a second
#: derivation of a join key is how two keys drift apart (that function's own
#: docstring).
_RAW_EVENT_ID_SEPARATOR = ":1m:"
_RAW_EVENT_ID_STAMP_FORMAT = "%Y%m%dT%H%M%S%z"


def _published_after_close(
    raw_event_id: str, as_of_ms: int | None, session_close: _dt.time | None
) -> bool:
    """Was this bar's line STAMPED at or after its own session's close?

    The close instant is built from the bar's OWN date (off the join key) and
    the window end the producer seeded with — so a seed day's bar is measured
    against that day's close, not against the target session's.

    Unanswerable inputs are ``False``, never ``True``: without a stamp or a
    window there is no evidence the line was unconsumable, and the caller's
    fall-through is :data:`REASON_UNCONSUMED_AFTER_BOOT`, the defect name. A
    missing input must not silently excuse a real miss.
    """
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
    """Why each produced-but-unconsumed bar has no live counterpart.

    Two of the reasons are structural rather than defects, one at each end of
    the day: :data:`REASON_PRE_BOOT` for a line already in the journal when
    the runtime booted, and :data:`REASON_PUBLISHED_AFTER_CLOSE` for a line
    stamped at or after the session close, which the scheduler can never tick.
    Everything else the producer published and the runtime did not consume is
    :data:`REASON_UNCONSUMED_AFTER_BOOT` — the M5 defect shape.
    """
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
    """The ``YYYYMMDD`` a bar id belongs to, or ``None`` when the id is not of that shape.

    ``A05611:1m:20261022T151200+0900`` -> ``"20261022"``. Reuses
    :data:`_RAW_EVENT_ID_SEPARATOR`/:data:`_RAW_EVENT_ID_STAMP_FORMAT` so this and
    :func:`_published_after_close` cannot drift into two id grammars.
    """
    try:
        stamp = raw_event_id.split(_RAW_EVENT_ID_SEPARATOR, 1)[1]
        return _dt.datetime.strptime(stamp, _RAW_EVENT_ID_STAMP_FORMAT).strftime(
            "%Y%m%d"
        )
    except (IndexError, ValueError):
        return None


def derive_session_day(snapshots: Sequence[Snapshot]) -> str | None:
    """The session day these snapshots were measured for: the NEWEST day present.

    ⛔ **Why this exists** (2026-10-22 evidence README §4). ``read_snapshots`` reads the whole
    ``snapshots`` table, and its docstring's "every issued snapshot of the session" was true
    only while each session had its own data dir. A tenant session writes into a NAMED DURABLE
    LEAF that is never cleared, so the table accumulates: on 2026-10-22 it held the 10-15
    genesis session too. The consequence was a silent miscount — the boot snapshot only lists
    TODAY's pre-boot ids, so the 10-15 session's pre-boot line was counted as post-boot and
    M5's number read 2 store-wide against 1 for the session. The measurement had to filter by
    day BY HAND to get the real number.

    Newest-day rather than an operator flag: the session being measured is the one that just
    ran, the ids already carry their day, and a flag is one more thing to get wrong at 08:45.
    A reader who needs to see the assumption gets ``session_day`` and ``days_present`` in the
    document rather than having to know this rule.

    Returns:
        The ``YYYYMMDD``, or ``None`` when no snapshot carries a parseable id (then nothing is
        scoped and every count stays store-wide, reported as such).
    """
    days = {
        day
        for day in (session_day_of(snapshot.raw_event_id) for snapshot in snapshots)
        if day is not None
    }
    return max(days) if days else None


def consumed_field_states(
    *, snapshots: Sequence[Snapshot], pre_boot: frozenset[str]
) -> dict[str, Any]:
    """M5's first count: lines the issuer HELD a value for and refused anyway.

    **Why it is not a count of ``STALE``.** Plan §5 M5 asks for "lines
    consumed STALE", and the durable side does not write that word.
    ``tos_runtime.marketfeed.snapshot._derive_field_state`` returns
    ``(FieldState.UNKNOWN, "stale")`` when ``now_ms - as_of_ms >
    spec.max_age_ms``; only the STATE is persisted into
    ``field_evaluations``, while the reason stays on the in-memory
    ``IssuedSnapshot.field_reports``. A count of persisted ``STALE`` is
    therefore 0 on every real session however stale its lines were (Claude
    lane BLOCKER R2', 2026-10-14) — measured on the real issuer, in the hinge.

    **What is counted instead.** ``_derive_field_state`` has exactly four
    UNKNOWN causes, in this order: ``absent_from_payload`` (the key is not in
    the preimage), ``now_ms_unknown`` (no trustworthy clock), ``stale`` (over
    ``max_age_ms``), ``unprojectable`` (``project_scalar`` refuses the token).
    Two of them are decidable from durable bytes — presence of the key in
    ``preimages.preimage_json``, and whether its token projects
    (:func:`_projectable`) — and what is left in the middle is exactly "the
    issuer HAD a usable value for this field and refused it on age or on an
    unestablished clock". That is

    ``m5_post_boot_consumed_ids_with_a_present_value_refused_as_unknown``:
    consumed ``raw_event_id``s with at least one ``field_evaluations`` entry
    in state ``UNKNOWN`` whose ``field_ref`` IS a key of that snapshot's
    preimage and whose token is projectable, counted once per id, excluding
    ids the runner's boot snapshot lists as pre-boot (plan §5 M5 excludes
    those from both of its counts). Read it as **"stale, or the evaluation
    clock was unknown"**: an UPPER BOUND on STALE that, unlike a count of the
    word, cannot read 0 when lines were consumed stale.

    The two separated causes are reported under their own names
    (:data:`CAUSE_ABSENT_FROM_PAYLOAD`, :data:`CAUSE_UNPROJECTABLE`), never
    folded in: a field the payload never carried says nothing about freshness,
    and a token the kernel would refuse to project is a different defect.

    **The one gap, stated.** When ``now_ms`` is ``None`` the issuer returns at
    its second check, before projection — so a field that is present but
    UNPROJECTABLE could also be a clock refusal, and this side files it under
    ``unprojectable``. It is visible rather than lost (that count sits beside
    the number), and it cannot hide a clock failure on its own: with no
    trustworthy clock EVERY declared field reads UNKNOWN, so any present,
    projectable field in the same snapshot is counted.

    **The criterion, as of 2026-10-23** (operator directive; measured on the
    2026-10-22 session). It is no longer "0, and anything else is a finding":

    1. **Scoped to one session day** (:func:`derive_session_day`). The durable
       leaf accumulates sessions and the boot snapshot only lists TODAY's
       pre-boot ids, so a store-wide count reads an older session's pre-boot
       line as post-boot. 2026-10-22 measured 2 store-wide against 1 for the
       session; only the second number means anything.
    2. **A stale-refusal budget of <= 0.5% of ``post_boot_consumed_ids``.**
       2026-10-22 measured 1 of 409 = 0.244%, caused by host scheduling
       jitter, not by a late producer: the bar's own ``as_of`` was +2258 ms
       after its minute close against a session p50 of 2221, while the
       scheduler pass that read it ran 1280 ms into a 408 ms loop, so the line
       was 922 ms old against ``max_age_ms`` 800. ``max_age_ms`` STAYS at 800
       (operator decision 2026-10-09: 1000 kernel budget minus 200 delay) —
       widening it to absorb host jitter would widen the window in which a
       decision runs on an old price. A budget of 0.1% was considered and
       rejected: the only session measured would have failed it.
    3. **Any refusal for a reason other than staleness is a finding at any
       count**, including one. The budget is for jitter, and nothing else.
       That clause is checkable only because the runtime now records the
       reason: ``MARKETFEED_FIELD_REFUSED``
       (``tos_runtime.marketfeed.scheduler.TickScheduler._record_field_refusals``)
       carries ``refused_by_reason`` plus both sides of the age comparison.
       This function's own number cannot make the distinction — it is an
       upper bound over "stale OR clock unknown" by construction.

    The pre-boot key is where a non-zero count is unremarkable.
    """
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
    # ⛔ SCOPE (2026-10-22 README §4, :func:`derive_session_day`): the durable leaf accumulates
    # sessions, so every count below is over THIS session's day only. Without it an older
    # session's pre-boot line — absent from today's boot snapshot — reads as post-boot and
    # inflates M5's number, which is exactly what happened on 2026-10-22 (2 store-wide, 1 for
    # the session). `days_present` keeps the accumulation visible rather than hidden by the fix.
    session_day = derive_session_day(snapshots)
    days_present = sorted(
        {
            day
            for day in (session_day_of(s.raw_event_id) for s in snapshots)
            if day is not None
        }
    )
    in_session = [
        snapshot
        for snapshot in snapshots
        if session_day is None or session_day_of(snapshot.raw_event_id) == session_day
    ]
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
        "session_day": session_day,
        "days_present": days_present,
        "counts": {
            "consumed_ids": len(in_session),
            "consumed_ids_all_days": len(snapshots),
            "pre_boot_consumed_ids": sum(
                1 for snapshot in in_session if snapshot.raw_event_id in pre_boot
            ),
            # the denominator of the number above it, so "1 refused" is read
            # against how many post-boot lines the session consumed at all
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
    """What the RESOLVER did on each consumed tick — reported beside M5, not as it.

    Every admitted tick carries the resolver's ``value_view``, which is either
    absent (no view published at all), explicitly empty (the binding resolved
    and nothing was admissible) or populated. That is a useful second view of
    the same session, and it is NOT the STALE count: ``tos.marketfeed.value
    ._admit_one`` rejects a candidate for ten reasons, of which the only
    state-shaped one (``FIELD_STATE_NOT_VALID``) folds STALE together with
    UNKNOWN, CONFLICTED and INVALID. An earlier revision of this docstring
    called ``empty_view + no_view`` M5's first count; that was both too broad
    and backwards, and M5 now reads :func:`consumed_field_states` (Claude lane
    MEDIUM R2).

    **Expectation at genesis** with ③ live (plan §5 M5, M6 < 300 ms against
    ``max_age_ms`` 800): values ARE expected to be admitted on post-boot
    ticks, so ``values_admitted`` near the consumed count is the healthy
    reading and a session of ``empty_view`` is the finding. The ids with
    admitted values are listed because that list is the evidence for it.
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
    """The ``consumed-ids`` document: the id filter plus the reason map.

    Raises:
        SessionInputsError: ``boot_snapshot`` is missing. Every document this
            function writes carries the M5 block, and plan §5 M5 excludes
            pre-boot lines from its counts — without the runner's own record
            of what was already in the journal at boot, EVERY pre-boot line
            would be counted as a post-boot one, in the number the acceptance
            criterion is read off. The same omission also moves every pre-boot
            unconsumed line into ``published_not_consumed`` (the second M5
            count). An absent flag is not a legitimate "no pre-boot lines":
            that is an empty list, which the runner writes (Claude lane LOW
            L-a, 2026-10-14).
    """
    if boot_snapshot is None:
        raise SessionInputsError(
            "consumed-ids needs the runner's boot-journal snapshot "
            "(--boot-snapshot): the document always carries M5's counts, and "
            "plan §5 M5 excludes pre-boot lines from them. Without it every "
            "pre-boot line is counted as a post-boot one — silently, in the "
            "number the criterion is read off. 'No pre-boot lines' is an "
            "empty pre_boot_raw_event_ids list, not a missing file"
        )
    snapshots = read_snapshots(data_dir)
    if not snapshots:
        raise SessionInputsError(
            f"{data_dir / MARKETFEED_FILE_NAME} holds no snapshots — the runtime "
            "consumed nothing, so an id filter built from it would silently "
            "empty every comparison"
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
    pre_boot = read_boot_snapshot(boot_snapshot)
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
            # null when the log carried no readable `seed` record — then
            # REASON_PUBLISHED_AFTER_CLOSE could not be decided for ANY bar,
            # and a zero in that reason means "not asked", not "none".
            "producer_session_close": (
                facts.session_close.isoformat() if facts.session_close else None
            ),
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
        "consumed_field_states": consumed_field_states(
            snapshots=snapshots, pre_boot=pre_boot
        ),
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
        That is why :func:`_attribute` has a SECOND durable key for the
        records with no capsule: the driver's receipt bracket around the
        event that wrote them.
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
    #: ``None`` when it published no view at all (see
    #: :func:`consumed_value_view_counts`).
    admitted_values: int | None
    #: This row's ``EVENT_HANDLING_STARTED`` evidence ``seq``, or ``None`` when
    #: the driver never started handling it (a tick queued and never run).
    handling_started_evidence_seq: int | None = None
    #: This row's ``EVENT_CONSUMED`` evidence ``seq``, or ``None`` when the
    #: driver started and never finished (a crash inside handling).
    consumed_evidence_seq: int | None = None

    def brackets(self, evidence_seq: int) -> bool:
        """Does this tick's durable handling window contain ``evidence_seq``?

        ``(handling_started, consumed]`` — the open lower end is the
        ``EVENT_HANDLING_STARTED`` receipt itself, which is not a decision
        record; the closed upper end is the ``EVENT_CONSUMED`` receipt, also
        not a decision record, and is written closed only to match the
        interval this is documented as. A tick with no handling-started stamp
        brackets nothing (it never ran). A started-but-unconsumed tick has an
        OPEN upper end: everything after it is inside, which makes any later
        decision ambiguous — :func:`_attribute` refuses rather than picking.
        """
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
    """Every admitted market tick, in admission order, with its two ids.

    This is the link the evidence store does not carry. The scheduler issues a
    snapshot, binds it into a capsule and hands the engine ONE
    ``DECISION_TICK`` event (``marketfeed/scheduler.py::tick_once``); the
    driver admits that event durably before processing it
    (``engine/driver.py::enqueue_and_run`` -> ``SqliteEventInbox.enqueue``),
    and the stored ``payload_json`` is the whole event — capsule id and
    ``SnapshotRef`` included. So ``decision.capsule_id -> tick.snapshot_id ->
    preimages.raw_event_id`` is a keyed join over durable rows.

    The row also carries the two receipt stamps
    (:data:`INBOX_HANDLING_STARTED_COLUMN`, :data:`INBOX_CONSUMED_COLUMN`)
    that bracket the window this tick's evidence was written in — the durable
    key for the records that name no capsule (:meth:`DecisionTick.brackets`,
    :func:`_attribute`).

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
    """Pair each decision with the tick it was about, by durable key only.

    Two keys, both durable, neither positional:

    ``capsule_id``
        ``DECISION_OUTCOME_EMITTED`` names the capsule it consumed, and
        exactly one inbox row admitted that capsule.

    ``evidence_seq_range``
        ``DECISION_WITHHELD`` and ``COORDINATOR_PRECONDITION_REFUSED`` name no
        capsule — the pipeline never reached a signature — so they are
        attributed by the bracket the driver itself writes around each event:
        the ``EVENT_HANDLING_STARTED`` receipt's ``seq`` and the
        ``EVENT_CONSUMED`` receipt's ``seq``, stamped onto the inbox row
        (:data:`INBOX_HANDLING_STARTED_COLUMN`,
        :data:`INBOX_CONSUMED_COLUMN`). The driver's loop is single-threaded
        and refuses re-entry, so the records written during one event's
        handling are exactly those whose evidence ``seq`` lies in
        ``(handling_started, consumed]``, and the record is attributed to the
        UNIQUE tick whose bracket contains it.

    A keyed record is CROSS-CHECKED against the same bracket: if the capsule's
    tick has a bracket and the record's ``seq`` is outside it, the two durable
    keys disagree and that is a refusal, not a preference for one of them.

    The first two cuts paired capsule-less records by POSITION (the k-th
    unclaimed tick, in file order). That is an inference the stores can
    contradict silently, and the reviewer's own sequence shows it: three ticks
    c1–c3, evidence ``DECISION_WITHHELD{A on bar1}``,
    ``DECISION_TICK_DROPPED_ON_RECOVERY`` (tick 2 never ran), ``DECISION_
    WITHHELD{B on bar3}`` — positionally B lands on bar2, with every count
    still matching and nothing refused (Claude lane MEDIUM R1, 2026-10-14).
    Under the bracket, B's ``seq`` is inside c3's window and only c3's.

    Raises:
        SessionInputsError: a decision names a capsule the inbox never
            admitted; a keyed record falls outside its own tick's bracket; a
            keyed record's tick has no bracket at all (the receipts the
            cross-check needs are missing); a capsule-less record is in no
            tick's bracket, or in more than one; or two decisions land on one
            tick.
    """
    by_capsule = {tick.capsule_id: (index, tick) for index, tick in enumerate(ticks)}
    assigned: dict[int, tuple[int, str]] = {}  # block position -> (tick index, how)
    used: dict[int, int] = {}  # tick index -> evidence seq

    # Pass 1 — every decision that names a capsule, by key, each cross-checked
    # against its tick's own bracket. Keyed first and in their own pass, so a
    # capsule-less record cannot take a tick a later keyed record names.
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

    # Pass 2 — the capsule-less records, each into the one bracket that holds
    # it. No ordering, no leftovers, no "next unclaimed": a record the
    # brackets cannot place is refused.
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


def live_decision_records(data_dir: Path) -> list[dict[str, Any]]:
    """One record per live decision, in B1b's trace shape.

    The keys B3 reads from a trace line — ``raw_event_id``, ``as_of_ms``,
    ``outcome_kind``, ``rule_id``, ``capacity_denied`` — are all present, and
    each record also says WHICH durable key attributed it
    (``attributed_by``): ``capsule_id`` for a record that names its capsule,
    ``evidence_seq_range`` for one that cannot (:func:`_attribute`).

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
