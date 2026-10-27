"""Discharging the ENTRY reservation a close attempt closed (#966, plan §2.4).

Extracted from :mod:`tos_runtime.posttrade.release_consumer` to keep that module under the
repo's 1000-line module size budget (``tools/tos_size_budget.py``) — a pure decomposition, no
behaviour change, the same discipline :mod:`tos_runtime.rcl.gates` was split out of
``rcl/log.py`` under. Everything here is a pure read or a pure predicate; the one RCL mutation
stays in the consumer, which owns every writable handle.

Why this concern exists at all: before #966 a scope held ONE reservation for its whole life, so
``POSITION_CONSUMED`` was terminal in practice and no operational path reached ``RELEASED``
after a fill. Each attempt now holds its own reservation, so a close fill both releases its own
(it opens no position) and — under the conjunctive gates below — discharges the entry's.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.engine.records``/
``tos.rcl`` + ``tos_runtime.evidence.store``/``tos_runtime.rcl.*``/``tos_runtime.recon.*`` only.
No ``shared.*``, no write call.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from tos.engine.records import EgressResultPayload, InstrumentKey
from tos.engine.vocabulary import FILL_RESULT_KINDS

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.projection import (
    ReservationProjectionReader,
    ScopeReservation,
    outstanding_reservations,
)
from tos_runtime.rcl.reservation_identity import permit_identity_of
from tos_runtime.rcl.reservation_lookup import attempt_id_for_reservation
from tos_runtime.recon.evidence_reader import SqliteEvidenceReceiptReader
from tos_runtime.recon.ports import WitnessScope, WitnessUnavailable
from tos_runtime.recon.service import ReconciliationReport

__all__ = [
    "DischargeRefusal",
    "any_quantity_filled",
    "broker_position_flat",
    "entry_discharge_refusal",
    "entry_final_quantity",
    "entry_release_command_id",
    "other_outstanding",
    "recorded_final_quantity",
]


def entry_release_command_id(close_attempt_id: str) -> str:
    """The RCL idempotency key for discharging the ENTRY reservation a close attempt closed.

    A SECOND spelling is required: the close attempt commits two distinct release transitions —
    its own reservation and the entry's — and the log's ``command_id`` is UNIQUE, so re-using
    :func:`~tos_runtime.posttrade.release_consumer.release_command_id` would make the second a
    ``DUPLICATE_COMMAND_ID`` refusal. Keyed on the close attempt (never a clock or counter), so
    a replay of the same close reproduces the same key and the transition stays idempotent.
    """
    return f"release-entry-{close_attempt_id}"


#: The recorded ``egress_result_kind`` strings that assert a fill, from the kernel's own closed
#: set — a receipt of one of these kinds with no magnitude on record is an unknown quantity,
#: not a zero one (review-973 round 2 LOW).
_FILL_KIND_VALUES: frozenset[str] = frozenset(kind.value for kind in FILL_RESULT_KINDS)


class DischargeRefusal(StrEnum):
    """Why an entry reservation may not be discharged yet.

    Mapped onto a :class:`~tos_runtime.posttrade.release_consumer.ReleaseHoldReason` by the
    consumer, which owns the evidence vocabulary; kept separate so this module stays free of
    the consumer's own imports (no cycle).
    """

    #: The close did not provably discharge the entry in full.
    QUANTITY_UNPROVEN = "QUANTITY_UNPROVEN"
    #: The witness still observes a non-zero holding of this instrument.
    POSITION_NOT_FLAT = "POSITION_NOT_FLAT"


def other_outstanding(
    projection: ReservationProjectionReader,
    *,
    account: str,
    instrument: str,
    reservation_id: str,
) -> tuple[ScopeReservation, ...]:
    """The scope's outstanding (non-``RELEASED``) reservations OTHER than ``reservation_id``.

    Empty for an ordinary entry fill; exactly one ``POSITION_CONSUMED`` row — the entry being
    closed — for a close fill. Any other shape is one the consumer refuses to act on.
    """
    key = InstrumentKey(account=account, instrument=instrument)
    return tuple(
        row
        for row in outstanding_reservations(projection.scope_reservations(key))
        if row.reservation_id != reservation_id
    )


def broker_position_flat(report: ReconciliationReport, instrument: str) -> bool:
    """Whether the broker is AFFIRMATIVELY PROVEN to hold none of ``instrument``.

    Two conditions, both required:

    1. the holdings observation is complete — every row the witness was given was readable and
       attributable (:attr:`~tos_runtime.recon.service.ReconciliationReport
       .observed_positions_complete`);
    2. that complete observation carries no non-zero holding of ``instrument``.

    Reads the SAME observation gate 3 already judged on, never a second ``observe`` call.

    **Why (1) is not optional** (#966 review round 1, Codex HIGH — measured): emptiness is not
    flatness. :class:`~tos_runtime.recon.witness_kis.KisStockBrokerWitness` DROPS a holdings row
    whose ``pdno`` is blank or whose ``hldg_qty`` does not parse, so a balance answer of
    ``{"pdno": "005930", "hldg_qty": ""}`` — an account that may well still be holding the
    position this close was supposed to flatten — produced ``observed_positions=()``, byte-
    identical to a genuinely flat account. Reading that as flat released the entry reservation
    and re-opened the scope to a fresh OPEN on the strength of a row the witness could not
    read. A dropped row now makes the observation incomplete, which holds.

    Consequence, stated rather than hidden:
    :class:`~tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness` has no broker ledger
    to read at all, so it never reports a complete holdings observation and this never returns
    ``True`` on a synthetic-transport boot. The entry reservation then stays
    ``POSITION_CONSUMED`` after a close, with a ``CAPACITY_RELEASE_HELD`` row naming why — that
    scope still admits a further CLOSE but no new OPEN. That is the honest reading: the plan's
    condition is broker-confirmed flatness, and a witness derived from this process's own
    evidence store confirms nothing about the broker.
    """
    if not report.observed_positions_complete:
        return False
    return not any(
        symbol == instrument and quantity != 0
        for symbol, quantity in report.observed_positions
    )


def recorded_final_quantity(
    evidence_store: SqliteEvidenceStore,
    *,
    account: str,
    instrument: str,
    attempt_id: str,
) -> Decimal | None:
    """``attempt_id``'s own durably recorded FINAL filled quantity, if it has one.

    The receipt whose recorded result is a full fill — a filled magnitude with zero remaining.
    ``None`` when the attempt has no such receipt (never filled, filled only partially, or the
    receipt path is unreadable); absence is never read as zero.
    """
    scope = WitnessScope(
        account=account,
        instrument_keys=(InstrumentKey(account=account, instrument=instrument),),
        attempt_ids=(attempt_id,),
    )
    try:
        receipts = SqliteEvidenceReceiptReader(evidence_store).receipts(scope)
    except WitnessUnavailable:
        return None
    for receipt in receipts:
        if (
            receipt.attempt_id == attempt_id
            and receipt.filled_quantity is not None
            and receipt.remaining_quantity is not None
            and Decimal(receipt.remaining_quantity) == Decimal(0)
            and Decimal(receipt.filled_quantity) > Decimal(0)
        ):
            return Decimal(receipt.filled_quantity)
    return None


def any_quantity_filled(
    evidence_store: SqliteEvidenceStore,
    *,
    account: str,
    instrument: str,
    attempt_id: str,
) -> bool:
    """Whether ``attempt_id`` has ANY recorded receipt showing a filled quantity above zero.

    The gate a non-execution result (``CANCEL_ACK``/``EXPIRED``/``REJECT``) needs before it may
    release (review-973 M3): a cancel of the REMAINDER of a partially-filled order ends the
    order, not the position. Releasing the reservation there would report zero outstanding
    capacity while the filled part is still held — and under #966's step-8 table that admits a
    fresh OPEN over a live position and leaves no reservation for a CLOSE to discharge.

    Fail-closed in three ways (review-973 round 2 LOW — the earlier wording claimed the third
    and the code did not do it):

    * an unreadable receipt path returns ``True`` — cannot tell, so do not release;
    * a receipt with a filled magnitude above zero returns ``True``;
    * a receipt whose recorded kind IS a fill (``FULL_FILL``/``PARTIAL_FILL``) but whose filled
      magnitude is absent returns ``True`` — a fill with no magnitude on record is "unknown
      quantity", never "zero". A receipt of any OTHER kind with no magnitude (an ``ACK``, a
      plain ``CANCEL_ACK``) carries no fill claim at all and does not block.
    """
    scope = WitnessScope(
        account=account,
        instrument_keys=(InstrumentKey(account=account, instrument=instrument),),
        attempt_ids=(attempt_id,),
    )
    try:
        receipts = SqliteEvidenceReceiptReader(evidence_store).receipts(scope)
    except WitnessUnavailable:
        return True
    for receipt in receipts:
        if receipt.attempt_id != attempt_id:
            continue
        if receipt.filled_quantity is None:
            if receipt.egress_result_kind in _FILL_KIND_VALUES:
                return True
            continue
        if Decimal(receipt.filled_quantity) > Decimal(0):
            return True
    return False


def entry_final_quantity(
    evidence_store: SqliteEvidenceStore,
    *,
    account: str,
    instrument: str,
    reservation_id: str,
) -> tuple[str | None, Decimal | None]:
    """The ``(attempt_id, final filled quantity)`` behind an entry reservation.

    Recovered from the reservation's OWN id — the permit it is named after, then the durable
    evidence join (:mod:`tos_runtime.rcl.reservation_lookup`) — never from whatever attempt is
    live, which during a close is the close's. Either element is ``None`` when it cannot be
    established: a pre-#966 scope-level row carries no attempt identity at all, and an attempt
    with no full-fill receipt has no final quantity.
    """
    permit_identity = permit_identity_of(
        reservation_id, account=account, instrument=instrument
    )
    if permit_identity is None:
        return None, None
    attempt_id = attempt_id_for_reservation(evidence_store, permit_identity)
    if attempt_id is None:
        return None, None
    return attempt_id, recorded_final_quantity(
        evidence_store, account=account, instrument=instrument, attempt_id=attempt_id
    )


def entry_discharge_refusal(
    payload: EgressResultPayload,
    *,
    entry_quantity: Decimal | None,
    report: ReconciliationReport,
    instrument: str,
) -> DischargeRefusal | None:
    """The first gate that refuses this discharge, or ``None`` when both admit.

    Conjunctive, in the plan's own order (§2.4):

    1. the close's cumulative filled quantity equals the entry's recorded final filled quantity
       AND its remaining quantity is zero — the position the entry reservation accounts for is
       discharged in full, not in part. This is what makes
       ``TransitionCause.FINAL_QUANTITY_PROOF`` an honest claim rather than a label;
    2. the broker-side reading corroborates it (:func:`broker_position_flat`).

    A partial close therefore refuses, and the entry's capacity stays committed for the part of
    the position still open (ADR-002-012 :179 — committed consumption cannot be released).
    """
    if (
        entry_quantity is None
        or payload.filled_quantity is None
        or payload.remaining_quantity is None
        or Decimal(payload.remaining_quantity) != Decimal(0)
        or Decimal(payload.filled_quantity) != entry_quantity
    ):
        return DischargeRefusal.QUANTITY_UNPROVEN
    if not broker_position_flat(report, instrument):
        return DischargeRefusal.POSITION_NOT_FLAT
    return None
