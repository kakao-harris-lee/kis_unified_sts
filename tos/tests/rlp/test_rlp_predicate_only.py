"""Predicate-only §6 substrate (RLP-EV-002/003/007/009/010/011) + not-Phase-1 §6b (RLP-EV-004).

These predicates author the L1-decidable structural substrate for the ≥ L2 rows but close **no**
RLP-EV: the real worst-credible-effect computation (rcl + +Broker), per-send binding (egress +Broker),
registry replay (+Security), hard-fence (+Security), and abort latency (+Security runtime) are all
out of scope. The abort-order model (§6b) is not-Phase-1 (``EV-L3+Security``).

Regime tag: predicate substrate only; the named RLP-EV rows remain NOT_IMPLEMENTED pending L2/L3 +
+Security / +Broker; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given
from tos.rlp import (
    AllFalseTrialAuthority,
    ArtifactIntegrityError,
    ProductionScopePromotionDecision,
    PromotionResult,
    TrialRunState,
    abort_precedes_action,
    action_potentially_live,
    demotion_not_rearm,
    economic_effect_persists,
    expiry_denies_future_use_only,
    monitoring_not_preventive,
    promotion_progressive_single_use,
    recovery_revives_nothing,
    trial_budget_is_not_capacity,
    trial_status_waives_no_gate,
)

from ._rlp_strategies import (
    PROMOTION_PREDECESSOR_FLOOR,
    TRIBOOL,
    clean_budget,
    clean_coverage_claim,
    clean_decision,
    clean_policy,
    clean_promotion_policy,
)

# --- §6.1 trial_budget_is_not_capacity (RLP-EV-002 · +Broker) ---------------


def test_trial_budget_is_a_request_envelope_not_capacity() -> None:
    """(§6.1) A present budget is a request envelope (structurally not capacity); None ⇒ deny."""
    assert trial_budget_is_not_capacity(clean_budget()) is True
    assert trial_budget_is_not_capacity(None) is False


# --- §6.2 trial_status_waives_no_gate (RLP-EV-003 · +Broker; RLP-INV-004) ----


def test_trial_status_waives_no_gate_all_false() -> None:
    """(§6.2 / RLP-INV-004) An all-false authority waives no gate; None ⇒ deny."""
    assert trial_status_waives_no_gate(AllFalseTrialAuthority()) is True
    assert trial_status_waives_no_gate(None) is False


@given(
    flag=st.sampled_from(
        [
            "transmits",
            "clears_halt",
            "grants_broker_permission",
            "issues_capability",
            "issues_live_authorization",
        ]
    )
)
def test_trial_status_bypass_flag_denies(flag: str) -> None:
    """(§6.2) Any bypass-relevant flag (model_construct) means the trial status would waive a gate."""
    permissive = AllFalseTrialAuthority.model_construct(**{flag: True})
    assert trial_status_waives_no_gate(permissive) is False


# --- §6.3 promotion_progressive_single_use (RLP-EV-007 · +Security) ----------


def test_promotion_single_use_positive_and_reuse_denied() -> None:
    """(§6.3) A fresh eligible single-use, within-delta, non-retired decision passes; a consumed one is rejected."""
    policy = clean_promotion_policy()
    assert (
        promotion_progressive_single_use(
            clean_decision(), policy, PROMOTION_PREDECESSOR_FLOOR
        )
        is True
    )
    assert (
        promotion_progressive_single_use(
            clean_decision(single_use_consumed=True),
            policy,
            PROMOTION_PREDECESSOR_FLOOR,
        )
        is False
    )
    assert (
        promotion_progressive_single_use(None, policy, PROMOTION_PREDECESSOR_FLOOR)
        is False
    )
    # a None policy (no approved delta ceiling) also fails closed.
    assert (
        promotion_progressive_single_use(
            clean_decision(), None, PROMOTION_PREDECESSOR_FLOOR
        )
        is False
    )


def test_promotion_within_max_delta_null_gated_fail_closed() -> None:
    """(§6.3 point 4 / §18 line 466) A null requested delta or a null approved ceiling fails closed."""
    # no approved ceiling (policy max_delta null — the Phase-1 default) ⇒ deny (no approved delta).
    assert (
        promotion_progressive_single_use(
            clean_decision(), clean_policy(), PROMOTION_PREDECESSOR_FLOOR
        )
        is False
    )
    # a null requested delta on the decision ⇒ deny even with an approved ceiling.
    assert (
        promotion_progressive_single_use(
            clean_decision(requested_delta=None),
            clean_promotion_policy(),
            PROMOTION_PREDECESSOR_FLOOR,
        )
        is False
    )


def test_promotion_generation_fence_retires_stale_decision() -> None:
    """(§6.3 point 5 / §5.10 / §18 line 466) A stale (non-advancing) generation is retired ⇒ deny."""
    policy = clean_promotion_policy()
    # decision at promotion_generation=1 does NOT advance a predecessor floor of 1 (equal) or 2
    # (newer) ⇒ retired by a newer Promotion Generation ⇒ deny, even though it is unconsumed.
    stale = clean_decision(single_use_consumed=False, promotion_generation=1)
    assert (
        promotion_progressive_single_use(stale, policy, 1) is False
    )  # equal, not an advance
    assert (
        promotion_progressive_single_use(stale, policy, 2) is False
    )  # retired by a newer gen
    # a fresh decision that strictly advances the floor passes.
    fresh = clean_decision(single_use_consumed=False, promotion_generation=3)
    assert promotion_progressive_single_use(fresh, policy, 2) is True


def test_promotion_generation_fence_none_fails_closed() -> None:
    """(§6.3 point 5 / §5.10) A None generation floor or a None decision generation fails closed."""
    policy = clean_promotion_policy()
    # a None predecessor floor ⇒ deny (fail-closed).
    assert promotion_progressive_single_use(clean_decision(), policy, None) is False
    # a None decision promotion_generation (via model_construct — issuance requires it concrete)
    # reaches the generation-fence and fails closed there.
    none_gen = ProductionScopePromotionDecision.model_construct(
        decision_id="dec-none",
        result=PromotionResult.ELIGIBLE_TO_REQUEST_NEW_SCOPE,
        single_use_consumed=False,
        requested_delta="delta-1",
        promotion_generation=None,
        coverage_claims=(clean_coverage_claim(),),
    )
    assert (
        promotion_progressive_single_use(none_gen, policy, PROMOTION_PREDECESSOR_FLOOR)
        is False
    )


def test_coexistence_seal_blocks_eligible_decision_without_coverage() -> None:
    """(§2.3 coexistence 3-of-3) An eligible promotion decision with no coverage is unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_decision(coverage_claims=())


def test_coexistence_seal_allows_non_eligible_decision_without_coverage() -> None:
    """(§2.3) A DENY decision with no coverage IS constructable (the seal is eligible-only)."""
    decision = clean_decision(result=PromotionResult.DENY, coverage_claims=())
    assert decision.result is PromotionResult.DENY


def test_model_construct_bypass_recaught_by_promotion_predicate() -> None:
    """(§2.3 defence in depth) A model_construct eligible decision with no coverage is re-caught."""
    malformed = ProductionScopePromotionDecision.model_construct(
        decision_id="d",
        result=PromotionResult.ELIGIBLE_TO_REQUEST_NEW_SCOPE,
        single_use_consumed=False,
        requested_delta="delta-1",
        promotion_generation=1,
        coverage_claims=(),
    )
    # no_union_coverage over an empty claim set ⇒ deny ⇒ the predicate re-catches the bypass.
    assert (
        promotion_progressive_single_use(
            malformed, clean_promotion_policy(), PROMOTION_PREDECESSOR_FLOOR
        )
        is False
    )


# --- §6.5 expiry_denies_future_use_only + economic_effect_persists (RLP-EV-009)


@given(expired=TRIBOOL)
def test_expiry_denies_future_use_only(expired: bool | None) -> None:
    """(§6.5 negative polarity) is_expired not-False ⇒ deny future use (capacity unchanged)."""
    assert expiry_denies_future_use_only(expired) is (expired is not False)


def test_economic_effect_persists() -> None:
    """(§6.5 / RLP-INV-012) An all-false authority cannot release capacity — the effect persists."""
    assert economic_effect_persists(AllFalseTrialAuthority()) is True
    assert economic_effect_persists(None) is False
    permissive = AllFalseTrialAuthority.model_construct(creates_capacity=True)
    assert economic_effect_persists(permissive) is False


# --- §6.6 recovery_revives_nothing (RLP-EV-010 · +Security) ------------------


@given(prior=st.sampled_from(list(TrialRunState)))
def test_recovery_event_revives_nothing(prior: TrialRunState) -> None:
    """(§6.6 / RLP-INV-013) A recovery event revives nothing, whatever the prior state."""
    assert recovery_revives_nothing(True, prior) is False


def test_recovery_absent_only_running_is_live() -> None:
    """(§6.6) Only an explicit non-recovery (False) + RUNNING is live; terminals / None deny."""
    assert recovery_revives_nothing(False, TrialRunState.RUNNING) is True
    assert recovery_revives_nothing(False, TrialRunState.TERMINATED) is False
    assert recovery_revives_nothing(False, None) is False


def test_recovery_none_flag_revives_nothing() -> None:
    """(§6.6 / §4.3 negative polarity — #25 MAJOR-2 seal) A None recovery flag is NOT a non-recovery.

    An unknown recovery flag (``None``) must revive nothing: it is not a proven non-recovery, so a
    prior ``RUNNING`` run is treated as dead (no fail-open to "not a recovery ⇒ still live").
    """
    assert recovery_revives_nothing(None, TrialRunState.RUNNING) is False
    assert recovery_revives_nothing(None, TrialRunState.TERMINATED) is False
    assert recovery_revives_nothing(None, None) is False


# --- §6.7 monitoring_not_preventive + demotion_not_rearm (RLP-EV-011) --------


def test_monitoring_is_detective_not_authorizing() -> None:
    """(§6.7 / RLP-INV-015) A CONFORMING monitor result's authority is all-false (non-authorizing)."""
    assert monitoring_not_preventive(AllFalseTrialAuthority()) is True
    assert monitoring_not_preventive(None) is False
    permissive = AllFalseTrialAuthority.model_construct(re_arms=True)
    assert monitoring_not_preventive(permissive) is False


@given(reused=TRIBOOL)
def test_demotion_not_rearm(reused: bool | None) -> None:
    """(§6.7 / §19 line 484) Only an explicit non-reuse demotion passes (historical promotion ≠ reusable)."""
    assert demotion_not_rearm(reused) is (reused is False)


# --- §6b abort order model (RLP-EV-004 · not-Phase-1) -----------------------


@given(
    abort=st.integers(min_value=0, max_value=20),
    action=st.integers(min_value=0, max_value=20),
)
def test_abort_precedes_action_and_potentially_live_complement(
    abort: int, action: int
) -> None:
    """(§6b) abort dominates iff abort < action; the action is potentially-live otherwise."""
    dominated = abort_precedes_action(abort, action)
    assert dominated is (abort < action)
    assert action_potentially_live(abort, action) is (not dominated)


def test_unknown_abort_order_is_potentially_live() -> None:
    """(§6b / §15 line 408) An unknown (None) generation is potentially-live, never a clean abort."""
    assert abort_precedes_action(None, 5) is False
    assert abort_precedes_action(5, None) is False
    assert action_potentially_live(None, 5) is True
    assert action_potentially_live(5, None) is True
    # an equal / ambiguous order is not a clean abort ⇒ potentially-live.
    assert abort_precedes_action(5, 5) is False
    assert action_potentially_live(5, 5) is True
