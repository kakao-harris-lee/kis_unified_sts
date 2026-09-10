"""``tos_runtime.recon`` — Phase 5 W1 three-way reconciliation (plan §2 decision 3).

Runtime realization of the kernel ``tos.recon`` predicate substrate: this package
assembles injected RCL / evidence-receipt / broker-witness observations and calls the
kernel's own predicates for every judgement — it authors none itself (see
:mod:`tos_runtime.recon.service`'s module docstring).

Design: ``docs/plans/2026-09-10-tos-phase5-recovery-governance-plan.md`` §2 decision 3,
§4 W1 row. Kernel substrate: ``tos.recon`` (``docs/plans/2026-07-25-tos-reconciliation-
confidence-design.md``).
"""

from __future__ import annotations

from tos_runtime.recon.ports import (
    BrokerWitness,
    EgressReceiptObservation,
    EvidenceReceiptReader,
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
    WitnessUnavailable,
)
from tos_runtime.recon.service import (
    AttemptClassification,
    ReconciliationClass,
    ReconciliationReport,
    ReconciliationService,
)
from tos_runtime.recon.witness_synthetic import SyntheticLedgerWitness

__all__ = [
    "AttemptClassification",
    "BrokerWitness",
    "EgressReceiptObservation",
    "EvidenceReceiptReader",
    "ReconciliationClass",
    "ReconciliationReport",
    "ReconciliationService",
    "SyntheticLedgerWitness",
    "WitnessOrder",
    "WitnessOrderState",
    "WitnessScope",
    "WitnessSnapshot",
    "WitnessUnavailable",
]
