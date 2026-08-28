"""wdr digest-bound artifacts — the five safety-deviation ledger citizens (design #26 §2).

Every artifact is a **pydantic v2 frozen model** (``frozen=True, extra="forbid"`` via
:class:`~tos.wdr._base.FrozenModel`): ``extra="forbid"`` is the schema-level "omission is restrictive"
and frozen is the append-only realization; there is **no** update / delete / mutate / transmit / sign /
arm / clear-halt / approve / authorize / activate method on any model (design #26 §2.3/§4.1 — the
constructive-absence canary). Field names use the ADR §5-§26 terms **verbatim** (spec terms = code
terms, boundary design #1 §2.4).

**Five id-independent artifacts (design #26 §2.1/§3.1).** ``SafetyDeviationPolicy`` /
``SafetyDeviationRequest`` / ``SafetyDeviationDecision`` / ``ResidualRiskAcceptanceRecord`` /
``ActiveDeviationSet`` are **issued-identity** records (:class:`~tos.wdr._base.IndependentIdArtifact`,
``id != f(digest)``): the id is separately issued, so a same-id / different-**covered**-bytes forged,
re-issued, or replayed record is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` (design
#26 §2.1/§3.1 — WDR-EV-001/012). ADR §10 line 284 "canonical digest, and predecessor"; §12 line 356
"bind the exact request digest"; §13 line 368 "consumed exactly once".

**WDR = greenfield deviation-governance content owner, NO inbound deferee (design #26 §0.4b — the key
architecture decision, the maximum contrast with RLP).** RLP was a *deferee* — egress / cur carried the
restricted-live trial claim and deferred its content validation to ``tos.rlp`` by name. **WDR has zero
inbound deferral seam** (grep-witnessed, §0.4b): no landed sibling defers deviation content to
``tos.wdr``. wdr **authors** the five deviation artifacts here as a pure greenfield producer; its
``Deviation Generation`` coordinates are destined to flow downstream into the cur Safety Currentness
Vector (§14), but cur does not yet own that dimension. wdr re-authors **no** sibling boundary seal and
imports **neither** sibling (sibling edge 0, §3.4).

**Malformed-model self-defence — positive-claim + incomplete-scope coexistence seal (rlp
``ExactTrialPlan`` / egress QCC ``_trial_claim_completeness`` isomorph; design #26 §2.3 / #20 lesson).**
Three artifacts carry a construction-time coexistence seal:

* ``SafetyDeviationRequest`` — a ``WAIVABLE_ELIGIBLE`` classification while any §5.7 mandated scope
  dimension is ``None`` / wildcard, or while any §8 boundary item is hit, is **unconstructable** (a
  request that claims eligibility while its exact scope is blank or it targets a non-waivable boundary
  cannot exist).
* ``SafetyDeviationDecision`` — ``result is ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`` while the reduced
  scope is incomplete / wildcard is **unconstructable** (an "eligible" decision whose exact scope is
  blank cannot exist).
* ``ResidualRiskAcceptanceRecord`` — an ``evidence_status is WAIVED_WITH_RESIDUAL_RISK`` acceptance
  while no compensating control is present is **unconstructable** (an accepted residual risk with no
  compensation cannot exist, §11).

The ``model_construct`` escape hatch that skips validators is re-caught in the §5 predicate layer
(defence in depth, §2.3): the yolk predicates re-derive completeness structurally and never trust a
stored flag.

**Coordinate non-collapse (design #26 §2.3/§4.4).** No mutable lifecycle coordinate — the decision
``single_use_consumed``, the active-set ``state``, the injected sibling verdicts
(``effective_principal_verdict`` hag / ``within_hard_safety_envelope`` spg /
``combined_within_envelope`` spg) — is a covered digest field: a lawful lifecycle transition or an
injected verdict change must not change an artifact's digest and be mis-flagged as a same-id /
different-bytes ``CRITICAL_CONFLICT`` (the rcl / egress / cur / rlp coordinate-non-collapse precedent).
Every covered field is an immutable claim; the current lifecycle state / injected verdict is fed into
the predicate.

**Deterministic set-covered digest (design #26 §3.1).** ``frozenset`` covered fields (policy class /
scope-dimension manifests) are **sorted** in :meth:`covered_content` so the digest is deterministic
across processes; the field type stays a ``frozenset`` for the predicate's subset math. Nested value
models with only scalar / bool fields (``DeviationScope`` / ``NonWaivableBoundaryAnchor`` /
``AllFalseDeviationAuthority``) are digest-safe; nested models carrying frozensets are kept **out** of
the covered set to avoid unstable serialization.

**All-false authority (design #26 §2.4/§7; WDR-INV-001).** Every artifact carries an
:class:`~tos.wdr._base.AllFalseDeviationAuthority` with every flag ``False`` — a deviation artifact is
governed content / a non-authorizing decision, not permission.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.wdr._base``) + ``tos.wdr.*`` only;
no ``shared.*``, no sibling ``tos.*`` (design #26 §0.3).
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import model_validator

from tos.wdr._base import (
    AllFalseDeviationAuthority,
    ArtifactIntegrityError,
    IndependentIdArtifact,
)
from tos.wdr.state import (
    CompensatingControl,
    DeviationClassification,
    DeviationDependencyClosure,
    DeviationScope,
    NonWaivableBoundaryAnchor,
)
from tos.wdr.vocabulary import (
    MANDATED_SCOPE_FLOOR,
    ActiveDeviationState,
    DecisionResult,
    NonWaivableClassification,
    ScopeDimension,
    WaivedEvidenceStatus,
)

__all__ = [
    "SafetyDeviationPolicy",
    "SafetyDeviationRequest",
    "SafetyDeviationDecision",
    "ResidualRiskAcceptanceRecord",
    "ActiveDeviationSet",
    "AllFalseDeviationAuthority",
]


def _sorted_set_fields(content: dict[str, Any], *names: str) -> dict[str, Any]:
    """Sort the named ``frozenset``-derived list fields for a deterministic digest (§3.1)."""
    for name in names:
        value = content.get(name)
        if value is not None:
            content[name] = sorted(value)
    return content


def _scope_incomplete(scope: DeviationScope | None) -> bool:
    """Whether a scope is absent or misses / wildcards any §5.7 mandated dimension (§2.3)."""
    return scope is None or scope.concrete_dimensions() != MANDATED_SCOPE_FLOOR


class SafetyDeviationPolicy(IndependentIdArtifact):
    """The governed Safety Deviation Policy content model (ADR-002-026 §5.1/§9; design #26 §2.4).

    §5.1: the immutable ADR-002-014 governed policy defining eligible deviation classes, the
    non-waivable boundary, scope and dependency rules, compensating-control requirements, approval
    independence, duration, currentness, invalidation, evidence, and failure behavior. wdr **authors**
    the policy *content* model, but the policy's **activation / generation is spg/014-governed** (design
    #26 §0.4c; §9 line 275 "Policy activation follows ADR-002-014") — carried as injected
    ``policy_generation`` / ``policy_digest`` scalars, re-authored not at all. An
    :class:`~tos.wdr._base.IndependentIdArtifact` (``id != f(digest)``). Its
    :class:`~tos.wdr._base.AllFalseDeviationAuthority` is all-false — a policy is governed content, not
    permission (WDR-INV-001). Every numeric bound (``max_duration`` / ``max_decision_age`` / ...) is an
    injected Profile-INSTANCE value, null in Phase 1 (§8).
    """

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "policy_id",
        "policy_generation",
        "policy_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "policy_generation",
            "policy_digest",
            "eligible_deviation_classes",
            "prohibited_deviation_classes",
            "non_waivable_boundary",
            "scope_dimensions",
            "required_compensating_control_classes",
            "required_evidence_levels",
            "compatibility_manifest_digest",
            "authority_effect",
        }
    )

    policy_id: str | None = None
    #: Injected spg/014-governed activation generation (§0.4c; ``None`` ⇒ fail-closed at predicate).
    policy_generation: int | None = None
    policy_digest: str | None = None
    eligible_deviation_classes: frozenset[str] = frozenset()
    prohibited_deviation_classes: frozenset[str] = frozenset()
    #: The §8 15-item non-waivable boundary the policy declares (union-only; §5.6).
    non_waivable_boundary: NonWaivableBoundaryAnchor | None = None
    #: The §5.7 mandated scope-dimension catalogue the policy declares (subset math; §5.2).
    scope_dimensions: frozenset[ScopeDimension] = frozenset()
    required_compensating_control_classes: frozenset[str] = frozenset()
    required_evidence_levels: frozenset[str] = frozenset()
    #: Injected numeric bounds (null in Phase 1, §8) — not covered / not required.
    max_duration: int | None = None
    max_decision_age: int | None = None
    max_review_interval: int | None = None
    #: hag-referenced quorum rule (§12; hag-owned, §0.4e) — an injected reference string.
    effective_principal_quorum_rule: str | None = None
    compatibility_manifest_digest: str | None = None
    #: §7 — a policy is governed content, not permission (all-false, WDR-INV-001).
    authority_effect: AllFalseDeviationAuthority = AllFalseDeviationAuthority()

    def covered_content(self) -> dict[str, Any]:
        """Digest preimage with the ``frozenset`` class fields serialized deterministically (§3.1)."""
        return _sorted_set_fields(
            super().covered_content(),
            "eligible_deviation_classes",
            "prohibited_deviation_classes",
            "scope_dimensions",
            "required_compensating_control_classes",
            "required_evidence_levels",
        )


class SafetyDeviationRequest(IndependentIdArtifact):
    """The immutable Safety Deviation Request (ADR-002-026 §5.2/§10; design #26 §2.4).

    §5.2: the immutable proposal to accept one identified unmet or degraded requirement for one exact
    reduced scope and duration under specified compensating controls — "**It grants no authority**." §10
    line 281-297 enumerates the field groups (identity / policy, requirement / hazard, status, scope /
    closure, cause / remediation, time, worst-credible risk, assumptions, compensating controls,
    envelope / profile, constraints, behavior, principals, inferences). An
    :class:`~tos.wdr._base.IndependentIdArtifact` (``id != f(digest)``): a same-id / different-bytes
    request substitution is a detectable ``CRITICAL_CONFLICT``.

    **Coexistence seal (§2.3).** A ``WAIVABLE_ELIGIBLE`` classification while any §5.7 mandated scope
    dimension is ``None`` / wildcard, or while any §8 boundary item is hit, is **unconstructable** (the
    rlp ``ExactTrialPlan`` isomorph). The ``worst_credible_effect_envelope`` is an **injected opaque
    rcl coordinate** — **not** a ``CapacityVector`` type (design #26 §0.4g; wdr does no capacity
    arithmetic, edge 0).
    """

    _ID_FIELD: ClassVar[str] = "request_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "request_id",
        "request_version",
        "request_digest",
        "policy_id",
        "policy_generation",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "request_version",
            "request_digest",
            "predecessor_request_id",
            "policy_id",
            "policy_generation",
            "policy_digest",
            "compatibility_manifest_digest",
            "requirement_ids",
            "hazard_ids",
            "non_waivable_classification",
            "deviation_scope",
            # §10 groups 9-15 immutable request content (deterministic str / tuple types) — covered.
            "assumptions",
            "uncertainties",
            "unsupported_semantics",
            "failure_modes",
            "control_owners",
            "control_evidence",
            "control_independence",
            "control_currentness",
            "hard_safety_envelope_ref",
            "requested_reduced_profile",
            "capacity_constraints",
            "protective_constraints",
            "action_flow_constraints",
            "supervision_constraints",
            "evidence_constraints",
            "recovery_constraints",
            "revocation_behavior",
            "halt_behavior",
            "egress_deny_behavior",
            "rollback_behavior",
            "reconciliation_behavior",
            "trapped_exposure_behavior",
            "prohibited_inferences",
            "non_waivable_classification_result",
            "authority_effect",
        }
    )

    #: The ADR §10 line 283-297 "Every request SHALL bind at least" 15 field-groups mapped to a
    #: representative model field per group (a manually-transcribed regression anchor; design #26 §2.4 /
    #: §0.4h). Every representative MUST exist as a model field — the §7.2 group-drift property asserts
    #: it, so dropping a whole §10 group (the MAJOR-1 defect) is caught immediately. Over/under both
    #: caught: exactly 15 groups, every representative present.
    REQUEST_FIELD_GROUPS: ClassVar[dict[str, tuple[str, ...]]] = {
        "policy_identity": (
            "policy_id",
            "policy_generation",
            "policy_digest",
            "compatibility_manifest_digest",
        ),
        "request_identity": (
            "request_id",
            "request_version",
            "request_digest",
            "predecessor_request_id",
        ),
        "requirement_hazard": (
            "requirement_ids",
            "hazard_ids",
            "adr_rfc_citations",
            "verification_ids",
        ),
        "status_no_relabel": ("current_requirement_status", "current_evidence_status"),
        "scope_closure": ("deviation_scope", "dependency_closure"),
        "cause_remediation": (
            "technical_cause",
            "why_control_unavailable",
            "remediation_plan",
        ),
        "time": (
            "requested_start",
            "hard_expiry",
            "review_interval",
            "trustworthy_time_basis",
        ),
        "worst_credible_risk": ("worst_credible_effect_envelope", "common_mode_risk"),
        "assumptions": (
            "assumptions",
            "uncertainties",
            "unsupported_semantics",
            "failure_modes",
        ),
        "compensating_controls": (
            "compensating_controls",
            "control_owners",
            "control_evidence",
            "control_independence",
            "control_currentness",
        ),
        "envelope_profile": ("hard_safety_envelope_ref", "requested_reduced_profile"),
        "constraints": (
            "capacity_constraints",
            "protective_constraints",
            "action_flow_constraints",
            "supervision_constraints",
            "evidence_constraints",
            "recovery_constraints",
        ),
        "behavior": (
            "revocation_behavior",
            "halt_behavior",
            "egress_deny_behavior",
            "rollback_behavior",
            "reconciliation_behavior",
            "trapped_exposure_behavior",
        ),
        "principals": (
            "requester",
            "implementer",
            "beneficiaries",
            "evidence_owners",
            "reviewers",
            "conflict_graph",
        ),
        "inferences": ("prohibited_inferences", "non_waivable_classification_result"),
    }

    # identity / policy (§10 line 283-284)
    request_id: str | None = None
    request_version: int | None = None
    request_digest: str | None = None
    predecessor_request_id: str | None = None
    policy_id: str | None = None
    policy_generation: int | None = None
    policy_digest: str | None = None
    compatibility_manifest_digest: str | None = None

    # requirement / hazard (§10 line 285)
    requirement_ids: tuple[str, ...] = ()
    hazard_ids: tuple[str, ...] = ()
    adr_rfc_citations: tuple[str, ...] = ()
    verification_ids: tuple[str, ...] = ()
    #: The §8 classification result (flat field; the classification view derives from it).
    non_waivable_classification: NonWaivableClassification | None = None

    # status — no relabel (§10 line 286 / §19)
    current_requirement_status: WaivedEvidenceStatus | None = None
    current_evidence_status: WaivedEvidenceStatus | None = None

    # scope / closure (§10 line 287)
    deviation_scope: DeviationScope | None = None
    dependency_closure: DeviationDependencyClosure | None = None

    # cause / remediation (§10 line 288)
    technical_cause: str | None = None
    why_control_unavailable: str | None = None
    remediation_plan: str | None = None

    # time (§10 line 289; time-injected)
    requested_start: str | None = None
    hard_expiry: str | None = None
    review_interval: str | None = None
    trustworthy_time_basis: str | None = None

    # worst-credible risk (§10 line 290; §0.4g — injected opaque, NOT a CapacityVector)
    worst_credible_effect_envelope: str | None = None
    common_mode_risk: str | None = None

    # assumptions (§10 line 291 — group 9; injected descriptive, +Security surface, no predicate consumes)
    assumptions: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    unsupported_semantics: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()

    # compensating controls (§10 line 292 — group 10)
    compensating_controls: tuple[CompensatingControl, ...] = ()
    control_owners: tuple[str, ...] = ()
    control_evidence: tuple[str, ...] = ()
    control_independence: str | None = None
    control_currentness: str | None = None

    # envelope / profile (§10 line 293 — group 11; spg-injected refs, §0.4c)
    hard_safety_envelope_ref: str | None = None
    requested_reduced_profile: str | None = None

    # constraints (§10 line 294 — group 12; injected descriptive, +Security surface)
    capacity_constraints: str | None = None
    protective_constraints: str | None = None
    action_flow_constraints: str | None = None
    supervision_constraints: str | None = None
    evidence_constraints: str | None = None
    recovery_constraints: str | None = None

    # behavior (§10 line 295 — group 13; injected descriptive, +Security surface)
    revocation_behavior: str | None = None
    halt_behavior: str | None = None
    egress_deny_behavior: str | None = None
    rollback_behavior: str | None = None
    reconciliation_behavior: str | None = None
    trapped_exposure_behavior: str | None = None

    # principals (§10 line 296 — group 14)
    requester: str | None = None
    implementer: str | None = None
    beneficiaries: tuple[str, ...] = ()
    evidence_owners: tuple[str, ...] = ()
    reviewers: tuple[str, ...] = ()
    conflict_graph: str | None = None

    # inferences (§10 line 297 — group 15)
    prohibited_inferences: tuple[str, ...] = ()
    #: The recorded §8 classification-result reference (§10 line 297; distinct from the
    #: ``non_waivable_classification`` enum input — this is the injected result coordinate).
    non_waivable_classification_result: str | None = None

    # classification input (§8; flat fields the classification view derives)
    #: The §8 boundary items this request would waive (any hit ⇒ deny; §8 line 234).
    boundary_hits: frozenset[str] = frozenset()

    # polarity fields (§4.3)
    #: Positive-polarity (§9 line 273) — only ``is True`` clears; ``None`` / ``False`` ⇒ deny.
    applicability_resolved: bool | None = None
    #: Negative-polarity scope drift (§10 line 299) — ``is not False`` (True / None) ⇒ deny.
    scope_wildcard: bool | None = None
    scope_patched: bool | None = None
    scope_widened: bool | None = None
    scope_stale: bool | None = None
    scope_conflicting: bool | None = None
    #: Negative-polarity (§9 line 273 "Unknown materiality is material") — ``is not False`` ⇒ deny.
    materiality_unknown: bool | None = None
    #: Negative-polarity common-mode (§11/§12) — ``is not False`` (True / None) ⇒ deny.
    common_mode_present: bool | None = None
    #: Negative-polarity (§11 line 331 / §17 line 442) — protective label bypass ⇒ ``is not False`` deny.
    protective_label_bypass: bool | None = None
    # UNKNOWN confinement flags (§16 line 423-431; all negative-polarity — ``is not False`` ⇒ deny)
    broker_state_unknown: bool | None = None
    order_state_unknown: bool | None = None
    exposure_unknown: bool | None = None
    residual_risk_unknown: bool | None = None
    control_state_unknown: bool | None = None
    evidence_unknown: bool | None = None
    scope_unknown: bool | None = None
    currentness_unknown: bool | None = None

    #: §7 — a request grants no authority (all-false, WDR-INV-001).
    authority_effect: AllFalseDeviationAuthority = AllFalseDeviationAuthority()

    def classification_view(self) -> DeviationClassification:
        """The §8 classification-input view derived from the request's flat fields (§5.1).

        Returns:
            A :class:`~tos.wdr.state.DeviationClassification` bundling the classification result, the
            positive-polarity applicability resolution, and the §8 boundary hits — consumed by
            :func:`~tos.wdr.predicates.classification_admissible`.
        """
        return DeviationClassification(
            classification=self.non_waivable_classification,
            applicability_resolved=self.applicability_resolved,
            boundary_hits=self.boundary_hits,
        )

    @model_validator(mode="after")
    def _eligible_requires_exact_non_boundary(self) -> SafetyDeviationRequest:
        """An eligible-classified request cannot carry a boundary hit or blank scope (§2.3).

        Malformed-model self-defence (design #26 §2.3 / #20 lesson): a request that positively claims
        ``non_waivable_classification is WAIVABLE_ELIGIBLE`` requires **no** §8 boundary hit and
        **every** §5.7 mandated scope dimension bound to an exact (non-``None``, non-wildcard) value. A
        ``WAIVABLE_ELIGIBLE`` claim coexisting with a boundary hit — or a blank / wildcard scope
        dimension — is a malformed model and **unconstructable** on the normal validation path (the rlp
        ``ExactTrialPlan`` isomorph; the ``model_construct`` escape hatch is re-caught by
        :func:`~tos.wdr.predicates.boundary_denies_non_waivable` /
        :func:`~tos.wdr.predicates.scope_exact_and_complete`, §5.1/§5.2).
        """
        if (
            self.non_waivable_classification
            is NonWaivableClassification.WAIVABLE_ELIGIBLE
        ):
            if self.boundary_hits:
                raise ArtifactIntegrityError(
                    "SafetyDeviationRequest declares non_waivable_classification="
                    "WAIVABLE_ELIGIBLE but carries a §8 non-waivable boundary hit "
                    f"({sorted(self.boundary_hits)}) — an eligible request cannot target a "
                    "non-waivable boundary (malformed-model self-defence, design #26 §2.3 / "
                    "WDR-INV-002 line 152 / ADR-002-026 §8 line 234)."
                )
            if _scope_incomplete(self.deviation_scope):
                raise ArtifactIntegrityError(
                    "SafetyDeviationRequest declares non_waivable_classification="
                    "WAIVABLE_ELIGIBLE but carries an incomplete or wildcard exact scope — an "
                    "eligible request requires every §5.7 line 128 scope dimension bound to an exact "
                    "concrete value (malformed-model self-defence, design #26 §2.3 / WDR-INV-003 "
                    "line 156 / ADR-002-026 §10 line 299)."
                )
        return self


class SafetyDeviationDecision(IndependentIdArtifact):
    """The immutable single-use Safety Deviation Decision (ADR-002-026 §5.3/§12; design #26 §2.4).

    §5.3: an immutable independent result of ``DENY``, ``HOLD``, or
    ``ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`` for **one exact request digest** — "Eligibility permits
    only a single request to the separate safety-configuration workflow." §12 line 356 "bind the exact
    request digest"; §13 line 368 "consumed exactly once". The ``effective_principal_verdict`` (hag) is
    an **injected** positive-polarity verdict, re-authored not at all (§0.4e). An
    :class:`~tos.wdr._base.IndependentIdArtifact` (``id != f(digest)``).

    **Coexistence seal (§2.3).** ``result is ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`` while the reduced
    scope is incomplete / wildcard is **unconstructable** (the rlp ``ExactTrialPlan`` isomorph).

    **Coordinate non-collapse (§2.3).** ``single_use_consumed`` (mutable lifecycle) and the injected
    ``effective_principal_verdict`` (hag verdict) are **excluded** from the covered digest.
    """

    _ID_FIELD: ClassVar[str] = "decision_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "decision_id",
        "decision_generation",
        "request_id",
        "request_digest",
        "deviation_generation",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "decision_generation",
            "decision_digest",
            "request_id",
            "request_digest",
            "deviation_generation",
            "accepted_residual_risk_id",
            "reduced_scope",
            "policy_id",
            "expiry",
            "result",
            "authority_effect",
        }
    )

    decision_id: str | None = None
    decision_generation: int | None = None
    decision_digest: str | None = None
    request_id: str | None = None
    #: The exact request digest this decision binds (§12 line 356).
    request_digest: str | None = None
    #: Injected Deviation Generation ordering coordinate (§5.8; MAX fence at reconcile, §4.4).
    deviation_generation: int | None = None
    accepted_residual_risk_id: str | None = None
    reduced_scope: DeviationScope | None = None
    compensating_controls: tuple[CompensatingControl, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    #: Injected hag reviewer quorum coordinate (§12; hag-owned, §0.4e).
    reviewer_quorum: int | None = None
    #: Injected hag effective-principal verdict (§12; positive-polarity, ``is True`` clears; NOT
    #: covered — §0.4e/§2.3).
    effective_principal_verdict: bool | None = None
    expiry: str | None = None
    policy_id: str | None = None
    result: DecisionResult | None = None
    #: Negative-polarity single-use state (mutable — NOT covered, §2.3). ``is not False`` reject reuse.
    single_use_consumed: bool | None = None
    #: §7 — a decision is non-authorizing, not permission (all-false, WDR-INV-001).
    authority_effect: AllFalseDeviationAuthority = AllFalseDeviationAuthority()

    @model_validator(mode="after")
    def _eligible_requires_exact_scope(self) -> SafetyDeviationDecision:
        """An eligible decision cannot carry an incomplete / wildcard reduced scope (§2.3).

        Malformed-model self-defence: a decision that positively claims ``result is
        ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`` requires **every** §5.7 mandated scope dimension bound
        to an exact concrete value. An eligible claim coexisting with a blank / wildcard scope is
        malformed and **unconstructable** (the rlp ``ExactTrialPlan`` isomorph; the ``model_construct``
        escape hatch is re-caught by :func:`~tos.wdr.predicates.deviation_single_use_non_authorizing`,
        §6.3).
        """
        if self.result is DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION:
            if _scope_incomplete(self.reduced_scope):
                raise ArtifactIntegrityError(
                    "SafetyDeviationDecision declares result="
                    "ELIGIBLE_FOR_RESTRICTED_CONFIGURATION but carries an incomplete or wildcard "
                    "reduced scope — an eligible decision requires every §5.7 line 128 scope "
                    "dimension bound to an exact concrete value (malformed-model self-defence, "
                    "design #26 §2.3 / ADR-002-026 §12)."
                )
        return self


class ResidualRiskAcceptanceRecord(IndependentIdArtifact):
    """The immutable Residual-Risk Acceptance Record (ADR-002-026 §5.4/§11; design #26 §2.4).

    §5.4: an immutable record of the bounded risk, assumptions, compensating controls, reviewers,
    expiry, evidence status, and explicit scope accepted by the authorized quorum — "**It is not proof
    that the underlying requirement passed and grants no authority.**" The ``within_hard_safety_envelope``
    verdict (spg) is an **injected** positive-polarity coordinate: the *profile-level* envelope
    containment is spg-owned (§0.4c), re-authored not at all. An
    :class:`~tos.wdr._base.IndependentIdArtifact` (``id != f(digest)``).

    **Coexistence seal (§2.3).** An ``evidence_status is WAIVED_WITH_RESIDUAL_RISK`` acceptance while no
    compensating control is present is **unconstructable** (an accepted residual risk with no
    compensation cannot exist, §11).

    **Coordinate non-collapse (§2.3).** The injected ``within_hard_safety_envelope`` (spg verdict) is
    **excluded** from the covered digest.
    """

    _ID_FIELD: ClassVar[str] = "acceptance_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "acceptance_id",
        "acceptance_generation",
        "request_id",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "acceptance_generation",
            "acceptance_digest",
            "request_id",
            "bounded_risk",
            "explicit_scope",
            "evidence_status",
            "expiry",
            "authority_effect",
        }
    )

    acceptance_id: str | None = None
    acceptance_generation: int | None = None
    acceptance_digest: str | None = None
    request_id: str | None = None
    bounded_risk: str | None = None
    assumptions: tuple[str, ...] = ()
    compensating_controls: tuple[CompensatingControl, ...] = ()
    #: Injected hag reviewer coordinate (§11; hag-owned, §0.4e).
    reviewers: tuple[str, ...] = ()
    expiry: str | None = None
    evidence_status: WaivedEvidenceStatus | None = None
    explicit_scope: DeviationScope | None = None
    #: Injected spg envelope-containment verdict (§11 line 333; positive-polarity, ``is True`` clears;
    #: NOT covered — §0.4c/§2.3).
    within_hard_safety_envelope: bool | None = None
    #: §7 — an acceptance record is not proof, not permission (all-false, WDR-INV-001).
    authority_effect: AllFalseDeviationAuthority = AllFalseDeviationAuthority()

    @model_validator(mode="after")
    def _accepted_requires_compensation(self) -> ResidualRiskAcceptanceRecord:
        """A WAIVED-with-residual-risk acceptance cannot lack a compensating control (§2.3).

        Malformed-model self-defence: an acceptance that positively claims ``evidence_status is
        WAIVED_WITH_RESIDUAL_RISK`` requires at least one compensating control. An accepted claim
        coexisting with no compensation is malformed and **unconstructable** (symmetric to the request /
        decision seals; the ``model_construct`` escape hatch is re-caught by the §5 predicate layer,
        §2.3 / §11).
        """
        if self.evidence_status is WaivedEvidenceStatus.WAIVED_WITH_RESIDUAL_RISK:
            if not self.compensating_controls:
                raise ArtifactIntegrityError(
                    "ResidualRiskAcceptanceRecord declares evidence_status="
                    "WAIVED_WITH_RESIDUAL_RISK but carries no compensating control — an accepted "
                    "residual risk requires compensation (malformed-model self-defence, design #26 "
                    "§2.3 / ADR-002-026 §5.4/§11)."
                )
        return self


class ActiveDeviationSet(IndependentIdArtifact):
    """The immutable canonical Active Deviation Set (ADR-002-026 §5.9/§13; design #26 §2.4).

    §5.9: one immutable canonical set of every deviation and residual risk applicable to an exact Safety
    Configuration Bundle — "evaluated as a combined risk set and **cannot be assembled by permissive
    union at a consumer**." §13 line 364 "Absence of the set, an omitted applicable deviation, mixed
    generation, or conflicting digest is **invalid configuration**"; line 380 "No consumer may locally
    combine decisions ... or choose a more permissive interpretation" (WDR-INV-006 no-union). §13 line
    364 also binds "**either an explicit empty Active Deviation Set or one complete canonical set**" —
    an empty, no-deviation bundle's canonical representation is valid, never rejected (design #26 v1.1
    MAJOR-1). The ``combined_within_envelope`` verdict (spg) is an **injected** positive-polarity
    coordinate (§13 item 3, §0.4c). An :class:`~tos.wdr._base.IndependentIdArtifact` (``id !=
    f(digest)``).

    **Coordinate non-collapse (§2.3).** The injected ``combined_within_envelope`` (spg verdict) and the
    mutable ``state`` are **excluded** from the covered digest.
    """

    _ID_FIELD: ClassVar[str] = "active_set_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "active_set_id",
        "active_set_generation",
        "deviation_generation",
        "configuration_bundle_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "active_set_generation",
            "active_set_digest",
            "configuration_bundle_digest",
            "deviation_generation",
            "member_decisions",
            "member_digests",
            "is_complete",
            "authority_effect",
        }
    )

    active_set_id: str | None = None
    active_set_generation: int | None = None
    active_set_digest: str | None = None
    configuration_bundle_digest: str | None = None
    #: Injected Deviation Generation ordering coordinate (§5.8; MAX fence at reconcile, §4.4).
    deviation_generation: int | None = None
    #: Every applicable decision id (order-significant tuple — the canonical member list, §13 line 364).
    member_decisions: tuple[str, ...] = ()
    member_digests: tuple[str, ...] = ()
    #: Positive-polarity (§13 line 364) — only ``is True`` clears; ``None`` / ``False`` ⇒ invalid config.
    is_complete: bool | None = None
    #: Injected spg combined-envelope verdict (§13 item 3; positive-polarity, ``is True`` clears; NOT
    #: covered — §0.4c/§2.3).
    combined_within_envelope: bool | None = None
    #: Mutable lifecycle state (NOT covered — §2.3). No state grants live authority (§21 line 536).
    state: ActiveDeviationState | None = None
    #: §7 — an active set is a combined-risk view, not permission (all-false, WDR-INV-001).
    authority_effect: AllFalseDeviationAuthority = AllFalseDeviationAuthority()
