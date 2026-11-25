"""RCL Safety Commit Log **port** + fault-contract predicates (design #40 D2.1)."""

from __future__ import annotations

from collections.abc import Iterator
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable

from tos.canonical import RecordPairKind, classify_record_pair
from tos.rcl._base import FrozenModel
from tos.rcl.predicates import transition_allowed
from tos.rcl.vector import CapacityVector
from tos.rcl.vocabulary import CapacityState, CommandType, TransitionCause

__all__ = [
    "AppendRefusalReason",
    "AppendReceipt",
    "AppendRefusal",
    "CapacityReservationTransition",
    "CommitEntry",
    "CommitLog",
    "LogView",
    "ReservationScope",
    "WriterEpoch",
    "duplicate_command",
    "release_admissible",
    "replay_reproduces_state",
    "reservation_transition_structurally_legal",
    "stale_writer_epoch",
]

WriterEpoch = int


class AppendRefusalReason(StrEnum):
    """Closed vocabulary of reasons ``CommitLog.append_cas`` may refuse (D2.1 ①②⑦)."""

    STALE_EPOCH = "STALE_EPOCH"
    SEQ_MISMATCH = "SEQ_MISMATCH"
    DUPLICATE_COMMAND_ID = "DUPLICATE_COMMAND_ID"
    COMMAND_BYTES_MISMATCH = "COMMAND_BYTES_MISMATCH"
    STORE_UNAVAILABLE = "STORE_UNAVAILABLE"
    PARTIAL_COMMIT_SUSPECTED = "PARTIAL_COMMIT_SUSPECTED"
    INTEGRITY_VIOLATION = "INTEGRITY_VIOLATION"


class CommitEntry(FrozenModel):
    """One command as it is submitted for / held in the Safety Commit Log (§9)."""

    seq: int | None = None
    writer_epoch: WriterEpoch | None = None
    command_id: str | None = None
    command_digest: str | None = None
    kind: CommandType | None = None
    payload_digest: str | None = None


class AppendReceipt(FrozenModel):
    """Proof of one durable commit (D2.1 ⑦: no "recorded" claim without one)."""

    seq: int | None = None
    writer_epoch: WriterEpoch | None = None
    durable: Literal[True] = True


class AppendRefusal(FrozenModel):
    """A structural, evidence-bearing refusal of ``append_cas`` (D2.1 ①②⑦)."""

    reason: AppendRefusalReason | None = None
    detail: str | None = None


class LogView(FrozenModel):
    """A linearizable read snapshot: current epoch + last seq + entries (§8.4)."""

    epoch: WriterEpoch | None = None
    last_seq: int | None = None
    entries: tuple[CommitEntry, ...] = ()


class ReservationScope(FrozenModel):
    """The ``(account, instrument)`` scope a reservation transition is bound to."""

    account: str
    instrument: str


class CapacityReservationTransition(FrozenModel):
    """One committed reservation-lifecycle transition (design #40 D2.1 line 64)."""

    reservation_id: str | None = None
    seq: int | None = None
    writer_epoch: WriterEpoch | None = None
    from_state: CapacityState | None = None
    to_state: CapacityState | None = None
    scope: ReservationScope | None = None
    committed_vector: CapacityVector | None = None


@runtime_checkable
class CommitLog(Protocol):
    """The Safety Commit Log port (design #40 D2.1 line 65; ADR-002-012 §1/§5-§9)."""

    def current_epoch(self) -> WriterEpoch:
        """Return the currently active Writer Epoch (ADR-002-012 §5.5, line 129)."""
        ...

    def append_cas(
        self,
        entry: CommitEntry,
        *,
        expected_seq: int,
        writer_epoch: WriterEpoch,
    ) -> AppendReceipt | AppendRefusal:
        """Compare-and-set append: admit ``entry`` iff ``expected_seq``/``writer_epoch``"""
        ...

    def read_linearizable(self, *, writer_epoch: WriterEpoch) -> LogView:
        """Return a linearizable :class:`LogView` under a current-epoch read barrier"""
        ...

    def replay(self) -> Iterator[CommitEntry]:
        """Replay the full committed log in commit order (ADR-002-012 §17.1, line"""
        ...


def stale_writer_epoch(
    current: WriterEpoch | None,
    attempted: WriterEpoch | None,
) -> AppendRefusalReason | None:
    """D2.1 fault ① — reject a write whose Writer Epoch is not the current one."""
    if current is None or attempted is None:
        return AppendRefusalReason.STALE_EPOCH
    if attempted != current:
        return AppendRefusalReason.STALE_EPOCH
    return None


def duplicate_command(
    existing_digest_for_id: str | None,
    attempted_digest: str | None,
) -> AppendRefusalReason | None:
    """D2.1 fault ② — classify a command against any prior entry sharing its id."""
    if existing_digest_for_id is None:
        return None
    kind = classify_record_pair(
        "_same_command_id",
        existing_digest_for_id,
        "_same_command_id",
        attempted_digest,
    )
    if kind is RecordPairKind.IDEMPOTENT_DUP:
        return AppendRefusalReason.DUPLICATE_COMMAND_ID
    return AppendRefusalReason.COMMAND_BYTES_MISMATCH


def replay_reproduces_state(
    replayed_digest: str | None,
    held_digest: str | None,
) -> AppendRefusalReason | None:
    """D2.1 fault ⑤ — cross-check a full replay against the authoritative state digest."""
    if replayed_digest is None or held_digest is None:
        return AppendRefusalReason.INTEGRITY_VIOLATION
    if replayed_digest != held_digest:
        return AppendRefusalReason.INTEGRITY_VIOLATION
    return None


_WITNESS_REQUIRED_DESTINATIONS: frozenset[CapacityState] = frozenset(
    {CapacityState.RELEASED, CapacityState.POSITION_CONSUMED}
)


def release_admissible(
    transition: CapacityReservationTransition,
    finality_witness: bool | None,
) -> bool:
    """Whether a reservation transition to a finality state may be admitted."""
    if transition.to_state is None:
        return False
    if transition.to_state not in _WITNESS_REQUIRED_DESTINATIONS:
        return True
    return finality_witness is True


_LEGAL_RESERVATION_TRANSITIONS: frozenset[tuple[CapacityState, CapacityState]] = (
    frozenset(
        (from_state, to_state)
        for from_state in CapacityState
        for to_state in CapacityState
        if any(
            transition_allowed(from_state, to_state, cause) for cause in TransitionCause
        )
    )
)


def reservation_transition_structurally_legal(
    from_state: CapacityState | None,
    to_state: CapacityState | None,
) -> bool:
    """Whether ``(from_state, to_state)`` is a structurally legal reservation transition."""
    if from_state is None or to_state is None:
        return False
    return (from_state, to_state) in _LEGAL_RESERVATION_TRANSITIONS
