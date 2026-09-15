"""The release-witness seam: turns a SYNTHETIC :class:`~tos.posttrade.records
.PostTradeFinalityProof` into the ``finality_witness`` :meth:`~tos_runtime.rcl.log
.SqliteCommitLog.apply_reservation_transition` admits a ``RELEASED``/``POSITION_CONSUMED``
transition on (TOS Phase 3 Wave 2 Lane C-R; plan §2.2).

**The seam now has a call site (TOS Phase 5 W2-R; plan §10 row ①).**
:mod:`tos_runtime.posttrade.release_consumer`'s ``FinalityReleaseConsumer`` is the ONE
production call site that calls :func:`release_reservation` (via
:meth:`~tos_runtime.rcl.log.SqliteCommitLog.apply_reservation_transition`) toward a
``RELEASED``/``POSITION_CONSUMED`` destination — it owns the reservation-identity / writer-epoch
/ expected-seq bookkeeping this module deliberately never invented. :func:`finality_witness_for`
is the plumbing that consumer supplies its re-loaded proof through; :func:`release_reservation`
remains the thin wrapper this module always was, still exercised in isolation end to end
(``tos/runtime/tests/rcl/test_finality_witness.py``) exactly as before.

``finality_witness_for`` never re-derives the finality gates
:mod:`tos_runtime.posttrade.finality`'s producer already checked before handing out a proof — it
trusts a proof's mere existence at this seam (the producer never yields an unvalidated one, per
its own docstring) and only enforces the ``is True`` positive-polarity discipline
:func:`tos.rcl.release_admissible` itself requires (``None`` for "no proof", never a truthy
coercion).

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.rcl``/
``tos.posttrade`` + ``tos_runtime.rcl.log`` only. No ``shared.*``.
"""

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
    """The ``finality_witness`` a release call site should supply, for a possibly-absent proof.

    Positive polarity only (design #40 D2.1 line 64 / ADR-002-005 CPL-2): ``True`` iff a proof
    was actually produced for this attempt; ``None`` — never ``False`` — otherwise, so
    :func:`tos.rcl.release_admissible`'s own ``finality_witness is True`` gate reads it as
    "no witness supplied" (fail-closed) rather than a fabricated negative claim.

    Args:
        proof: The :class:`~tos.posttrade.records.PostTradeFinalityProof`
            :class:`~tos_runtime.posttrade.finality.SyntheticFinalityProducer` produced for this
            attempt, or ``None`` when it produced none (every non-``FULL_FILL`` result, and any
            ``FULL_FILL`` whose built artifacts failed a kernel gate).

    Returns:
        ``True`` when a proof exists; ``None`` otherwise.
    """
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
    """Apply a reservation-lifecycle transition under the ``FINAL_QUANTITY_PROOF`` cause, with
    the witness derived from ``proof`` via :func:`finality_witness_for`.

    A thin wrapper demonstrating the exact seam a future release-trigger lane supplies its own
    reservation identity / writer epoch / expected-seq bookkeeping through — this function
    invents none of that bookkeeping itself; ``transition`` is the caller's own, already-bound
    :class:`~tos.rcl.CapacityReservationTransition`.

    Args:
        log: The durable reservation-lifecycle log.
        transition: The proposed transition (typically to ``RELEASED``).
        command_id: The idempotency key for this transition command.
        command_digest: The canonical digest of the command bytes.
        expected_seq: The log's current tip, as the caller last observed it.
        proof: The finality proof for this attempt, or ``None``.

    Returns:
        Whatever :meth:`~tos_runtime.rcl.log.SqliteCommitLog.apply_reservation_transition`
        returns.

    Raises:
        ReservationTransitionRefusal: If any reservation-lifecycle gate refuses — in particular,
            ``proof is None`` on a ``RELEASED``/``POSITION_CONSUMED`` destination always refuses
            (CPL-2: no release without proof).
    """
    return log.apply_reservation_transition(
        transition,
        TransitionCause.FINAL_QUANTITY_PROOF,
        command_type=CommandType.RELEASE_RESERVATION,
        command_id=command_id,
        command_digest=command_digest,
        expected_seq=expected_seq,
        finality_witness=finality_witness_for(proof),
    )
