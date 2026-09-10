"""Possibly-live reconciliation — TOS Phase 5 W1 close-out, GAP 1's own wiring half (plan §2
decision 3: "confidence 가 양성 아니면 재무장 0·용량 반환 0").

**What this module closes.** :mod:`tos_runtime.recovery.barrier`'s own ``RECON_UNAVAILABLE``
docstring recorded, at landing time, that a genuine
:class:`~tos_runtime.recon.service.ReconciliationService` could not yet be constructed because
the evidence-receipt port (:class:`~tos_runtime.recon.ports.EvidenceReceiptReader`) had no
concrete implementation anywhere in the tree. :mod:`tos_runtime.recon.evidence_reader` now ships
one (:class:`~tos_runtime.recon.evidence_reader.SqliteEvidenceReceiptReader`); this module is the
caller that actually RUNS reconciliation against a real, fully-wired service, rather than a
partial one built under time pressure.

**One scope, one report, applied uniformly.** ``tos_runtime.compose._engine_wiring``'s own module
docstring records, as a standing assumption, that "this compose root wires exactly one
``InstrumentKey`` ... for its whole process lifetime". Reused verbatim here: every possibly-live
attempt this boot ever holds belongs to that SAME account/instrument scope, so ONE
:meth:`~tos_runtime.recon.service.ReconciliationService.reconcile` call per boot — never one per
attempt — already covers every attempt in scope
(:class:`~tos_runtime.recon.service.ReconciliationService.reconcile`'s own ``attempt_ids``
discovery reads them off the injected evidence/witness observations directly, it does not need
the caller to enumerate them up front). The report's ``permits_capacity_release`` /
``permits_rearm`` are themselves already conjunctions over every attempt AND orphan order found
in that scope (that service's own module docstring), so applying the SAME verdict to every
possibly-live attempt in :class:`~tos_runtime.recovery.inputs.RecoveryInputs` is not a
simplification this module introduces — it is what the report already means.

**``MATCHED`` is reachable (TOS Phase 5 W1 close-out, previously disclosed as unreachable).**
:mod:`tos_runtime.recon.service`'s own module docstring used to record this compose root's
scope-level RCL reservation ids (``f"resv-{account}-{instrument}"``,
:class:`~tos_runtime.rcl.obligation.CapacityObligationRecorder`'s own convention) as making
:class:`~tos_runtime.recon.service.ReconciliationClass.MATCHED` structurally unreachable, since
:meth:`~tos_runtime.recon.service.ReconciliationService.reconcile` looked up
``rcl_reader.reservation_state`` keyed by the RAW attempt id. That service now accepts an
injected ``reservation_id_for_attempt`` resolver for exactly this bridge (see its own module
docstring's "``attempt_id`` vs ``reservation_id``" section); :mod:`tos_runtime.recovery.inputs`
supplies one that mirrors ``CapacityObligationRecorder``'s own formula, so a genuinely
corroborated attempt (RCL reservation open, evidence-receipt + witness agreeing, Final Quantity
Proof recorded) can now actually clear.

**Fail-closed on any read failure (defence in depth).** :meth:`ReconciliationService.reconcile`
guards its own ``BrokerWitness.observe`` call against
:class:`~tos_runtime.recon.ports.WitnessUnavailable` internally, but does **not** guard its
``EvidenceReceiptReader.receipts`` call the same way — and
:class:`~tos_runtime.recon.evidence_reader.SqliteEvidenceReceiptReader` raises that SAME
exception type on a genuine sqlite read failure (its own module docstring). Rather than patch a
sibling lane's already-landed ``service.py`` control flow to add a second guard there, this
module wraps the WHOLE ``.reconcile()`` call in a broad ``except Exception`` — a boot-time
barrier must resolve to a definite verdict, never propagate an unhandled exception out of
``compose_paper_runtime`` — and treats ANY failure exactly like an unavailable witness: every
possibly-live attempt stays HELD with :data:`RECON_UNAVAILABLE`.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.*`` +
``tos_runtime.*`` only. No ``shared.*``. Pure judgement over an injected, already-constructed
:class:`~tos_runtime.recon.service.ReconciliationService` — this module opens no store, no log,
no witness of its own; that construction is the caller's (``tos_runtime.compose
._recovery_wiring`` -> ``tos_runtime.recovery.inputs``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tos.recon import FreshnessMarker

from tos_runtime.recon.ports import WitnessScope
from tos_runtime.recon.service import ReconciliationService

if TYPE_CHECKING:
    # Type-only: tos_runtime.recovery.inputs itself imports this module (for
    # reconcile_possibly_live_attempts), so an eager import here would be circular. `from
    # __future__ import annotations` (above) already defers every annotation in this module to a
    # string, so this import is never executed at runtime -- zero behavioral difference from an
    # eager one, just breaks the cycle at import time.
    from tos_runtime.recovery.inputs import RecoveryInputs

#: :attr:`~tos_runtime.recovery.inputs.RecoveryInputs.possibly_live_reconciliation`'s own value
#: for a possibly-live attempt this module positively cleared — only when the kernel-backed
#: :class:`~tos_runtime.recon.service.ReconciliationReport` says BOTH
#: ``permits_capacity_release`` AND ``permits_rearm`` for the whole scope (module docstring).
#: Defined HERE (not in :mod:`tos_runtime.recovery.barrier`) because :mod:`tos_runtime.recovery
#: .barrier` itself depends on :mod:`tos_runtime.recovery.inputs`, which depends on this module —
#: defining it in ``barrier.py`` and importing it back here would be the exact import cycle the
#: ``TYPE_CHECKING`` guard above avoids for ``RecoveryInputs``; ``barrier.py`` re-exports both
#: constants from here instead.
RECONCILED = "RECONCILED"
#: The reason recorded when reconciliation could not be run, or ran but did not clear an attempt
#: with a report-supplied reason of its own (module docstring's fail-closed path).
RECON_UNAVAILABLE = "RECON_UNAVAILABLE"

__all__ = ["RECONCILED", "RECON_UNAVAILABLE", "reconcile_possibly_live_attempts"]


def reconcile_possibly_live_attempts(
    inputs: RecoveryInputs,
    *,
    service: ReconciliationService | None,
    scope: WitnessScope,
    freshness: FreshnessMarker,
) -> dict[str, str]:
    """Attempt to clear every possibly-live attempt in ``inputs`` against ``service``.

    Args:
        inputs: The already-assembled :class:`~tos_runtime.recovery.inputs.RecoveryInputs` for
            THIS boot. Read-only — never mutated.
        service: The already-constructed :class:`~tos_runtime.recon.service.ReconciliationService`
            for this runtime, or ``None`` when one could not be built at all (module docstring's
            fail-closed path — the caller decides what "could not be built" means for its own
            construction; this function only branches on the ``None``/not-``None`` distinction).
        scope: The (account, instrument) window every possibly-live attempt in THIS runtime
            belongs to (module docstring's "one scope" assumption).
        freshness: The injected freshness/time-confidence marker for THIS boot
            (:class:`~tos.recon.FreshnessMarker`) — never the kernel's own all-``None`` default;
            an all-``None`` marker fails every field closed regardless of how corroborated the
            evidence otherwise is (``tos.recon.predicates.freshness_ok``'s own contract), which
            would make this function permanently unable to clear anything even when it should.

    Returns:
        ``{event_id: RECONCILED}`` for every possibly-live attempt in ``inputs`` when, and ONLY
        when, one :meth:`~tos_runtime.recon.service.ReconciliationService.reconcile` call over
        ``scope`` reports BOTH ``permits_capacity_release`` AND ``permits_rearm`` (plan §2
        decision 3's own conjunction — never one flag alone: a mutation that accepted
        ``permits_capacity_release`` in isolation would clear an attempt the kernel's own
        no-blended-release discipline never actually authorized a re-arm for).
        ``{event_id: <reason>}`` for every possibly-live attempt otherwise, where ``<reason>`` is
        the report's own ``reason`` string when one is available, else
        :data:`RECON_UNAVAILABLE`. An empty ``inputs.possibly_live_attempts`` always returns
        ``{}`` — nothing to reconcile is not a reconciliation failure.
    """
    if not inputs.possibly_live_attempts:
        return {}
    if service is None:
        return {
            attempt.event_id: RECON_UNAVAILABLE
            for attempt in inputs.possibly_live_attempts
        }
    try:
        report = service.reconcile(scope, freshness=freshness)
    except (
        Exception
    ):  # noqa: BLE001 — module docstring's "fail-closed on any read failure"
        return {
            attempt.event_id: RECON_UNAVAILABLE
            for attempt in inputs.possibly_live_attempts
        }
    if report.permits_capacity_release and report.permits_rearm:
        return {
            attempt.event_id: RECONCILED for attempt in inputs.possibly_live_attempts
        }
    reason = report.reason or RECON_UNAVAILABLE
    return {attempt.event_id: reason for attempt in inputs.possibly_live_attempts}
