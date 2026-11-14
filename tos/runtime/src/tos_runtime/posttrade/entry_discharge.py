"""Discharging the ENTRY reservation a close attempt closed (#966, plan §2.4)."""

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
from tos_runtime.risk.close_quantity import close_within_entry

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
    """The RCL idempotency key for discharging the ENTRY reservation a close attempt closed."""
    return f"release-entry-{close_attempt_id}"


_FILL_KIND_VALUES: frozenset[str] = frozenset(kind.value for kind in FILL_RESULT_KINDS)


class DischargeRefusal(StrEnum):
    """Why an entry reservation may not be discharged yet."""

    QUANTITY_UNPROVEN = "QUANTITY_UNPROVEN"
    POSITION_NOT_FLAT = "POSITION_NOT_FLAT"


def other_outstanding(
    projection: ReservationProjectionReader,
    *,
    account: str,
    instrument: str,
    reservation_id: str,
) -> tuple[ScopeReservation, ...]:
    """The scope's outstanding (non-``RELEASED``) reservations OTHER than ``reservation_id``."""
    key = InstrumentKey(account=account, instrument=instrument)
    return tuple(
        row
        for row in outstanding_reservations(projection.scope_reservations(key))
        if row.reservation_id != reservation_id
    )


def broker_position_flat(report: ReconciliationReport, instrument: str) -> bool:
    """Whether the broker is AFFIRMATIVELY PROVEN to hold none of ``instrument``."""
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
    """``attempt_id``'s own durably recorded FINAL filled quantity, if it has one."""
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
    """Whether ``attempt_id`` has ANY recorded receipt showing a filled quantity above zero."""
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
    """The ``(attempt_id, final filled quantity)`` behind an entry reservation."""
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
    prior_closed: Decimal | None,
    report: ReconciliationReport,
    instrument: str,
) -> DischargeRefusal | None:
    """The first gate that refuses this discharge, or ``None`` when both admit."""
    if (
        entry_quantity is None
        or payload.filled_quantity is None
        or payload.remaining_quantity is None
        or Decimal(payload.remaining_quantity) != Decimal(0)
        or close_within_entry(entry_quantity, prior_closed, payload.filled_quantity)
        is not True
        or prior_closed is None
        or prior_closed + payload.filled_quantity != entry_quantity
    ):
        return DischargeRefusal.QUANTITY_UNPROVEN
    if not broker_position_flat(report, instrument):
        return DischargeRefusal.POSITION_NOT_FLAT
    return None
