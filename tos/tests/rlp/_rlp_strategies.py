"""Shared valid-artifact builders + strategies for the rlp property tests (design #25 §7).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #25 §0.3). The builders enforce the
§7 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must be *genuinely*
complete, never a permissive shortcut):

* a **clean** plan carries **every** §9 scope dimension bound to an exact concrete value, concrete
  baseline digests, ``result=ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION``, and ``pre_registered`` /
  ``independently_reviewed`` positively ``True``, so a genuine ``plan_scope_exact_and_complete`` is
  achievable (not a shortcut);
* a **clean** package carries **every** ``EvidenceClass`` (so the negative-result classes are
  retained), ``selection_fixed_before_start=True`` with every post-hoc selection flag ``False``,
  ``causal_chain_complete=True``, and ``has_unresolved_gap=False``, so a genuine
  ``evidence_package_complete`` is satisfiable;
* a **clean** coverage claim has ``claimed_scope ⊆ observed_scope``, disjoint unexercised conditions,
  and ``verdict=COVERED``;
* a **clean** ladder has all nine stages as explicit ``False`` bools and an all-false authority;
* the **polarity strategies** deliberately generate ``None`` / ``False`` / ``True`` tri-bools so the
  polarity seals (the #22 MAJOR-2 lesson) are exercised across every ``bool | None`` field.

Every generation / floor value is an explicit fixture int — nothing here is a *policy* number; the
real rlp bounds are Verification-Profile injected and all null in Phase 1 (design #25 §8). The
reserved ``"TBD"`` placeholder is excluded from required-field text.
"""

from __future__ import annotations

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.rlp import (
    MANDATED_EVIDENCE_FLOOR,
    CoverageClaim,
    CoverageVerdict,
    ExactTrialPlan,
    GateStatusLadder,
    PlanResult,
    ProductionScopePromotionDecision,
    PromotionResult,
    ScopeDimension,
    TrialBudget,
    TrialClaimGroup,
    TrialEvidencePackage,
    TrialPolicy,
    TrialRun,
    TrialRunState,
    TrialScope,
)

#: The injected provisional canonicalizer (REUSE, design #25 §3.1 — no new scheme).
SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Injected ``bool | None`` flag (fail-closed on ``None`` / ``False`` per polarity).
TRIBOOL = st.sampled_from([True, False, None])


def clean_scope(**overrides: object) -> TrialScope:
    """A TrialScope with every §9 dimension bound to an exact concrete value (genuinely complete)."""
    kwargs: dict[str, object] = {
        dimension.name.lower(): f"v-{dimension.name.lower()}"
        for dimension in ScopeDimension
    }
    kwargs.update(overrides)
    return TrialScope(**kwargs)


def clean_budget(**overrides: object) -> TrialBudget:
    """A trial request envelope (NOT capacity; numerics injected, null-safe in Phase 1)."""
    return TrialBudget(**overrides)


def clean_policy(
    *,
    policy_id: str = "pol-1",
    policy_generation: int = 1,
    policy_digest: str = "poldg",
    **overrides: object,
) -> TrialPolicy:
    """A digest-verified governed Trial Policy (id ⊥ digest, all-false)."""
    return TrialPolicy.issue(
        scheme=SCHEME,
        policy_id=policy_id,
        policy_generation=policy_generation,
        policy_digest=policy_digest,
        scope_dimensions=frozenset(ScopeDimension),
        required_evidence_classes=MANDATED_EVIDENCE_FLOOR,
        **overrides,
    )


def clean_plan(
    *,
    plan_id: str = "plan-1",
    plan_generation: int = 1,
    plan_digest: str = "plandg",
    policy_id: str = "pol-1",
    policy_generation: int = 1,
    scope: TrialScope | None = None,
    baseline_digests: tuple[str, ...] = ("baseline-1", "baseline-2"),
    result: PlanResult | None = PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION,
    pre_registered: bool | None = True,
    independently_reviewed: bool | None = True,
    **overrides: object,
) -> ExactTrialPlan:
    """A digest-verified, genuinely eligible Exact Trial Plan (id ⊥ digest, all-false)."""
    return ExactTrialPlan.issue(
        scheme=SCHEME,
        plan_id=plan_id,
        plan_generation=plan_generation,
        plan_digest=plan_digest,
        policy_id=policy_id,
        policy_generation=policy_generation,
        trial_scope=scope if scope is not None else clean_scope(),
        baseline_digests=baseline_digests,
        trial_budget=clean_budget(),
        result=result,
        pre_registered=pre_registered,
        independently_reviewed=independently_reviewed,
        **overrides,
    )


def clean_run(
    *,
    run_id: str = "run-1",
    run_generation: int = 1,
    plan_id: str = "plan-1",
    plan_digest: str = "plandg",
    state: TrialRunState | None = TrialRunState.RUNNING,
    is_aborted: bool | None = False,
    is_invalidated: bool | None = False,
    **overrides: object,
) -> TrialRun:
    """A digest-verified Trial Run (mutable lifecycle state injected, not covered)."""
    return TrialRun.issue(
        scheme=SCHEME,
        run_id=run_id,
        run_generation=run_generation,
        plan_id=plan_id,
        plan_digest=plan_digest,
        state=state,
        is_aborted=is_aborted,
        is_invalidated=is_invalidated,
        **overrides,
    )


def clean_package(
    *,
    package_id: str = "pkg-1",
    package_generation: int = 1,
    package_digest: str = "pkgdg",
    plan_id: str = "plan-1",
    plan_digest: str = "plandg",
    run_id: str = "run-1",
    present_element_classes: frozenset = MANDATED_EVIDENCE_FLOOR,
    promotion_complete_claim: bool | None = None,
    selection_fixed_before_start: bool | None = True,
    optional_stopping: bool | None = False,
    discarded_runs: bool | None = False,
    selected_windows: bool | None = False,
    removed_adverse: bool | None = False,
    causal_chain_complete: bool | None = True,
    has_unresolved_gap: bool | None = False,
    **overrides: object,
) -> TrialEvidencePackage:
    """A digest-verified, genuinely complete Trial Evidence Package (every class + negatives retained).

    Injected evidence-owned verdicts (``causal_chain_complete`` / ``has_unresolved_gap``) and the
    mutable-ish selection flags are set directly; the covered digest fields are set via ``issue``.
    """
    return TrialEvidencePackage.issue(
        scheme=SCHEME,
        package_id=package_id,
        package_generation=package_generation,
        package_digest=package_digest,
        plan_id=plan_id,
        plan_digest=plan_digest,
        run_id=run_id,
        present_element_classes=present_element_classes,
        promotion_complete_claim=promotion_complete_claim,
        selection_fixed_before_start=selection_fixed_before_start,
        optional_stopping=optional_stopping,
        discarded_runs=discarded_runs,
        selected_windows=selected_windows,
        removed_adverse=removed_adverse,
        causal_chain_complete=causal_chain_complete,
        has_unresolved_gap=has_unresolved_gap,
        **overrides,
    )


def clean_coverage_claim(
    *,
    claimed_scope: frozenset[str] = frozenset({"a", "b"}),
    observed_scope: frozenset[str] = frozenset({"a", "b", "c"}),
    exercised_conditions: frozenset[str] = frozenset({"nominal"}),
    unexercised_conditions: frozenset[str] = frozenset({"crash"}),
    equivalence_positively_proven: bool | None = None,
    verdict: CoverageVerdict | None = CoverageVerdict.COVERED,
) -> CoverageClaim:
    """A coverage claim with claimed ⊆ observed, disjoint unexercised, verdict COVERED (genuine)."""
    return CoverageClaim(
        claimed_scope=claimed_scope,
        observed_scope=observed_scope,
        exercised_conditions=exercised_conditions,
        unexercised_conditions=unexercised_conditions,
        equivalence_positively_proven=equivalence_positively_proven,
        verdict=verdict,
    )


def clean_ladder(**overrides: object) -> GateStatusLadder:
    """A gate-status ladder with every stage an explicit False bool and an all-false authority."""
    kwargs: dict[str, object] = dict.fromkeys(GateStatusLadder.STAGE_FIELDS, False)
    kwargs.update(overrides)
    return GateStatusLadder(**kwargs)


def clean_claims(
    *,
    trial_policy_generation: int | None = 1,
    trial_plan_generation: int | None = 2,
    trial_run_generation: int | None = 3,
    promotion_generation: int | None = 4,
    remaining_envelope: str | None = "env",
    abort_generation: int | None = 5,
) -> TrialClaimGroup:
    """A genuinely complete 6-scalar trial claim group (egress ``is_complete()`` mirror)."""
    return TrialClaimGroup(
        trial_policy_generation=trial_policy_generation,
        trial_plan_generation=trial_plan_generation,
        trial_run_generation=trial_run_generation,
        promotion_generation=promotion_generation,
        remaining_envelope=remaining_envelope,
        abort_generation=abort_generation,
    )


def clean_decision(
    *,
    decision_id: str = "dec-1",
    decision_generation: int = 1,
    promotion_generation: int = 1,
    source_run_id: str = "run-1",
    source_package_id: str = "pkg-1",
    result: PromotionResult | None = PromotionResult.ELIGIBLE_TO_REQUEST_NEW_SCOPE,
    single_use_consumed: bool | None = False,
    requested_delta: str | None = "delta-1",
    coverage_claims: tuple[CoverageClaim, ...] | None = None,
    **overrides: object,
) -> ProductionScopePromotionDecision:
    """A digest-verified, genuinely eligible single-use Production Scope Promotion Decision."""
    claims = (
        coverage_claims if coverage_claims is not None else (clean_coverage_claim(),)
    )
    return ProductionScopePromotionDecision.issue(
        scheme=SCHEME,
        decision_id=decision_id,
        decision_generation=decision_generation,
        promotion_generation=promotion_generation,
        source_run_id=source_run_id,
        source_package_id=source_package_id,
        result=result,
        single_use_consumed=single_use_consumed,
        requested_delta=requested_delta,
        coverage_claims=claims,
        **overrides,
    )


#: The approved max-delta ceiling for the promotion single-use gate — an injected Profile-INSTANCE
#: value (null in Phase 1, §8), set concretely here so the null-gated ``_within_max_delta`` check is
#: satisfiable in tests.
PROMOTION_MAX_DELTA = 5

#: The predecessor Promotion Generation floor a clean decision (``promotion_generation=1``) strictly
#: advances (§5.10 generation-fence). A decision at / below this floor is retired (denied).
PROMOTION_PREDECESSOR_FLOOR = 0


def clean_promotion_policy(
    *, max_delta: int = PROMOTION_MAX_DELTA, **overrides: object
) -> TrialPolicy:
    """A Trial Policy carrying a concrete approved ``max_delta`` ceiling (§18) for the promotion gate."""
    return clean_policy(max_delta=max_delta, **overrides)
