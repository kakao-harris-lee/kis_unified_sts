"""Shared valid-artifact builders + strategies for the wdr property tests (design #26 §7).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #26 §0.3). The builders enforce the
§7 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must be *genuinely* complete,
never a permissive shortcut):

* a **clean** boundary declares **every** one of the 15 §8 items, so a genuine
  ``boundary_denies_non_waivable`` is achievable (not a shortcut);
* a **clean** request carries **every** §5.7 scope dimension bound to an exact concrete value, a
  non-empty positively-complete dependency closure, ``WAIVABLE_ELIGIBLE`` with ``applicability_resolved``
  ``True``, no boundary hit, and every negative-polarity drift / UNKNOWN flag explicitly ``False``;
* a **clean** decision is ``ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`` with a complete reduced scope,
  ``single_use_consumed=False``, and an all-false authority;
* a **clean** active set has ``member_decisions`` equal to the applicable set, ``is_complete=True``,
  and a concrete ``deviation_generation``;
* a **clean** ladder has all six stages as explicit ``False`` bools and an all-false authority;
* the **polarity strategies** deliberately generate ``None`` / ``False`` / ``True`` tri-bools so the
  polarity seals (the #18/#22 MAJOR-2 lesson) are exercised across every ``bool | None`` field.

Every generation / floor value is an explicit fixture int — nothing here is a *policy* number; the real
wdr bounds are Verification-Profile injected and all null in Phase 1 (design #26 §8). The reserved
``"TBD"`` placeholder is excluded from required-field text.
"""

from __future__ import annotations

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.wdr import (
    ActiveDeviationSet,
    CompensatingControl,
    CompensatingControlKind,
    DecisionResult,
    DeviationDependencyClosure,
    DeviationScope,
    GateSeparationLadder,
    NonWaivableBoundaryAnchor,
    NonWaivableClassification,
    ResidualRiskAcceptanceRecord,
    SafetyDeviationDecision,
    SafetyDeviationPolicy,
    SafetyDeviationRequest,
    ScopeDimension,
    WaivedEvidenceItem,
    WaivedEvidenceStatus,
)

#: The injected provisional canonicalizer (REUSE, design #26 §3.1 — no new scheme).
SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Injected ``bool | None`` flag (fail-closed on ``None`` / ``False`` per polarity).
TRIBOOL = st.sampled_from([True, False, None])


def clean_boundary(**overrides: object) -> NonWaivableBoundaryAnchor:
    """A boundary anchor with every one of the 15 §8 items declared present (genuinely complete)."""
    kwargs: dict[str, object] = dict.fromkeys(
        NonWaivableBoundaryAnchor.BOUNDARY_ITEMS, True
    )
    kwargs.update(overrides)
    return NonWaivableBoundaryAnchor(**kwargs)


def clean_scope(**overrides: object) -> DeviationScope:
    """A DeviationScope with every §5.7 dimension bound to an exact concrete value (genuinely complete)."""
    kwargs: dict[str, object] = {
        dimension.name.lower(): f"v-{dimension.name.lower()}"
        for dimension in ScopeDimension
    }
    kwargs.update(overrides)
    return DeviationScope(**kwargs)


def clean_closure(**overrides: object) -> DeviationDependencyClosure:
    """A dependency closure that enumerates at least one affected coordinate and proves complete."""
    kwargs: dict[str, object] = {
        "components": ("component-1",),
        "closure_complete": True,
    }
    kwargs.update(overrides)
    return DeviationDependencyClosure(**kwargs)


def clean_control(**overrides: object) -> CompensatingControl:
    """A genuine preventive/containment compensating control (all positive polarity, observation False)."""
    kwargs: dict[str, object] = {
        "control_id": "ctl-1",
        "kind": CompensatingControlKind.PREVENTIVE,
        "is_preventive_or_containment": True,
        "objective_evidence": True,
        "fails_closed": True,
        "independent_of_failed_control": True,
        "observation_only": False,
    }
    kwargs.update(overrides)
    return CompensatingControl(**kwargs)


def clean_policy(
    *,
    policy_id: str = "pol-1",
    policy_generation: int = 1,
    policy_digest: str = "poldg",
    **overrides: object,
) -> SafetyDeviationPolicy:
    """A digest-verified governed Safety Deviation Policy (id ⊥ digest, all-false)."""
    return SafetyDeviationPolicy.issue(
        scheme=SCHEME,
        policy_id=policy_id,
        policy_generation=policy_generation,
        policy_digest=policy_digest,
        non_waivable_boundary=clean_boundary(),
        scope_dimensions=frozenset(ScopeDimension),
        **overrides,
    )


def clean_request(
    *,
    request_id: str = "req-1",
    request_version: int = 1,
    request_digest: str = "reqdg",
    policy_id: str = "pol-1",
    policy_generation: int = 1,
    scope: DeviationScope | None = None,
    non_waivable_classification: NonWaivableClassification | None = (
        NonWaivableClassification.WAIVABLE_ELIGIBLE
    ),
    applicability_resolved: bool | None = True,
    boundary_hits: frozenset[str] = frozenset(),
    dependency_closure: DeviationDependencyClosure | None = None,
    scope_wildcard: bool | None = False,
    scope_patched: bool | None = False,
    scope_widened: bool | None = False,
    scope_stale: bool | None = False,
    scope_conflicting: bool | None = False,
    materiality_unknown: bool | None = False,
    **overrides: object,
) -> SafetyDeviationRequest:
    """A digest-verified, genuinely eligible Safety Deviation Request (id ⊥ digest, all-false)."""
    return SafetyDeviationRequest.issue(
        scheme=SCHEME,
        request_id=request_id,
        request_version=request_version,
        request_digest=request_digest,
        policy_id=policy_id,
        policy_generation=policy_generation,
        deviation_scope=scope if scope is not None else clean_scope(),
        non_waivable_classification=non_waivable_classification,
        applicability_resolved=applicability_resolved,
        boundary_hits=boundary_hits,
        dependency_closure=(
            dependency_closure if dependency_closure is not None else clean_closure()
        ),
        scope_wildcard=scope_wildcard,
        scope_patched=scope_patched,
        scope_widened=scope_widened,
        scope_stale=scope_stale,
        scope_conflicting=scope_conflicting,
        materiality_unknown=materiality_unknown,
        **overrides,
    )


def construct_request(**overrides: object) -> SafetyDeviationRequest:
    """A request built via ``model_construct`` (bypasses the coexistence validator, §2.3).

    Used to reach the malformed states the construction-time seal forbids on the normal path (a
    ``WAIVABLE_ELIGIBLE`` claim coexisting with a boundary hit / blank scope) so the §5 predicate layer
    (defence in depth) can be exercised on them.
    """
    base: dict[str, object] = {
        "request_id": "req-mc",
        "request_version": 1,
        "request_digest": "reqdg",
        "policy_id": "pol-1",
        "policy_generation": 1,
        "deviation_scope": clean_scope(),
        "non_waivable_classification": NonWaivableClassification.WAIVABLE_ELIGIBLE,
        "applicability_resolved": True,
        "boundary_hits": frozenset(),
        "dependency_closure": clean_closure(),
        "scope_wildcard": False,
        "scope_patched": False,
        "scope_widened": False,
        "scope_stale": False,
        "scope_conflicting": False,
        "materiality_unknown": False,
    }
    base.update(overrides)
    return SafetyDeviationRequest.model_construct(**base)


def clean_unknown_request(**overrides: object) -> SafetyDeviationRequest:
    """A request with every §16 UNKNOWN flag explicitly ``False`` (all-known) + no protective bypass."""
    kwargs: dict[str, object] = {
        "broker_state_unknown": False,
        "order_state_unknown": False,
        "exposure_unknown": False,
        "residual_risk_unknown": False,
        "control_state_unknown": False,
        "evidence_unknown": False,
        "scope_unknown": False,
        "currentness_unknown": False,
        "materiality_unknown": False,
        "protective_label_bypass": False,
    }
    kwargs.update(overrides)
    return clean_request(**kwargs)


def clean_decision(
    *,
    decision_id: str = "dec-1",
    decision_generation: int = 1,
    request_id: str = "req-1",
    request_digest: str = "reqdg",
    deviation_generation: int = 5,
    reduced_scope: DeviationScope | None = None,
    result: (
        DecisionResult | None
    ) = DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION,
    single_use_consumed: bool | None = False,
    **overrides: object,
) -> SafetyDeviationDecision:
    """A digest-verified, genuinely eligible single-use Safety Deviation Decision."""
    return SafetyDeviationDecision.issue(
        scheme=SCHEME,
        decision_id=decision_id,
        decision_generation=decision_generation,
        request_id=request_id,
        request_digest=request_digest,
        deviation_generation=deviation_generation,
        reduced_scope=reduced_scope if reduced_scope is not None else clean_scope(),
        result=result,
        single_use_consumed=single_use_consumed,
        **overrides,
    )


def clean_acceptance(
    *,
    acceptance_id: str = "acc-1",
    acceptance_generation: int = 1,
    request_id: str = "req-1",
    evidence_status: WaivedEvidenceStatus | None = (
        WaivedEvidenceStatus.WAIVED_WITH_RESIDUAL_RISK
    ),
    **overrides: object,
) -> ResidualRiskAcceptanceRecord:
    """A digest-verified Residual-Risk Acceptance Record (WAIVED with compensation present)."""
    kwargs: dict[str, object] = {"compensating_controls": (clean_control(),)}
    kwargs.update(overrides)
    return ResidualRiskAcceptanceRecord.issue(
        scheme=SCHEME,
        acceptance_id=acceptance_id,
        acceptance_generation=acceptance_generation,
        request_id=request_id,
        evidence_status=evidence_status,
        explicit_scope=clean_scope(),
        within_hard_safety_envelope=True,
        **kwargs,
    )


def clean_active_set(
    *,
    active_set_id: str = "set-1",
    active_set_generation: int = 1,
    deviation_generation: int = 5,
    configuration_bundle_digest: str = "cbd",
    member_decisions: tuple[str, ...] = (),
    is_complete: bool | None = True,
    **overrides: object,
) -> ActiveDeviationSet:
    """A digest-verified Active Deviation Set (mutable state / spg verdict injected, not covered)."""
    return ActiveDeviationSet.issue(
        scheme=SCHEME,
        active_set_id=active_set_id,
        active_set_generation=active_set_generation,
        deviation_generation=deviation_generation,
        configuration_bundle_digest=configuration_bundle_digest,
        member_decisions=member_decisions,
        is_complete=is_complete,
        **overrides,
    )


def clean_ladder(**overrides: object) -> GateSeparationLadder:
    """A gate-separation ladder with every stage an explicit False bool and an all-false authority."""
    kwargs: dict[str, object] = dict.fromkeys(GateSeparationLadder.STAGE_FIELDS, False)
    kwargs.update(overrides)
    return GateSeparationLadder(**kwargs)


def clean_waived_item(**overrides: object) -> WaivedEvidenceItem:
    """A genuinely honest waived verification-item view (WAIVED with the exact-current gate satisfied)."""
    kwargs: dict[str, object] = {
        "measured_status": WaivedEvidenceStatus.WAIVED_WITH_RESIDUAL_RISK,
        "deviation_exists": True,
        "exact_current_decision_present": True,
        "reduced_scope_present": True,
        "compensation_present": True,
        "review_record_present": True,
        "relabeled_status": WaivedEvidenceStatus.WAIVED_WITH_RESIDUAL_RISK,
    }
    kwargs.update(overrides)
    return WaivedEvidenceItem(**kwargs)
