"""rlp digest-bound artifacts — the five restricted-live / promotion ledger citizens (design #25 §2).

Every artifact is a **pydantic v2 frozen model** (``frozen=True, extra="forbid"`` via
:class:`~tos.rlp._base.FrozenModel`): ``extra="forbid"`` is the schema-level "omission is restrictive"
and frozen is the append-only realization; there is **no** update / delete / mutate / transmit / sign
/ arm / clear-halt / approve / authorize / promote method on any model (design #25 §2.3/§4.1 — the
constructive-absence canary). Field names use the ADR §5-§26 terms **verbatim** (spec terms = code
terms, boundary design #1 §2.4).

**Five id-independent artifacts (design #25 §2.1/§3.1).** ``TrialPolicy`` / ``ExactTrialPlan`` /
``TrialRun`` / ``TrialEvidencePackage`` / ``ProductionScopePromotionDecision`` are **issued-identity**
records (:class:`~tos.rlp._base.IndependentIdArtifact`, ``id != f(digest)``): the id is separately
issued, so a same-id / different-bytes forged, re-issued, or replayed record is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT`` (design #25 §2.1/§3.1 — RLP-EV-001/007). §16 line 428
"Evidence Commit Receipt proves custody"; §9 line 261 "canonical digest and predecessor"; §18 line
462 "single-use consumption identity".

**RLP = trial-content owner; egress / cur = downstream per-boundary consumer (design #25 §0.4b — the
key architecture decision, witnessed by sibling code).** egress (``state.py:196``) and cur
(``state.py:140``) carry the restricted-live trial claim group as an opaque optional scalar group and
**defer its content validation to RLP by name** (``tos.rlp``). rlp **authors** the trial-content
artifacts here and their :class:`~tos.rlp.state.TrialClaimGroup` generation coordinates flow
**downstream** into the egress ``QuorumCommitCertificate`` / cur ``SafetyCurrentnessVector`` 6-scalar
``TrialClaims``. rlp re-authors **no** egress QCC / cur RESTRICTED_LIVE_TRIAL boundary seal, and
imports **neither** sibling (sibling edge 0; an import would be a cycle since egress / cur consume rlp).

**Malformed-model self-defence — positive-claim + incomplete-group coexistence seal (egress QCC
``_trial_claim_completeness`` isomorph; design #25 §2.3 / #20 lesson).** Three artifacts carry a
construction-time coexistence seal (a 3-of-3 symmetry, v1.1 MINOR-3):

* ``ExactTrialPlan`` — ``result is ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION`` while any §9 mandated
  scope dimension is ``None`` / wildcard, or a baseline digest is missing / wildcard, is
  **unconstructable** (an "eligible" plan whose exact scope is blank cannot exist).
* ``TrialEvidencePackage`` — ``promotion_complete_claim is True`` while a negative-result element
  class is absent is **unconstructable** (a "complete promotion" package that stripped its failure
  evidence is selective reporting, §16 line 426).
* ``ProductionScopePromotionDecision`` — ``result is ELIGIBLE_TO_REQUEST_NEW_SCOPE`` while no
  coverage claim is present is **unconstructable** (a promotion eligibility with no coverage cannot
  exist).

The ``model_construct`` escape hatch that skips validators is re-caught in the §5 predicate layer
(defence in depth, §2.3): the yolk predicates re-derive completeness structurally and never trust a
stored flag.

**Coordinate non-collapse (design #25 §2.3/§4.4).** No mutable lifecycle coordinate — the run
``state`` / ``is_aborted`` / ``is_invalidated``, the promotion ``single_use_consumed``, the package's
injected ``causal_chain_complete`` / gap state — is a covered digest field: a lawful lifecycle
transition must not change an artifact's digest and be mis-flagged as a same-id / different-bytes
``CRITICAL_CONFLICT`` (the rcl / egress / cur coordinate-non-collapse precedent). Every covered field
is an immutable claim; the current lifecycle state is injected into the predicate.

**Deterministic set-covered digest (design #25 §3.1).** ``frozenset`` covered fields (policy /
package class manifests) are **sorted** in :meth:`covered_content` so the digest is deterministic
across processes (a frozenset's iteration order is otherwise unstable); the field type stays a
``frozenset`` for the predicate's subset math (the cur ``required_dimensions`` precedent).

**All-false authority (design #25 §2.4/§7; RLP-INV-001).** Every artifact carries an
:class:`~tos.rlp._base.AllFalseTrialAuthority` with all nine flags ``False`` — a trial artifact is
verified data / a non-authorizing decision, not permission.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.rlp._base``) + ``tos.rlp.*``
only; no ``shared.*``, no sibling ``tos.*`` (design #25 §0.3).
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import model_validator

from tos.rlp._base import (
    AllFalseTrialAuthority,
    ArtifactIntegrityError,
    IndependentIdArtifact,
)
from tos.rlp.state import (
    CoverageClaim,
    TrialBudget,
    TrialScope,
    is_wildcard_value,
)
from tos.rlp.vocabulary import (
    MANDATED_SCOPE_FLOOR,
    NEGATIVE_RESULT_CLASSES,
    EvidenceClass,
    PlanResult,
    PromotionResult,
    ScopeDimension,
    TrialRunState,
)

__all__ = [
    "TrialPolicy",
    "ExactTrialPlan",
    "TrialRun",
    "TrialEvidencePackage",
    "ProductionScopePromotionDecision",
    "AllFalseTrialAuthority",
]


def _sorted_set_fields(content: dict[str, Any], *names: str) -> dict[str, Any]:
    """Sort the named ``frozenset``-derived list fields for a deterministic digest (§3.1)."""
    for name in names:
        value = content.get(name)
        if value is not None:
            content[name] = sorted(value)
    return content


class TrialPolicy(IndependentIdArtifact):
    """The governed Trial Policy content model (ADR-002-025 §5.1/§8; design #25 §2.4).

    §8: the governed policy that declares the trial-class eligibility, the §9 mandated scope-dimension
    catalogue, the §16 required evidence classes, the coverage rules, abort triggers, and promotion
    ladder. rlp **authors** the policy *content* model, but the policy's **activation / generation is
    spg/014-governed** (design #25 §0.4g; §8 line 253 "Policy activation follows ADR-002-014") —
    carried as injected ``policy_generation`` / ``policy_digest`` scalars, re-authored not at all. An
    :class:`~tos.rlp._base.IndependentIdArtifact` (``id != f(digest)``). Its
    :class:`~tos.rlp._base.AllFalseTrialAuthority` is all-false — a policy is governed content, not
    permission (RLP-INV-001). Every numeric bound (``max_delta`` / required-reviewer count / ...) is
    an injected Profile-INSTANCE value, null in Phase 1 (§8).
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
            "eligible_trial_classes",
            "prohibited_trial_classes",
            "scope_dimensions",
            "required_evidence_classes",
            "compatibility_manifest_digest",
            "authority_effect",
        }
    )

    policy_id: str | None = None
    #: Injected spg/014-governed activation generation (§0.4g; ``None`` ⇒ fail-closed at predicate).
    policy_generation: int | None = None
    policy_digest: str | None = None
    eligible_trial_classes: frozenset[str] = frozenset()
    prohibited_trial_classes: frozenset[str] = frozenset()
    #: The §9 mandated scope-dimension catalogue the policy declares (subset math; §5.1).
    scope_dimensions: frozenset[ScopeDimension] = frozenset()
    #: The §16 required evidence element classes (subset math; §5.2).
    required_evidence_classes: frozenset[EvidenceClass] = frozenset()
    #: Injected numeric bounds (null in Phase 1, §8) — a request envelope ceiling, not capacity.
    max_delta: int | None = None
    required_reviewers: int | None = None
    compatibility_manifest_digest: str | None = None
    #: §7 — a policy is governed content, not permission (all-false, RLP-INV-001).
    authority_effect: AllFalseTrialAuthority = AllFalseTrialAuthority()

    def covered_content(self) -> dict[str, Any]:
        """Digest preimage with the ``frozenset`` class fields serialized deterministically (§3.1)."""
        return _sorted_set_fields(
            super().covered_content(),
            "eligible_trial_classes",
            "prohibited_trial_classes",
            "scope_dimensions",
            "required_evidence_classes",
        )


class ExactTrialPlan(IndependentIdArtifact):
    """The immutable pre-registered Exact Trial Plan (ADR-002-025 §5.2/§9; design #25 §2.4).

    §9: the immutable pre-registered proposal that binds the exact scope + baseline digests + targeted
    claims + pre-registered actions / observations / coverage claims + trial budget + assumptions +
    prerequisite coordinates + principals + evidence plan + abort/recovery + residual risks (§9 line
    263-273). Its 6-scalar generation coordinates flow **downstream** into the egress / cur
    ``TrialClaims`` (§0.4b). An :class:`~tos.rlp._base.IndependentIdArtifact` (``id != f(digest)``): a
    same-id / different-bytes plan substitution is a detectable ``CRITICAL_CONFLICT``.

    **Coexistence seal (§2.3).** ``result is ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION`` while the §9
    mandated scope is incomplete / wildcard or a baseline digest is missing / wildcard is
    **unconstructable** (the egress QCC ``_trial_claim_completeness`` isomorph). ``result`` /
    ``pre_registered`` / ``independently_reviewed`` never grant authority (all-false, RLP-INV-001).
    """

    _ID_FIELD: ClassVar[str] = "plan_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "plan_id",
        "plan_generation",
        "plan_digest",
        "policy_id",
        "policy_generation",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "plan_generation",
            "plan_digest",
            "predecessor_plan_id",
            "policy_id",
            "policy_generation",
            "policy_digest",
            "compatibility_manifest_digest",
            "trial_scope",
            "baseline_digests",
            "result",
            "pre_registered",
            "independently_reviewed",
            "authority_effect",
        }
    )

    # identity (§9 line 261)
    plan_id: str | None = None
    plan_generation: int | None = None
    plan_digest: str | None = None
    predecessor_plan_id: str | None = None
    policy_id: str | None = None
    policy_generation: int | None = None
    policy_digest: str | None = None
    compatibility_manifest_digest: str | None = None

    # scope / baseline (§9 line 263)
    trial_scope: TrialScope | None = None
    baseline_digests: tuple[str, ...] = ()

    # claims (§9 line 264)
    targeted_safety_claims: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    # pre-registered plan body (§9 line 265)
    pre_registered_actions: tuple[str, ...] = ()
    order_shapes: tuple[str, ...] = ()
    failure_injections: tuple[str, ...] = ()
    observations: tuple[str, ...] = ()
    coverage_claims: tuple[CoverageClaim, ...] = ()

    # budget (§9 line 266) — NOT capacity (§10)
    trial_budget: TrialBudget | None = None

    # assumptions (§9 line 267)
    existing_exposure: str | None = None
    external_activity_window: str | None = None
    protective_obligation: str | None = None
    abort_overlap: str | None = None
    recovery_assumptions: str | None = None

    # prerequisite coordinates (§9 line 268-269; all injected)
    rcl_capacity_request: str | None = None
    action_flow_reserve: str | None = None
    protective_capacity: str | None = None
    start_window: str | None = None
    expiry: str | None = None
    trustworthy_time_requirements: str | None = None
    consumer_receipt_anchors: tuple[str, ...] = ()

    # principals (§9 line 270)
    required_principals: tuple[str, ...] = ()
    operators: tuple[str, ...] = ()
    independent_reviewers: tuple[str, ...] = ()
    observers: tuple[str, ...] = ()

    # evidence plan (§9 line 271)
    evidence_sources: tuple[str, ...] = ()
    pre_effect_durability: str | None = None
    package_schema: str | None = None
    retention: str | None = None

    # abort / recovery (§9 line 272)
    abort_triggers: tuple[str, ...] = ()
    halt_scope: str | None = None
    egress_latch_behavior: str | None = None
    reconciliation: str | None = None
    recovery_disposition: str | None = None

    # residual (§9 line 273)
    residual_risks: tuple[str, ...] = ()
    prohibited_inferences: tuple[str, ...] = ()

    # result + review (§9 line 275; polarity §4.3)
    result: PlanResult | None = None
    #: Positive-polarity (§9 line 275) — only ``is True`` clears; ``None`` / ``False`` ⇒ deny.
    pre_registered: bool | None = None
    #: Positive-polarity (§11 item 6 / RLP-INV-014) — only ``is True`` clears; ``None`` / ``False`` deny.
    independently_reviewed: bool | None = None
    #: §7 — a plan is a proposal, not permission (all-false, RLP-INV-001).
    authority_effect: AllFalseTrialAuthority = AllFalseTrialAuthority()

    def covered_content(self) -> dict[str, Any]:
        """Digest preimage with the ``baseline_digests`` tuple kept order-significant (§3.1)."""
        return super().covered_content()

    @model_validator(mode="after")
    def _eligible_requires_exact_scope(self) -> ExactTrialPlan:
        """An eligible plan cannot carry an incomplete / wildcard scope or baseline (§2.3).

        Malformed-model self-defence (design #25 §2.3 / #20 lesson): a plan that positively claims
        ``result is ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION`` requires **every** §9 mandated scope
        dimension bound to an exact (non-``None``, non-wildcard) value and **every** baseline digest
        concrete. An eligible claim coexisting with a blank / wildcard scope dimension — or a missing
        / wildcard baseline — is a malformed model and **unconstructable** on the normal validation
        path (the egress QCC ``_trial_claim_completeness`` isomorph; the ``model_construct`` escape
        hatch is re-caught by :func:`~tos.rlp.predicates.plan_scope_exact_and_complete`, §5.1).
        """
        if self.result is PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION:
            scope = self.trial_scope
            scope_incomplete = (
                scope is None or scope.concrete_dimensions() != MANDATED_SCOPE_FLOOR
            )
            baseline_incomplete = not self.baseline_digests or any(
                digest is None or is_wildcard_value(digest)
                for digest in self.baseline_digests
            )
            if scope_incomplete or baseline_incomplete:
                raise ArtifactIntegrityError(
                    "ExactTrialPlan declares result="
                    "ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION but carries an incomplete or wildcard "
                    "exact scope / baseline — an eligible plan requires every §9 line 263 scope "
                    "dimension bound to an exact concrete value and every baseline digest concrete "
                    "(malformed-model self-defence, design #25 §2.3 / RLP-INV-002 line 154 / "
                    "ADR-002-025 §9)."
                )
        return self


class TrialRun(IndependentIdArtifact):
    """A Trial Run instance + state machine (ADR-002-025 §5.5/§14; design #25 §2.4).

    §14: the run instance that binds one plan identity + plan digest (§12 line 335 "binds one Trial
    Run identity, plan digest"), the baseline digest, the promotion + Live Authorization generations
    (liveauth-injected, §12), the max-action/effect/count/duration envelope, the start window /
    expiry, the abort generation, and the run ``state``. §14 line 374 "``RUNNING`` ... does not itself
    grant transmission permission" — **no** state grants authority (all-false, RLP-INV-001). An
    :class:`~tos.rlp._base.IndependentIdArtifact` (``id != f(digest)``).

    **Coordinate non-collapse (§2.3).** ``state`` / ``is_aborted`` / ``is_invalidated`` (mutable
    lifecycle) are **excluded** from the covered digest — a lawful transition must not change the
    run's digest. The current lifecycle state is injected into the predicate.
    """

    _ID_FIELD: ClassVar[str] = "run_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "run_id",
        "run_generation",
        "plan_id",
        "plan_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "run_generation",
            "plan_id",
            "plan_digest",
            "baseline_digest",
            "promotion_generation",
            "live_authorization_generation",
            "max_action_effect_count_duration_envelope",
            "start_window",
            "expiry",
            "abort_generation",
            "authority_effect",
        }
    )

    run_id: str | None = None
    run_generation: int | None = None
    plan_id: str | None = None
    plan_digest: str | None = None
    baseline_digest: str | None = None
    #: Injected promotion generation coordinate (§12; ordering scalar, not a clock).
    promotion_generation: int | None = None
    #: Injected liveauth Live Authorization generation (§12; rlp does not issue it, RLP-INV-001).
    live_authorization_generation: int | None = None
    max_action_effect_count_duration_envelope: str | None = None
    start_window: str | None = None
    expiry: str | None = None
    abort_generation: int | None = None
    #: Mutable lifecycle state (NOT covered — §2.3). No state grants transmission (§14 line 374).
    state: TrialRunState | None = None
    #: Negative-polarity abort state (mutable — NOT covered, §2.3). ``is not False`` (True / None) deny.
    is_aborted: bool | None = None
    #: Negative-polarity invalidation state (mutable — NOT covered, §2.3). ``is not False`` deny.
    is_invalidated: bool | None = None
    #: §7 — a run is a lifecycle marker, not permission (all-false, RLP-INV-001).
    authority_effect: AllFalseTrialAuthority = AllFalseTrialAuthority()


class TrialEvidencePackage(IndependentIdArtifact):
    """The immutable gap-checked Trial Evidence Package (ADR-002-025 §5.7/§16; design #25 §2.4).

    §16: the immutable package that proves what occurred across every element class — the event
    classes, capacity/flow transitions, coverage / **negative-result** classes, broker evidence, and
    generation/review classes (§16 line 416-424). The **assembly + custody integrity** is
    evidence-owned (ADR-002-016 ``SegmentCommitmentScheme`` / ``causal_chain_complete`` / gap machine,
    §0.4d) — carried here as **injected** ``causal_chain_complete`` / gap-status verdicts, re-authored
    not at all. rlp owns the **completeness contract**: the element-class manifest + the
    **negative-result retention gate** (§16 line 426 "Post-hoc metric changes, optional stopping,
    discarded runs, selected time windows, selected accounts, or removal of adverse results invalidate
    the promotion claim"). An :class:`~tos.rlp._base.IndependentIdArtifact` (``id != f(digest)``).

    **Coexistence seal (§2.3, v1.1 MINOR-3).** ``promotion_complete_claim is True`` while a
    negative-result element class is absent is **unconstructable** — a "complete promotion" package
    that stripped its failure evidence is selective reporting. The §5.2 predicate-layer
    negative-retention gate is a separate second layer (defence in depth).
    """

    _ID_FIELD: ClassVar[str] = "package_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "package_id",
        "package_generation",
        "plan_id",
        "plan_digest",
        "run_id",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "package_generation",
            "package_digest",
            "plan_id",
            "plan_digest",
            "policy_digest",
            "baseline_digest",
            "run_id",
            "present_element_classes",
            "promotion_complete_claim",
            "selection_fixed_before_start",
            "authority_effect",
        }
    )

    package_id: str | None = None
    package_generation: int | None = None
    package_digest: str | None = None
    plan_id: str | None = None
    plan_digest: str | None = None
    policy_digest: str | None = None
    baseline_digest: str | None = None
    run_id: str | None = None
    approvals: tuple[str, ...] = ()
    authorizations: tuple[str, ...] = ()

    #: The §16 element-class manifest — which element classes the package carries (subset math; §5.2).
    present_element_classes: frozenset[EvidenceClass] = frozenset()

    #: v1.1 MINOR-3 coexistence-seal key (§2.3): a positive promotion-complete claim requires the
    #: negative-result classes retained. Positive-polarity (``is True`` ⇒ claim; None / False ⇒ none).
    promotion_complete_claim: bool | None = None

    # selection discipline (§16 line 426; §4.3 polarity)
    #: Positive-polarity (§16 line 426) — only ``is True`` clears; None / False ⇒ incomplete.
    selection_fixed_before_start: bool | None = None
    #: Negative-polarity (§16 line 426) — ``is not False`` (True / None) ⇒ invalidate the claim.
    optional_stopping: bool | None = None
    discarded_runs: bool | None = None
    selected_windows: bool | None = None
    removed_adverse: bool | None = None

    # evidence integrity (evidence-owned injected verdicts — NOT covered, §0.4d/§2.3)
    #: Positive-polarity (§16, evidence-owned) — ``is True`` ⇒ chain complete; None / False deny.
    causal_chain_complete: bool | None = None
    #: Negative-polarity (§16, evidence-owned gap machine) — ``is not False`` (True / None) ⇒ gap.
    has_unresolved_gap: bool | None = None
    commit_receipt_id: str | None = None
    #: §7 — a package is verified data, not permission (all-false, RLP-INV-001).
    authority_effect: AllFalseTrialAuthority = AllFalseTrialAuthority()

    def covered_content(self) -> dict[str, Any]:
        """Digest preimage with the ``present_element_classes`` set serialized deterministically (§3.1)."""
        return _sorted_set_fields(super().covered_content(), "present_element_classes")

    @model_validator(mode="after")
    def _complete_claim_requires_negative_retention(self) -> TrialEvidencePackage:
        """A promotion-complete package cannot omit a negative-result class (§2.3, v1.1 MINOR-3).

        Malformed-model self-defence: a package that positively claims
        ``promotion_complete_claim is True`` requires **every** negative-result element class
        (:data:`~tos.rlp.vocabulary.NEGATIVE_RESULT_CLASSES` — the §16 line 422 six: negative /
        failed / inconclusive / aborted / superseded / conflicting) present in its manifest. A
        complete claim coexisting with an absent negative class is selective reporting and
        **unconstructable** on the normal validation path (symmetric to the plan / decision
        result-enum seals; the ``model_construct`` escape hatch is re-caught by
        :func:`~tos.rlp.predicates.evidence_package_complete`, §5.2).
        """
        if self.promotion_complete_claim is True:
            if not self.present_element_classes >= NEGATIVE_RESULT_CLASSES:
                raise ArtifactIntegrityError(
                    "TrialEvidencePackage declares promotion_complete_claim=True but its "
                    "element-class manifest omits a negative-result class — a complete promotion "
                    "package must retain every negative / failed / inconclusive / aborted / "
                    "superseded / conflicting result class (removal of adverse results is selective "
                    "reporting; malformed-model self-defence, design #25 §2.3 / RLP-INV-009 / "
                    "ADR-002-025 §16 line 422)."
                )
        return self


class ProductionScopePromotionDecision(IndependentIdArtifact):
    """A single-use Production Scope Promotion Decision (ADR-002-025 §5.9/§18; design #25 §2.4).

    §18: a single-use, non-authorizing independent decision to widen the production scope by a
    requested delta. It binds the source run / package identity + digest, the current scope, the
    requested delta (§18 line 455), the coverage claims, the uncovered conditions, the residual risks,
    the reviewer quorum (hag-injected), and the effective-principal verdict (hag-injected). §18 line
    464 "It is not approval of an order or production permission" — the decision grants **no**
    authority (all-false, RLP-INV-001). An :class:`~tos.rlp._base.IndependentIdArtifact`.

    **Coexistence seal (§2.3).** ``result is ELIGIBLE_TO_REQUEST_NEW_SCOPE`` while no coverage claim
    is present is **unconstructable** (an eligible promotion with no coverage cannot exist).

    **Coordinate non-collapse (§2.3).** ``single_use_consumed`` (mutable lifecycle) and the injected
    ``effective_principal_verdict`` (hag verdict) are **excluded** from the covered digest.
    """

    _ID_FIELD: ClassVar[str] = "decision_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "decision_id",
        "decision_generation",
        "promotion_generation",
        "source_run_id",
        "source_package_id",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "decision_generation",
            "promotion_generation",
            "source_run_id",
            "source_package_id",
            "source_package_digest",
            "baseline_digest",
            "current_scope",
            "requested_delta",
            "max_effect",
            "expiry",
            "result",
            "authority_effect",
        }
    )

    decision_id: str | None = None
    decision_generation: int | None = None
    #: Injected Promotion Generation ordering coordinate (§5.10; MAX fence at reconcile, §4.4).
    promotion_generation: int | None = None
    source_run_id: str | None = None
    source_package_id: str | None = None
    source_package_digest: str | None = None
    baseline_digest: str | None = None
    current_scope: str | None = None
    #: The requested scope delta (§18 line 455).
    requested_delta: str | None = None
    coverage_claims: tuple[CoverageClaim, ...] = ()
    uncovered_conditions: frozenset[str] = frozenset()
    residual_risks: tuple[str, ...] = ()
    max_effect: str | None = None
    config_profile_changes_required: tuple[str, ...] = ()
    required_additional_evidence: tuple[str, ...] = ()
    expiry: str | None = None
    #: Injected hag reviewer quorum coordinate (§18; hag-owned, §0.4e).
    reviewer_quorum: int | None = None
    #: Injected hag effective-principal verdict (§22; positive-polarity, ``is True`` clears, §0.4e).
    effective_principal_verdict: bool | None = None
    #: Negative-polarity single-use state (mutable — NOT covered, §2.3). ``is not False`` reject reuse.
    single_use_consumed: bool | None = None
    result: PromotionResult | None = None
    #: §7 — a decision is non-authorizing, not permission (all-false, RLP-INV-001).
    authority_effect: AllFalseTrialAuthority = AllFalseTrialAuthority()

    @model_validator(mode="after")
    def _eligible_requires_coverage(self) -> ProductionScopePromotionDecision:
        """An eligible promotion decision cannot lack coverage (§2.3).

        Malformed-model self-defence: a decision that positively claims
        ``result is ELIGIBLE_TO_REQUEST_NEW_SCOPE`` requires at least one coverage claim. An eligible
        claim coexisting with no coverage is malformed and **unconstructable** (symmetric to the plan
        / package seals; the ``model_construct`` escape hatch is re-caught by
        :func:`~tos.rlp.predicates.promotion_progressive_single_use`, §6.3).
        """
        if self.result is PromotionResult.ELIGIBLE_TO_REQUEST_NEW_SCOPE:
            if not self.coverage_claims:
                raise ArtifactIntegrityError(
                    "ProductionScopePromotionDecision declares result="
                    "ELIGIBLE_TO_REQUEST_NEW_SCOPE but carries no coverage claim — an eligible "
                    "promotion requires coverage evidence (malformed-model self-defence, design "
                    "#25 §2.3 / ADR-002-025 §18)."
                )
        return self
