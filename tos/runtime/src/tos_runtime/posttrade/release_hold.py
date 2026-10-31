"""The release path's hold vocabulary — why a release did NOT happen.

Extracted from :mod:`tos_runtime.posttrade.release_consumer` to keep that module under the
repo's 1000-line module size budget (``tools/tos_size_budget.py``) — the same pure
decomposition, no behaviour change, that :mod:`tos_runtime.posttrade.entry_discharge` and
:mod:`tos_runtime.posttrade.release_currentness` were split out under, and for the same reason.

It is also a genuinely separate concern from the consumer's gate sequence: this is the closed
set of names a ``CAPACITY_RELEASE_HELD`` evidence row may carry, plus the two mappings onto it
(from :class:`~tos_runtime.posttrade.entry_discharge.DischargeRefusal`, and from a
reconciliation report that did not corroborate). Those names are read back by
:func:`~tos_runtime.posttrade.release_currentness.latest_release_is_conflict_free`,
:mod:`tos_runtime.posttrade.fill_observer` and the entry-discharge recovery pass, so the
vocabulary outliving any one consumer's structure is the honest shape.

:mod:`tos_runtime.posttrade.release_consumer` re-exports every name here, so an existing
``from ...release_consumer import ReleaseHoldReason`` keeps working unchanged.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``enum``,
``collections.abc``) + ``tos_runtime.posttrade.entry_discharge`` + ``tos_runtime.recon.service``
only. No ``shared.*``; no I/O of any kind (this module reads nothing and writes nothing).
"""

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
    """Why :meth:`FinalityReleaseConsumer.consume` recorded ``CAPACITY_RELEASE_HELD`` instead of
    releasing (module docstring's numbered gate list)."""

    #: Gate 1 (``FULL_FILL`` only): the durable witness row is not ``True``.
    NO_WITNESS = "NO_WITNESS"
    #: Gate 2: the expected durable proof/obligation row could not be re-loaded.
    PROOF_NOT_RELOADED = "PROOF_NOT_RELOADED"
    #: The non-execution proof itself could not be built (kernel gate refusal).
    NON_EXECUTION_PROOF_UNPRODUCIBLE = "NON_EXECUTION_PROOF_UNPRODUCIBLE"
    #: Gate 3: :meth:`~tos_runtime.recon.service.ReconciliationService.reconcile` itself raised.
    RECONCILIATION_UNAVAILABLE = "RECONCILIATION_UNAVAILABLE"
    #: Gate 3: the report did not positively corroborate this exact attempt — and the
    #: reconciliation genuinely disagreed (an orphan broker order, a non-``MATCHED``
    #: classification). Since #1011 §3.5 this no longer also covers "the witness is not
    #: independent", which is :attr:`WITNESS_NOT_INDEPENDENT` below.
    NOT_CORROBORATED = "NOT_CORROBORATED"
    #: Gate 3, #1011 §3.5: the report could not corroborate because the witness it had is
    #: derived from the evidence store it would be corroborating
    #: (:data:`~tos_runtime.recon.service.WITNESS_NOT_INDEPENDENT_REASON`). The release is
    #: held either way — the decision is UNCHANGED — but this is a statement about the
    #: witness, not about a conflict between what this scope expected and what happened
    #: downstream. The POST_TRADE currentness dimension reads only the latter as a conflict
    #: (:func:`~tos_runtime.posttrade.release_currentness.latest_release_is_conflict_free`),
    #: so folding the two into one string made every old synthetic leaf report a conflict it
    #: did not have (#1011 F6).
    WITNESS_NOT_INDEPENDENT = "WITNESS_NOT_INDEPENDENT"
    #: Gate 4: :func:`~tos.posttrade.predicates.finality_proof_non_transferable` is ``False``.
    PROOF_NOT_TRANSFERABLE = "PROOF_NOT_TRANSFERABLE"
    #: Gate 4: :func:`~tos.posttrade.predicates.finality_proof_current` is ``False``.
    PROOF_NOT_CURRENT = "PROOF_NOT_CURRENT"
    #: The reservation's own current state could not be read (no reservation for this scope).
    NO_RESERVATION = "NO_RESERVATION"
    #: Every prior gate passed but the RCL log itself refused the transition (e.g. a concurrent
    #: writer moved the tip — a genuine CAS race, not a gate this consumer can pre-empt).
    RCL_TRANSITION_REFUSED = "RCL_TRANSITION_REFUSED"
    #: #966: the scope's OTHER outstanding reservations are not the one shape a close is
    #: admitted over (exactly one, at ``POSITION_CONSUMED``) — two of them, or one mid-flight.
    AMBIGUOUS_SCOPE_RESERVATIONS = "AMBIGUOUS_SCOPE_RESERVATIONS"
    #: #966: the close did not provably discharge the entry in full (quantities disagree, a
    #: remainder is left, or the entry's own final quantity is not on record).
    ENTRY_QUANTITY_UNPROVEN = "ENTRY_QUANTITY_UNPROVEN"
    #: #966: the witness still observes a non-zero holding of this instrument.
    BROKER_POSITION_NOT_FLAT = "BROKER_POSITION_NOT_FLAT"
    #: review-973 M3: a non-execution result (cancel/expire/reject) ended the ORDER, but this
    #: attempt had already filled part of it — releasing would discard capacity still held.
    FILLED_QUANTITY_STILL_HELD = "FILLED_QUANTITY_STILL_HELD"
    #: A close release is held if its durable entry-recovery link could not be written first.
    ENTRY_DISCHARGE_PENDING_UNAVAILABLE = "ENTRY_DISCHARGE_PENDING_UNAVAILABLE"


def uncorroborated_hold_reason(
    report: ReconciliationReport | None,
) -> ReleaseHoldReason:
    """Which "gate 3 did not corroborate" reason ``report`` earns (#1011 §3.5).

    ONE place, because three call sites record this hold — the ``FULL_FILL`` path, the
    non-execution path, and the entry-discharge recovery pass
    (:mod:`tos_runtime.posttrade.entry_recovery`) — and a split that only reached two of them
    would leave the third reporting a conflict the witness never found.

    Args:
        report: The reconciliation report, or ``None`` when ``.reconcile()`` itself raised
            (that case has its own :attr:`~ReleaseHoldReason.RECONCILIATION_UNAVAILABLE`
            reason and never reaches here; accepted as ``None`` only so the recovery pass's
            own ``report | None`` type needs no second narrowing).

    Returns:
        :attr:`~ReleaseHoldReason.WITNESS_NOT_INDEPENDENT` when the report names exactly that
        (:data:`~tos_runtime.recon.service.WITNESS_NOT_INDEPENDENT_REASON`), otherwise
        :attr:`~ReleaseHoldReason.NOT_CORROBORATED`. The release is HELD for both.
    """
    if witness_independence_collapsed(report):
        return ReleaseHoldReason.WITNESS_NOT_INDEPENDENT
    return ReleaseHoldReason.NOT_CORROBORATED


#: :class:`~tos_runtime.posttrade.entry_discharge.DischargeRefusal` -> this module's own
#: evidence vocabulary. The two live apart so ``entry_discharge`` never imports the release
#: path (which imports it) — the mapping is the one place they meet.
DISCHARGE_HOLD_REASONS: Mapping[DischargeRefusal, ReleaseHoldReason] = {
    DischargeRefusal.QUANTITY_UNPROVEN: ReleaseHoldReason.ENTRY_QUANTITY_UNPROVEN,
    DischargeRefusal.POSITION_NOT_FLAT: ReleaseHoldReason.BROKER_POSITION_NOT_FLAT,
}
