"""predicate-only §6 — start-closed / egress / owner / broker / HALT / restore / authority
(design #17 §6; SBR-EV-001/002/003/005/008/010/011 substrate).

Each is predicate-only: it closes NO SBR-EV (minimum EV-L2, +Security ×5 / +Broker ×1). Causal
isolation: each polarity assertion fixes a valid baseline and flips exactly one input.

Regime tag: predicate / model substrate only; SBR-EV-001/002/003/005/008/010/011
NOT_IMPLEMENTED; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.sbr import (
    OwnerStatus,
    RecoveryAuthorityEffect,
    RecoveryBarrierState,
    SelectionBasis,
    competing_owner_fenced,
    halt_dominates_recovery,
    non_atomic_broker_conservative,
    recovery_authority_separated,
    restore_worst_credible_union,
    stale_generation_rejected_at_egress,
    start_closed,
)

from ._sbr_strategies import clean_broker_reads

# ---------------------------------------------------------------------------
# §6.1 start_closed (SBR-EV-001)
# ---------------------------------------------------------------------------


def test_start_closed_barrier_with_incomplete_chain_is_denied() -> None:
    """(§8/§9; SBR-AC-001) A CLOSED barrier + incomplete live-arming chain => new-risk denied."""
    for chain in (None, False):
        assert start_closed(RecoveryBarrierState.CLOSED_NON_LIVE, chain) is True


def test_start_closed_complete_chain_lifts_denial_positive_side() -> None:
    """(§9 canary b) A positively-complete live-arming chain lifts the denial."""
    assert start_closed(RecoveryBarrierState.CLOSED_NON_LIVE, True) is False


def test_start_closed_none_barrier_is_denied() -> None:
    """(§9 line 257) A None / unrecognized barrier is never a permission => denied."""
    assert start_closed(None, True) is True


# ---------------------------------------------------------------------------
# §6.2 stale_generation_rejected_at_egress (SBR-EV-002, +Security)
# ---------------------------------------------------------------------------


def test_egress_rejects_older_generation() -> None:
    """(§9 line 268) An older referenced generation is rejected."""
    assert stale_generation_rejected_at_egress(2, 5, True) is True


def test_egress_rejects_newer_unrecognized_generation() -> None:
    """(§4.3 non-collapse) A newer / substituted generation is an unrecognized future gen => reject."""
    assert stale_generation_rejected_at_egress(9, 5, True) is True


def test_egress_rejects_unverifiable_currentness() -> None:
    """(§9 line 270; SBR-INV-004) cache / heartbeat / absence never establishes currentness."""
    for established in (None, False):
        assert stale_generation_rejected_at_egress(5, 5, established) is True


def test_egress_rejects_none_generation() -> None:
    """(∅) An unverifiable (None) generation => reject."""
    assert stale_generation_rejected_at_egress(None, 5, True) is True
    assert stale_generation_rejected_at_egress(5, None, True) is True


def test_egress_admits_exactly_current_and_established_positive_side() -> None:
    """(§9 canary b) An exactly-current, actively-established request is admitted."""
    assert stale_generation_rejected_at_egress(5, 5, True) is False


# ---------------------------------------------------------------------------
# §6.3 competing_owner_fenced (SBR-EV-003, +Security)
# ---------------------------------------------------------------------------


def test_only_current_owner_with_matching_epoch_is_fenced() -> None:
    """(§11 canary b) A single CURRENT owner with a matching epoch is admissible."""
    assert competing_owner_fenced(7, 7, OwnerStatus.CURRENT) is True


def test_non_current_owner_status_is_rejected() -> None:
    """(§11 line 303-304) minority / stale / paused / restored / removed / partitioned => reject."""
    for status in (
        OwnerStatus.MINORITY,
        OwnerStatus.STALE,
        OwnerStatus.PAUSED,
        OwnerStatus.RESTORED,
        OwnerStatus.REMOVED,
        OwnerStatus.PARTITIONED,
    ):
        assert competing_owner_fenced(7, 7, status) is False


def test_mismatched_or_none_epoch_is_rejected() -> None:
    """(§11 line 305) A mismatched / None epoch (heartbeat-only) is insufficient fencing."""
    assert competing_owner_fenced(6, 7, OwnerStatus.CURRENT) is False
    assert competing_owner_fenced(None, 7, OwnerStatus.CURRENT) is False
    assert competing_owner_fenced(7, None, OwnerStatus.CURRENT) is False


# ---------------------------------------------------------------------------
# §6.4 non_atomic_broker_conservative (SBR-EV-005, +Broker)
# ---------------------------------------------------------------------------


def test_bounded_convergence_is_conservative_positive_side() -> None:
    """(§6.4 canary b) Bounded, stable convergence with events reflected passes."""
    assert non_atomic_broker_conservative(clean_broker_reads(), frozenset()) is True


def test_single_read_without_convergence_is_not_complete() -> None:
    """(SBR-INV-007 line 170) A read sequence without bounded convergence fails closed."""
    reads = clean_broker_reads().model_copy(update={"bounded_convergence_proven": None})
    assert non_atomic_broker_conservative(reads, frozenset()) is False


def test_unstable_field_proof_is_not_complete() -> None:
    """(§12 line 333) An unstable field-specific proof fails closed."""
    reads = clean_broker_reads().model_copy(
        update={"field_specific_proof_stable": False}
    )
    assert non_atomic_broker_conservative(reads, frozenset()) is False


def test_unreflected_intervening_event_is_not_complete() -> None:
    """(§12 line 333) Equality between reads is not proof — unreflected intervening events fail."""
    reads = clean_broker_reads().model_copy(
        update={"intervening_events_reflected": None}
    )
    assert non_atomic_broker_conservative(reads, frozenset({"late-fill"})) is False
    # …but with no intervening events, the reflect flag is not required.
    assert non_atomic_broker_conservative(reads, frozenset()) is True


def test_none_reads_fail_closed() -> None:
    """(∅) A None read sequence proves nothing."""
    assert non_atomic_broker_conservative(None, frozenset()) is False


# ---------------------------------------------------------------------------
# §6.5 halt_dominates_recovery (SBR-EV-008, +Security)
# ---------------------------------------------------------------------------


def test_ambiguous_halt_is_treated_as_applied() -> None:
    """(§15 line 408) Ambiguous HALT (None) is treated as applied => dominates."""
    assert halt_dominates_recovery(None, False, False) is True


def test_applied_halt_dominates() -> None:
    """(SBR-INV-009) An applied HALT dominates recovery."""
    assert halt_dominates_recovery(True, False, False) is True


def test_safety_owned_protection_present_dominates() -> None:
    """(§15 line 406) Recovery cleanup may not cancel present safety-owned protection => dominates."""
    assert halt_dominates_recovery(False, False, True) is True
    assert halt_dominates_recovery(False, False, None) is True


def test_dominating_incident_dominates() -> None:
    """(§15) A dominating halt / incident present => dominates."""
    assert halt_dominates_recovery(False, True, False) is True


def test_no_restriction_does_not_dominate_positive_side() -> None:
    """(§15 canary b) HALT positively not applied, no incident, no safety-owned => not dominated."""
    assert halt_dominates_recovery(False, False, False) is False


# ---------------------------------------------------------------------------
# §6.6 restore_worst_credible_union (SBR-EV-010, +Security)
# ---------------------------------------------------------------------------


def test_all_branches_union_is_proper_positive_side() -> None:
    """(§20 line 496 canary b) No single-basis selection + a present union => proper restore."""
    assert restore_worst_credible_union(frozenset({"b1", "b2"}), None, object()) is True


def test_single_basis_selection_is_rejected() -> None:
    """(§20 line 497) Selecting a branch by recency / backup / admin / wall-clock alone => reject."""
    for basis in (
        SelectionBasis.RECENCY,
        SelectionBasis.BACKUP_SUCCESS,
        SelectionBasis.ADMIN_CHOICE,
        SelectionBasis.WALL_CLOCK,
    ):
        assert (
            restore_worst_credible_union(frozenset({"b1", "b2"}), basis, object())
            is False
        )


def test_empty_branches_or_missing_union_fail_closed() -> None:
    """(∅) An empty branch set or an absent rcl union fails closed."""
    assert restore_worst_credible_union(frozenset(), None, object()) is False
    assert restore_worst_credible_union(frozenset({"b1"}), None, None) is False


# ---------------------------------------------------------------------------
# §6.7 recovery_authority_separated (SBR-EV-011, +Security)
# ---------------------------------------------------------------------------


def test_all_false_effect_no_forced_ready_is_separated_positive_side() -> None:
    """(SBR-INV-003 canary b) An all-false effect with no forced-ready separates authority."""
    assert recovery_authority_separated(RecoveryAuthorityEffect(), False) is True


def test_forced_ready_request_is_rejected() -> None:
    """(§19 line 483 / §21 line 517-526) A forced-ready request is rejected."""
    for forced in (True, None):
        assert recovery_authority_separated(RecoveryAuthorityEffect(), forced) is False


def test_none_effect_fails_closed() -> None:
    """(∅) A None authority effect proves nothing."""
    assert recovery_authority_separated(None, False) is False
