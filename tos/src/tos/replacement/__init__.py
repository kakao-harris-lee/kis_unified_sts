"""Protective Replacement pure models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-011 (Protective Replacement and Protection-Gap Control — "PR") part
of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design contract
``docs/plans/2026-07-26-tos-protective-replacement-design.md`` (v1.1, operator-ratified
2026-07-26). It authors the replacement **decision layer** — overlap-first reservation
completeness + structural no-netting + new-protection-first sequencing, partial-fill
re-evaluation completeness + no-hiding-clamp + egress disposition, the cancel-first
8-condition admission gate, replacement-authorization currentness, mode admissibility,
and the label-grants-nothing workflow lifecycle — over a two-artifact digest-bound data
model.

It is a **decision kernel, not a ledger, not an arbiter, and not an egress** (design #18
§0.2). Every one of the following is sibling-owned and **consumed as an injected
produced bool / token / magnitude, never re-authored**:

* capacity reservation, commitment, remap, and release arithmetic — **rcl**
  (ADR-002-002/012; §1 line 21 "the sole authority that reserves, commits, remaps, and
  releases capacity"; §9 line 231 atomic commit);
* the Cancellation Arbiter, partition-time lease admissibility, protective
  classification, and bounded retry — **protective** (ADR-002-001; §5 line 139
  "ADR-002-001 owns this rule");
* the cancel-ACK-is-not-a-Final-Quantity-Proof **L1** rule, missing-ACK / no-blind-retry,
  and economic-effect persistence — **afg** (ADR-002-022);
* Final Quantity Proof adequacy, the five replace/amend semantics, idempotency, and rate
  admission — **brokercap** / **evidence** (ADR-002-004/006; §4.6 line 99, §6.1 line 147);
* the broker-order and transmission-attempt state machines — **orthostate**
  (ADR-002-005);
* HALT precedence — **authority** (ADR-002-003); recovery bounds — **recon**; the
  aggregate-risk projection — **are** (ADR-002-021); per-leg order admissibility —
  **ADR-002-019**; the final egress — ADR-002-013 runtime.

This package is **pure, non-transmitting, non-enforcing, and clock-free** (design #18
§0.2/§4.4): frozen pydantic models over injected state plus conservative fail-closed
predicates. It **cannot** transmit, mutate capacity, release capacity, remove protection,
issue a capability, override the arbiter, or declare completion — it produces decision
bools, a :class:`ReplacementOutcome`, and forward-only records; the owning runtime (a
future Protective Action Controller / RCL-admission / Final Egress / Reconciliation
Service) enforces them. There is no "assume-covered" / "assume-complete" /
"assume-admissible" path: ``REPLACEMENT_ADMISSIBLE`` / ``True`` comes only from a
positive conjunction identity, and the residual branch of every dispatch is restrictive
(design #18 §4.1 — the seal against the #6 fail-open REJECT and the #16 CRITICAL
"a GRANT must not be the fall-through residue" lesson).

**Polarity discipline (design #18 §0.1(j), the v1.1 C1 lesson).** ``ReplacementOutcome``
is a ``StrEnum`` whose every member — including ``REPLACEMENT_DENIED`` /
``REPLACEMENT_UNKNOWN`` — is *truthy*, so a consuming gate SHALL test
``outcome is ReplacementOutcome.REPLACEMENT_ADMISSIBLE`` (identity). The same holds for
the injected protective ``Admissibility`` verdict (only the ``ADMISSIBLE`` token passes).
Positive-polarity ``bool | None`` fields are gated ``is True``; **negative-polarity**
fields (``hides_uncovered_or_reversing``, ``material_change``, ``expired``,
``became_risk_increasing``, ``bound_exceeded``) are gated ``is False`` **only** — ``is
not True`` on those would let ``None`` through and is the v1.0 fail-open this package
structurally forbids. No-netting is not a flag at all: it is derived structurally from
coexisting non-negative magnitudes.

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (``FrozenModel`` /
``DigestBoundArtifact`` / ``IndependentIdArtifact`` / ``CanonicalDecimal`` /
``classify_record_pair``) + ``tos.ordering`` (append-only generation order). It imports
**no sibling at all** — **sibling edge 0, PROMOTE 0** (design #18 §0.4b/§0.4c; notably
the rcl ``CapacityVector`` REUSE was considered and **rejected**, unlike afg/are/ioc,
because the Phase-1 decision is set / polarity / magnitude logic that needs no vector
type). The §7.1 **allowlist** import-closure test asserts the ``tos.*`` closure ⊆
{``tos.canonical``, ``tos.ordering``, ``tos.replacement``} and stays robust as new
siblings land.

Identity is **independent, not** ``f(digest)`` (design #18 §3.1/§0.4e): each
authorization / workflow generation is an immutable record; a legitimate re-issuance
after a §7 line 201 material change is a new generation, and a same-id /
different-bytes forgery, contradictory authorization, or double-commit workflow is a
detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``.

**Discipline tag (design #18 §1 / the ratified document-wide tag).** *predicate /
coordinate substrate only; PR-EV-001..012 are all ``NOT_IMPLEMENTED`` — the two core
rows (001 Overlap-First, 005 Partial-Fill) hold only an ``EV-L1`` slice and await their
``/3`` integration plus independent review, and the other ten rows await EV-L2/L3 fault
injection, adversarial interleaving, and ``+Broker`` evidence.* **No EV-L1-complete claim.
Closing PR-EV = 0.** Authoring is not acceptance: acceptance comes only from registered,
executed, retained, and independently reviewed evidence under VER-002-001 (ADR §18 line
410, §24 line 519-531). Nothing here authorizes restricted-live or production operation.
"""

from __future__ import annotations

from tos.replacement._base import (
    AllFalseReplacementAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    DigestBoundArtifact,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.replacement.predicates import (
    cancel_first_admission_gate,
    cancel_first_admission_outcome,
    halt_precedence_disposition,
    netting_absent,
    no_hiding_clamp,
    overlap_first_reservation_complete,
    overlap_first_reservation_outcome,
    overlap_first_sequencing_valid,
    partial_fill_egress_disposition,
    partial_fill_reevaluation_complete,
    partition_replacement_admissible,
    replacement_mode_admissible,
    reversal_bounded_outcome,
)
from tos.replacement.records import (
    CancelFirstConditions,
    OverlapReservationClaim,
    ProtectionObligation,
    ReplacementAuthorityEffect,
    ReplacementAuthorization,
    ReplacementWorkflowRecord,
)
from tos.replacement.state import (
    expiry_releases_no_economic_effect,
    replacement_authorization_current,
    workflow_generation_append_only,
    workflow_generation_order,
    workflow_label_grants_nothing,
    workflow_record_axes_not_collapsed,
)
from tos.replacement.vocabulary import (
    ADMISSIBILITY_ADMISSIBLE,
    ATTEMPT_STATE_SENT_UNCONFIRMED,
    BROKER_ORDER_STATE_CANCELLED,
    BROKER_ORDER_STATE_UNKNOWN,
    CANCEL_FIRST_ADMISSION_CONDITIONS,
    NO_NETTING_MAGNITUDE_KINDS,
    ORDER_ADMISSIBILITY_ADMISSIBLE,
    ORTHOGONAL_WORKFLOW_AXES,
    PROTECTION_SUFFICIENCY_FIELDS,
    PROTECTIVE_ACTION_KIND_CANCEL_FIRST_OR_REMOVAL,
    PROTECTIVE_ACTION_KIND_OVERLAP_FIRST_ADD_ONLY,
    REPLACE_SEMANTICS_ATOMIC_REPLACE,
    REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES,
    REQUIRED_REEVALUATION_TARGETS,
    WORKFLOW_LIFECYCLE_ORDER,
    WORKFLOW_NON_LINEAR_STATES,
    CredibleIntermediateOutcomeKind,
    ReevaluationTargetKind,
    ReplacementMode,
    ReplacementOutcome,
    ReplacementWorkflowState,
    protective_action_kind_token,
)

__all__ = [
    # base substrate (re-exported from tos.canonical; PROMOTE 0)
    "AllFalseReplacementAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
    # vocabulary — the 5 replacement StrEnums (§2.2)
    "ReplacementMode",
    "ReplacementWorkflowState",
    "CredibleIntermediateOutcomeKind",
    "ReevaluationTargetKind",
    "ReplacementOutcome",
    # vocabulary — required universes + structural constants
    "REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES",
    "REQUIRED_REEVALUATION_TARGETS",
    "NO_NETTING_MAGNITUDE_KINDS",
    "CANCEL_FIRST_ADMISSION_CONDITIONS",
    "PROTECTION_SUFFICIENCY_FIELDS",
    "WORKFLOW_LIFECYCLE_ORDER",
    "WORKFLOW_NON_LINEAR_STATES",
    "ORTHOGONAL_WORKFLOW_AXES",
    # vocabulary — injected sibling-coordinate tokens (§3.4)
    "ADMISSIBILITY_ADMISSIBLE",
    "ORDER_ADMISSIBILITY_ADMISSIBLE",
    "PROTECTIVE_ACTION_KIND_OVERLAP_FIRST_ADD_ONLY",
    "PROTECTIVE_ACTION_KIND_CANCEL_FIRST_OR_REMOVAL",
    "BROKER_ORDER_STATE_CANCELLED",
    "BROKER_ORDER_STATE_UNKNOWN",
    "ATTEMPT_STATE_SENT_UNCONFIRMED",
    "REPLACE_SEMANTICS_ATOMIC_REPLACE",
    "protective_action_kind_token",
    # records — values + the 2 digest-bound artifacts (§2.1)
    "ReplacementAuthorityEffect",
    "ProtectionObligation",
    "OverlapReservationClaim",
    "CancelFirstConditions",
    "ReplacementAuthorization",
    "ReplacementWorkflowRecord",
    # predicates — core §5.1 overlap-first (PR-EV-001 substrate)
    "netting_absent",
    "overlap_first_reservation_complete",
    "overlap_first_sequencing_valid",
    "overlap_first_reservation_outcome",
    "reversal_bounded_outcome",
    # predicates — core §5.2 partial fill (PR-EV-005 substrate)
    "partial_fill_reevaluation_complete",
    "no_hiding_clamp",
    "partial_fill_egress_disposition",
    # predicates — §6.1 cancel-first gate (PR-EV-002 substrate, predicate-only)
    "cancel_first_admission_gate",
    "cancel_first_admission_outcome",
    # predicates — §5.3 mode admissibility + §8 HALT precedence
    "replacement_mode_admissible",
    "halt_precedence_disposition",
    # predicates — §3.4 injected partition coordinate (PR-EV-010, consumed)
    "partition_replacement_admissible",
    # state — §5.3 label-grants-nothing + §6.2 authorization currentness
    "workflow_label_grants_nothing",
    "workflow_record_axes_not_collapsed",
    "replacement_authorization_current",
    "expiry_releases_no_economic_effect",
    "workflow_generation_order",
    "workflow_generation_append_only",
]
