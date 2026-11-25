"""The release path's hold vocabulary — why a release did NOT happen."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from tos_runtime.posttrade.entry_discharge import DischargeRefusal
from tos_runtime.recon.service import (
    ReconciliationReport,
    witness_independence_collapsed,
)

__all__ = [
    "DISCHARGE_HOLD_REASONS",
    "ReleaseHoldReason",
    "uncorroborated_hold_reason",
]


class ReleaseHoldReason(StrEnum):
    """Why :meth:`FinalityReleaseConsumer.consume` recorded ``CAPACITY_RELEASE_HELD`` instead of"""

    NO_WITNESS = "NO_WITNESS"
    PROOF_NOT_RELOADED = "PROOF_NOT_RELOADED"
    NON_EXECUTION_PROOF_UNPRODUCIBLE = "NON_EXECUTION_PROOF_UNPRODUCIBLE"
    RECONCILIATION_UNAVAILABLE = "RECONCILIATION_UNAVAILABLE"
    NOT_CORROBORATED = "NOT_CORROBORATED"
    WITNESS_NOT_INDEPENDENT = "WITNESS_NOT_INDEPENDENT"
    PROOF_NOT_TRANSFERABLE = "PROOF_NOT_TRANSFERABLE"
    PROOF_NOT_CURRENT = "PROOF_NOT_CURRENT"
    NO_RESERVATION = "NO_RESERVATION"
    RCL_TRANSITION_REFUSED = "RCL_TRANSITION_REFUSED"
    AMBIGUOUS_SCOPE_RESERVATIONS = "AMBIGUOUS_SCOPE_RESERVATIONS"
    ENTRY_QUANTITY_UNPROVEN = "ENTRY_QUANTITY_UNPROVEN"
    BROKER_POSITION_NOT_FLAT = "BROKER_POSITION_NOT_FLAT"
    FILLED_QUANTITY_STILL_HELD = "FILLED_QUANTITY_STILL_HELD"
    ENTRY_DISCHARGE_PENDING_UNAVAILABLE = "ENTRY_DISCHARGE_PENDING_UNAVAILABLE"


def uncorroborated_hold_reason(
    report: ReconciliationReport | None,
) -> ReleaseHoldReason:
    """Which "gate 3 did not corroborate" reason ``report`` earns (#1011 §3.5)."""
    if witness_independence_collapsed(report):
        return ReleaseHoldReason.WITNESS_NOT_INDEPENDENT
    return ReleaseHoldReason.NOT_CORROBORATED


DISCHARGE_HOLD_REASONS: Mapping[DischargeRefusal, ReleaseHoldReason] = {
    DischargeRefusal.QUANTITY_UNPROVEN: ReleaseHoldReason.ENTRY_QUANTITY_UNPROVEN,
    DischargeRefusal.POSITION_NOT_FLAT: ReleaseHoldReason.BROKER_POSITION_NOT_FLAT,
}
