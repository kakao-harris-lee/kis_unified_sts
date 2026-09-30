"""SQLite implementation of the Safety Commit Log.

The log implements the kernel ``CommitLog`` protocol over its own WAL/FULL
SQLite file, separate from the evidence store. Append and reservation updates
use ``BEGIN IMMEDIATE``; linearizable reads use an explicit transaction and
writer-epoch fencing. Acquiring a writer epoch establishes the writer fence.
Command IDs provide idempotency and byte-mismatch detection; SQLite errors
inside a transaction become explicit refusal outcomes.

Reservation transitions validate the held ``from_state`` in the same
transaction and mark transition rows with an internal discriminator so replay
cannot infer them from caller-controlled payload shape. Evidence is appended
before the RCL commit, so a later rollback may over-record evidence but never
leaves a committed RCL row without its evidence. Replay verification folds
only discriminated transition rows. The optional OS file lock is advisory;
correctness comes from SQLite fencing and writer epochs.
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
    CapacityVector,
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
from tos_runtime.rcl.gates import (
    ReservationRefusalReason,
    ReservationTransitionRefusal,
    align_unrecorded_vectors,
    check_reservation_from_state,
    classify_duplicate_command,
    digest_of_reservation_map,
    existing_command_row,
    fold_reservations_from_entries,
    held_reservation_map,
    reservation_lifecycle_refusal,
    reservation_transition_payload_json,
    row_to_commit_entry,
)
from tos_runtime.rcl.gates import (
    reservation_committed_vector as gates_reservation_committed_vector,
)
from tos_runtime.rcl.gates import reservation_rows as gates_reservation_rows
from tos_runtime.rcl.gates import (
    upsert_reservation_projection as gates_upsert_reservation_projection,
)
from tos_runtime.rcl.schema import apply_schema_ledger

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

#: ``(reservation_id, claimed_from_state, to_state, scope, committed_vector)``, or ``None`` for
#: a plain :meth:`SqliteCommitLog.append_cas` call. ``committed_vector`` (kernel round #4 K-4)
#: is ``None`` when the transition carries no vector — never a zero vector.
_ReservationUpdate = (
    tuple[str, CapacityState, CapacityState, ReservationScope, CapacityVector | None]
    | None
)


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
        # This log's DDL, the freshness decision and the genesis stamp all inside ONE
        # `BEGIN IMMEDIATE` (#801) — `tos_runtime.rcl.schema` owns the statements, and
        # `open_or_create_schema`'s own docstring names the two races that closes.
        apply_schema_ledger(self._conn, monotonic_ns=monotonic_ns)

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
                all required, checked here; ``committed_vector`` — kernel
                round #4 K-4 — is OPTIONAL and persisted as-is, ``None``
                included, never defaulted).
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
        payload_json = reservation_transition_payload_json(
            transition, cause, finality_witness
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
                transition.committed_vector,
            ),
        )

    def reservation_rows(
        self,
    ) -> Iterator[tuple[str, CapacityState, int, ReservationScope]]:
        """Yield every held ``(reservation_id, state, last_seq, scope)`` — the projection's read
        shape (delegates to :func:`~tos_runtime.rcl.gates.reservation_rows`, moved there for
        this module's own 1000-line size budget, kernel round #4 K-4 decomposition)."""
        return gates_reservation_rows(self._conn)

    def reservation_committed_vector(
        self, reservation_id: str
    ) -> CapacityVector | None:
        """The committed Capacity Vector last written for ``reservation_id``, if any (delegates
        to :func:`~tos_runtime.rcl.gates.reservation_committed_vector`, kernel round #4 K-4).
        """
        return gates_reservation_committed_vector(self._conn, reservation_id)

    # -- replay / corruption detection (fault ⑤) --------------------------

    def verify_replay(self) -> None:
        """Independently re-fold entries and compare against the held projection (fault ⑤).

        Raises:
            CommitLogCorruption: If the replayed reservations-state digest
                disagrees with the ``reservations`` table's own digest
                (:func:`tos.rcl.replay_reproduces_state` — fail-closed on
                any disagreement, never a partial pass).
        """
        held = held_reservation_map(self._conn)
        replayed = fold_reservations_from_entries(self._conn)
        align_unrecorded_vectors(held, replayed)
        held_digest = digest_of_reservation_map(self._canon_scheme, held)
        replayed_digest = digest_of_reservation_map(self._canon_scheme, replayed)
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
            (
                reservation_id,
                claimed_from_state,
                _to_state,
                _scope,
                _committed_vector,
            ) = reservation_update
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
        gates_upsert_reservation_projection(
            self._conn, next_seq=next_seq, reservation_update=reservation_update
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
