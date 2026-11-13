"""The release-witness seam: turns a SYNTHETIC :class:`~tos.posttrade.records"""

from __future__ import annotations

from tos.posttrade import PostTradeFinalityProof
from tos.rcl import (
    AppendReceipt,
    AppendRefusal,
    CapacityReservationTransition,
    CommandType,
    TransitionCause,
)

from tos_runtime.rcl.log import SqliteCommitLog

__all__ = ["finality_witness_for", "release_reservation"]


def finality_witness_for(proof: PostTradeFinalityProof | None) -> bool | None:
    """The ``finality_witness`` a release call site should supply, for a possibly-absent proof."""
    return True if proof is not None else None


def release_reservation(
    log: SqliteCommitLog,
    transition: CapacityReservationTransition,
    *,
    command_id: str,
    command_digest: str | None,
    expected_seq: int,
    proof: PostTradeFinalityProof | None,
) -> AppendReceipt | AppendRefusal:
    """Apply a reservation-lifecycle transition under the ``FINAL_QUANTITY_PROOF`` cause, with"""
    return log.apply_reservation_transition(
        transition,
        TransitionCause.FINAL_QUANTITY_PROOF,
        command_type=CommandType.RELEASE_RESERVATION,
        command_id=command_id,
        command_digest=command_digest,
        expected_seq=expected_seq,
        finality_witness=finality_witness_for(proof),
    )
