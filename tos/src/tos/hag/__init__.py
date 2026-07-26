"""Human Safety Authority, Dual Control, and Break-Glass Governance pure models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-015 (Human Safety Authority, Dual Control, and Break-Glass Governance —
"HAG") part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design contract
``docs/plans/2026-07-26-tos-human-authority-design.md`` (v1.1, operator-delegated auto-ratified
2026-07-26). It authors the **human-authority general model** — the effective-principal control
graph and its collapse, quorum-independence, exact approval binding, single-use consumption and
lifecycle, break-glass directional confinement, human-protective proposal-only, dual-control
effective distinctness and narrow scope, approval / economic continuity and non-revival, human
authority replay reconstruction, separation of duties, human HALT monotonicity, delegation bounds,
compromise fail-closed, and the governed-single-operator variant substrate — over eight
digest-bound artifacts plus injected value models (design #20 §2).

HAG owns the **human-authority general model**; it is **not** a re-authoring of any sibling
instance (design #20 §0.4b/§3.5): the liveauth §17 re-arm consumption instance
(``rearm_dual_control_satisfied`` / ``Safe053VariantAttestation`` / ``ReArmPathKind`` /
7-control / 13-prerequisite) is liveauth-owned, the safety-config break-glass action-token
(``break_glass_confined`` / ``BREAK_GLASS_ALLOWED_ACTIONS``) is spg-owned, the automated
per-proposal decision (``IndependentApprovalDecision`` / ``ProposalApprovalRequest``) is iap-owned,
the protective classification verdict (``protective_classification``) is protective-owned, capacity
is rcl-owned, and replay custody is evidence-owned. HAG **consumes** every one of those as an
**injected produced scalar / bool / verdict / digest** and re-authors none of them. It owns only
the human-authority general model: effective-principal collapse (the yolk — the same-person-
multi-identity that the liveauth string ``!=`` cannot catch, §3.5), the eight artifacts, the human
approval axis (distinct from the iap automated axis — ADR §4 line 98), and the human break-glass
authority-class direction (8 classes, distinct from the spg 2-token action).

This package is **pure, non-transmitting, non-enforcing, and clock-free** (design #20 §0.2/§4.6):
frozen pydantic models over injected state plus conservative fail-closed predicates. It **cannot**
mutate capacity, activate configuration, issue Live Authorization, clear a deny latch, transmit to
a broker, or re-arm (all-false :class:`~tos.hag._base.HumanAuthorityEffect`, HAG-INV-004) — it
produces decision **verdicts** / mappings and forward record artifacts; the owning runtime (a
future Human Authority Service / Approval Verifier / HALT ingress, +Security) enforces them. There
is no "assume-authority" / "silence-is-approval" / "auto-re-arm" / "collapse-bypass" path: a
positive result comes only from positive proof, everything else is ``False`` (design #20 §4.1/§4.3
— the structural seal against the #6 fail-open lesson).

**Truthy-sentinel discipline (design #20 §2.2/§4.7 — #13/#14 M1 adopted from the start).**
``AttestationDecision`` (APPROVE / DENY / ABSTAIN) and ``ApprovalLifecycleState`` are
**truthy-untestable** ``StrEnum``s (``__bool__`` raises ``TypeError``), so a consumer's
``if decision:`` misuse raises rather than reading ``DENY`` / ``ABSTAIN`` / ``EXPIRED`` / ``REVOKED``
as approval. The mandated gates are ``decision is AttestationDecision.APPROVE`` /
``state is ApprovalLifecycleState.QUORUM_SATISFIED``, and ``bool | None`` flags use ``is True`` /
``is not True``.

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``classify_record_pair``) + ``tos.ordering`` (append-only generation
order). It imports **no** sibling — ``tos.afg`` / ``tos.are`` / ``tos.authority`` / ``tos.brokercap``
/ ``tos.capsule`` / ``tos.dsl`` / ``tos.evidence`` / ``tos.iap`` / ``tos.ioc`` / ``tos.liveauth`` /
``tos.orthostate`` / ``tos.protective`` / ``tos.rcl`` / ``tos.recon`` / ``tos.replacement`` /
``tos.sbr`` / ``tos.spg`` / ``tos.time`` / ``tos.venue`` and any future sibling are all excluded by
the §7.1 **allowlist** closure test (``tos.*`` closure ⊆ {``tos.canonical``, ``tos.ordering``,
``tos.hag``}) — **sibling edge 0** (design #20 §0.3/§0.4c). The liveauth ``rearm_dual_control_
satisfied`` / spg ``break_glass_confined`` / iap ``IndependentApprovalDecision`` / protective
``protective_classification`` are **re-authored not at all and imported not at all** (produced
facts injected as scalars). **PROMOTE 0** — the digest / ordering substrate is already core.

Identity is **independent, not** ``f(digest)`` for all eight artifacts (design #20 §2.1/§3.1): each
is an immutable issued record; a same-id / different-bytes forgery, re-issue, contradiction, or
replay is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` (HAG-EV-002/004/012).

**Completion discipline (design #20 §1).** ``HAG-EV-001..018`` are all predicate / model substrate.
Eight rows (001 / 002 / 004 / 006 / 007 / 010 / 011 / 012) carry an ``EV-L1`` slice in
EVIDENCE-REGISTER-002; the other ten (003 / 005 / 008 / 009 / 013-018) are minimum ``EV-L2``.
Phase 1 authors the L1-decidable substrate and closes **no** HAG-EV item — even the eight carry
``/3`` residue plus +Security (001 / 002 / 004 / 006 / 010) (authoring is not evidence,
VER-002-001 §5; ADR §26 line 696 "Written cases are not completed evidence"). Tag for any claim:
"predicate / model substrate only; HAG-EV-001..018 remain NOT_IMPLEMENTED pending EV-L2/L3 fault
injection, adversarial, and +Security evidence; **EV-L1-complete claim forbidden**; no ADR
acceptance, restricted-live, or production is authorized."

Public surface groups by module:

* :mod:`tos.hag.vocabulary` — the HAG-axis StrEnums (truthy-untestable ``AttestationDecision`` /
  ``ApprovalLifecycleState`` + closed ``AuthorityClass`` / ``AuthorityDirection`` / ``ConflictRole``).
* :mod:`tos.hag.records` — the eight digest-bound artifacts + the all-false ``HumanAuthorityEffect``.
* :mod:`tos.hag.state` — the injected value / input models + the ``tos.ordering`` generation REUSE.
* :mod:`tos.hag.predicates` — the core §5.1-§5.8 + predicate-only §6.1-§6.6 decision rules + the
  effective-principal collapse yolk.
"""

from __future__ import annotations

from tos.hag._base import (
    ArtifactIntegrityError,
    ArtifactStatus,
    HumanAuthorityEffect,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)
from tos.hag.predicates import (
    approval_binding_exact,
    approval_expiry_preserves_economic_effect,
    approval_set_single_use,
    break_glass_direction_restrictive,
    compromise_fails_closed,
    degraded_path_no_permissive,
    delegation_bounded_nontransitive,
    dual_control_effective_distinct,
    effective_principal_collapse,
    human_authority_effect_separated,
    human_authority_replay_reconstructs,
    human_halt_monotonic_restrictive,
    human_protective_request_proposal_only,
    lifecycle_transition_legal,
    material_change_invalidates,
    no_automatic_rearm,
    operator_config_authz_error_fail_closed,
    partial_rearm_scope_narrows,
    quorum_independence_satisfied,
    separation_of_duties_satisfied,
    stale_replayed_rejected,
    variant_pre_declared_exact_scope,
)
from tos.hag.records import (
    ApprovalSetConsumptionRecord,
    EffectivePrincipalGraph,
    HumanApprovalAttestation,
    HumanApprovalRequest,
    HumanApprovalSet,
    HumanAuthorityPolicy,
    HumanDelegationRecord,
    HumanHaltCommand,
)
from tos.hag.state import (
    ApprovalScope,
    AttestationInputs,
    EffectiveControlEdge,
    EffectivePrincipalNode,
    QuorumRule,
    RoleAssignment,
    RoleGrant,
    generation_monotone,
)
from tos.hag.vocabulary import (
    AUTHORITY_DIRECTION,
    BREAK_GLASS_RESTRICTIVE_CLASSES,
    PROGRESS_LIFECYCLE_STATES,
    TERMINAL_LIFECYCLE_STATES,
    ApprovalLifecycleState,
    AttestationDecision,
    AuthorityClass,
    AuthorityDirection,
    ConflictRole,
)

__all__ = [
    # base (reused core + hag-local all-false authority)
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
    "HumanAuthorityEffect",
    # vocabulary
    "AuthorityClass",
    "AuthorityDirection",
    "AttestationDecision",
    "ApprovalLifecycleState",
    "ConflictRole",
    "AUTHORITY_DIRECTION",
    "BREAK_GLASS_RESTRICTIVE_CLASSES",
    "PROGRESS_LIFECYCLE_STATES",
    "TERMINAL_LIFECYCLE_STATES",
    # records — the eight digest-bound artifacts
    "HumanAuthorityPolicy",
    "EffectivePrincipalGraph",
    "HumanApprovalRequest",
    "HumanApprovalAttestation",
    "HumanApprovalSet",
    "ApprovalSetConsumptionRecord",
    "HumanHaltCommand",
    "HumanDelegationRecord",
    # state — injected value / input models + ordering REUSE
    "EffectivePrincipalNode",
    "EffectiveControlEdge",
    "ApprovalScope",
    "RoleGrant",
    "RoleAssignment",
    "QuorumRule",
    "AttestationInputs",
    "generation_monotone",
    # core §5 predicates
    "effective_principal_collapse",
    "quorum_independence_satisfied",
    "approval_binding_exact",
    "material_change_invalidates",
    "approval_set_single_use",
    "stale_replayed_rejected",
    "lifecycle_transition_legal",
    "break_glass_direction_restrictive",
    "human_protective_request_proposal_only",
    "dual_control_effective_distinct",
    "partial_rearm_scope_narrows",
    "approval_expiry_preserves_economic_effect",
    "no_automatic_rearm",
    "human_authority_replay_reconstructs",
    "human_authority_effect_separated",
    # predicate-only §6 predicates
    "separation_of_duties_satisfied",
    "human_halt_monotonic_restrictive",
    "degraded_path_no_permissive",
    "delegation_bounded_nontransitive",
    "compromise_fails_closed",
    "variant_pre_declared_exact_scope",
    "operator_config_authz_error_fail_closed",
]
