"""``tos_runtime.recovery`` — the Phase 5 W1 boot-time recovery barrier.

Plan: ``docs/plans/2026-09-10-tos-phase5-recovery-governance-plan.md`` §2 decision 2, wave W1.
Design: ``docs/plans/2026-07-26-tos-startup-recovery-design.md``. Kernel: :mod:`tos.sbr`
(Safe-Startup / Recovery-Barrier / Conservative-Resume).

Public surface:

* :mod:`tos_runtime.recovery.inputs` — :class:`~tos_runtime.recovery.inputs.RecoveryInputs` +
  :func:`~tos_runtime.recovery.inputs.assemble_recovery_inputs` (pure derivation from durable
  stores; no operator input parameter anywhere).
* :mod:`tos_runtime.recovery.possibly_live` — crash-window (finding #3) possibly-live attempt
  reconstruction.
* :mod:`tos_runtime.recovery.legacy_receipts` — Phase 3 carryover ⓑ (fingerprint-less receipts
  in the replay window).
* :mod:`tos_runtime.recovery.reconciliation` — runs a real, already-constructed
  :class:`~tos_runtime.recon.service.ReconciliationService` (assembled by
  :mod:`tos_runtime.recovery.inputs`, using :class:`~tos_runtime.recon.evidence_reader
  .SqliteEvidenceReceiptReader` for the one port that package ships as a bare Protocol only)
  against every possibly-live attempt's shared account/instrument scope; only a positively-
  established confidence clears them.
* :mod:`tos_runtime.recovery.barrier` — :class:`~tos_runtime.recovery.barrier.RecoveryBarrier`,
  folding the above into the kernel's own :class:`~tos.sbr.vocabulary.ReadinessVerdict` via
  :func:`tos.sbr.predicates.obligation_graph_closed` (never re-authoring that judgement here).

Compose wiring lives in :mod:`tos_runtime.compose._recovery_wiring` (a separate module, not
this package — the package boundary here is kernel-shaped, decision-and-observation logic only;
compose is where a durable evidence record and the ``ComposedRuntime.driver=None`` hold actually
happen).

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.*`` +
``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

from tos_runtime.recovery.barrier import (
    RECON_UNAVAILABLE,
    RECONCILED,
    RecoveryBarrier,
    RecoveryVerdict,
)
from tos_runtime.recovery.inputs import (
    OpenReservation,
    RecoveryInputs,
    assemble_recovery_inputs,
)
from tos_runtime.recovery.legacy_receipts import (
    LegacyReceiptFacts,
    legacy_receipts_in_window,
)
from tos_runtime.recovery.possibly_live import (
    PossiblyLiveAttempt,
    reconstruct_possibly_live_attempts,
)
from tos_runtime.recovery.reconciliation import reconcile_possibly_live_attempts

__all__ = [
    "RECONCILED",
    "RECON_UNAVAILABLE",
    "LegacyReceiptFacts",
    "OpenReservation",
    "PossiblyLiveAttempt",
    "RecoveryBarrier",
    "RecoveryInputs",
    "RecoveryVerdict",
    "assemble_recovery_inputs",
    "legacy_receipts_in_window",
    "reconcile_possibly_live_attempts",
    "reconstruct_possibly_live_attempts",
]
