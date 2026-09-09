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
from pathlib import Path

from tos.canonical import CanonicalizationScheme
from tos.engine.records import EngineEvent, event_identity

__all__ = ["InboxReceipt", "SqliteEventInbox"]

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
