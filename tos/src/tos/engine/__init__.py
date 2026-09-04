"""tos.engine — the single event core + Execution Coordinator decision-pipeline orchestration.

Realizes the ratified project-side design contract
``docs/plans/2026-07-29-tos-engine-event-core-design.md`` (#31, D-E1, v1.1, operator-delegated
auto-ratification 2026-07-29) — the **owning runtime** for RFC-003 (Decision Framework §7 pipeline),
RFC-005 (Execution Model §6/§7/§11/§12), RFC-002 §10.7 (Execution Coordinator), and RFC-008 §10
(consuming layers), wired around ADR-002-002 §11's 19-step Normal Commitment Flow.

**This is the series' first owning-runtime package.** The thirty-two packages before it are pure
decision kernels with a minimal import closure; ``tos.engine`` is the integrator that assembles
them, so its closure is deliberately a **superset** of theirs (design #31 §0.3/§10.2-1). The
allowlist is still a strict subset::

    {tos, tos.canonical, tos.ordering, tos.dsl, tos.capsule, tos.time, tos.evidence,
     tos.ioc, tos.venue, tos.rcl, tos.are, tos.afg, tos.cur, tos.engine}

Six of those are *directly realized* edges (canonical / ordering / dsl / capsule / time / evidence —
the decision pipeline, the core state, and the provisional sink); the rest are **contract-typing**
edges: the sequencer references the sibling verdict *types* while every stage's *logic* stays
injected (design #31 §0.3/§5.2). ``tos.brokercap`` and ``tos.egress`` are deliberately **outside**
the closure — they live beyond the D-E4 send-boundary injection point, and ``tos.egress`` (the QCC
kernel) is never encroached upon (design #31 §5.4/§4.5).

⚠ **Provisional; closes no EV** (design #31 §1.1 — the document's top-level honesty declaration).
Three independent reasons converge:

1. production canonicalization is unresolved — every digest here rides
   ``ev-l1-provisional-0``, explicitly non-production;
2. the DSL evaluation budget this package's sequencer consumes (``dsl_evaluation_budget_steps``,
   DCE-INV-007) is **not a VERIFICATION-PROFILE-002 key at all** — no such name is in the
   profile's bounds/limits census (:mod:`tos.engine.records` ``EngineConfiguration``); the
   profile does carry ``MAX_dsl_evaluation_ms`` (non-null), but that bounds a distinct,
   still-deferred wall-clock metering layer, not this slice's symbolic step counter. Independent-reviewer
   designation (P0-3) is likewise a register concern (``EVIDENCE-REGISTER-DEV.csv``), not a
   profile key, and no evidence-register row is scoped to ``tos.engine`` to check it against;
3. the authority runtimes this sequencer calls in order — Independent Approval, the Aggregate Risk
   Authority, the Action Flow Governor, and above all the RCL's atomic commit — exist here only as
   **NON-AUTHORITATIVE PROVISIONAL** stand-ins (:mod:`tos.engine.standins`). Without a real
   linearizable ledger and a real independent approver, capacity and approval evidence cannot be
   produced *in principle*.

VER-002-KEYS: ``dsl_evaluation_budget_steps``; CONTRAST: ``MAX_dsl_evaluation_ms``

So this slice demonstrates the **wiring** — the call order, the binding hand-off, the fail-closed
stop, and backtest/live parity — and it demonstrates nothing about the decision, execution, or risk
models' acceptance. Of ADR-002-002 §11's nineteen steps this package realizes exactly **two**
directly (step 1's proposal and step 12's attempt request); its real product is the fail-closed
sequencer between them.

Where the honesty boundaries sit, explicitly:

* **fail-closed guarantee: steps 1-14 only.** Steps 15-19 (final-egress currentness, QCC,
  single-use capability, actual-outbound comparison) are constitutionally D-E4's; this package
  refuses to host them and claims nothing about them (design #31 §4.5 item-7).
* **escape-safety: not demonstrated.** Slice #1 accepts in-process typed
  :class:`~tos.dsl.AuthoredStrategy` objects, which are admissible by construction, so the
  escape-checker seam is never exercised. A serialized authoring path's escape-safety is not
  claimed (design #31 §3.5).
* **env-configuration sealing: partial.** Admission requires at least one capsule-sourced operand
  in every outcome-gating comparison, which blocks the core config-relabelling escape; complete
  enforcement is the D-E2 Critical Input Snapshot provenance surface (design #31 §3.2 (3)).
* **reproducibility, not distinctness.** The pipeline reproduces the same outcome from the same
  inputs; making *different* bars produce *different* identities depends on D-E2 distinct Snapshot
  digests (design #31 §6 Gap-1 / §9-9).
* **release: impossible here.** The provisional projection has no release path at all, because
  releasing capacity is the RCL's and a producer-local counter creates no headroom
  (RFC-002 §9.1:557-558).

The package is **pure, non-transmitting, authority-free, and clock-free**: it imports ``pydantic`` +
stdlib + the allowlisted ``tos.*`` only; it reads no ``os.environ``, opens no socket, uses no
``importlib`` / ``exec`` / ``eval`` / ``compile``, calls no wall clock, and contains no ``random`` /
``secrets`` / ``uuid`` — the attempt identity is content-addressed instead, so replay identity
survives (design #31 §7.1). Every one of those is actively verified by the import-closure and
determinism canaries in ``tos/tests/engine``.

Public surface groups by module:

* :mod:`tos.engine.vocabulary` — the closed event / stage / 19-step vocabulary + the truthy seals.
* :mod:`tos.engine.records` — events, injected coordinates, stage verdicts, the attempt request.
* :mod:`tos.engine.admission` — typed strategy admission (the D1↔D4 coupling) + key derivation.
* :mod:`tos.engine.registry` — the instrument-keyed dispatch registry (∅ both ways).
* :mod:`tos.engine.state` — the non-authoritative reservation projection + at-most-one retention.
* :mod:`tos.engine.adapters` — sibling verdict → positive-admit stage-verdict wrappers.
* :mod:`tos.engine.pipeline` — the RFC-003 §7 four-phase decision pipeline + the degrade fold.
* :mod:`tos.engine.sequencer` — the 19-step fail-closed Execution Coordinator sequencer.
* :mod:`tos.engine.standins` — the non-authoritative provisional authority stand-ins.
* :mod:`tos.engine.sink` — the provisional evidence sink + the replay-result adapter.
* :mod:`tos.engine.core` — the synchronous, deterministic single event core.
"""

from __future__ import annotations

from tos.engine._base import (
    COORDINATOR_SHALL_NOT_FLAGS,
    AllFalseCoordinatorAuthority,
)
from tos.engine.adapters import (
    action_flow_decision_verdict,
    action_flow_permit_verdict,
    aggregate_risk_decision_verdict,
    conformance_proof_verdict,
    economic_effect_envelope_verdict,
    egress_currentness_verdict,
    transmission_capability_verdict,
    venue_admissibility_verdict,
)
from tos.engine.admission import (
    AdmissionResult,
    compare_has_capsule_operand,
    declared_target_scopes,
    derive_instrument_key,
    iter_outcome_gating_compares,
    operand_source,
    policy_work_steps,
    strategy_admissible,
)
from tos.engine.core import (
    DecisionContextResolver,
    EngineCore,
    EventBatch,
    EventResult,
    EventSource,
    UnknownEventKindError,
    admit_kind,
    ordering_admission,
)
from tos.engine.pipeline import (
    PipelineResult,
    capsule_admitted,
    run_decision_pipeline,
    time_admits,
)
from tos.engine.records import (
    ATTEMPT_ID_PREFIX,
    AttemptRequest,
    DecisionTickPayload,
    EgressResultPayload,
    EngineConfiguration,
    EngineEvent,
    EngineEvidenceRecord,
    InstrumentKey,
    ProvisionalReservation,
    RegisteredStrategy,
    SendHandoff,
    StageRequest,
    StageVerdict,
    TimeAdmissionInputs,
)
from tos.engine.registry import Dispatch, RegistrationRefused, StrategyRegistry
from tos.engine.sequencer import (
    FlowResult,
    Stage,
    Transmit,
    build_attempt_request,
    reference_coordinate_digest,
    run_commitment_flow,
    validate_stage_map,
)
from tos.engine.sink import (
    PROVISIONAL_SINK_CHAIN_VERSION,
    EvidenceSink,
    NullEvidenceSink,
    RecordingEvidenceSink,
    replay_result_for,
)
from tos.engine.standins import ProvisionalStandIn, provisional_stage_map
from tos.engine.state import (
    PROJECTION_ORDER,
    PROJECTION_RANK,
    ProvisionalReservationLedger,
    knowledge_for_result,
)
from tos.engine.vocabulary import (
    ADMISSIBLE_EVENT_KINDS,
    CAPSULE_CONTEXT_SOURCE,
    COMMITMENT_FLOW_ORDER,
    CONFIG_CONTEXT_SOURCE,
    COORDINATOR_REALIZED_STEPS,
    FILL_RESULT_KINDS,
    GUARANTEED_FAIL_CLOSED_STEPS,
    INJECTED_STAGE_STEPS,
    SEND_BOUNDARY_STEPS,
    SEQUENCED_STEPS,
    AdmissionVerdict,
    CommitmentStep,
    DispatchResolution,
    EgressKnowledge,
    EgressResultKind,
    EventKind,
    EvidenceKind,
    HaltReason,
    OrderingAdmission,
    StageAuthorityClass,
    StageOutcome,
    step_number,
)

__all__ = [
    # base
    "COORDINATOR_SHALL_NOT_FLAGS",
    "AllFalseCoordinatorAuthority",
    # vocabulary
    "ADMISSIBLE_EVENT_KINDS",
    "CAPSULE_CONTEXT_SOURCE",
    "COMMITMENT_FLOW_ORDER",
    "CONFIG_CONTEXT_SOURCE",
    "COORDINATOR_REALIZED_STEPS",
    "FILL_RESULT_KINDS",
    "GUARANTEED_FAIL_CLOSED_STEPS",
    "INJECTED_STAGE_STEPS",
    "SEND_BOUNDARY_STEPS",
    "SEQUENCED_STEPS",
    "AdmissionVerdict",
    "CommitmentStep",
    "DispatchResolution",
    "EgressKnowledge",
    "EgressResultKind",
    "EventKind",
    "EvidenceKind",
    "HaltReason",
    "OrderingAdmission",
    "StageAuthorityClass",
    "StageOutcome",
    "step_number",
    # records
    "ATTEMPT_ID_PREFIX",
    "AttemptRequest",
    "DecisionTickPayload",
    "EgressResultPayload",
    "EngineConfiguration",
    "EngineEvent",
    "EngineEvidenceRecord",
    "InstrumentKey",
    "ProvisionalReservation",
    "RegisteredStrategy",
    "SendHandoff",
    "StageRequest",
    "StageVerdict",
    "TimeAdmissionInputs",
    # admission (D1 ↔ D4)
    "AdmissionResult",
    "compare_has_capsule_operand",
    "declared_target_scopes",
    "derive_instrument_key",
    "iter_outcome_gating_compares",
    "operand_source",
    "policy_work_steps",
    "strategy_admissible",
    # registry (D2)
    "Dispatch",
    "RegistrationRefused",
    "StrategyRegistry",
    # provisional core state (§2.4 / §4.4)
    "PROJECTION_ORDER",
    "PROJECTION_RANK",
    "ProvisionalReservationLedger",
    "knowledge_for_result",
    # sibling verdict adapters (§5.2 contract-typing edges)
    "action_flow_decision_verdict",
    "action_flow_permit_verdict",
    "aggregate_risk_decision_verdict",
    "conformance_proof_verdict",
    "economic_effect_envelope_verdict",
    "egress_currentness_verdict",
    "transmission_capability_verdict",
    "venue_admissibility_verdict",
    # decision pipeline (§3)
    "PipelineResult",
    "capsule_admitted",
    "run_decision_pipeline",
    "time_admits",
    # sequencer (§4)
    "FlowResult",
    "Stage",
    "Transmit",
    "build_attempt_request",
    "reference_coordinate_digest",
    "run_commitment_flow",
    "validate_stage_map",
    # provisional stand-ins (§4.4)
    "ProvisionalStandIn",
    "provisional_stage_map",
    # provisional evidence sink (§5.1 / §12-5)
    "PROVISIONAL_SINK_CHAIN_VERSION",
    "EvidenceSink",
    "NullEvidenceSink",
    "RecordingEvidenceSink",
    "replay_result_for",
    # event core (§2) + the D-E2/D-E3 plug slots (§12-1 / §12-4)
    "DecisionContextResolver",
    "EngineCore",
    "EventBatch",
    "EventResult",
    "EventSource",
    "UnknownEventKindError",
    "admit_kind",
    "ordering_admission",
]
