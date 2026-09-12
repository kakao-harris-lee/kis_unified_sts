"""``SqliteCommitLog`` — the linearizable Safety Commit Log (design #40 D2.1, §2 item 1).

Implements the kernel's ``tos.rcl.commitlog.CommitLog`` Protocol
(``current_epoch``/``append_cas``/``read_linearizable``/``replay``) over a
single sqlite3 file, **separate from the evidence store's own file** (design
#40 D3.1 "장애 도메인 분리"): ``journal_mode=WAL``, ``synchronous=FULL``, every
mutation inside ``BEGIN IMMEDIATE`` ... ``COMMIT``.

**Module layout note (size-budget decomposition, 2026-09-08; extended 2026-09-12).** The sqlite
schema DDL/triggers AND the schema-ledger boot check (``apply_schema_ledger``, TOS Phase 5 W4
plan §2 decision 3) live in :mod:`tos_runtime.rcl.schema`; the pre-insert gate + replay-fold
helpers (reservation from_state checking, duplicate-command classification, the replay fold
itself, and the row->model helper ``row_to_commit_entry`` shared by :meth:`replay`/
:meth:`read_linearizable`) live in :mod:`tos_runtime.rcl.gates` — all extracted purely to keep
this module under the repo's 1000-line module size budget (``tools/tos_size_budget.py``). No
behavior changed by that extraction: every function there is called from exactly the places it
used to be, over the exact same ``sqlite3.Connection``, inside the exact
same transactions. Likewise, :meth:`SqliteCommitLog._commit_entry` was split
into three sequentially-called private methods
(:meth:`~SqliteCommitLog._pre_insert_checks`,
:meth:`~SqliteCommitLog._insert_entry_and_reservation`,
:meth:`~SqliteCommitLog._append_evidence_or_refuse`) to keep each under the
100-line function size budget — **the ``BEGIN IMMEDIATE`` ... ``COMMIT``
transaction boundary is unchanged**: all three still run synchronously
inside the one ``try`` block :meth:`_commit_entry` opens, on the same
connection, before that same ``COMMIT``.

Fault-contract table (slice plan §1 "장애 계약"; column = how this module
satisfies it):

=======  ============================================================
Contract  How :class:`SqliteCommitLog` satisfies it
=======  ============================================================
①        Writer fencing. :meth:`acquire_epoch` atomically inserts a new,
         strictly-greater ``epoch`` row. Every subsequent
         :meth:`append_cas` / :meth:`apply_reservation_transition` /
         :meth:`read_linearizable` re-reads ``current_epoch()`` **inside
         the same transaction** as the write/read and refuses via
         :func:`tos.rcl.stale_writer_epoch` (equality check, D2.1's own
         "OS 파일 잠금은 보조이지 정체성이 아니다") the instant a second
         handle has acquired a newer epoch — the older handle's own
         ``current_epoch()`` observation is now stale even though it
         never called :meth:`acquire_epoch` again.
②        ``command_id`` is the sqlite ``UNIQUE`` constraint on
         ``entries``; :func:`tos.rcl.duplicate_command` classifies a
         repeat id against the digest already committed for it —
         identical bytes => ``DUPLICATE_COMMAND_ID`` (idempotent,
         contains no new effect); differing bytes =>
         ``COMMAND_BYTES_MISMATCH`` (contained conflict, never
         last-write-wins). A stored ``command_digest`` of ``NULL`` is a
         real prior entry, not "no prior entry" —
         :func:`tos_runtime.rcl.gates.existing_command_row` reports
         row-existence separately from the (possibly ``NULL``) digest so
         :func:`tos_runtime.rcl.gates.classify_duplicate_command` never
         lets a second ``command_digest=None`` append reach the
         ``UNIQUE`` constraint unclassified (independent review
         MEDIUM-3, 2026-09-08).
③        A file the process cannot open/lock (e.g. another connection
         holding an unreleased ``BEGIN IMMEDIATE`` reservation on the
         same file) makes ``BEGIN IMMEDIATE`` itself raise
         :class:`sqlite3.OperationalError`; every write path catches
         that BEFORE any row is touched and refuses with
         ``STORE_UNAVAILABLE`` — no partial write is possible because
         nothing was written.
④        Two crash-injection points mirror
         :mod:`tos_runtime.evidence.store`'s own pattern (a real
         ``os._exit``/subprocess harness is unavailable in runtime
         scope — ``subprocess`` is firewall-forbidden, R1): an
         injectable ``crash_hook`` may raise
         :class:`InjectedCrash` at ``"before_commit"`` (caught,
         ``ROLLBACK``ed, the row never exists — re-raised so the test
         observes the crash) or ``"after_commit_before_receipt"`` (the
         row is already durably committed; only the return of the
         receipt to the caller never happens).
⑤        :meth:`verify_replay` independently re-folds every committed
         reservation-transition entry into a reservation-state map and
         compares its canonical digest against the ``reservations``
         projection table's own digest via
         :func:`tos.rcl.replay_reproduces_state`; any disagreement
         raises :class:`CommitLogCorruption` (the caller decides
         non-live disposition — this module only detects and reports).
         The fold reads ONLY entries whose ``is_reservation_transition``
         column is ``1`` (see "the replay fold is discriminated, not
         payload-shape-matched" below) — a plain :meth:`append_cas` entry
         can never be folded in, no matter what ``payload_json`` string a
         caller supplies.
⑥        The log **never reads a clock to order anything** —
         ``issued_at_monotonic_ns`` on ``epochs`` is record-only
         (informational); every ordering coordinate (``epoch`` via
         ``MAX(epoch) + 1``, ``seq`` via ``MAX(seq) + 1``) is derived
         from the durable table state, never from the injected
         ``monotonic_ns`` callable's return value. A regressing
         monotonic source therefore cannot move ``seq``/``epoch``
         backward or duplicate them (see
         ``test_regressing_monotonic_source_does_not_affect_seq_order``).
⑦        Any :class:`sqlite3.Error` raised inside the
         ``BEGIN IMMEDIATE`` ... ``COMMIT`` body (a simulated mid-
         transaction sqlite failure) is caught, ``ROLLBACK``ed, and
         converted to ``AppendRefusal(reason=PARTIAL_COMMIT_SUSPECTED)``
         — never a silently-swallowed success, never an uncaught
         exception escaping this module for this class of failure (the
         kernel's own "no third outcome" contract, ``commitlog.py``
         line 33-34).
=======  ============================================================

**The kernel's ``InstrumentKey`` scope-binding port fix (laneO port-fix
round, design #40 runtime slice #2 §5 disposition, 2026-09-08).**
``CapacityReservationTransition`` now carries ``scope: ReservationScope``
(a structural mirror of ``tos.engine.records.InstrumentKey`` — see
``tos.rcl.commitlog``'s own docstring for why this is not an import),
closing this module's own previously-reported gap: the engine's read
projection is ``InstrumentKey``-keyed, but this log had no binding from
``reservation_id`` to that scope. :meth:`apply_reservation_transition` now
refuses (``COMMAND_BYTES_MISMATCH``) a transition with no ``scope``, exactly
like it already refuses one missing ``reservation_id``/``writer_epoch``;
``reservations.scope_account``/``scope_instrument`` (schema.py) persist it,
the ``payload_json`` embeds it for the fault-⑤ fold (gates.py), and
``projection.py`` now reads back by the real ``InstrumentKey``.

**A claimed ``from_state`` is checked against the held record, in-transaction
(independent review HIGH-1, 2026-09-08).** :meth:`apply_reservation_transition`'s
three kernel gates (structural legality, cause admissibility, release
admissibility) all operate purely on the caller's *claimed*
``transition.from_state`` — none of them reads what this log actually holds
for ``reservation_id``. Left unchecked, a caller could submit a stale or
simply mistaken ``from_state`` that happens to be structurally legal and
cause-admissible (e.g. claiming ``COMMITTED_UNBOUND -> POTENTIALLY_LIVE`` for
a reservation this log already holds at ``RELEASED``) and have it silently
admitted — an automatic re-arm of a finalized reservation, exactly what
ADR-002-012 line 37 forbids ("SHALL NOT automatically re-arm... or revive a
prior capability"). :func:`tos_runtime.rcl.gates.check_reservation_from_state`
closes this in the SAME ``BEGIN IMMEDIATE`` transaction as the write: when a
row already exists for ``reservation_id``, the claimed ``from_state`` MUST
equal the held ``state`` exactly, or the transition is refused; when no row
exists yet, the claimed ``from_state`` must be one of
:data:`tos_runtime.rcl.gates.INITIAL_RESERVATION_STATES` (a transition cannot
originate from a state that was never held). This mirrors
``tos.engine.state.ProvisionalReservationLedger._store``'s own forward-only,
held-state-aware discipline (``engine/state.py`` lines 219-233 refuse a
RANK regression against the held projection) — the sibling check a
persistent, multi-writer log additionally needs is refusing a claim that
disagrees with the held record at all, not only one that regresses its rank.
No kernel ``AppendRefusalReason`` member names "claimed from_state disagrees
with the held record" (the closed vocabulary is CAS-fencing / idempotency /
storage-failure only); ``INTEGRITY_VIOLATION`` is reused for it rather than
inventing a kernel member, because a from_state that disagrees with the held
record is exactly the same integrity concern :func:`replay_reproduces_state`
(fault ⑤) detects independently after the fact — this check catches it
before admission instead of after.

**The replay fold is discriminated, not payload-shape-matched (independent
review MEDIUM-4, 2026-09-08).** :func:`tos_runtime.rcl.gates.fold_reservations_from_entries`
(fault ⑤'s independent re-fold) used to select entries by SHAPE — any row
whose ``payload_json`` happened to decode to an object containing
``reservation_id`` and ``to_state`` keys. But ``payload_json`` is a public,
caller-supplied argument of :meth:`append_cas` (the kernel ``CommitLog``
Protocol method — any caller may pass any string there), so a plain
``append_cas`` call with a crafted ``payload_json`` like
``'{"reservation_id": "GHOST", "to_state": "RELEASED"}'`` would be folded in
as if it were a real reservation transition, inventing a "GHOST" reservation
that disagrees with the (unaffected) ``reservations`` table and forging a
:class:`CommitLogCorruption` on an otherwise healthy log. A ``kind`` value
was considered and rejected as the discriminator: ``kind`` on a plain
``append_cas`` entry is *also* a caller-supplied ``CommandType`` (via
``CommitEntry.kind``), so a caller could equally well set ``kind`` to
whatever value this module might have picked to mean "reservation
transition" — ``kind`` cannot distinguish "went through
:meth:`apply_reservation_transition`" from "a plain ``append_cas`` caller
chose a matching ``CommandType``" any more than payload shape can. The fix
is a dedicated ``entries.is_reservation_transition`` column instead:
:meth:`_insert_entry_and_reservation` sets it to ``1`` iff its own internal
``reservation_update`` parameter is not ``None`` — a value :meth:`append_cas`
NEVER supplies (it always passes ``reservation_update=None``) and that is
not exposed as a public parameter of either :meth:`append_cas` or
:meth:`apply_reservation_transition`, so no caller of the public API can
ever set it, regardless of what ``payload_json``/``kind`` they choose.
:func:`~tos_runtime.rcl.gates.fold_reservations_from_entries` reads only
rows where this column is ``1``.

**Evidence may over-record, but never under-records, on a post-evidence RCL
failure (independent review LOW, 2026-09-08).** :meth:`_append_evidence_or_refuse`
calls ``self._evidence_port.append(...)`` — a durable write to the EVIDENCE
STORE'S OWN, separate sqlite file/connection (design #40 D3.1 "장애 도메인
분리") — before this log's own ``COMMIT``. If the evidence append succeeds
but something afterward in THIS transaction fails (the ``crash_hook``
raising, or ``COMMIT`` itself raising a genuine :class:`sqlite3.Error`), this
log's own ``ROLLBACK`` undoes the ``entries``/``reservations`` rows, but
CANNOT undo the evidence store's already-committed record (it lives in a
different file entirely — that is the whole point of D3.1's domain
separation). The result: the evidence store may hold a record for an entry
that, from this log's perspective, never existed. This is the deliberately
CONSERVATIVE direction and is accepted as-is (an evidence record for an
attempt that was later abandoned is over-reporting, never a lie of
omission) — but the reverse can never happen: this log never holds an entry
without a PRIOR successful evidence append (the evidence-append failure
path, just above, refuses and rolls back before any entries/reservations row
is left committed). See
``test_evidence_over_records_but_never_under_records_on_post_evidence_rollback``.

**Reservation-lifecycle refusal is a separate, runtime-local vocabulary
(anti-phantom decision).** :meth:`apply_reservation_transition` gates a
transition through THREE kernel predicates
(:func:`tos.rcl.reservation_transition_structurally_legal`,
:func:`tos.rcl.transition_allowed`, :func:`tos.rcl.release_admissible`) whose
failure is not one of the kernel's own closed
``tos.rcl.AppendRefusalReason`` members (that enum's seven members are
CAS-fencing / idempotency / storage-failure reasons — none of them means "this
transition shape is not on the ADR-002-002 §10.2 whitelist" or "this cause
does not authorize a less-conservative move" or "release needs a finality
witness that was not supplied"). Force-fitting one of the seven existing
reasons onto a semantically different refusal would silently overload it (the
same anti-phantom discipline the kernel module's own docstring applies to
``WriterEpoch``/``CapacityState``). This module therefore raises
:class:`ReservationTransitionRefusal` (carrying a runtime-local
:class:`ReservationRefusalReason`) for those three gates instead, and reserves
``AppendRefusal``/the kernel's closed reasons for the CAS-append mechanics
that DO map onto it (stale epoch, seq mismatch, duplicate command, store
unavailable, partial commit).

**Writer fencing beyond the kernel Protocol.** ``current_epoch``/
``append_cas``/``read_linearizable``/``replay`` are exactly the kernel
``CommitLog`` Protocol's four methods (this class satisfies it structurally —
see ``test_sqlite_commit_log_satisfies_commitlog_protocol``).
:meth:`acquire_epoch`, :meth:`apply_reservation_transition`,
:meth:`verify_replay`, :meth:`latest_runtime_generation`,
:meth:`reservation_rows`, and :meth:`close` are runtime-only extensions the
Protocol does not require or forbid (extra methods never break structural
conformance to a narrower ``Protocol``).

**OS file locking is advisory only, never relied upon (D2.1).** An optional
:meth:`try_acquire_advisory_flock` uses stdlib ``fcntl.flock`` in
non-blocking mode as a best-effort hint; it is never called automatically by
:meth:`__init__` (acquiring a whole-file ``flock`` unconditionally risks
interacting unpredictably with sqlite's own internal file locking on some
platforms) and every correctness guarantee above comes from the
``BEGIN IMMEDIATE``/epoch-fencing discipline, never from this lock.

Firewall: stdlib (``sqlite3``, ``json``, ``time``, ``fcntl``) + ``pydantic``
(transitively, via ``tos.rcl``/``tos.canonical``/``tos.workload`` models) +
``tos.canonical``/``tos.rcl``/``tos.workload`` + ``tos_runtime.evidence``
(the ``EvidenceAppendPort`` seam) + ``tos_runtime.rcl`` (self — ``schema``/
``gates`` siblings; ``schema`` also carries the schema-ledger boot check) only (R1 allowlist).
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable, Iterator
from pathlib import Path

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.rcl import (
    AppendReceipt,
    AppendRefusal,
    AppendRefusalReason,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    CommitEntry,
    LogView,
    ReservationScope,
    TransitionCause,
    WriterEpoch,
    replay_reproduces_state,
    stale_writer_epoch,
)
from tos.workload import RuntimeIdentity

from tos_runtime.evidence.ports import EvidenceAppendPort
from tos_runtime.operations.schema_ledger import file_is_fresh
from tos_runtime.rcl.gates import (
    ReservationRefusalReason,
    ReservationTransitionRefusal,
    check_reservation_from_state,
    classify_duplicate_command,
    digest_of_reservation_map,
    existing_command_row,
    fold_reservations_from_entries,
    reservation_lifecycle_refusal,
    row_to_commit_entry,
)
from tos_runtime.rcl.schema import (
    CREATE_ENTRIES_TABLE_SQL,
    CREATE_EPOCHS_TABLE_SQL,
    CREATE_RESERVATIONS_TABLE_SQL,
    NO_MUTATION_TRIGGERS_SQL,
    apply_schema_ledger,
)

__all__ = [
    "CommitLogCorruption",
    "InjectedCrash",
    "ReservationRefusalReason",
    "ReservationTransitionRefusal",
    "SqliteCommitLog",
    "StaleEpochRead",
]

#: See the module docstring's "canonicalization version note" analog in
#: ``tos_runtime.evidence.store`` — same convention, same reason: no Phase-2
#: canonicalization scheme is registered yet, so this reuses the one existing
#: registered EV-L1 provisional scheme for the reservations-state digest
#: :meth:`SqliteCommitLog.verify_replay` folds and compares.
_CANONICALIZATION_VERSION = EV_L1_PROVISIONAL_VERSION

#: ``(reservation_id, claimed_from_state, to_state, scope)``, or ``None`` for
#: a plain :meth:`SqliteCommitLog.append_cas` call.
_ReservationUpdate = tuple[str, CapacityState, CapacityState, ReservationScope] | None


class CommitLogCorruption(RuntimeError):
    """Raised by :meth:`SqliteCommitLog.verify_replay` on fold/held disagreement (fault ⑤)."""


class InjectedCrash(RuntimeError):
    """Raised by a test-supplied ``crash_hook`` to simulate a process death (fault ④).

    Never raised by production code paths — this module only *calls* the
    injected hook; the hook itself decides whether, and with what, to raise.
    """


class StaleEpochRead(RuntimeError):
    """Raised by :meth:`SqliteCommitLog.read_linearizable` on a stale epoch (fault ①).

    The kernel ``CommitLog.read_linearizable`` Protocol signature returns
    only ``LogView`` (no ``AppendRefusal`` union) — a stale read therefore
    cannot be represented as a return value and must be an exception instead
    (slice plan §1 item 3: "stale epoch 는 읽기도 거부 (``AppendRefusal``
    반환 또는 전용 예외 — Protocol 시그니처를 따른다)").
    """

    def __init__(self, reason: AppendRefusalReason) -> None:
        super().__init__(f"read_linearizable refused: {reason}")
        self.reason = reason


class SqliteCommitLog:
    """The linearizable Safety Commit Log (design #40 D2.1) — satisfies ``tos.rcl.CommitLog``.

    One sqlite3 file (``journal_mode=WAL``, ``synchronous=FULL``, separate
    from the evidence store's own file). Every mutation happens inside
    ``BEGIN IMMEDIATE`` ... ``COMMIT`` so a concurrent writer is serialized
    rather than corrupting the file, and every failure path issues
    ``ROLLBACK`` before returning a refusal (fault ⑦).
    """

    def __init__(
        self,
        path: Path,
        *,
        evidence_port: EvidenceAppendPort,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        crash_hook: Callable[[str], None] | None = None,
        canonicalization_version: str = _CANONICALIZATION_VERSION,
        sqlite_timeout_s: float = 5.0,
    ) -> None:
        """Open (or create) the commit log at ``path``.

        Args:
            path: The sqlite file path — MUST be a different file from any
                evidence store the caller also opens (design #40 D3.1 "장애
                도메인 분리"; this module does not itself check that, the
                caller is responsible for passing distinct paths).
            evidence_port: The injected durable-append seam every committed
                transition is evidenced through, inside the same RCL
                transaction (slice plan §1 item 1 (f)).
            monotonic_ns: Injected monotonic-clock callable for
                ``epochs.issued_at_monotonic_ns`` — record-only, never used
                to order anything (fault ⑥).
            crash_hook: Test-only crash-injection callable (fault ④); see
                the module docstring's fault-contract table. ``None`` in
                production.
            canonicalization_version: The registered ``tos.canonical``
                scheme version used by :meth:`verify_replay`'s digest.
            sqlite_timeout_s: sqlite3's own busy-timeout — how long a write
                retries against a file another connection holds locked
                before raising :class:`sqlite3.OperationalError` (fault ③).
                Lowered to ``0`` in tests so a locked-file refusal is
                observed immediately instead of after the 5s stdlib default.
        """
        self.path = path
        self._evidence_port = evidence_port
        self._monotonic_ns = monotonic_ns
        self._crash_hook = crash_hook
        self._canon_scheme = get_scheme(canonicalization_version)
        self._advisory_lock_fd: int | None = None
        self._conn = sqlite3.connect(
            str(path), isolation_level=None, timeout=sqlite_timeout_s
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        was_fresh = file_is_fresh(self._conn)  # before any CREATE TABLE below
        self._conn.execute(CREATE_EPOCHS_TABLE_SQL)
        self._conn.execute(CREATE_ENTRIES_TABLE_SQL)
        self._conn.execute(CREATE_RESERVATIONS_TABLE_SQL)
        for trigger_sql in NO_MUTATION_TRIGGERS_SQL:
            self._conn.execute(trigger_sql)
        apply_schema_ledger(self._conn, was_fresh=was_fresh, monotonic_ns=monotonic_ns)

    # -- lifecycle -------------------------------------------------------

    def close(self) -> None:
        """Close the underlying sqlite3 connection (and any advisory lock fd)."""
        if self._advisory_lock_fd is not None:
            import os

            os.close(self._advisory_lock_fd)
            self._advisory_lock_fd = None
        self._conn.close()

    def try_acquire_advisory_flock(self) -> bool:
        """Best-effort, non-blocking ``fcntl.flock`` on this log's file (D2.1 "보조").

        Never relied upon for correctness — see the module docstring.
        Returns ``False`` (never raises) on any failure, including a
        platform with no ``fcntl`` module.

        Returns:
            ``True`` iff the advisory exclusive lock was acquired.
        """
        try:
            import fcntl
            import os

            fd = os.open(str(self.path), os.O_RDWR)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        except ImportError:
            return False
        self._advisory_lock_fd = fd
        return True

    # -- writer fencing (D2.1 item 2) ------------------------------------

    def acquire_epoch(
        self, identity: RuntimeIdentity, *, runtime_generation: int | None = None
    ) -> WriterEpoch:
        """Atomically issue a new, strictly-greater Writer Epoch (fault ①).

        Args:
            identity: The acquiring process's :class:`RuntimeIdentity` —
                recorded (not equated with the epoch) on the new row.
            runtime_generation: Design #40 §3's own D4 workload generation,
                recorded alongside the epoch in the SAME row without being
                equated with it (design #40 v1.1 note ②: "두 epoch 를
                증명 없이 결합하지 않는다"). :meth:`latest_runtime_generation`
                reads this column back for ``tos_runtime.time.generation``'s
                ``seed_from`` helper.

        Returns:
            The newly acquired :data:`~tos.rcl.WriterEpoch`.
        """
        issued_at_ns = self._monotonic_ns()
        identity_json = json.dumps(identity.model_dump(mode="json"), sort_keys=True)
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(epoch), 0) FROM epochs"
            ).fetchone()
            new_epoch = int(row[0]) + 1
            self._conn.execute(
                "INSERT INTO epochs (epoch, issued_at_monotonic_ns, "
                "runtime_generation, runtime_identity_json) VALUES (?, ?, ?, ?)",
                (new_epoch, issued_at_ns, runtime_generation, identity_json),
            )
            self._conn.execute("COMMIT")
        except BaseException:
            self._safe_rollback()
            raise
        return new_epoch

    def current_epoch(self) -> WriterEpoch:
        """Return the currently active Writer Epoch, or ``0`` if none was ever acquired."""
        row = self._conn.execute(
            "SELECT COALESCE(MAX(epoch), 0) FROM epochs"
        ).fetchone()
        return int(row[0])

    def latest_runtime_generation(self) -> int | None:
        """The ``runtime_generation`` recorded on the most recent ``epochs`` row.

        Used by ``tos_runtime.time.generation.seed_from`` (slice plan §3) —
        NEVER equated with :meth:`current_epoch`'s own value (design #40
        v1.1 note ②).

        Returns:
            The most recent recorded generation, or ``None`` if no epoch was
            ever acquired, or the most recent acquisition did not record one.
        """
        row = self._conn.execute(
            "SELECT runtime_generation FROM epochs ORDER BY epoch DESC LIMIT 1"
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return int(row[0])

    # -- append / read (kernel CommitLog Protocol) ------------------------

    def append_cas(
        self,
        entry: CommitEntry,
        *,
        expected_seq: int,
        writer_epoch: WriterEpoch,
        payload_json: str | None = None,
    ) -> AppendReceipt | AppendRefusal:
        """Compare-and-set append (kernel ``CommitLog.append_cas``; faults ①②③④⑥⑦).

        Args:
            entry: The command to append. ``entry.command_id`` is required
                (fail-closed if absent — nothing to key idempotency on).
            expected_seq: The log's current tip, as the caller last observed
                it (``-1`` for an empty log) — the CAS fence (fault ⑦'s
                sibling "부분 커밋" concern's positive-admission half).
            writer_epoch: The Writer Epoch this write is fenced under.
            payload_json: Optional caller-supplied raw payload, stored
                alongside the entry (an extra keyword-only argument beyond
                the kernel Protocol's three — a wider signature is still a
                satisfying implementation of the narrower Protocol, same
                convention as ``tos_runtime.evidence.store``'s ``append``).

        Returns:
            An :class:`~tos.rcl.AppendReceipt` on durable commit, or a
            structural :class:`~tos.rcl.AppendRefusal` — never both, never
            neither.
        """
        if entry.command_id is None:
            return AppendRefusal(
                reason=AppendRefusalReason.COMMAND_BYTES_MISMATCH,
                detail="CommitEntry.command_id is required to append (fail-closed)",
            )
        return self._commit_entry(
            expected_seq=expected_seq,
            writer_epoch=writer_epoch,
            command_id=entry.command_id,
            command_digest=entry.command_digest,
            kind=entry.kind.value if entry.kind is not None else None,
            payload_digest=entry.payload_digest,
            payload_json=payload_json,
            evidence_kind="RCL_APPEND",
            evidence_record_class="RCL_ENTRY",
            reservation_update=None,
        )

    def read_linearizable(self, *, writer_epoch: WriterEpoch) -> LogView:
        """Linearizable read snapshot (kernel ``CommitLog.read_linearizable``; fault ①).

        Raises:
            StaleEpochRead: If ``writer_epoch`` is not the current epoch,
                checked in the same transaction as the ``seq`` snapshot.
        """
        self._conn.execute("BEGIN")
        try:
            current = self.current_epoch()
            stale_reason = stale_writer_epoch(current, writer_epoch)
            if stale_reason is not None:
                raise StaleEpochRead(stale_reason)
            tip = self._current_seq_tip()
            rows = self._conn.execute(
                "SELECT seq, writer_epoch, command_id, command_digest, kind, "
                "payload_digest FROM entries ORDER BY seq ASC"
            ).fetchall()
            self._conn.execute("COMMIT")
        except BaseException:
            self._safe_rollback()
            raise
        entries = tuple(row_to_commit_entry(row) for row in rows)
        return LogView(
            epoch=current, last_seq=(None if tip < 0 else tip), entries=entries
        )

    def replay(self) -> Iterator[CommitEntry]:
        """Replay the full committed log in commit order (kernel ``CommitLog.replay``; fault ⑤)."""
        rows = self._conn.execute(
            "SELECT seq, writer_epoch, command_id, command_digest, kind, "
            "payload_digest FROM entries ORDER BY seq ASC"
        ).fetchall()
        for row in rows:
            yield row_to_commit_entry(row)

    # -- reservation lifecycle (D2.1 item 4) ------------------------------

    def apply_reservation_transition(
        self,
        transition: CapacityReservationTransition,
        cause: TransitionCause,
        *,
        command_type: CommandType,
        command_id: str,
        command_digest: str | None,
        expected_seq: int,
        finality_witness: bool | None = None,
    ) -> AppendReceipt | AppendRefusal:
        """Commit one reservation-lifecycle transition (D2.1 item 4).

        Gates through :func:`~tos_runtime.rcl.gates.reservation_lifecycle_refusal`
        (structural whitelist, cause admissibility, finality-witness — moved
        to ``gates.py`` for the 100-line function size budget, laneO
        port-fix round, 2026-09-08).

        Args:
            transition: The proposed transition (``reservation_id``,
                ``from_state``, ``to_state``, ``writer_epoch``, ``scope`` —
                all required, checked here).
            cause: The :class:`~tos.rcl.TransitionCause` driving it.
            command_type: The ``CommandType`` recorded as the entry's
                ``kind`` (caller-supplied — this module does not infer a
                command type from the state pair; see the module docstring).
            command_id: The idempotency key for this transition command.
            command_digest: The canonical digest of the command bytes.
            expected_seq: The log's current tip, as the caller last observed it.
            finality_witness: The broker-truth / evidence witness for a
                finality destination, or ``None``.

        Returns:
            An :class:`~tos.rcl.AppendReceipt` or CAS-level
            :class:`~tos.rcl.AppendRefusal` (mechanics, not lifecycle gates).

        Raises:
            ReservationTransitionRefusal: If any of the three lifecycle
                gates refuses (see the module docstring's anti-phantom note
                on why these are not ``AppendRefusal``).
        """
        gate_failure = reservation_lifecycle_refusal(
            transition, cause, finality_witness
        )
        if gate_failure is not None:
            raise ReservationTransitionRefusal(*gate_failure)
        from_state = transition.from_state
        to_state = transition.to_state
        writer_epoch = transition.writer_epoch
        if (
            transition.reservation_id is None
            or writer_epoch is None
            or transition.scope is None
            or from_state is None
            or to_state is None
        ):
            # from_state/to_state None is unreachable (the gate above always
            # refuses it first) — kept so mypy narrows both to non-None below.
            return AppendRefusal(
                reason=AppendRefusalReason.COMMAND_BYTES_MISMATCH,
                detail=(
                    "transition.reservation_id, .writer_epoch, .scope, "
                    ".from_state, and .to_state are required"
                ),
            )
        payload_json = json.dumps(
            {
                "reservation_id": transition.reservation_id,
                "from_state": from_state.value,
                "to_state": to_state.value,
                "cause": cause.value,
                "finality_witness": finality_witness,
                "scope": {
                    "account": transition.scope.account,
                    "instrument": transition.scope.instrument,
                },
            },
            sort_keys=True,
        )
        return self._commit_entry(
            expected_seq=expected_seq,
            writer_epoch=writer_epoch,
            command_id=command_id,
            command_digest=command_digest,
            kind=command_type.value,
            payload_digest=None,
            payload_json=payload_json,
            evidence_kind="RCL_RESERVATION_TRANSITION",
            evidence_record_class="RCL_RESERVATION",
            reservation_update=(
                transition.reservation_id,
                from_state,
                to_state,
                transition.scope,
            ),
        )

    def reservation_rows(
        self,
    ) -> Iterator[tuple[str, CapacityState, int, ReservationScope]]:
        """Yield every held ``(reservation_id, state, last_seq, scope)`` — the projection's read shape."""
        rows = self._conn.execute(
            "SELECT reservation_id, state, last_seq, scope_account, "
            "scope_instrument FROM reservations ORDER BY reservation_id ASC"
        ).fetchall()
        for reservation_id, state, last_seq, scope_account, scope_instrument in rows:
            yield (
                reservation_id,
                CapacityState(state),
                int(last_seq),
                ReservationScope(account=scope_account, instrument=scope_instrument),
            )

    # -- replay / corruption detection (fault ⑤) --------------------------

    def verify_replay(self) -> None:
        """Independently re-fold entries and compare against the held projection (fault ⑤).

        Raises:
            CommitLogCorruption: If the replayed reservations-state digest
                disagrees with the ``reservations`` table's own digest
                (:func:`tos.rcl.replay_reproduces_state` — fail-closed on
                any disagreement, never a partial pass).
        """
        held = {
            reservation_id: {
                "state": state.value,
                "scope_account": scope.account,
                "scope_instrument": scope.instrument,
            }
            for reservation_id, state, _seq, scope in self.reservation_rows()
        }
        held_digest = digest_of_reservation_map(self._canon_scheme, held)
        replayed_digest = digest_of_reservation_map(
            self._canon_scheme, fold_reservations_from_entries(self._conn)
        )
        reason = replay_reproduces_state(replayed_digest, held_digest)
        if reason is not None:
            raise CommitLogCorruption(
                f"SqliteCommitLog.verify_replay: {reason} for {self.path} — replayed "
                "reservations state disagrees with the held projection (non-live "
                "disposition is the caller's responsibility, ADR-002-012 :491)"
            )

    # -- internals ---------------------------------------------------------

    def _current_seq_tip(self) -> int:
        """The current log tip: the last committed ``seq``, or ``-1`` if empty.

        Deliberately re-read from disk every call (never a Python-side
        counter) — the durable table is the only source of truth, matching
        ``tos_runtime.evidence.store``'s own ``_read_tail`` discipline.
        """
        row = self._conn.execute("SELECT MAX(seq) FROM entries").fetchone()
        return -1 if row is None or row[0] is None else int(row[0])

    def _safe_rollback(self) -> None:
        try:
            self._conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    def _pre_insert_checks(
        self,
        *,
        writer_epoch: WriterEpoch,
        expected_seq: int,
        command_id: str,
        command_digest: str | None,
        reservation_update: _ReservationUpdate,
    ) -> AppendRefusal | None:
        """Fence + CAS + duplicate + reservation-gate checks, in that order.

        Split out of :meth:`_commit_entry` for the 100-line function size
        budget (operator size-budget decomposition, 2026-09-08) — the
        transaction boundary is UNCHANGED: this must still be called from
        inside the same ``BEGIN IMMEDIATE`` transaction :meth:`_commit_entry`
        holds (every read here — ``current_epoch()``, ``_current_seq_tip()``,
        the ``reservations`` lookup — is consistent only within that one
        transaction), and nothing is written by this method itself (faults
        ①②, HIGH-1).

        Returns:
            An :class:`~tos.rcl.AppendRefusal` the instant any check fails
            (nothing yet written), or ``None`` to proceed with the insert.
        """
        current = self.current_epoch()
        stale_reason = stale_writer_epoch(current, writer_epoch)
        if stale_reason is not None:
            return AppendRefusal(reason=stale_reason)
        tip = self._current_seq_tip()
        if expected_seq != tip:
            return AppendRefusal(
                reason=AppendRefusalReason.SEQ_MISMATCH,
                detail=f"expected_seq={expected_seq} but log tip is {tip}",
            )
        row_exists, existing_digest = existing_command_row(self._conn, command_id)
        dup_reason = classify_duplicate_command(
            row_exists, existing_digest, command_digest
        )
        if dup_reason is not None:
            return AppendRefusal(reason=dup_reason)
        if reservation_update is not None:
            reservation_id, claimed_from_state, _to_state, _scope = reservation_update
            from_state_refusal = check_reservation_from_state(
                self._conn, reservation_id, claimed_from_state
            )
            if from_state_refusal is not None:
                return from_state_refusal
        return None

    def _insert_entry_and_reservation(
        self,
        *,
        next_seq: int,
        writer_epoch: WriterEpoch,
        command_id: str,
        command_digest: str | None,
        kind: str | None,
        payload_digest: str | None,
        payload_json: str | None,
        reservation_update: _ReservationUpdate,
    ) -> None:
        """``INSERT`` the ``entries`` row (+ ``UPSERT`` ``reservations``, if applicable).

        Split out of :meth:`_commit_entry` for the 100-line function size
        budget — the transaction boundary is UNCHANGED: this must still run
        inside the same ``BEGIN IMMEDIATE`` transaction as the rest of
        :meth:`_commit_entry`; it neither begins nor commits/rolls back
        anything itself. ``is_reservation_transition`` is derived ONLY from
        ``reservation_update`` — never from ``payload_json``/``kind``, and
        never settable by a public caller (independent review MEDIUM-4; see
        the module docstring's "replay fold is discriminated, not
        payload-shape-matched" section).
        """
        self._conn.execute(
            "INSERT INTO entries (seq, writer_epoch, command_id, command_digest, "
            "kind, payload_digest, payload_json, is_reservation_transition) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                next_seq,
                writer_epoch,
                command_id,
                command_digest,
                kind,
                payload_digest,
                payload_json,
                1 if reservation_update is not None else 0,
            ),
        )
        if reservation_update is not None:
            reservation_id, _claimed_from_state, to_state, scope = reservation_update
            self._conn.execute(
                "INSERT INTO reservations (reservation_id, state, last_seq, "
                "scope_account, scope_instrument) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(reservation_id) DO UPDATE SET "
                "state=excluded.state, last_seq=excluded.last_seq, "
                "scope_account=excluded.scope_account, "
                "scope_instrument=excluded.scope_instrument",
                (
                    reservation_id,
                    to_state.value,
                    next_seq,
                    scope.account,
                    scope.instrument,
                ),
            )

    def _append_evidence_or_refuse(
        self,
        *,
        next_seq: int,
        writer_epoch: WriterEpoch,
        command_id: str,
        command_digest: str | None,
        kind: str | None,
        evidence_kind: str,
        evidence_record_class: str,
    ) -> AppendRefusal | None:
        """Durably evidence this append; on failure, roll back and refuse (D2.1 item 1(f)).

        Split out of :meth:`_commit_entry` for the 100-line function size
        budget — the transaction boundary is UNCHANGED: this must still run
        inside the same ``BEGIN IMMEDIATE`` transaction as the rest of
        :meth:`_commit_entry`, strictly BEFORE that method's own ``COMMIT``.
        Durably committed to the EVIDENCE STORE'S OWN, separate file/
        connection (D3.1 domain separation) — a later failure in THIS
        transaction rolls back only the RCL side, so evidence may
        over-record an attempt this log itself never holds, but never the
        reverse (independent review LOW, 2026-09-08; see the module
        docstring's "evidence may over-record" section).

        Returns:
            An :class:`~tos.rcl.AppendRefusal` (already rolled back) if the
            evidence append raised, else ``None`` to proceed to ``COMMIT``.
        """
        try:
            self._evidence_port.append(
                {
                    "seq": next_seq,
                    "writer_epoch": writer_epoch,
                    "command_id": command_id,
                    "command_digest": command_digest,
                    "kind": kind,
                },
                kind=evidence_kind,
                record_class=evidence_record_class,
            )
        except (
            Exception
        ) as evidence_error:  # noqa: BLE001 - any evidence failure refuses
            self._safe_rollback()
            return AppendRefusal(
                reason=AppendRefusalReason.STORE_UNAVAILABLE,
                detail=(
                    "evidence append failed, entry not committed (D2.1 item 1(f)): "
                    f"{evidence_error!r}"
                ),
            )
        return None

    def _commit_entry(
        self,
        *,
        expected_seq: int,
        writer_epoch: WriterEpoch,
        command_id: str,
        command_digest: str | None,
        kind: str | None,
        payload_digest: str | None,
        payload_json: str | None,
        evidence_kind: str,
        evidence_record_class: str,
        reservation_update: _ReservationUpdate,
    ) -> AppendReceipt | AppendRefusal:
        """The whole durable-append body: fence, CAS, insert, evidence, commit (faults ①②③④⑥⑦).

        Delegates to :meth:`_pre_insert_checks`,
        :meth:`_insert_entry_and_reservation`, and
        :meth:`_append_evidence_or_refuse` (a size-budget decomposition,
        2026-09-08) — but the ``BEGIN IMMEDIATE`` ... ``COMMIT`` transaction
        boundary is exactly what it always was: all three run synchronously,
        in this order, inside the ONE ``try`` block below, on the same
        connection, before this method's own ``COMMIT``. No transaction
        boundary changed.

        Args:
            reservation_update: See :data:`_ReservationUpdate`. When
                present, :meth:`_pre_insert_checks` gates the claimed
                ``from_state`` against the held record before anything is
                written (independent review HIGH-1, 2026-09-08).
        """
        try:
            self._conn.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            return AppendRefusal(
                reason=AppendRefusalReason.STORE_UNAVAILABLE,
                detail=f"cannot start transaction: {exc!r}",
            )
        try:
            refusal = self._pre_insert_checks(
                writer_epoch=writer_epoch,
                expected_seq=expected_seq,
                command_id=command_id,
                command_digest=command_digest,
                reservation_update=reservation_update,
            )
            if refusal is not None:
                self._conn.execute("ROLLBACK")
                return refusal
            next_seq = self._current_seq_tip() + 1
            self._insert_entry_and_reservation(
                next_seq=next_seq,
                writer_epoch=writer_epoch,
                command_id=command_id,
                command_digest=command_digest,
                kind=kind,
                payload_digest=payload_digest,
                payload_json=payload_json,
                reservation_update=reservation_update,
            )
            evidence_refusal = self._append_evidence_or_refuse(
                next_seq=next_seq,
                writer_epoch=writer_epoch,
                command_id=command_id,
                command_digest=command_digest,
                kind=kind,
                evidence_kind=evidence_kind,
                evidence_record_class=evidence_record_class,
            )
            if evidence_refusal is not None:
                return evidence_refusal
            if self._crash_hook is not None:
                self._crash_hook("before_commit")
            self._conn.execute("COMMIT")
        except InjectedCrash:
            self._safe_rollback()
            raise
        except sqlite3.Error as exc:
            self._safe_rollback()
            return AppendRefusal(
                reason=AppendRefusalReason.PARTIAL_COMMIT_SUSPECTED, detail=repr(exc)
            )
        if self._crash_hook is not None:
            self._crash_hook("after_commit_before_receipt")
        return AppendReceipt(seq=next_seq, writer_epoch=writer_epoch, durable=True)
