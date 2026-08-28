"""Corporate Actions and Non-Trade State Changes — pure models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-010 (Corporate Actions and Non-Trade State Changes — "NT") part of
IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design contract
``docs/plans/2026-07-26-tos-non-trade-design.md`` (v1.1, operator-ratified 2026-07-26). It
authors the non-trade **decision layer** — transition-envelope leg completeness +
structural no-netting, split / reverse-split polarity coherence + explicit units and
rounding + conservative fractional residual, correction / reversal idempotency + lineage,
the label-grants-nothing workflow seal, and the single
:class:`NonTradeDisposition` producer — over a two-artifact digest-bound data model.

It is a **decision kernel, not a ledger, not a projector, not an arbiter, and not an
egress** (design #21 §0.2). Every one of the following is sibling-owned and **consumed as
an injected produced bool / token / magnitude, never re-authored**:

* capacity reservation, commitment, remap, and release arithmetic — **rcl**
  (ADR-002-002/012; §1 line 19 "the sole authority that reserves, commits, releases,
  transfers, or remaps capacity"; §10 line 217 "the event processor ... may propose a remap
  but SHALL NOT update capacity independently");
* the aggregate-risk projection over the credible state space and the hard-envelope bound —
  **are** (ADR-002-021; it already owns the concurrent non-trade trapped scenario as
  ``AdverseScenarioKind.EXTERNAL_TRAPPED_NONTRADE_CONCURRENT``);
* the material-change invalidation closure, order admissibility, the instrument route
  fields, and the protective-label carve-out — **venue** (ADR-002-019; §10 line 221);
* per-field evidence confidence and contradiction status — **recon** (ADR-002-006; §7);
* the order / transmission / knowledge state axes — **orthostate** (ADR-002-005; §6 line
  123);
* broker corporate-administrative and open-order capability — **brokercap** (ADR-002-004);
* protective-order cancellation, replacement, gap, and overlap — **replacement**
  (ADR-002-011; §13 line 272 "ADR-002-011 governs cancellation, replacement, gap, overlap,
  and capacity");
* authority invalidation and no-automatic-re-arm — **authority** / **liveauth** (§17 line
  334); recovery obligations — **sbr** (§19 line 359); trustworthy time — **time** (§8);
  the obligation-lifecycle serialization — **ADR-002-030** (§16 line 309 "This ADR owns the
  non-trade event and transformation identity; ADR-002-030 owns the obligation-lifecycle
  serialization"); the final egress — ADR-002-013 runtime.

This package is **pure, non-transmitting, non-enforcing, and clock-free** (design #21
§0.2/§4.4): frozen pydantic models over injected state plus conservative fail-closed
predicates. It **cannot** transmit, mutate or release capacity, close an instrument, prove
a final quantity, issue an admissibility, or grant authority — it produces decision bools,
a :class:`CorrectionReversalOutcome`, a :class:`NonTradeDisposition`, and forward-only
records; the owning runtime (a future Reconciliation Service / rcl remap-admission / venue
invalidation / Final Egress) enforces them. There is no "assume-complete" /
"assume-coherent" / "assume-admissible" path: ``NONTRADE_ADMISSIBLE`` / ``APPLIED_ONCE`` /
``True`` comes only from a positive conjunction identity, and the residual branch of every
dispatch is restrictive (design #21 §4 — the seal against the #6 fail-open REJECT and the
#16 CRITICAL "a GRANT must not be the fall-through residue" lesson).

**Polarity discipline (design #21 §0.1(8), the v1.1 C1/C2 lessons).**
:class:`NonTradeDisposition` and :class:`CorrectionReversalOutcome` are **truthy-untestable**
(``__bool__`` raises ``TypeError``), so a consuming gate SHALL test
``disposition is NonTradeDisposition.NONTRADE_ADMISSIBLE`` (identity). An injected sibling
verdict crosses the seam as a bare **token** compared against a local constant (the venue
``OrderAdmissibilityResult``, recon ``FieldConfidenceClass``, time ``FreshnessVerdict``),
never as an imported type. Positive-polarity ``bool | None`` premises are gated ``is True``
only. **Phase-1 nontrade has zero negative-polarity fields** (honest disclosure, design #21
M7): no-netting is derived structurally from two coexisting non-negative magnitudes, split
polarity is derived from the pre/post magnitudes rather than declared, history preservation
is the positive ``original_retained``, and a capacity release is *unrepresentable* — there
is no field and no predicate that could express it. A §7 property asserts the three phantom
names (``favorable_netted`` / ``destructive_overwrite`` / ``released_on_transformation``)
stay absent. ``event_is_material`` is the one relaxation-condition field, and its exemption
requires the **positive** ``is False`` proof — "Unknown materiality is material".

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (``FrozenModel`` /
``DigestBoundArtifact`` / ``IndependentIdArtifact`` / ``CanonicalDecimal`` /
``classify_record_pair`` / ``RecordPairKind``) + ``tos.ordering`` (append-only generation
order). It imports **no sibling at all** — **sibling edge 0, PROMOTE 0** (design #21
§0.4b/§0.4c; notably the rcl ``CapacityVector`` and are ``ProjectedCell`` REUSE was
considered and **rejected**, because the Phase-1 decision is set / polarity / idempotency
logic that needs no vector or cell type and a nontrade-local dimension axis would collide
with the are / rcl namespaces). The §7.1 **allowlist** import-closure test asserts the
``tos.*`` closure ⊆ {``tos.canonical``, ``tos.ordering``, ``tos.nontrade``} and stays robust
as new siblings land.

Identity is **independent, not** ``f(digest)`` (design #21 §3.1/§0.4f): each event /
correction version is an immutable record, and **two** identity axes stay forgery-detectable
— a same **primary** id / different-bytes pair is a ``classify_record_pair``
``CRITICAL_CONFLICT``, and a same **idempotency key** / different-bytes pair is a
``DIVERGENT_EMISSION``. Both fold to ``REJECTED_CONFLICT``: contain both, no
last-write-wins, never a silent double-apply.

**Discipline tag (design #21 §1 / the ratified document-wide tag).** *predicate /
coordinate substrate only; NT-EV-001..012 are all ``NOT_IMPLEMENTED`` — the three core rows
(001 Split and Reverse-Split Transition, 002 Multi-Leg Merger and Spin-Off, 010 Correction
and Reversal Idempotency) hold only an ``EV-L1`` slice and await their ``/3`` integration
(plus ``+Broker`` for 001) and independent review, and the other nine rows await EV-L2/L3
fault injection, adversarial interleaving, and ``+Broker`` evidence.* **No EV-L1-complete
claim. Closing NT-EV = 0.** Authoring is not acceptance: acceptance comes only from
registered, executed, retained, and independently reviewed evidence under VER-002-001 (ADR
§18 line 392, §26 line 502-514). Nothing here authorizes restricted-live or production
operation.
"""

from __future__ import annotations

from tos.nontrade._base import (
    AllFalseNonTradeAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    DigestBoundArtifact,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.nontrade.predicates import (
    correction_reversal_idempotent,
    effective_window_blocks_new_risk,
    favorable_netting_absent,
    instrument_lineage_preserved,
    material_change_trigger_nonempty,
    nontrade_authority_effect_all_false,
    nontrade_disposition,
    split_polarity_coherent,
    transformation_residual_conservative,
    transformation_units_and_rounding_explicit,
    transition_envelope_complete,
)
from tos.nontrade.records import (
    CorrectionReversalRecord,
    NonTradeAuthorityEffect,
    NonTradeEventRecord,
    SplitTransformationSpec,
    TransitionEnvelope,
)
from tos.nontrade.state import (
    correction_generation_append_only,
    correction_generation_order,
    event_axes_not_collapsed,
    event_generation_append_only,
    event_generation_order,
)
from tos.nontrade.vocabulary import (
    ADVERSE_SCENARIO_EXTERNAL_TRAPPED_NONTRADE_CONCURRENT,
    CAPACITY_STATE_QUARANTINED_UNKNOWN,
    CAPACITY_STATE_TRAPPED_CONSUMED,
    CREDIBLE_TRANSITION_LEG_MINIMUM_SET,
    EVENT_IDENTITY_FIELD_GROUPS,
    FIELD_CONFIDENCE_CONFLICTED,
    FIELD_CONFIDENCE_CORROBORATED,
    FIELD_CONFIDENCE_UNKNOWN,
    FRESHNESS_VERDICT_FRESH,
    ORDER_ADMISSIBILITY_ADMISSIBLE,
    ORDER_ADMISSIBILITY_INADMISSIBLE,
    ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY,
    ORDER_ADMISSIBILITY_UNKNOWN,
    ORDINARY_NEW_RISK_ADMISSIBILITY_TOKENS,
    ORTHOGONAL_EVENT_AXES,
    PROHIBITED_VERBS,
    RECIPROCAL_DIRECTION_PAIRS,
    SPLIT_KIND_DIRECTIONS,
    TRANSFORMATION_DISTINCTION_OWNERSHIP,
    TRANSITION_CAUSE_RECOGNIZED_EXTERNAL_CHANGE,
    WORKFLOW_BRANCH_STATES,
    WORKFLOW_LINEAR_LIFECYCLE,
    CorrectionReversalOutcome,
    CredibleTransitionLegKind,
    NonTradeDisposition,
    NonTradeEventClass,
    NonTradeEventWorkflowState,
    SplitTransformationKind,
    TransformationDirection,
)

__all__ = [
    # base substrate (re-exported from tos.canonical; PROMOTE 0)
    "AllFalseNonTradeAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
    # vocabulary — the 7 nontrade StrEnums (§2.2)
    "NonTradeEventClass",
    "NonTradeEventWorkflowState",
    "CredibleTransitionLegKind",
    "SplitTransformationKind",
    "TransformationDirection",
    "CorrectionReversalOutcome",
    "NonTradeDisposition",
    # vocabulary — structural universes + transcription tables
    "CREDIBLE_TRANSITION_LEG_MINIMUM_SET",
    "WORKFLOW_LINEAR_LIFECYCLE",
    "WORKFLOW_BRANCH_STATES",
    "ORTHOGONAL_EVENT_AXES",
    "RECIPROCAL_DIRECTION_PAIRS",
    "SPLIT_KIND_DIRECTIONS",
    "EVENT_IDENTITY_FIELD_GROUPS",
    "TRANSFORMATION_DISTINCTION_OWNERSHIP",
    "PROHIBITED_VERBS",
    # vocabulary — injected sibling-coordinate tokens (§3.4)
    "ORDER_ADMISSIBILITY_ADMISSIBLE",
    "ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY",
    "ORDER_ADMISSIBILITY_INADMISSIBLE",
    "ORDER_ADMISSIBILITY_UNKNOWN",
    "ORDINARY_NEW_RISK_ADMISSIBILITY_TOKENS",
    "FIELD_CONFIDENCE_CORROBORATED",
    "FIELD_CONFIDENCE_UNKNOWN",
    "FIELD_CONFIDENCE_CONFLICTED",
    "FRESHNESS_VERDICT_FRESH",
    "CAPACITY_STATE_TRAPPED_CONSUMED",
    "CAPACITY_STATE_QUARANTINED_UNKNOWN",
    "TRANSITION_CAUSE_RECOGNIZED_EXTERNAL_CHANGE",
    "ADVERSE_SCENARIO_EXTERNAL_TRAPPED_NONTRADE_CONCURRENT",
    # records — values + the 2 digest-bound artifacts (§2.1)
    "NonTradeAuthorityEffect",
    "TransitionEnvelope",
    "SplitTransformationSpec",
    "NonTradeEventRecord",
    "CorrectionReversalRecord",
    # predicates — core §5.1 transition envelope (NT-EV-002 substrate)
    "transition_envelope_complete",
    "favorable_netting_absent",
    # predicates — core §5.2 split polarity / units / residual (NT-EV-001 substrate)
    "split_polarity_coherent",
    "transformation_units_and_rounding_explicit",
    "transformation_residual_conservative",
    # predicates — core §5.3 correction idempotency (NT-EV-010 substrate)
    "correction_reversal_idempotent",
    # predicates — core §5.4 label-grants-nothing
    "nontrade_authority_effect_all_false",
    # predicates — core §5.5 the sole disposition producer (C1)
    "nontrade_disposition",
    # predicates — §6.1-§6.3 predicate-only (NT-EV-003/007 substrate)
    "instrument_lineage_preserved",
    "effective_window_blocks_new_risk",
    "material_change_trigger_nonempty",
    # state — §5.4 orthogonality + §3.2 append-only generation order
    "event_axes_not_collapsed",
    "event_generation_order",
    "event_generation_append_only",
    "correction_generation_order",
    "correction_generation_append_only",
]
