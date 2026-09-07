"""``SqliteCommitLog`` — the linearizable Safety Commit Log (design #40 D2.1, §2 item 1).

Implements the kernel's ``tos.rcl.commitlog.CommitLog`` Protocol
(``current_epoch``/``append_cas``/``read_linearizable``/``replay``) over a
single sqlite3 file, **separate from the evidence store's own file** (design
#40 D3.1 "장애 도메인 분리"): ``journal_mode=WAL``, ``synchronous=FULL``, every
mutation inside ``BEGIN IMMEDIATE`` ... ``COMMIT``.

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
         last-write-wins).
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
(the ``EvidenceAppendPort`` seam) only (R1 allowlist).
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable, Iterator, Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

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
    TransitionCause,
    WriterEpoch,
    duplicate_command,
    release_admissible,
    replay_reproduces_state,
    reservation_transition_structurally_legal,
    stale_writer_epoch,
    transition_allowed,
)
from tos.workload import RuntimeIdentity

from tos_runtime.evidence.ports import EvidenceAppendPort

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

_CREATE_EPOCHS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS epochs (
    epoch INTEGER PRIMARY KEY,
    issued_at_monotonic_ns INTEGER NOT NULL,
    runtime_generation INTEGER,
    runtime_identity_json TEXT
)
"""

_CREATE_ENTRIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    seq INTEGER PRIMARY KEY,
    writer_epoch INTEGER NOT NULL,
    command_id TEXT NOT NULL UNIQUE,
    command_digest TEXT,
    kind TEXT,
    payload_digest TEXT,
    payload_json TEXT
)
"""

_CREATE_RESERVATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    last_seq INTEGER NOT NULL
)
"""

_NO_MUTATION_TRIGGERS_SQL: tuple[str, ...] = (
    """
    CREATE TRIGGER IF NOT EXISTS epochs_no_update
    BEFORE UPDATE ON epochs
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: epochs is append-only — UPDATE forbidden');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS epochs_no_delete
    BEFORE DELETE ON epochs
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: epochs is append-only — DELETE forbidden');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS entries_no_update
    BEFORE UPDATE ON entries
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: entries is append-only — UPDATE forbidden');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS entries_no_delete
    BEFORE DELETE ON entries
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: entries is append-only — DELETE forbidden');
    END
    """,
    # reservations is the ONE mutable projection table (design #40 D2.1 "컴팩션/
    # 보존: 항목 삭제 0" + slice plan §1 item 6 "reservations 만 UPDATE 허용
    # (그것이 투영)") — UPDATE is deliberately NOT blocked here; only DELETE is.
    """
    CREATE TRIGGER IF NOT EXISTS reservations_no_delete
    BEFORE DELETE ON reservations
    BEGIN
        SELECT RAISE(ABORT, 'tos_runtime rcl log: reservations rows are never deleted');
    END
    """,
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


class ReservationRefusalReason(StrEnum):
    """Runtime-local (NOT the kernel's closed) reservation-lifecycle refusal reasons.

    See the module docstring's "reservation-lifecycle refusal is a separate,
    runtime-local vocabulary" section for why these are not force-fit onto
    ``tos.rcl.AppendRefusalReason``.
    """

    NOT_STRUCTURALLY_LEGAL = "NOT_STRUCTURALLY_LEGAL"
    CAUSE_NOT_ADMISSIBLE = "CAUSE_NOT_ADMISSIBLE"
    FINALITY_WITNESS_REQUIRED = "FINALITY_WITNESS_REQUIRED"


class ReservationTransitionRefusal(RuntimeError):
    """Raised by :meth:`SqliteCommitLog.apply_reservation_transition` on a lifecycle gate refusal."""

    def __init__(self, reason: ReservationRefusalReason, detail: str = "") -> None:
        super().__init__(f"reservation transition refused: {reason} {detail}".strip())
        self.reason = reason


def _row_to_commit_entry(row: tuple[Any, ...]) -> CommitEntry:
    """Build a :class:`~tos.rcl.CommitEntry` from one ``entries`` row (shared by replay/read)."""
    seq, writer_epoch, command_id, command_digest, kind, payload_digest = row
    return CommitEntry(
        seq=seq,
        writer_epoch=writer_epoch,
        command_id=command_id,
        command_digest=command_digest,
        kind=CommandType(kind) if kind is not None else None,
        payload_digest=payload_digest,
    )


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
        self._conn.execute(_CREATE_EPOCHS_TABLE_SQL)
        self._conn.execute(_CREATE_ENTRIES_TABLE_SQL)
        self._conn.execute(_CREATE_RESERVATIONS_TABLE_SQL)
        for trigger_sql in _NO_MUTATION_TRIGGERS_SQL:
            self._conn.execute(trigger_sql)

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
        entries = tuple(_row_to_commit_entry(row) for row in rows)
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
            yield _row_to_commit_entry(row)

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

        Gates through, in order: :func:`tos.rcl.reservation_transition_structurally_legal`
        (the ADR-002-002 §10.1 whitelist), :func:`tos.rcl.transition_allowed`
        (the cause-specific conservatism check), and — only for a
        RELEASED/POSITION_CONSUMED destination —
        :func:`tos.rcl.release_admissible` (the finality-witness gate).

        Args:
            transition: The proposed transition (``reservation_id``,
                ``from_state``, ``to_state``, ``writer_epoch`` — all
                required, checked here).
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
        from_state = transition.from_state
        to_state = transition.to_state
        writer_epoch = transition.writer_epoch
        if not reservation_transition_structurally_legal(from_state, to_state):
            raise ReservationTransitionRefusal(
                ReservationRefusalReason.NOT_STRUCTURALLY_LEGAL,
                f"({from_state} -> {to_state}) is not on the closed whitelist",
            )
        if (
            from_state is None
            or to_state is None
            or not transition_allowed(from_state, to_state, cause)
        ):
            raise ReservationTransitionRefusal(
                ReservationRefusalReason.CAUSE_NOT_ADMISSIBLE,
                f"cause {cause} does not authorize ({from_state} -> {to_state})",
            )
        if not release_admissible(transition, finality_witness):
            raise ReservationTransitionRefusal(
                ReservationRefusalReason.FINALITY_WITNESS_REQUIRED,
                f"destination {to_state} requires finality_witness is True",
            )
        if transition.reservation_id is None or writer_epoch is None:
            return AppendRefusal(
                reason=AppendRefusalReason.COMMAND_BYTES_MISMATCH,
                detail="transition.reservation_id and .writer_epoch are required",
            )
        payload_json = json.dumps(
            {
                "reservation_id": transition.reservation_id,
                "from_state": from_state.value,
                "to_state": to_state.value,
                "cause": cause.value,
                "finality_witness": finality_witness,
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
            reservation_update=(transition.reservation_id, to_state),
        )

    def reservation_rows(self) -> Iterator[tuple[str, CapacityState, int]]:
        """Yield every held ``(reservation_id, state, last_seq)`` — the projection's read shape."""
        rows = self._conn.execute(
            "SELECT reservation_id, state, last_seq FROM reservations "
            "ORDER BY reservation_id ASC"
        ).fetchall()
        for reservation_id, state, last_seq in rows:
            yield reservation_id, CapacityState(state), int(last_seq)

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
            reservation_id: state.value
            for reservation_id, state, _ in self.reservation_rows()
        }
        held_digest = self._digest_of_reservation_map(held)
        replayed_digest = self._digest_of_reservation_map(
            self._fold_reservations_from_entries()
        )
        reason = replay_reproduces_state(replayed_digest, held_digest)
        if reason is not None:
            raise CommitLogCorruption(
                f"SqliteCommitLog.verify_replay: {reason} for {self.path} — replayed "
                "reservations state disagrees with the held projection (non-live "
                "disposition is the caller's responsibility, ADR-002-012 :491)"
            )

    def _fold_reservations_from_entries(self) -> dict[str, str]:
        """Re-derive the final ``{reservation_id: to_state}`` map by replaying every entry."""
        rows = self._conn.execute(
            "SELECT payload_json FROM entries WHERE payload_json IS NOT NULL ORDER BY seq ASC"
        ).fetchall()
        folded: dict[str, str] = {}
        for (payload_json,) in rows:
            payload = json.loads(payload_json)
            reservation_id = payload.get("reservation_id")
            to_state = payload.get("to_state")
            if reservation_id is not None and to_state is not None:
                folded[reservation_id] = to_state
        return folded

    def _digest_of_reservation_map(self, mapping: Mapping[str, str]) -> str:
        """Canonical digest of a ``{reservation_id: state}`` map (sorted, deterministic)."""
        return self._canon_scheme.compute_digest(
            {"reservations": dict(sorted(mapping.items()))}
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

    def _existing_digest_for_command(self, command_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT command_digest FROM entries WHERE command_id = ?", (command_id,)
        ).fetchone()
        return None if row is None else row[0]

    def _safe_rollback(self) -> None:
        try:
            self._conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

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
        reservation_update: tuple[str, CapacityState] | None,
    ) -> AppendReceipt | AppendRefusal:
        """The whole durable-append body: fence, CAS, insert, evidence, commit (faults ①②③④⑥⑦)."""
        try:
            self._conn.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            return AppendRefusal(
                reason=AppendRefusalReason.STORE_UNAVAILABLE,
                detail=f"cannot start transaction: {exc!r}",
            )
        try:
            current = self.current_epoch()
            stale_reason = stale_writer_epoch(current, writer_epoch)
            if stale_reason is not None:
                self._conn.execute("ROLLBACK")
                return AppendRefusal(reason=stale_reason)
            tip = self._current_seq_tip()
            if expected_seq != tip:
                self._conn.execute("ROLLBACK")
                return AppendRefusal(
                    reason=AppendRefusalReason.SEQ_MISMATCH,
                    detail=f"expected_seq={expected_seq} but log tip is {tip}",
                )
            existing_digest = self._existing_digest_for_command(command_id)
            dup_reason = duplicate_command(existing_digest, command_digest)
            if dup_reason is not None:
                self._conn.execute("ROLLBACK")
                return AppendRefusal(reason=dup_reason)
            next_seq = tip + 1
            self._conn.execute(
                "INSERT INTO entries (seq, writer_epoch, command_id, command_digest, "
                "kind, payload_digest, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    next_seq,
                    writer_epoch,
                    command_id,
                    command_digest,
                    kind,
                    payload_digest,
                    payload_json,
                ),
            )
            if reservation_update is not None:
                reservation_id, to_state = reservation_update
                self._conn.execute(
                    "INSERT INTO reservations (reservation_id, state, last_seq) "
                    "VALUES (?, ?, ?) ON CONFLICT(reservation_id) DO UPDATE SET "
                    "state=excluded.state, last_seq=excluded.last_seq",
                    (reservation_id, to_state.value, next_seq),
                )
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
