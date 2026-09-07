"""Currentness assembly + egress currentness proof issuance + steps 13/14.

Design #40 (`docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-
decisions.md`) §5 order 6, lane R
(`docs/plans/2026-09-08-tos-phase2-runtime-slice3-authority-risk-currentness-
compose-plan.md` §3). Realizes the kernel's ``tos.cur`` (ADR-002-024) pure
aggregator over live RCL/Trustworthy-Time/authority/afg inputs: this package
never judges currentness itself — every admissibility/completeness decision
is a call-through to a kernel predicate (``vector_complete``,
``proof_admissible``, ``authority_epoch_current``, ``exact_binding_holds``).

Public surface groups by module:

* :mod:`tos_runtime.currentness.vector` — :class:`~tos_runtime.currentness.
  vector.CurrentnessAssembler`, :class:`~tos_runtime.currentness.vector.
  DimensionReport` (the exact shape lanes P/Q's injected readers return —
  the owner decides ``positively_established``/``restrictive_floor``, never
  this assembler), :class:`~tos_runtime.currentness.vector.
  SingleNodeCommitCertificate` (explicitly NOT a quorum certificate —
  R-RCL-F0), :class:`~tos_runtime.currentness.vector.Item3Fields`.
* :mod:`tos_runtime.currentness.proof` — :class:`~tos_runtime.currentness.
  proof.EgressCurrentnessProofIssuer`, :class:`~tos_runtime.currentness.
  proof.Item16Fields`.
* :mod:`tos_runtime.currentness.stages` — :class:`~tos_runtime.currentness.
  stages.AttemptBindVerificationStage` (step 13),
  :class:`~tos_runtime.currentness.stages.TransmissionCapabilityStage`
  (step 14), :class:`~tos_runtime.currentness.stages.
  TransmissionCapabilityContext`.
* :mod:`tos_runtime.currentness.config` — :func:`~tos_runtime.currentness.
  config.load_currentness_config`.

This package does not import ``tos_runtime.authority`` or ``tos_runtime.risk``
(lanes P/Q's own packages) — cross-lane inputs are injected callables only
(see :class:`~tos_runtime.currentness.vector.CurrentnessAssembler`'s own
constructor).
"""

from __future__ import annotations

from tos_runtime.currentness.config import (
    CurrentnessConfig,
    CurrentnessConfigError,
    load_currentness_config,
)
from tos_runtime.currentness.proof import EgressCurrentnessProofIssuer, Item16Fields
from tos_runtime.currentness.stages import (
    AttemptBindVerificationStage,
    TransmissionCapabilityContext,
    TransmissionCapabilityStage,
)
from tos_runtime.currentness.vector import (
    CurrentnessAssembler,
    DimensionReport,
    Item3Fields,
    SingleNodeCommitCertificate,
)

__all__ = [
    "AttemptBindVerificationStage",
    "CurrentnessAssembler",
    "CurrentnessConfig",
    "CurrentnessConfigError",
    "DimensionReport",
    "EgressCurrentnessProofIssuer",
    "Item16Fields",
    "Item3Fields",
    "SingleNodeCommitCertificate",
    "TransmissionCapabilityContext",
    "TransmissionCapabilityStage",
    "load_currentness_config",
]
