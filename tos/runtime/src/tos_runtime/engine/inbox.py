"""``SqliteEventInbox`` — the durable, single-writer event admission queue (TOS Phase 3 Wave 1
Lane A-R; plan §1.1).

**A separate sqlite file from the Evidence Store (operator-confirmed item 2, D3 failure-domain
separation).** The evidence store's ``entries`` table is mechanically append-only (``BEFORE
UPDATE``/``BEFORE DELETE`` triggers that always abort — see
:mod:`tos_runtime.evidence.store`'s module docstring). This inbox's ``events`` table is a working
QUEUE: :meth:`SqliteEventInbox.mark_consumed` performs a genuine ``UPDATE`` on exactly two
consumption-marker columns (``consumed_evidence_seq``, ``consumed_generation``) every time an event
is drained. Sharing one file between an append-only log and a queue that legitimately mutates rows
would either weaken the evidence store's own append-only invariant or force the queue to fake
append-only-ness through a second unconsumed-row table — the rejected-alternatives list in the plan
(§4 "inbox 를 evidence store 같은 파일에") calls this out explicitly. Two files, two fault domains.

**Content-addressed identity, duplicate-safe.** ``event_id`` is
:func:`tos.engine.records.event_identity` — the same bytes always produce the same id, so a
double-``enqueue`` of the exact same :class:`~tos.engine.EngineEvent` (a caller retry after an
uncertain outcome, or the driver's own crash-window replay of an unmarked-but-already-consumed row)
is recognised and refused as a ``UNIQUE`` violation on ``event_id`` — refused as a **typed return
value** (:attr:`InboxReceipt.duplicate`), never an unhandled exception the caller has to guess how
to interpret. A different id can only mean different bytes, so there is no representable case where
retrying loses data.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``json``, ``sqlite3``) +
``pydantic`` + ``tos.canonical``/``tos.engine`` only. No ``shared.*``, no ``tos.backtest``.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from tos.canonical import CanonicalizationScheme
from tos.engine.records import EngineEvent, event_identity

__all__ = ["InboxReceipt", "NewRiskHaltClearOutcome", "SqliteEventInbox"]

_CREATE_EVENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    account TEXT NOT NULL,
    instrument TEXT NOT NULL,
    reference_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    consumed_evidence_seq INTEGER,
    consumed_generation INTEGER,
    handling_started_evidence_seq INTEGER,
    handling_started_generation INTEGER
)
"""

#: Columns added after the table's original shape — guarded with a
#: ``PRAGMA table_info`` check (:func:`_ensure_column`) rather than a bare ``ALTER TABLE`` so
#: reopening an inbox file created before independent-review finding #3 landed does not raise
#: "duplicate column" on a fresh file (which already carries both via
#: ``_CREATE_EVENTS_TABLE_SQL`` above) while still gaining them on an older one.
_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("handling_started_evidence_seq", "INTEGER"),
    ("handling_started_generation", "INTEGER"),
)

_CREATE_UNCONSUMED_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS events_unconsumed
ON events (seq) WHERE consumed_evidence_seq IS NULL
"""

#: TOS Phase 3 Wave 2 Lane C-R (plan §2.2 "커널 결합"): a small side table, in this SAME inbox
#: file (never the evidence store — the D3 failure-domain separation this file's own module
#: docstring already argues for applies here identically: this is a durable, mutable, keyed-by
#: -scope PROJECTION, not an append-only log entry), holding the LAST orthostate
#: ``CompositeState`` observation :mod:`tos_runtime.engine.orthostate_projection` derived for
#: each ``attempt_id`` — so a restart resumes projecting from the last known composite
#: (conservatively, via ``tos.orthostate.reconstruct_conservative``) rather than from a wrongly
#: re-derived genesis. Deliberately keyed by ``attempt_id``, never overwritten in place with a
#: mutated value: :meth:`record_composite` REPLACES the row wholesale on every call — there is no
#: partial-field update, mirroring ``tos.orthostate.records.CompositeState``'s own "no update
#: method; a legitimate transition is a fresh observation" discipline at the storage layer too.
_CREATE_ATTEMPT_COMPOSITES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS attempt_composites (
    attempt_id TEXT PRIMARY KEY,
    composite_json TEXT NOT NULL,
    observation_revision INTEGER NOT NULL
)
"""

#: TOS Phase 3 Wave 2 Lane C-R follow-up (team-lead CR-4 dispatch, plan §2.2): a second small
#: side table, same file, same D3 rationale as :data:`_CREATE_ATTEMPT_COMPOSITES_TABLE_SQL` —
#: durably holds the LAST ``finality_witness`` (:func:`tos_runtime.rcl.finality_witness
#: .finality_witness_for`) :mod:`tos_runtime.engine.driver` derived for each ``attempt_id``, so a
#: FUTURE release-trigger lane (Phase 5 — no such lane exists yet in this runtime, see
#: ``tos_runtime.rcl.finality_witness``'s own module docstring) can read a durable witness
#: instead of re-deriving one from a possibly-already-drained ``EGRESS_RESULT``. ``witness`` is
#: stored as ``0``/``1``/``NULL`` (sqlite has no bool type) — ``NULL`` means "no witness
#: currently established" (the ``finality_witness_for`` ``None`` case), never a stored ``False``
#: (this dimension's own positive-polarity discipline: absence, not a negative claim).
_CREATE_ATTEMPT_FINALITY_WITNESS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS attempt_finality_witness (
    attempt_id TEXT PRIMARY KEY,
    witness INTEGER
)
"""

#: TOS Phase 3 wave 2 independent review finding #3 (2026-09-09, lane C-R2): a durable,
#: RUNTIME-WIDE (never per-attempt) new-risk halt latch, in this SAME inbox file (same D3
#: rationale as the two side tables above). ADR-002-005 §10 "an invariant violation is a
#: Critical incident and an immediate new-risk halt condition" — before this table existed, a
#: recorded ``COUPLING_VIOLATION``/``ORTHOSTATE_OWNERSHIP_VIOLATION`` durably logged the
#: violation but blocked nothing (:mod:`tos_runtime.engine.orthostate_projection`'s own module
#: docstring). The ``CHECK (id = 1)`` + ``PRIMARY KEY`` makes this a genuine SINGLETON row: the
#: FIRST halt recorded here sticks (an ``INSERT OR IGNORE`` — see :meth:`SqliteEventInbox
#: .record_new_risk_halt` — silently no-ops on a second write, a primary-key conflict, never an
#: overwrite), preserving the original cause.
#:
#: **Operator re-arm (re-review finding R3, 2026-09-09).** A runtime-wide, singleton, durable,
#: and UNCLEARABLE latch is too strong: ADR-002-005 §7 / ADR-002-002 §15.2 both require a
#: cancel-crossing fill (independent review finding #8's own dispatched scenario) to be
#: *accepted*, not to leave the runtime permanently unable to take new risk. Deferring the clear
#: path to "Phase 5" (the original disposition) makes the latch a ONE-WAY door on the normal
#: path, for a race the spec calls routine — an operator decision, so this module provides the
#: MECHANISM (:meth:`SqliteEventInbox.clear_new_risk_halt`) now rather than deferring it, while
#: the latch itself (a genuine ledger/broker disagreement IS unknown exposure) stays in place —
#: nothing clears it automatically anywhere in this runtime. The clear is guarded two ways: (1)
#: it names the EXACT ``evidence_seq`` the operator is attesting they reviewed — a stale clear
#: (naming an OLDER seq than the currently-latched one) cannot silently wipe a NEWER violation
#: the operator never saw; (2) it requires a non-empty ``operator_attestation`` string — there is
#: no config literal or automatic path that supplies one.
#:
#: **:meth:`SqliteEventInbox.clear_new_risk_halt` is NOT the operator door (re-review finding
#: RR2, 2026-09-09).** It is the storage-layer GUARD :meth:`~tos_runtime.compose._types
#: .ComposedRuntime.clear_new_risk_halt` delegates to — that wrapper method is the only
#: sanctioned caller, because it is the one that durably records the
#: ``NEW_RISK_HALT_CLEARED_BY_OPERATOR`` / ``NEW_RISK_HALT_CLEAR_REFUSED`` evidence rows (evidence
#: BEFORE state change, this runtime's own discipline for every halt path). A direct call on
#: THIS method clears (or refuses) the latch with the exact same seq/attestation checks but
#: writes NO evidence at all — a caller-visible gap the review measured directly (a bare direct
#: call on this method clears the latch with zero evidence rows). Nothing
#: under ``tos/runtime/src`` outside ``compose/_types.py`` may call this method — enforced
#: mechanically by ``tos/runtime/tests/engine/test_no_direct_latch_clear.py`` (the same grep-pin
#: idiom ``test_no_direct_core_calls.py`` uses for ``core.handle``/``run``).
_CREATE_NEW_RISK_HALT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS new_risk_halt (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    reason TEXT NOT NULL,
    event_id TEXT,
    evidence_seq INTEGER
)
"""


class NewRiskHaltClearOutcome(StrEnum):
    """The typed outcome of a new-risk-halt clear attempt (re-review finding RR3, 2026-09-09).

    Replaces a bare ``bool`` return, which conflated four distinct refusal reasons into a single
    ``False`` — a caller (and, worse, an evidence record) could not tell "there was no latch to
    clear" from "you named a stale/wrong seq" from "the attestation was empty". Shared between
    this module's own storage-layer :meth:`SqliteEventInbox.clear_new_risk_halt` and
    :meth:`~tos_runtime.compose._types.ComposedRuntime.clear_new_risk_halt` — the wrapper adds
    :attr:`STORAGE_REFUSED` for the one case only IT can observe (its own pre-check passed, but
    the underlying storage call still refused — the disclosed TOCTOU window).
    """

    #: The latch was cleared.
    CLEARED = "CLEARED"
    #: There was no latch to clear at all.
    NO_LATCH = "NO_LATCH"
    #: ``operator_attestation`` was empty or all-whitespace.
    EMPTY_ATTESTATION = "EMPTY_ATTESTATION"
    #: ``latched_evidence_seq`` did not match the currently-latched row's own seq (stale or
    #: simply wrong) — "the operator is looking at a violation that is not the current one".
    SEQ_MISMATCH = "SEQ_MISMATCH"
    #: Wrapper-only: the pre-check (latch present, seq matched, attestation non-empty) passed,
    #: but the storage-layer clear itself still refused — a concurrent relatch changed the seq
    #: between the two (never reachable through this single-threaded runtime today).
    STORAGE_REFUSED = "STORAGE_REFUSED"
    #: Wrapper-only (TOS Phase 5 W3 plan §2 decision 7): the HAG two-person re-arm quorum
    #: (:mod:`tos_runtime.safety.rearm`) did not positively approve — a missing/malformed
    #: ``approvals/rearm/<seq>.yaml`` file, or any of the five kernel predicates
    #: (``dual_control_effective_distinct`` / ``quorum_independence_satisfied`` /
    #: ``approval_binding_exact`` / ``approval_set_single_use`` / ``no_automatic_rearm``) not
    #: positively satisfied. Replaces the free-text ``EMPTY_ATTESTATION`` refusal for this
    #: wrapper's own pre-checks (latch present + seq match still refuse with ``NO_LATCH`` /
    #: ``SEQ_MISMATCH`` before a re-arm file is even consulted).
    QUORUM_REFUSED = "QUORUM_REFUSED"


@dataclass(frozen=True)
class InboxReceipt:
    """The result of one :meth:`SqliteEventInbox.enqueue` call.

    ``duplicate=True`` is a **typed refusal**, not an exception: the plan (§1.1 "중복 event_id 는
    UNIQUE 로 거부") requires a caller (the driver's own crash-window recovery, or an external
    retrying producer) to be able to treat "this exact event is already admitted" as an ordinary,
    inspectable outcome rather than a swallowed or re-raised error. ``seq`` is the EXISTING row's
    sequence number in the duplicate case, so a caller can still locate it.
    """

    seq: int
    event_id: str
    duplicate: bool


class SqliteEventInbox:
    """The append-and-mark-consumed durable admission queue (design plan §1.1).

    One sqlite3 file (``journal_mode=WAL``, ``synchronous=FULL``), mirroring
    :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`'s own transaction discipline
    (``BEGIN IMMEDIATE`` ... ``COMMIT``, rollback on any failure) so a concurrent writer is
    serialized rather than corrupting the file. ``seq`` is allocated internally from
    ``MAX(seq) + 1``, read fresh inside the same transaction as the insert (never a cached
    counter) — the same "a crash-injected instance and a freshly reopened instance observe
    identical behaviour" discipline the evidence store's own ``_read_tail`` documents.

    Single-writer by construction: :class:`~tos_runtime.engine.driver.EngineDriver` is this
    queue's only intended caller, and it is itself single-threaded (design #31 §2 D5).
    """

    def __init__(self, path: Path, *, scheme: CanonicalizationScheme) -> None:
        """Open (or create) the event inbox at ``path``.

        Args:
            path: The sqlite file path — a SEPARATE file from the Evidence Store's own path (see
                module docstring). Parent directory must already exist.
            scheme: The canonicalization scheme used to derive each event's content-addressed
                ``event_id`` (:func:`tos.engine.records.event_identity`) and ``payload_digest``.
        """
        self.path = path
        self._scheme = scheme
        self._conn = sqlite3.connect(str(path), isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute(_CREATE_EVENTS_TABLE_SQL)
        self._conn.execute(_CREATE_UNCONSUMED_INDEX_SQL)
        self._conn.execute(_CREATE_ATTEMPT_COMPOSITES_TABLE_SQL)
        self._conn.execute(_CREATE_ATTEMPT_FINALITY_WITNESS_TABLE_SQL)
        self._conn.execute(_CREATE_NEW_RISK_HALT_TABLE_SQL)
        existing_columns = {
            row[1] for row in self._conn.execute("PRAGMA table_info(events)")
        }
        for column, decl in _ADDED_COLUMNS:
            if column not in existing_columns:
                self._conn.execute(f"ALTER TABLE events ADD COLUMN {column} {decl}")

    def close(self) -> None:
        """Close the underlying sqlite3 connection."""
        self._conn.close()

    def _next_seq(self) -> int:
        """Return the next row seq, read fresh from disk every call (no cached counter)."""
        row = self._conn.execute("SELECT MAX(seq) FROM events").fetchone()
        current = row[0]
        return 1 if current is None else current + 1

    @property
    def count(self) -> int:
        """How many events this inbox has ever admitted (consumed or not).

        Used by :class:`~tos_runtime.engine.driver.EngineDriver` to durably re-seed its
        yield-order counter across a restart: every admitted event was stamped by exactly one
        driver-issued coordinate, so this count IS the number of coordinates already issued.
        """
        row = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()
        return int(row[0])

    @property
    def unconsumed_count(self) -> int:
        """How many admitted events are NOT yet consumed (the subset :attr:`count` does not
        distinguish) — the MONITORING safety-mesh service's own inbox-backlog observation
        (Phase 5 W3-b, plan §2 decision 2's "MonitoringService" bullet, item 3:
        ``inbox_unconsumed_observer``). Reuses the SAME partial index
        :meth:`next_unconsumed`'s own query already relies on
        (``events_unconsumed ON events (seq) WHERE consumed_evidence_seq IS NULL``), so this
        count is never a second, independently-derived view of consumption.
        """
        row = self._conn.execute(
            "SELECT COUNT(*) FROM events WHERE consumed_evidence_seq IS NULL"
        ).fetchone()
        return int(row[0])

    def enqueue(self, event: EngineEvent) -> InboxReceipt:
        """Durably admit one event, allocating its ``seq`` internally.

        Args:
            event: The fully-formed, already-stamped :class:`~tos.engine.EngineEvent` (the
                driver is responsible for its ``reference`` coordinates — this queue stores
                whatever it is given, unchanged).

        Returns:
            The :class:`InboxReceipt`. ``duplicate=True`` when this exact event (same
            content-addressed ``event_id``) is already admitted — the EXISTING row's ``seq`` is
            returned, and no new row is written.
        """
        event_id = event_identity(event, scheme=self._scheme)
        key = event.instrument_key()
        reference = event.reference()
        dumped = event.model_dump(mode="json")
        payload_json = json.dumps(dumped, sort_keys=True, separators=(",", ":"))
        payload_digest = self._scheme.compute_digest(dumped)
        reference_json = json.dumps(
            reference.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            existing = self._conn.execute(
                "SELECT seq FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if existing is not None:
                self._conn.execute("COMMIT")
                return InboxReceipt(seq=existing[0], event_id=event_id, duplicate=True)
            next_seq = self._next_seq()
            self._conn.execute(
                "INSERT INTO events (seq, event_id, kind, account, instrument, "
                "reference_json, payload_json, payload_digest, consumed_evidence_seq, "
                "consumed_generation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)",
                (
                    next_seq,
                    event_id,
                    event.kind.value,
                    key.account,
                    key.instrument,
                    reference_json,
                    payload_json,
                    payload_digest,
                ),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        return InboxReceipt(seq=next_seq, event_id=event_id, duplicate=False)

    def next_unconsumed(self) -> tuple[int, EngineEvent] | None:
        """Return the oldest not-yet-consumed event, in ``seq`` order.

        Returns:
            ``(seq, event)``, or ``None`` when nothing is pending.
        """
        row = self._conn.execute(
            "SELECT seq, payload_json FROM events "
            "WHERE consumed_evidence_seq IS NULL ORDER BY seq ASC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        seq, payload_json = row
        return seq, EngineEvent.model_validate(json.loads(payload_json))

    def mark_consumed(self, seq: int, *, evidence_seq: int, generation: int) -> None:
        """Record that ``seq`` was durably consumed, binding it to its evidence receipt.

        Args:
            seq: The inbox row to mark.
            evidence_seq: The durable ``EVENT_CONSUMED`` evidence entry's own ``seq`` — the
                receipt that proves this event's consumption was recorded before this call.
            generation: The evidence store's signing key generation at the time of that receipt.
        """
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "UPDATE events SET consumed_evidence_seq = ?, consumed_generation = ? "
                "WHERE seq = ?",
                (evidence_seq, generation, seq),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def mark_handling_started(
        self, seq: int, *, evidence_seq: int, generation: int
    ) -> None:
        """Record this row's own write-ahead ``EVENT_HANDLING_STARTED`` evidence receipt
        (independent review finding #3), so :meth:`handling_started_receipt` can answer in O(1)
        by primary key instead of ``EngineDriver`` having to scan the whole evidence store by
        ``event_id`` the way the pre-existing ``EVENT_CONSUMED`` crash-window check still does
        (finding #13 — this NEW check gets an index from the start; the older one is disclosed,
        unindexed, LOW-severity future work: see ``driver.py``'s own ``_find_consumed_receipt``
        docstring).

        Args:
            seq: The inbox row this marker belongs to.
            evidence_seq: The durable ``EVENT_HANDLING_STARTED`` evidence entry's own ``seq``.
            generation: The evidence store's signing key generation at the time of that receipt.
        """
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "UPDATE events SET handling_started_evidence_seq = ?, "
                "handling_started_generation = ? WHERE seq = ?",
                (evidence_seq, generation, seq),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def handling_started_receipt(self, seq: int) -> tuple[int, int] | None:
        """``(evidence_seq, generation)`` of ``seq``'s own ``EVENT_HANDLING_STARTED`` marker, or
        ``None`` if handling was never (durably) started for this row — an O(1) lookup by primary
        key (finding #13)."""
        row = self._conn.execute(
            "SELECT handling_started_evidence_seq, handling_started_generation "
            "FROM events WHERE seq = ?",
            (seq,),
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return row[0], row[1]

    def is_consumed(self, seq: int) -> bool:
        """Whether ``seq`` is already marked consumed."""
        row = self._conn.execute(
            "SELECT consumed_evidence_seq FROM events WHERE seq = ?", (seq,)
        ).fetchone()
        return row is not None and row[0] is not None

    def replay(self) -> Iterator[tuple[int, EngineEvent]]:
        """Yield every admitted event, in ``seq`` order, consumed or not.

        Used by :func:`~tos_runtime.engine.replay.replay_engine` to re-derive a run from
        scratch.
        """
        cur = self._conn.execute(
            "SELECT seq, payload_json FROM events ORDER BY seq ASC"
        )
        for seq, payload_json in cur:
            yield seq, EngineEvent.model_validate(json.loads(payload_json))

    # -- per-attempt orthostate composite side table (Phase 3 wave 2, plan §2.2) ----

    def record_composite(
        self, attempt_id: str, composite: dict, *, observation_revision: int
    ) -> None:
        """Durably REPLACE ``attempt_id``'s last known orthostate composite observation.

        Args:
            attempt_id: The scope key (the ADR-002-005 dimensions are tracked per attempt).
            composite: The plain JSON-native mapping of the five dimension coordinates (this
                queue stores whatever it is given — it never imports or interprets
                ``tos.orthostate`` types itself, keeping this module's own firewall scope
                unchanged; the caller, :mod:`tos_runtime.engine.orthostate_projection`, owns the
                ``CompositeState`` <-> mapping conversion).
            observation_revision: The caller's own monotonically-advancing observation counter
                for this attempt (never a wall clock) — stored alongside for a caller that wants
                to detect a stale write without re-parsing ``composite_json``.
        """
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "INSERT INTO attempt_composites (attempt_id, composite_json, "
                "observation_revision) VALUES (?, ?, ?) "
                "ON CONFLICT(attempt_id) DO UPDATE SET "
                "composite_json = excluded.composite_json, "
                "observation_revision = excluded.observation_revision",
                (
                    attempt_id,
                    json.dumps(composite, sort_keys=True, separators=(",", ":")),
                    observation_revision,
                ),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def last_composite(self, attempt_id: str) -> tuple[dict, int] | None:
        """``(composite, observation_revision)`` last recorded for ``attempt_id``, or ``None``
        if this attempt has no prior recorded composite (a fresh/genesis attempt)."""
        row = self._conn.execute(
            "SELECT composite_json, observation_revision FROM attempt_composites "
            "WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
        if row is None:
            return None
        composite_json, observation_revision = row
        return json.loads(composite_json), observation_revision

    # -- per-attempt finality witness side table (Phase 3 wave 2 CR-4 follow-up) -----

    def record_finality_witness(self, attempt_id: str, witness: bool | None) -> None:
        """Durably REPLACE ``attempt_id``'s last derived ``finality_witness``.

        Args:
            attempt_id: The scope key.
            witness: The value :func:`tos_runtime.rcl.finality_witness.finality_witness_for`
                produced — ``True`` when a proof currently exists for this attempt, ``None``
                otherwise (never a stored ``False`` — positive polarity, matching
                ``finality_witness_for`` itself).
        """
        stored = None if witness is None else int(witness)
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "INSERT INTO attempt_finality_witness (attempt_id, witness) "
                "VALUES (?, ?) "
                "ON CONFLICT(attempt_id) DO UPDATE SET witness = excluded.witness",
                (attempt_id, stored),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def finality_witness(self, attempt_id: str) -> bool | None:
        """The last ``finality_witness`` recorded for ``attempt_id``, or ``None`` if none has
        ever been recorded (or the recorded value is itself ``None`` — the two are
        indistinguishable by design: a caller with no witness must always fail closed
        identically)."""
        row = self._conn.execute(
            "SELECT witness FROM attempt_finality_witness WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return bool(row[0])

    # -- runtime-wide new-risk halt latch (Phase 3 wave 2 review finding #3) ---------

    def record_new_risk_halt(
        self, *, reason: str, event_id: str | None, evidence_seq: int | None
    ) -> None:
        """Durably latch a runtime-wide new-risk halt — a no-op if one is ALREADY latched.

        Args:
            reason: The caller's own halt-reason vocabulary (e.g.
                ``NEW_RISK_HALTED_BY_COUPLING_VIOLATION`` —
                :mod:`tos_runtime.engine.orthostate_projection`'s own constant).
            event_id: An identifier for the record that caused this halt (e.g. an
                ``attempt_id``-derived key), for operator traceability.
            evidence_seq: The durable evidence entry's own ``seq`` that recorded the underlying
                violation, so an operator can cross-reference the two.

        This is a SINGLETON latch (module docstring): the FIRST call wins — a second call, for a
        different (or the same) reason, is silently ignored (``INSERT OR IGNORE`` against the
        ``id = 1`` primary key), preserving the original cause rather than overwriting it. See
        :meth:`clear_new_risk_halt` for the guarded operator re-arm path (module docstring "R3").
        """
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "INSERT OR IGNORE INTO new_risk_halt (id, reason, event_id, evidence_seq) "
                "VALUES (1, ?, ?, ?)",
                (reason, event_id, evidence_seq),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def clear_new_risk_halt(
        self, *, latched_evidence_seq: int, operator_attestation: str
    ) -> NewRiskHaltClearOutcome:
        """Clear the latch — ONLY if it is still the exact violation named (re-review finding R3).

        **NOT the operator door (re-review finding RR2, 2026-09-09) — see this module's own
        docstring "Operator re-arm" section.** This is the storage-layer GUARD
        :meth:`~tos_runtime.compose._types.ComposedRuntime.clear_new_risk_halt` delegates to; it
        performs the exact same seq/attestation checks that wrapper does, but writes NO evidence
        of its own — a direct call here clears (or refuses) the latch with zero durable trace.
        Calling this directly, from anywhere outside that one wrapper, is refused by
        ``tos/runtime/tests/engine/test_no_direct_latch_clear.py``'s mechanical pin. Kept public
        (not name-mangled) only because the wrapper needs to call it and because these hermetic
        unit tests exercise the storage-layer guard directly, on its own terms, independent of
        the compose fixture the wrapper needs (re-review finding RR1).

        Args:
            latched_evidence_seq: The ``evidence_seq`` of the violation the operator reviewed and
                is attesting to. Must equal the CURRENTLY-latched row's own ``evidence_seq``
                exactly — a caller naming a stale (older, already-superseded) seq is refused, so
                a clear issued against yesterday's violation can never silently wipe a NEWER one
                the operator has not seen.
            operator_attestation: A non-empty (non-whitespace) free-text attestation. This method
                does not interpret its content — the CALLER (:meth:`~tos_runtime.compose._types
                .ComposedRuntime.clear_new_risk_halt`) is responsible for durably recording it as
                evidence BEFORE calling this method (evidence-before-state-change, like every
                other halt path in this runtime) — this is only the storage-layer guard.

        Returns:
            :class:`NewRiskHaltClearOutcome` — :attr:`~NewRiskHaltClearOutcome.CLEARED` if the
            latch was cleared; :attr:`~NewRiskHaltClearOutcome.NO_LATCH`,
            :attr:`~NewRiskHaltClearOutcome.EMPTY_ATTESTATION`, or
            :attr:`~NewRiskHaltClearOutcome.SEQ_MISMATCH` naming the specific refusal reason —
            in every refusal case the latch (if any) is left completely untouched. Never returns
            :attr:`~NewRiskHaltClearOutcome.STORAGE_REFUSED` — that outcome exists only for the
            wrapper's own TOCTOU disclosure.
        """
        if not operator_attestation.strip():
            return NewRiskHaltClearOutcome.EMPTY_ATTESTATION
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT evidence_seq FROM new_risk_halt WHERE id = 1"
            ).fetchone()
            if row is None:
                self._conn.execute("COMMIT")
                return NewRiskHaltClearOutcome.NO_LATCH
            (current_evidence_seq,) = row
            if current_evidence_seq != latched_evidence_seq:
                self._conn.execute("COMMIT")
                return NewRiskHaltClearOutcome.SEQ_MISMATCH
            self._conn.execute(
                "DELETE FROM new_risk_halt WHERE id = 1 AND evidence_seq = ?",
                (latched_evidence_seq,),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        return NewRiskHaltClearOutcome.CLEARED

    def new_risk_halt(self) -> dict[str, object] | None:
        """The currently-latched new-risk halt, or ``None`` if none has ever been recorded.

        Returns:
            ``{"reason": str, "event_id": str | None, "evidence_seq": int | None}`` for the
            FIRST halt ever latched (module docstring — never a later one), or ``None`` if the
            latch has never been set.
        """
        row = self._conn.execute(
            "SELECT reason, event_id, evidence_seq FROM new_risk_halt WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        reason, event_id, evidence_seq = row
        return {"reason": reason, "event_id": event_id, "evidence_seq": evidence_seq}
