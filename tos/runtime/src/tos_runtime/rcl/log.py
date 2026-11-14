"""SQLite implementation of the Safety Commit Log."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
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
from tos_runtime.operations.schema_ledger import (
    closing_on_failure,
    enable_wal_journal,
)
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
    "ReservationTransitionHistory",
    "ReservationTransitionHistoryCorruption",
    "ReservationTransitionRecord",
    "SqliteCommitLog",
    "StaleEpochRead",
]

_CANONICALIZATION_VERSION = EV_L1_PROVISIONAL_VERSION

_ReservationUpdate = (
    tuple[str, CapacityState, CapacityState, ReservationScope, CapacityVector | None]
    | None
)


class CommitLogCorruption(RuntimeError):
    """Raised by :meth:`SqliteCommitLog.verify_replay` on fold/held disagreement (fault ⑤)."""


class InjectedCrash(RuntimeError):
    """Raised by a test-supplied ``crash_hook`` to simulate a process death (fault ④)."""


class StaleEpochRead(RuntimeError):
    """Raised by :meth:`SqliteCommitLog.read_linearizable` on a stale epoch (fault ①)."""

    def __init__(self, reason: AppendRefusalReason) -> None:
        super().__init__(f"read_linearizable refused: {reason}")
        self.reason = reason


class ReservationTransitionHistoryCorruption(RuntimeError):
    """Raised when a discriminated RCL transition cannot be read as a closed record."""


@dataclass(frozen=True)
class ReservationTransitionRecord:
    """One strictly decoded, committed reservation transition from the RCL log."""

    seq: int
    command_id: str
    kind: CommandType
    reservation_id: str
    from_state: CapacityState
    to_state: CapacityState
    scope: ReservationScope
    cause: TransitionCause
    finality_witness: bool | None


@dataclass(frozen=True)
class ReservationTransitionHistory:
    """A complete transition-history snapshot taken under one current writer epoch."""

    writer_epoch: WriterEpoch
    last_seq: int | None
    transitions: tuple[ReservationTransitionRecord, ...]


def _no_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate object keys instead of silently accepting the last value."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reservation_transition_record_from_row(
    row: tuple[object, ...],
) -> ReservationTransitionRecord:
    """Decode the closed, append-only payload shape of a discriminated transition row."""
    seq, raw_command_id, raw_kind, payload_json = row
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise ReservationTransitionHistoryCorruption(
            "reservation transition has an invalid committed sequence"
        )
    if not isinstance(raw_command_id, str) or not raw_command_id:
        raise ReservationTransitionHistoryCorruption(
            f"reservation transition seq={seq} has no command id"
        )
    if not isinstance(raw_kind, str) or not isinstance(payload_json, str):
        raise ReservationTransitionHistoryCorruption(
            f"reservation transition seq={seq} has an invalid stored row shape"
        )
    try:
        kind = CommandType(raw_kind)
        payload = json.loads(payload_json, object_pairs_hook=_no_duplicate_json_keys)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ReservationTransitionHistoryCorruption(
            f"reservation transition seq={seq} has invalid command or JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise ReservationTransitionHistoryCorruption(
            f"reservation transition seq={seq} payload is not an object"
        )
    required = {
        "reservation_id",
        "from_state",
        "to_state",
        "cause",
        "finality_witness",
        "scope",
    }
    allowed = required | {"committed_vector"}
    if not required <= payload.keys() or not payload.keys() <= allowed:
        raise ReservationTransitionHistoryCorruption(
            f"reservation transition seq={seq} has an incomplete or unknown payload shape"
        )
    reservation_id = payload["reservation_id"]
    scope_value = payload["scope"]
    witness = payload["finality_witness"]
    if not isinstance(reservation_id, str) or not reservation_id:
        raise ReservationTransitionHistoryCorruption(
            f"reservation transition seq={seq} has no reservation id"
        )
    if (
        not isinstance(scope_value, dict)
        or scope_value.keys() != {"account", "instrument"}
        or not isinstance(scope_value.get("account"), str)
        or not scope_value["account"]
        or not isinstance(scope_value.get("instrument"), str)
        or not scope_value["instrument"]
    ):
        raise ReservationTransitionHistoryCorruption(
            f"reservation transition seq={seq} has an invalid scope"
        )
    if witness is not None and not isinstance(witness, bool):
        raise ReservationTransitionHistoryCorruption(
            f"reservation transition seq={seq} has an invalid finality witness"
        )
    if "committed_vector" in payload and payload["committed_vector"] is not None:
        try:
            CapacityVector.model_validate(payload["committed_vector"])
        except (TypeError, ValueError) as exc:
            raise ReservationTransitionHistoryCorruption(
                f"reservation transition seq={seq} has an invalid committed vector"
            ) from exc
    try:
        return ReservationTransitionRecord(
            seq=seq,
            command_id=raw_command_id,
            kind=kind,
            reservation_id=reservation_id,
            from_state=CapacityState(payload["from_state"]),
            to_state=CapacityState(payload["to_state"]),
            scope=ReservationScope(
                account=scope_value["account"],
                instrument=scope_value["instrument"],
            ),
            cause=TransitionCause(payload["cause"]),
            finality_witness=witness,
        )
    except (TypeError, ValueError) as exc:
        raise ReservationTransitionHistoryCorruption(
            f"reservation transition seq={seq} has invalid lifecycle fields"
        ) from exc


class SqliteCommitLog:
    """The linearizable Safety Commit Log (design #40 D2.1) — satisfies ``tos.rcl.CommitLog``."""

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
        """Open (or create) the commit log at ``path``."""
        self.path = path
        self._evidence_port = evidence_port
        self._monotonic_ns = monotonic_ns
        self._crash_hook = crash_hook
        self._canon_scheme = get_scheme(canonicalization_version)
        self._advisory_lock_fd: int | None = None
        self._conn = sqlite3.connect(
            str(path), isolation_level=None, timeout=sqlite_timeout_s
        )
        with closing_on_failure(self._conn):
            enable_wal_journal(self._conn)
            self._conn.execute("PRAGMA synchronous=FULL")
            apply_schema_ledger(self._conn, monotonic_ns=monotonic_ns)

    def close(self) -> None:
        """Close the underlying sqlite3 connection (and any advisory lock fd)."""
        if self._advisory_lock_fd is not None:
            import os

            os.close(self._advisory_lock_fd)
            self._advisory_lock_fd = None
        self._conn.close()

    def try_acquire_advisory_flock(self) -> bool:
        """Best-effort, non-blocking ``fcntl.flock`` on this log's file (D2.1 "보조")."""
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

    def acquire_epoch(
        self, identity: RuntimeIdentity, *, runtime_generation: int | None = None
    ) -> WriterEpoch:
        """Atomically issue a new, strictly-greater Writer Epoch (fault ①)."""
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
        """The ``runtime_generation`` recorded on the most recent ``epochs`` row."""
        row = self._conn.execute(
            "SELECT runtime_generation FROM epochs ORDER BY epoch DESC LIMIT 1"
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return int(row[0])

    def append_cas(
        self,
        entry: CommitEntry,
        *,
        expected_seq: int,
        writer_epoch: WriterEpoch,
        payload_json: str | None = None,
    ) -> AppendReceipt | AppendRefusal:
        """Compare-and-set append (kernel ``CommitLog.append_cas``; faults ①②③④⑥⑦)."""
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
        """Linearizable read snapshot (kernel ``CommitLog.read_linearizable``; fault ①)."""
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

    def read_approval_only_gap(
        self, *, writer_epoch: WriterEpoch, proof_last_seq: int | None
    ) -> LogView | None:
        if type(writer_epoch) is not int or writer_epoch <= 0:
            return None
        if not (
            proof_last_seq is None
            or type(proof_last_seq) is int
            and proof_last_seq >= 0
        ):
            return None
        start = -1 if proof_last_seq is None else proof_last_seq
        try:
            self._conn.execute("BEGIN")
            current = self.current_epoch()
            tip = self._current_seq_tip()
            if current != writer_epoch or start > tip:
                raise ValueError
            rows = self._conn.execute(
                "SELECT seq, writer_epoch, command_id, command_digest, kind, "
                "payload_digest, payload_json, is_reservation_transition "
                "FROM entries WHERE seq > ? ORDER BY seq ASC",
                (start,),
            ).fetchall()
            if len(rows) != tip - start:
                raise ValueError
            for expected, row in enumerate(rows, start + 1):
                payload = json.loads(row[6], object_pairs_hook=_no_duplicate_json_keys)
                malformed = (
                    type(row[0]) is not int or row[0] != expected,
                    type(row[1]) is not int or row[1] != current,
                    not isinstance(row[2], str) or not row[2],
                    row[3] is not None and not isinstance(row[3], str),
                    row[4] != CommandType.CONSUME_APPROVAL_DECISION.value,
                    row[5] is not None and not isinstance(row[5], str),
                    not isinstance(row[6], str) or not isinstance(payload, dict),
                    type(row[7]) is not int or row[7] != 0,
                )
                if any(malformed):
                    raise ValueError
            self._conn.execute("COMMIT")
        except (sqlite3.Error, TypeError, ValueError):
            self._safe_rollback()
            return None
        return LogView(epoch=current, last_seq=None if tip < 0 else tip, entries=())

    def reservation_transition_history(
        self, *, writer_epoch: WriterEpoch
    ) -> ReservationTransitionHistory:
        """Read every committed, discriminated reservation transition in one snapshot."""
        self._conn.execute("BEGIN")
        try:
            current = self.current_epoch()
            stale_reason = stale_writer_epoch(current, writer_epoch)
            if stale_reason is not None:
                raise StaleEpochRead(stale_reason)
            self.verify_replay()
            (tip_value,) = self._conn.execute("SELECT MAX(seq) FROM entries").fetchone()
            tip = -1 if tip_value is None else int(tip_value)
            rows = self._conn.execute(
                "SELECT seq, command_id, kind, payload_json "
                "FROM entries WHERE is_reservation_transition = 1 AND seq <= ? "
                "ORDER BY seq ASC",
                (tip,),
            ).fetchall()
            self._conn.execute("COMMIT")
        except BaseException:
            self._safe_rollback()
            raise
        records = tuple(_reservation_transition_record_from_row(row) for row in rows)
        return ReservationTransitionHistory(
            writer_epoch=current,
            last_seq=None if tip < 0 else tip,
            transitions=records,
        )

    def replay(self) -> Iterator[CommitEntry]:
        """Replay the full committed log in commit order (kernel ``CommitLog.replay``; fault ⑤)."""
        rows = self._conn.execute(
            "SELECT seq, writer_epoch, command_id, command_digest, kind, "
            "payload_digest FROM entries ORDER BY seq ASC"
        ).fetchall()
        for row in rows:
            yield row_to_commit_entry(row)

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
        """Commit one reservation-lifecycle transition (D2.1 item 4)."""
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

    def committed_command(self, command_id: str) -> tuple[int, str | None] | None:
        """``(seq, command_digest)`` of the COMMITTED entry for ``command_id``, or ``None``."""
        row = self._conn.execute(
            "SELECT seq, command_digest FROM entries WHERE command_id = ?",
            (command_id,),
        ).fetchone()
        return None if row is None else (int(row[0]), row[1])

    def command_committed(self, command_id: str) -> bool:
        """Whether an entry with ``command_id`` is committed (PR-3b: the fill observer asks"""
        row_exists, _digest = existing_command_row(self._conn, command_id)
        return row_exists

    def reservation_rows(
        self,
    ) -> Iterator[tuple[str, CapacityState, int, ReservationScope]]:
        """Yield every held ``(reservation_id, state, last_seq, scope)`` — the projection's read"""
        return gates_reservation_rows(self._conn)

    def reservation_committed_vector(
        self, reservation_id: str
    ) -> CapacityVector | None:
        """The committed Capacity Vector last written for ``reservation_id``, if any (delegates"""
        return gates_reservation_committed_vector(self._conn, reservation_id)

    def verify_replay(self) -> None:
        """Independently re-fold entries and compare against the held projection (fault ⑤)."""
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

    def _current_seq_tip(self) -> int:
        """The current log tip: the last committed ``seq``, or ``-1`` if empty."""
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
        """Fence + CAS + duplicate + reservation-gate checks, in that order."""
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
        """``INSERT`` the ``entries`` row (+ ``UPSERT`` ``reservations``, if applicable)."""
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
        """Durably evidence this append; on failure, roll back and refuse (D2.1 item 1(f))."""
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
        """The whole durable-append body: fence, CAS, insert, evidence, commit (faults ①②③④⑥⑦)."""
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
