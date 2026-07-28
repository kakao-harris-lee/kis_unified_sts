"""Safety Incident Declaration, Containment, Controlled Shutdown, and Closure Governance
(ADR-002-027 — "SIR") pure models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-027 part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design
contract ``docs/plans/2026-07-28-tos-safety-incident-design.md`` (v1.1, operator-delegated
auto-ratified 2026-07-28). It authors the **restrictive-declaration / exact-scope-combined /
evidence-honesty structural substrate** — the restrictive, asymmetric, non-authorizing declaration
(SIR-EV-001), the exact greatest-credible scope with combined incidents and no favorable subset
(SIR-EV-002), and the evidence / communication / status honesty ladder (SIR-EV-009) — over six
digest-bound artifacts plus injected value models (design #28 §2).

**This is the series' safety-incident governance *greenfield content owner*, with NO inbound deferee but
ONE committed forward concept-seam (design #28 §0.1/§0.4b — the key architecture decision, the decisive
contrast with WDR).** No landed sibling defers incident *content* to ``tos.sir``. What is different from
WDR is that the concept this package produces — a dominating open incident restriction — is **already
consumed** by two committed siblings' de-restriction / recovery predicates
(``protective/predicates.py:395``; ``sbr/predicates.py:731``), and the §5.4 Incident Generation is
already consumed as an injected opaque coordinate by wdr (``wdr/predicates.py:14``;
``wdr/state.py:48-49``). Every one of those consumptions is an **anonymous** ``bool | None`` or opaque
scalar and none references a ``tos.sir`` type, so the seam is **forward** and the **sibling edge is 0**;
sir is the producer of those coordinates' *values*, artifacts and completeness judgements, not a deferee.
The name ``tos.sir`` is fixed only by three firewall *exclusion*-list comments
(``wdr/__init__.py:47`` / ``rlp/__init__.py:39`` / ``cur/__init__.py:51`` enumerate the future sibling
``tos.sir`` as auto-excluded), so **naming is weak soft load-bearing** — a different name would orphan no
functional reference, only make those list comments imprecise (design #28 §0.4a).

Two same-name / different-proposition collisions are sealed explicitly (design #28 §0.5): the spg
governed-artifact-**kind** tokens ``SAFETY_INCIDENT_POLICY`` / ``ACTIVE_SAFETY_INCIDENT_SET``
(``spg/vocabulary.py:215-216``) name the kind of artifact ADR-002-014 governs, not these artifact models;
and the cur currentness dimension key ``DimensionKey.INCIDENT`` (``cur/vocabulary.py:143``, a member of
cur's mandated floor) is a *currentness* dimension whose completeness judgement stays cur-owned — sir
produces that dimension's **value** (the Incident Generation and the Active Safety Incident Set digest)
and re-authors none of cur's judgement. A third, ``evidence/gap.py:41`` ``GapStatus.SUSPECTED``, collides
in string only with :class:`~tos.sir.vocabulary.IncidentLifecycleState`.

**The maximum risk here is over-realization (design #28 §0.4c).** SIR-INV-001..016 is sixteen invariants
over only three ``EV-L1``-sliced rows: exactly five (001 / 002 / 003 / 004 / 014) contribute to the L1
yolks and the other eleven (005-013 / 015 / 016) are authored as **predicate-only substrate that closes
no SIR-EV at all**. The authoritative signal registry and deterministic classifier, the dependency-graph
and common-mode engine, the Incident Generation registry and writer fence, the restrictive ingress and
final-egress currentness latch, the controlled-shutdown ordering proof, the Effective Principal quorum
counting, the external broker procedure and credential custody, the evidence / notification / timeline
pipelines, the ADR-002-025 demotion and ADR-002-017 Recovery Barrier handoff, and the §22 security
controls are **all human / runtime / +Security / +Broker / sibling-owned**, never L1. The second risk is
duplication: the sbr Recovery Barrier / Recovery Session, hag Effective Principal collapse + quorum +
Governed Single-Operator Re-Arm Variant, spg policy activation + Hard Safety Envelope, evidence custody /
causal chain / gap, liveauth Live Authorization, rcl capacity mutation + worst-credible effect, egress
final-egress enforcement, cur Active Currentness Vector, authority Safety Authority / HALT, protective
Protective Action Controller / Cancellation Arbiter, time Trustworthy Time, rlp demotion, and wdr
Non-Waivable Boundary are **all injected-consumed**, re-authored not at all (design #28 §3.5).

This package is **pure, non-transmitting, non-mutating, and clock-free** (design #28 §0.2/§4.1): it has
**no** send / transmit / sign / arm / mutate / reserve / release / transfer / clear-halt method and no
imperative declare / contain / shutdown / close action — the structural absence of such a method is this
package's identity (§4.1 constructive-absence canary; the void-canary tests assert it). It **cannot**
create or release capacity, classify or create protection, create Safety Authority, issue Live
Authorization, create Transmission Capability, grant broker permission, clear a HALT, create production
scope, re-arm, or establish recovery readiness (all-false
:class:`~tos.sir._base.AllFalseIncidentAuthority`, SIR-INV-001). A positive result comes only from
positive proof, everything else is denial (design #28 §4.3 — the polarity seal against the #18/#22/#23/#25
MAJOR-2 fail-open lesson, with **negative-polarity fields never read with ``is not True``**; §4.4 — the
reconcile seal against the #22 MAJOR-1 first-entry lesson, with the §5.5/§16 explicit-empty Active Safety
Incident Set kept **valid** against the #26 MAJOR-1 over-sealing lesson).

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``classify_record_pair``) + ``tos.ordering`` (Incident Generation order). It
imports **no** sibling — every real sibling and any future one (``tos.stm`` / ``tos.sci``) is excluded by
the §7.1 **allowlist** closure test (``tos.*`` closure ⊆ {``tos.canonical``, ``tos.ordering``,
``tos.sir``}) — **sibling edge 0** (design #28 §0.3/§3.4). **rcl edge 0** in particular: sir does no
capacity arithmetic (the worst-credible effect is an injected opaque coordinate, never a
``CapacityVector`` type), which is what ADR §13 line 380/382 demands — "RCL remains the sole capacity
mutation and serialization authority"; an incident budget, severity, responder priority, shutdown plan,
executive decision or accepted residual risk "is **never headroom**". **PROMOTE 0** — the digest /
ordering substrate is already core.

Identity is **independent, not** ``f(digest)`` for all six artifacts (design #28 §2.1/§3.1): each is an
immutable issued record; a same-id / different-**covered**-bytes forgery, re-issue or replay is a
detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` — the structural defence ADR §22 line 536
demands against "incident closure replay or duplicate consumption".

**Completion discipline (design #28 §1).** ``SIR-EV-001..012`` are all NOT_IMPLEMENTED. Three rows carry
an ``EV-L1`` slice (core): 001 Restrictive Detection and Declaration (``EV-L1/3+Security``), 002 Exact
Scope and Combined Incidents (``EV-L1/3``), 009 Evidence, Communication, and Status Honesty
(``EV-L1/3``). Six rows are predicate-only (≥ ``EV-L2``, +Broker / +Security): 003 / 005 / 006 / 010 /
011 / 012. Three rows are not-Phase-1 at an ``EV-L3`` floor — 004 Controlled Shutdown and Hard Fencing
(``EV-L3+Broker+Security``), 007 Incident Currentness and Send Race (``EV-L3+Security``), 008 Partition,
Common Mode, and Compromise (``EV-L3+Security``) — the **most** ``EV-L3``-floored rows of the governance
sextet. Phase 1 authors the L1-decidable structural substrate and closes **no** SIR-EV: even the core
rows carry ``/3`` (integration / adversarial) residue and 001 additionally carries the whole ``+Security``
signal-forgery / suppression / downgrade axis (§22 line 532). Authoring is not evidence (VER-002-001 §5;
ADR §26 line 644 "Written cases are not completed evidence"; §29 line 757 "Authorship ... does not satisfy
these gates"). Tag for any claim: "restrictive-declaration / exact-scope-combined / evidence-honesty
predicate substrate only; SIR-EV-001..012 remain NOT_IMPLEMENTED pending EV-L2/L3 integration,
adversarial, +Security and +Broker evidence; **EV-L1-complete claim forbidden**; the signal classifier /
dependency-graph engine / controlled-shutdown orchestrator / closure quorum / per-action egress binding /
worst-credible-effect computation / Live Authorization issuance are re-authored / runtime / human /
+Security / +Broker / sibling-owned; L1 is declaration / scope / honesty / closure structural judgement
only."

Public surface groups by module:

* :mod:`tos.sir.vocabulary` — the six truthy-untestable SIR StrEnums (``IncidentLifecycleState`` /
  ``ClosureDecisionResult`` / ``IncidentRecordState`` / ``CommunicationAssertionKind`` /
  ``SignalClassificationClass`` / ``ClosureDimension``) + the transcribed ADR anchors.
* :mod:`tos.sir.records` — the six digest-bound artifacts + the all-false
  ``AllFalseIncidentAuthority``.
* :mod:`tos.sir.state` — the injected value / input models + the ``tos.ordering`` generation REUSE.
* :mod:`tos.sir.predicates` — the three yolk predicates + supporting + the predicate-only §6 substrate +
  the not-Phase-1 §6b thin send-race / external-activity models + the §4.3 polarity registry.
"""

from __future__ import annotations

from tos.sir._base import (
    AllFalseIncidentAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)
from tos.sir.predicates import (
    DERIVED_NEGATIVE_POLARITY_NAMES,
    NEGATIVE_POLARITY_FIELDS,
    POSITIVE_POLARITY_FIELDS,
    active_set_is_canonical_union,
    all_false_incident_authority,
    analysis_not_prevention,
    attempt_potentially_live,
    broker_finality_unchanged,
    classification_admissible,
    closure_administrative_non_permissive,
    closure_contract_complete,
    closure_independence_non_self_exemption,
    closure_single_use_non_authorizing,
    communication_assertions_distinguished,
    containment_uses_normal_authority,
    controlled_shutdown_not_broker_finality,
    declaration_creates_no_authority,
    dependency_closure_complete,
    dominating_open_incident_present,
    economic_effect_outlives_incident_state,
    emergency_evidence_no_suppress,
    evidence_communication_status_honest,
    external_activity_conservative,
    final_quantity_proof_absent,
    incident_system_no_route,
    low_severity_no_narrow,
    message_ack_not_enforcement_ack,
    no_favorable_subset,
    obligations_survive_shutdown,
    recovery_handoff_requires_accepted_barrier,
    recovery_revives_nothing,
    restriction_dominates_send,
    restrictive_declaration_non_authorizing,
    scope_exact_combined_no_favorable_subset,
    scope_not_self_exempt_or_narrowed,
    step_completion_proven,
    unknown_remains_conservative,
)
from tos.sir.records import (
    ActiveSafetyIncidentSet,
    IncidentClosureDecision,
    IncidentContainmentPlan,
    IncidentRecoveryHandoffPackage,
    SafetyIncidentPolicy,
    SafetyIncidentRecord,
)
from tos.sir.state import (
    ActiveSetMember,
    AnalysisClaim,
    BrokerFinalityTokens,
    ClosureIndependenceLadder,
    CommunicationHonestyLadder,
    ContainmentAction,
    ControlledShutdownProcedure,
    ExternalActivityClaim,
    IncidentClassificationInput,
    IncidentDependencyClosure,
    IncidentScope,
    IncidentUnknownState,
    OngoingSafetyObligation,
    RecoveryRevivalInputs,
    SafetySignal,
    ShutdownStep,
    incident_generation_advances,
    max_incident_generation,
)
from tos.sir.vocabulary import (
    CLOSURE_CONTRACT_ITEM_COUNT,
    CLOSURE_CONTRACT_ITEM_POLARITY,
    CLOSURE_CONTRACT_ITEMS,
    INCIDENT_LIFECYCLE_ORDER,
    MANDATED_CLOSURE_DIMENSION_FLOOR,
    RESTRICTIVE_LIFECYCLE_STATES,
    SHUTDOWN_PROHIBITIONS,
    SHUTDOWN_STEP_KINDS,
    ClosureDecisionResult,
    ClosureDimension,
    CommunicationAssertionKind,
    IncidentLifecycleState,
    IncidentRecordState,
    SignalClassificationClass,
)

__all__ = [
    # base (reused core + sir-local all-false authority)
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
    "AllFalseIncidentAuthority",
    # vocabulary
    "IncidentLifecycleState",
    "ClosureDecisionResult",
    "IncidentRecordState",
    "CommunicationAssertionKind",
    "SignalClassificationClass",
    "ClosureDimension",
    "INCIDENT_LIFECYCLE_ORDER",
    "RESTRICTIVE_LIFECYCLE_STATES",
    "MANDATED_CLOSURE_DIMENSION_FLOOR",
    "CLOSURE_CONTRACT_ITEMS",
    "CLOSURE_CONTRACT_ITEM_POLARITY",
    "CLOSURE_CONTRACT_ITEM_COUNT",
    "SHUTDOWN_STEP_KINDS",
    "SHUTDOWN_PROHIBITIONS",
    # records — the six digest-bound artifacts
    "SafetyIncidentPolicy",
    "SafetyIncidentRecord",
    "ActiveSafetyIncidentSet",
    "IncidentContainmentPlan",
    "IncidentRecoveryHandoffPackage",
    "IncidentClosureDecision",
    # state — injected value / input models + ordering REUSE
    "SafetySignal",
    "ActiveSetMember",
    "IncidentDependencyClosure",
    "IncidentScope",
    "ShutdownStep",
    "ControlledShutdownProcedure",
    "OngoingSafetyObligation",
    "CommunicationHonestyLadder",
    "AnalysisClaim",
    "ClosureIndependenceLadder",
    "IncidentClassificationInput",
    "ContainmentAction",
    "IncidentUnknownState",
    "BrokerFinalityTokens",
    "RecoveryRevivalInputs",
    "ExternalActivityClaim",
    "incident_generation_advances",
    "max_incident_generation",
    # polarity registry (design #28 §4.3 / §7.2 (a))
    "POSITIVE_POLARITY_FIELDS",
    "NEGATIVE_POLARITY_FIELDS",
    "DERIVED_NEGATIVE_POLARITY_NAMES",
    # core §5 predicates — the three yolk + supporting
    "restrictive_declaration_non_authorizing",
    "declaration_creates_no_authority",
    "low_severity_no_narrow",
    "classification_admissible",
    "scope_not_self_exempt_or_narrowed",
    "scope_exact_combined_no_favorable_subset",
    "active_set_is_canonical_union",
    "no_favorable_subset",
    "dependency_closure_complete",
    "evidence_communication_status_honest",
    "communication_assertions_distinguished",
    "message_ack_not_enforcement_ack",
    "analysis_not_prevention",
    "emergency_evidence_no_suppress",
    # predicate-only §6 substrate
    "all_false_incident_authority",
    "containment_uses_normal_authority",
    "incident_system_no_route",
    "controlled_shutdown_not_broker_finality",
    "step_completion_proven",
    "recovery_revives_nothing",
    "dominating_open_incident_present",
    "obligations_survive_shutdown",
    "unknown_remains_conservative",
    "broker_finality_unchanged",
    "final_quantity_proof_absent",
    "economic_effect_outlives_incident_state",
    "closure_administrative_non_permissive",
    "closure_contract_complete",
    "closure_single_use_non_authorizing",
    "closure_independence_non_self_exemption",
    "recovery_handoff_requires_accepted_barrier",
    # not-Phase-1 thin models §6b
    "restriction_dominates_send",
    "attempt_potentially_live",
    "external_activity_conservative",
]
