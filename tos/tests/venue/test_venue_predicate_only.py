"""predicate-only §6 — conflict / account / currentness / exit / protective / common-mode / authority
(design #19 §6; VTG-EV-002/005/007/008/009/010/011 substrate).

Each is predicate-only: it closes NO VTG-EV (minimum EV-L2, +Security ×4 / +Broker ×4). Causal
isolation: each polarity assertion fixes a valid baseline and flips exactly one input.

Regime tag: predicate / model substrate only; VTG-EV-002/005/007/008/009/010/011
NOT_IMPLEMENTED; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.venue import (
    ActionClass,
    OrderAdmissibilityResult,
    PolicyResolution,
    SourceContinuity,
    SourceObservation,
    TradabilityState,
    VenueGateAuthorityEffect,
    account_constraint_conservative,
    common_mode_reduces_scope,
    egress_currentness_active,
    exit_not_assumed_admissible,
    gate_authority_separated,
    protective_label_no_bypass,
    stale_decision_rejected_at_egress,
    tradability_conflict_unknown,
    unknown_continuity_invalidates,
)

from ._venue_strategies import clean_account_facts, clean_continuity

# ---------------------------------------------------------------------------
# §6.1 tradability_conflict_unknown (VTG-EV-002, +Broker)
# ---------------------------------------------------------------------------


def test_conflicting_observations_without_resolution_are_unknown() -> None:
    """(§10 line 275) Conflicting observations with no policy resolution => UNKNOWN."""
    observations = frozenset(
        {
            SourceObservation(source_id="venue", state="OPEN"),
            SourceObservation(source_id="broker", state="HALTED"),
        }
    )
    assert (
        tradability_conflict_unknown(observations, None)
        is OrderAdmissibilityResult.UNKNOWN
    )


def test_conflict_majority_is_not_automatically_authoritative() -> None:
    """(§10 line 275) Even a 2-vs-1 'majority' does not auto-resolve — UNKNOWN without policy."""
    observations = frozenset(
        {
            SourceObservation(source_id="v1", state="OPEN"),
            SourceObservation(source_id="v2", state="OPEN"),
            SourceObservation(source_id="b1", state="HALTED"),
        }
    )
    assert (
        tradability_conflict_unknown(observations, None)
        is OrderAdmissibilityResult.UNKNOWN
    )


def test_policy_resolution_resolves_conflict_positive_side() -> None:
    """(§10 line 275 canary b) A policy-defined resolution decides the conflict."""
    observations = frozenset(
        {
            SourceObservation(source_id="venue", state="OPEN"),
            SourceObservation(source_id="broker", state="HALTED"),
        }
    )
    resolution = PolicyResolution(
        resolution_id="r1", resolved_result=OrderAdmissibilityResult.INADMISSIBLE
    )
    assert (
        tradability_conflict_unknown(observations, resolution)
        is OrderAdmissibilityResult.INADMISSIBLE
    )


def test_empty_observations_are_unknown() -> None:
    """(∅) No observation proves tradability => UNKNOWN."""
    assert (
        tradability_conflict_unknown(frozenset(), None)
        is OrderAdmissibilityResult.UNKNOWN
    )


def test_single_observation_alone_is_still_unknown() -> None:
    """(§10 line 275) A single OPEN observation is an INPUT, not permission => UNKNOWN."""
    observations = frozenset({SourceObservation(source_id="venue", state="OPEN")})
    assert (
        tradability_conflict_unknown(observations, None)
        is OrderAdmissibilityResult.UNKNOWN
    )


# ---------------------------------------------------------------------------
# §6.2 account_constraint_conservative (VTG-EV-005, +Broker)
# ---------------------------------------------------------------------------


def test_fresh_corroborated_facts_are_conservative_positive_side() -> None:
    """(§13 canary b) Fresh, corroborated, non-inferred facts establish headroom conservatively."""
    assert account_constraint_conservative(clean_account_facts(), None) is True


def test_stale_balance_inference_is_rejected() -> None:
    """(§13 line 319) Headroom inferred from a stale balance is not conservative."""
    facts = clean_account_facts().model_copy(
        update={"inferred_from_stale_balance": True}
    )
    assert account_constraint_conservative(facts, None) is False


def test_prior_order_or_absence_of_error_inference_is_rejected() -> None:
    """(§13 line 319) Inference from a prior order / absence-of-error is not conservative."""
    for field in ("inferred_from_prior_order", "inferred_from_absence_of_error"):
        facts = clean_account_facts().model_copy(update={field: True})
        assert account_constraint_conservative(facts, None) is False


def test_non_fresh_or_uncorroborated_facts_fail_closed() -> None:
    """(§13) Non-fresh or uncorroborated facts fail closed."""
    for field in ("fresh", "corroborated"):
        for value in (False, None):
            facts = clean_account_facts().model_copy(update={field: value})
            assert account_constraint_conservative(facts, None) is False


def test_none_facts_fail_closed() -> None:
    """(∅) None facts prove nothing."""
    assert account_constraint_conservative(None, None) is False


# ---------------------------------------------------------------------------
# §6.3 egress_currentness_active + stale_decision_rejected_at_egress (VTG-EV-007, +Security)
# ---------------------------------------------------------------------------


def test_actively_established_current_generation_admits() -> None:
    """(§17 canary b) Actively-established currentness for exactly the current gen admits."""
    assert egress_currentness_active(True, 5, 5) is True
    assert stale_decision_rejected_at_egress(True, 5, 5) is False


def test_cache_heartbeat_absence_never_establishes_currentness() -> None:
    """(§17 line 394) cache / heartbeat / absence (None/False) never establishes currentness."""
    for established in (None, False):
        assert egress_currentness_active(established, 5, 5) is False
        assert stale_decision_rejected_at_egress(established, 5, 5) is True


def test_older_generation_is_stale() -> None:
    """(§17) An older referenced generation is rejected at egress."""
    assert egress_currentness_active(True, 2, 5) is False
    assert stale_decision_rejected_at_egress(True, 2, 5) is True


def test_newer_generation_is_unrecognized_non_collapse() -> None:
    """(§4.3 non-collapse) A newer / substituted generation is an unrecognized future gen => reject."""
    assert egress_currentness_active(True, 9, 5) is False
    assert stale_decision_rejected_at_egress(True, 9, 5) is True


def test_none_generation_fails_closed() -> None:
    """(∅) An unverifiable (None) generation => reject."""
    assert egress_currentness_active(True, None, 5) is False
    assert egress_currentness_active(True, 5, None) is False


# ---------------------------------------------------------------------------
# §6.4 exit_not_assumed_admissible (VTG-EV-008, +Broker)
# ---------------------------------------------------------------------------


def test_exit_with_positive_tradable_is_admissible_positive_side() -> None:
    """(§11 canary b) An exit-class action with positively-TRADABLE tradability passes."""
    for action in (ActionClass.CLOSE, ActionClass.REDUCE_ONLY, ActionClass.CANCEL):
        assert exit_not_assumed_admissible(action, TradabilityState.TRADABLE) is True


def test_exit_without_tradable_is_not_assumed() -> None:
    """(VTG-INV-003 line 157) An exit with non-TRADABLE tradability is never assumed admissible."""
    for state in (
        TradabilityState.NOT_TRADABLE,
        TradabilityState.RESTRICTED,
        TradabilityState.UNKNOWN,
    ):
        assert exit_not_assumed_admissible(ActionClass.CLOSE, state) is False


def test_non_exit_action_is_not_cleared_by_this_predicate() -> None:
    """(§6.4 scope) A non-exit action is not cleared by the exit predicate (returns False)."""
    assert (
        exit_not_assumed_admissible(ActionClass.NEW_LONG, TradabilityState.TRADABLE)
        is False
    )


# ---------------------------------------------------------------------------
# §6.5 protective_label_no_bypass (VTG-EV-009, +Broker)
# ---------------------------------------------------------------------------


def test_all_three_conditions_allow_protective_positive_side() -> None:
    """(§19 canary b) Positive label + exact admissibility + separate authority + capacity => proceed."""
    assert (
        protective_label_no_bypass(
            True, OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY, True, True
        )
        is True
    )
    assert (
        protective_label_no_bypass(
            True, OrderAdmissibilityResult.ADMISSIBLE, True, True
        )
        is True
    )


def test_protective_label_does_not_bypass_inadmissible() -> None:
    """(VTG-INV-007 line 173) A protective label never bypasses an INADMISSIBLE exact admissibility."""
    assert (
        protective_label_no_bypass(
            True, OrderAdmissibilityResult.INADMISSIBLE, True, True
        )
        is False
    )
    assert (
        protective_label_no_bypass(True, OrderAdmissibilityResult.UNKNOWN, True, True)
        is False
    )


def test_missing_separate_authority_or_capacity_blocks() -> None:
    """(§19 line 426) Without separate authority or intermediate-effect capacity => blocked."""
    for auth, cap in ((None, True), (False, True), (True, None), (True, False)):
        assert (
            protective_label_no_bypass(
                True, OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY, auth, cap
            )
            is False
        )


def test_non_protective_label_is_blocked() -> None:
    """(§19) A non-protective (None/False) label cannot take the protective path."""
    for label in (None, False):
        assert (
            protective_label_no_bypass(
                label, OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY, True, True
            )
            is False
        )


# ---------------------------------------------------------------------------
# §6.6 common_mode_reduces_scope + unknown_continuity_invalidates (VTG-EV-010, +Security)
# ---------------------------------------------------------------------------


def test_shared_dependency_reduces_scope() -> None:
    """(§15 line 353) A shared dependency is common-mode => scope must reduce."""
    assert common_mode_reduces_scope(frozenset({"shared-feed"}), True) is True


def test_genuine_independence_does_not_reduce_positive_side() -> None:
    """(§15 canary b) No shared dependency + positive corroboration => no reduction."""
    assert common_mode_reduces_scope(frozenset(), True) is False


def test_absent_corroboration_reduces_scope() -> None:
    """(§15) No shared dependency but absent corroboration (None/False) still reduces (fail-closed)."""
    for corroboration in (None, False):
        assert common_mode_reduces_scope(frozenset(), corroboration) is True


def test_verifiable_continuity_holds_positive_side() -> None:
    """(§9 canary b) A verifiable continuity with no gap does not invalidate."""
    assert unknown_continuity_invalidates(clean_continuity()) is False


def test_gap_or_unverifiable_continuity_invalidates() -> None:
    """(§9 line 263) A gap or unverifiable continuity invalidates future decisions."""
    for field in (
        "restarted",
        "reconnected",
        "sequence_reset",
        "rolled_back",
        "failed_over",
    ):
        gapped = clean_continuity().model_copy(update={field: True})
        assert unknown_continuity_invalidates(gapped) is True
    assert (
        unknown_continuity_invalidates(
            clean_continuity().model_copy(update={"verifiable": None})
        )
        is True
    )
    assert unknown_continuity_invalidates(SourceContinuity(continuity_id=None)) is True


def test_none_continuity_invalidates() -> None:
    """(∅) A None continuity invalidates (fail-closed)."""
    assert unknown_continuity_invalidates(None) is True


# ---------------------------------------------------------------------------
# §6.7 gate_authority_separated (VTG-EV-011, +Security)
# ---------------------------------------------------------------------------


def test_all_false_effect_no_credential_is_separated_positive_side() -> None:
    """(VTG-INV-011 canary b) An all-false effect with no live credential separates authority."""
    assert gate_authority_separated(VenueGateAuthorityEffect(), False) is True


def test_holding_live_credential_is_rejected() -> None:
    """(§7 line 223) A gate holding (or maybe-holding) a live credential is rejected."""
    for holds in (True, None):
        assert gate_authority_separated(VenueGateAuthorityEffect(), holds) is False


def test_none_effect_fails_closed() -> None:
    """(∅) A None authority effect proves nothing."""
    assert gate_authority_separated(None, False) is False
