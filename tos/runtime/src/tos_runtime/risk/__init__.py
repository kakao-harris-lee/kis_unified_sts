"""``tos_runtime.risk`` — Aggregate Risk Authority (ARA) + Action Flow Governor
(AFG) runtime, and the engine ``Stage`` realizations for steps 6-10 of the
ADR-002-002 §11 Normal Commitment Flow (design #40 §5 order 5; slice plan §2).

The runtime never judges: every service here collects inputs (the RCL
reservation projection, an injected Trustworthy Time gate, caller-supplied
Phase-0/broker-capability-profile witnesses) and calls the kernel's own
conservative, fail-closed predicates (``tos.are``/``tos.afg``). See each
module's own docstring for its specific contract, the single-transaction
atomicity design (``ledger_stages``), and the reported ``CommandType``
vocabulary gap (``flow``).

Cross-lane isolation (slice plan §5): this package imports nothing from
``tos_runtime.authority`` / ``tos_runtime.currentness`` / ``tos_runtime.release``
(the sibling lanes of this same design #40 §5 sequence) — any cross-input a
future composition root needs (e.g. the time gate) is received here as an
injected callable/Protocol argument, never an import edge onto those
packages.
"""

from __future__ import annotations

from tos_runtime.risk.aggregate import (
    AggregateRiskConfigError,
    AggregateRiskDecisionInputs,
    AggregateRiskService,
    load_adverse_scenario_set,
    load_required_scenario_kinds,
)
from tos_runtime.risk.flow import (
    ActionFlowConfigError,
    ActionFlowDecisionInputs,
    ActionFlowGovernor,
    PermitIssueResult,
    permit_reservation_binding,
)
from tos_runtime.risk.ledger_stages import (
    ActionFlowDecisionStage,
    AggregateRiskDecisionStage,
    AtomicCommitStage,
    CommitmentUnavailabilityStage,
    LedgerVerificationStage,
    item15_fields,
)

__all__ = [
    "ActionFlowConfigError",
    "ActionFlowDecisionInputs",
    "ActionFlowDecisionStage",
    "ActionFlowGovernor",
    "AggregateRiskConfigError",
    "AggregateRiskDecisionInputs",
    "AggregateRiskDecisionStage",
    "AggregateRiskService",
    "AtomicCommitStage",
    "CommitmentUnavailabilityStage",
    "LedgerVerificationStage",
    "PermitIssueResult",
    "item15_fields",
    "load_adverse_scenario_set",
    "load_required_scenario_kinds",
    "permit_reservation_binding",
]
