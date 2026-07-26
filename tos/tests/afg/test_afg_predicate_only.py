"""predicate-only §6 — retry, cancel-storm, classification, reserve, currentness, partition.

AFG-EV-003/004/005/006/009/010/011/012 substrate (design #16 §6). Every one of these rows
is minimum ``EV-L2`` in EVIDENCE-REGISTER-002 (AFG-EV-004 carries an ``EV-L1/3+Broker``
slice, so its L1 substrate is a core target cross-referenced from §7) — this file authors
the **L1-decidable** rules only and closes **no** AFG-EV.

Every guard carries a both-ways canary plus the Gap-5 ∅ / ``None`` canary: with every
argument ``None`` the predicate must be restrictive, and a fully-proven positive tuple must
pass (a vacuous block is an availability defect just as a vacuous grant is a safety one).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError
from tos.afg import (
    ADMISSIBILITY_ADMISSIBLE,
    ATTEMPT_STATE_SEND_FAILED_PROVEN,
    ATTEMPT_STATE_SENT_UNCONFIRMED,
    BROKER_ORDER_STATE_CANCELLED,
    BROKER_ORDER_STATE_UNKNOWN,
    ActionClassKind,
    ActionFlowGovernorEffect,
    ActionFlowResult,
    MaterialChangeKind,
    action_class_conservative,
    cancel_ack_not_final_quantity_proof,
    currentness_invalidation,
    economic_effect_persists,
    governor_grants_no_authority,
    is_material,
    no_blind_retry,
    non_revival_holds,
    oscillation_bounded,
    partition_lease_exclusive,
    priority_is_not_reserve,
    reserve_exclusive,
)

from ._afg_strategies import (
    clean_cause,
    full_envelope,
    issue_decision,
    issue_permit,
    reserve_claim,
    trigger,
    within_observation,
)

# ---------------------------------------------------------------------------
# §6.1 — no_blind_retry (AFG-EV-003; AFG-INV-008)
# ---------------------------------------------------------------------------


def _retry(**overrides: object) -> bool:
    base: dict[str, object] = {
        "attempt_state": ATTEMPT_STATE_SEND_FAILED_PROVEN,
        "broker_order_state": "NONE_OBSERVED",
        "idempotency_proven": True,
        "budget_remaining": 2,
        "complete_evidence_capability_coverage_authority": True,
        "blind_failover_attempted": False,
    }
    base.update(overrides)
    attempt = base.pop("attempt_state")
    broker = base.pop("broker_order_state")
    idem = base.pop("idempotency_proven")
    budget = base.pop("budget_remaining")
    return no_blind_retry(attempt, broker, idem, budget, **base)  # type: ignore[arg-type]


def test_governed_retry_on_positive_send_failure_proof_passes() -> None:
    """(canary + §14:350) SEND_FAILED_PROVEN + idempotency + budget + authority => True."""
    assert _retry() is True


def test_sent_unconfirmed_attempt_stays_potentially_live() -> None:
    """(canary - AFG-INV-008:185) A SENT_UNCONFIRMED attempt is potentially live => no retry."""
    assert _retry(attempt_state=ATTEMPT_STATE_SENT_UNCONFIRMED) is False


def test_missing_attempt_state_is_no_retry() -> None:
    """(fail-closed) Any non-proven attempt state (incl. ``None``) => False."""
    for state in (None, "SEND_STARTED", "ACK_OBSERVED", "PREPARED"):
        assert _retry(attempt_state=state) is False


def test_unknown_broker_order_state_is_never_safe_to_retry() -> None:
    """(canary - orthostate:118) An UNKNOWN broker order is capacity-consuming => no retry."""
    assert _retry(broker_order_state=BROKER_ORDER_STATE_UNKNOWN) is False
    assert _retry(broker_order_state=None) is False


def test_unproven_idempotency_blocks_retry() -> None:
    """(canary 'blind-retry' §14:352) Unproven broker idempotency => False."""
    for value in (False, None):
        assert _retry(idempotency_proven=value) is False


def test_exhausted_or_unknown_budget_blocks_retry() -> None:
    """(protective seam) ``budget_remaining`` ``None`` / ``<= 0`` => no retry."""
    for value in (None, 0, -1):
        assert _retry(budget_remaining=value) is False


def test_incomplete_evidence_blocks_retry() -> None:
    """(canary - §14:350) Incomplete evidence / capability / coverage / authority => False."""
    for value in (False, None):
        assert _retry(complete_evidence_capability_coverage_authority=value) is False


def test_blind_failover_is_forbidden() -> None:
    """(canary 'blind-failover' §14:352) Any (or unknown) blind failover => False."""
    for value in (True, None):
        assert _retry(blind_failover_attempted=value) is False


def test_retry_count_elapsed_and_backoff_cannot_convert_unknown_to_rejection() -> None:
    """(structural §14:352) Accumulated retries / elapsed / backoff never change the verdict."""
    # Negative side: a SENT_UNCONFIRMED attempt stays refused no matter how much time,
    # how many retries, or how many identical responses accumulate.
    for retries, elapsed, backoff, repeated in (
        (0, 0, 0, False),
        (99, 999_999, 60_000, True),
    ):
        assert (
            no_blind_retry(
                ATTEMPT_STATE_SENT_UNCONFIRMED,
                "NONE_OBSERVED",
                True,
                5,
                complete_evidence_capability_coverage_authority=True,
                blind_failover_attempted=False,
                retry_count=retries,
                elapsed_ms=elapsed,
                backoff_ms=backoff,
                repeated_identical_response=repeated,
            )
            is False
        )
    # Positive side: the same accumulation cannot *remove* a legitimate governed retry.
    assert _retry(retry_count=99, elapsed_ms=999_999, backoff_ms=60_000) is True


def test_all_none_retry_inputs_is_no_retry() -> None:
    """(Gap-5 ∅ / None canary) Every argument ``None`` => ``False`` (unproven => no retry)."""
    assert no_blind_retry(None, None, None, None) is False


# ---------------------------------------------------------------------------
# §6.2 — cancel ACK is not a Final Quantity Proof + bounded oscillation
# ---------------------------------------------------------------------------


def _cancel(**overrides: object) -> bool:
    base: dict[str, object] = {
        "broker_order_state": BROKER_ORDER_STATE_CANCELLED,
        "final_quantity_proof_present": False,
        "original_and_replacement_covered": True,
        "capacity_release_claimed": False,
        "replacement_reuse_claimed": False,
        "retry_claimed": False,
    }
    base.update(overrides)
    state = base.pop("broker_order_state")
    return cancel_ack_not_final_quantity_proof(state, **base)  # type: ignore[arg-type]


def test_cancel_ack_without_any_claim_holds_the_invariant() -> None:
    """(canary +) A cancel ACK with both legs covered and nothing claimed => True."""
    assert _cancel() is True


def test_capacity_release_on_a_cancel_ack_alone_is_rejected() -> None:
    """(canary - §15:358) Releasing capacity on a cancel ACK without an FQP => False."""
    assert _cancel(capacity_release_claimed=True) is False


def test_replacement_reuse_or_retry_on_a_cancel_ack_is_rejected() -> None:
    """(canary - §15:358) Replacement reuse / retry without an FQP => False."""
    assert _cancel(replacement_reuse_claimed=True) is False
    assert _cancel(retry_claimed=True) is False


def test_a_separate_final_quantity_proof_permits_the_claim() -> None:
    """(canary + §15:358) A positively present FQP justifies the release (the positive side)."""
    assert (
        _cancel(capacity_release_claimed=True, final_quantity_proof_present=True)
        is True
    )


def test_uncovered_replacement_leg_fails_closed() -> None:
    """(canary - §15:358) Original + replacement not covered for overlap / late fill => False."""
    for value in (False, None):
        assert _cancel(original_and_replacement_covered=value) is False


def test_unknown_claim_status_fails_closed() -> None:
    """(fail-closed) An unknown (``None``) claim status demands an FQP."""
    assert _cancel(capacity_release_claimed=None) is False
    assert (
        _cancel(capacity_release_claimed=None, final_quantity_proof_present=True)
        is True
    )


def test_none_broker_order_state_fails_closed() -> None:
    """(∅ / None canary) A ``None`` broker order state => False."""
    assert _cancel(broker_order_state=None) is False


def test_bounded_oscillation_positive_side() -> None:
    """(canary + §15:360) Complete lineage + bounded amplification + reserve present => True."""
    assert (
        oscillation_bounded(
            clean_cause(),
            full_envelope(),
            within_observation(),
            new_cause_created_for_budget_reset=False,
            reserve_present=True,
        )
        is True
    )


def test_new_cause_for_budget_reset_is_rejected() -> None:
    """(canary 'invent-cause' §15:360) Minting a new cause to reset the budget => False."""
    for value in (True, None):
        assert (
            oscillation_bounded(
                clean_cause(),
                full_envelope(),
                within_observation(),
                new_cause_created_for_budget_reset=value,
                reserve_present=True,
            )
            is False
        )


def test_absent_reserve_makes_the_exposure_trapped() -> None:
    """(canary - §15:362) No protective reserve => trapped + contained => False."""
    for value in (False, None):
        assert (
            oscillation_bounded(
                clean_cause(),
                full_envelope(),
                within_observation(),
                new_cause_created_for_budget_reset=False,
                reserve_present=value,
            )
            is False
        )


def test_oscillation_shares_the_amplification_envelope() -> None:
    """(§6.2) Oscillation is bounded by the SAME §11 envelope — an over-bound count denies."""
    assert (
        oscillation_bounded(
            clean_cause(),
            full_envelope(),
            within_observation(mutations=99),
            new_cause_created_for_budget_reset=False,
            reserve_present=True,
        )
        is False
    )


def test_oscillation_none_inputs_fail_closed() -> None:
    """(Gap-5 ∅ / None canary) ``None`` cause / envelope / observation => False."""
    assert (
        oscillation_bounded(
            None,
            None,
            None,
            new_cause_created_for_budget_reset=None,
            reserve_present=None,
        )
        is False
    )


# ---------------------------------------------------------------------------
# §6.3 — action_class_conservative (AFG-EV-005)
# ---------------------------------------------------------------------------


def test_most_conservative_applicable_class_governs() -> None:
    """(canary + §9:268) The most conservative applicable class governs a conflict."""
    verdict = action_class_conservative(
        ActionClassKind.RECONCILIATION_QUERY,
        frozenset(
            {ActionClassKind.NORMAL_NEW_RISK, ActionClassKind.RECONCILIATION_QUERY}
        ),
    )
    assert verdict is ActionClassKind.NORMAL_NEW_RISK


def test_producer_label_cannot_create_a_more_permissive_class() -> None:
    """(canary - §7:218) A benign producer label never loosens the governing class."""
    verdict = action_class_conservative(
        ActionClassKind.ADMINISTRATIVE_NON_LIVE,
        frozenset({ActionClassKind.NORMAL_NEW_RISK}),
    )
    assert verdict is ActionClassKind.NORMAL_NEW_RISK


def test_a_more_conservative_claim_tightens_the_outcome() -> None:
    """(canary +) A claim may only ever tighten — never loosen — the governing class."""
    verdict = action_class_conservative(
        ActionClassKind.NORMAL_NEW_RISK,
        frozenset({ActionClassKind.ADMINISTRATIVE_NON_LIVE}),
    )
    assert verdict is ActionClassKind.NORMAL_NEW_RISK


def test_empty_applicable_class_set_is_unknown() -> None:
    """(∅ §4.7) An empty applicable set is not a classification => UNKNOWN."""
    assert (
        action_class_conservative(ActionClassKind.NORMAL_NEW_RISK, frozenset())
        is ActionFlowResult.UNKNOWN
    )


def test_cancel_and_query_classes_are_counted() -> None:
    """(§9:254) Cancel / query / session classes are governed, not exempt from classification."""
    for kind in (
        ActionClassKind.CANCEL_OR_REPLACE,
        ActionClassKind.RECONCILIATION_QUERY,
        ActionClassKind.SESSION_OR_CONNECTION_CONTROL,
    ):
        assert action_class_conservative(None, frozenset({kind})) is kind


def test_unknown_vector_dimension_makes_classification_unknown() -> None:
    """(§2.2-4) A vector carrying an unenumerated (economic) dimension => UNKNOWN."""
    from tos.rcl import CapacityComponent, CapacityVector

    alien = CapacityVector(
        components=(
            CapacityComponent(dimension_id="GROSS_NOTIONAL", magnitude=Decimal("1")),
        )
    )
    assert (
        action_class_conservative(
            ActionClassKind.NORMAL_NEW_RISK,
            frozenset({ActionClassKind.NORMAL_NEW_RISK}),
            alien,
        )
        is ActionFlowResult.UNKNOWN
    )


# ---------------------------------------------------------------------------
# §6.4 — protective reserve exclusivity (AFG-EV-006; AFG-INV-006)
# ---------------------------------------------------------------------------


def _reserve(**overrides: object) -> bool:
    base: dict[str, object] = {
        "claim": reserve_claim(),
        "is_reserved": True,
        "normal_traffic_borrowed": False,
        "normal_traffic_consumed": False,
        "relabelled_as_normal": False,
        "repay_reserve_later_claimed": False,
    }
    base.update(overrides)
    claim = base.pop("claim")
    is_reserved = base.pop("is_reserved")
    return reserve_exclusive(claim, is_reserved, **base)  # type: ignore[arg-type]


def test_exclusive_reserve_positive_side() -> None:
    """(canary +) A reserved guarantee with no encroachment => True."""
    assert _reserve() is True


def test_unproven_reserve_is_not_reserved() -> None:
    """(Gap-5 ∅ / None canary; truthy seal) ``is_reserved`` ``None`` / ``False`` => False."""
    for value in (False, None):
        assert _reserve(is_reserved=value) is False


def test_normal_traffic_may_not_borrow_consume_or_relabel_the_reserve() -> None:
    """(canary 'borrow / consume / relabel' AFG-INV-006:177) Any encroachment => False."""
    for field in (
        "normal_traffic_borrowed",
        "normal_traffic_consumed",
        "relabelled_as_normal",
    ):
        for value in (True, None):
            assert _reserve(**{field: value}) is False


def test_repay_the_reserve_later_is_rejected() -> None:
    """(canary 'repay-reserve-later' §16:370) There is no repay-later path => False."""
    for value in (True, None):
        assert _reserve(repay_reserve_later_claimed=value) is False


def test_reserve_on_a_non_afg_dimension_fails_closed() -> None:
    """(Gap-1) A reserve claimed on an economic dimension id => False."""
    assert _reserve(claim=reserve_claim(dimension_id="GROSS_NOTIONAL")) is False
    assert _reserve(claim=reserve_claim(dimension_id=None)) is False


def test_missing_reserve_magnitude_fails_closed() -> None:
    """(∅ §4.7 row 6) A ``None`` reserved magnitude => False, never assume-reserved."""
    assert _reserve(claim=reserve_claim(reserved_magnitude=None)) is False


def test_non_finite_reserve_magnitude_is_unconstructable() -> None:
    """(§3.1 CanonicalDecimal) A NaN / infinite magnitude cannot even be constructed."""
    for bad in (Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(ValidationError):
            reserve_claim(reserved_magnitude=bad)


def test_none_claim_fails_closed() -> None:
    """(∅ / None canary) A ``None`` claim => False."""
    assert _reserve(claim=None) is False


def test_priority_alone_is_not_a_reservation() -> None:
    """(canary 'priority≠reserve' §16:372) A priority queue without exclusive capacity => False."""
    assert (
        priority_is_not_reserve(
            "PRIORITIZED_ONLY",
            exclusive_capacity_present=True,
            high_priority_queue=True,
        )
        is False
    )
    for token in ("BEST_EFFORT", "UNAVAILABLE", None):
        assert priority_is_not_reserve(token, exclusive_capacity_present=True) is False


def test_reserved_label_without_exclusive_capacity_is_rejected() -> None:
    """(canary - §16:372) A reserved-looking label with no exclusive capacity => False."""
    for value in (False, None):
        assert (
            priority_is_not_reserve(
                "PHYSICALLY_RESERVED", exclusive_capacity_present=value
            )
            is False
        )


def test_genuine_exclusive_reservation_passes() -> None:
    """(canary +) A reserved guarantee backed by exclusive capacity => True."""
    for token in ("PHYSICALLY_RESERVED", "LOGICALLY_RESERVED"):
        assert priority_is_not_reserve(token, exclusive_capacity_present=True) is True


def test_high_priority_queue_never_upgrades_a_guarantee() -> None:
    """(structural §16:372) The queue-priority input cannot change the verdict either way."""
    for queue_flag in (True, False, None):
        assert (
            priority_is_not_reserve(
                "PHYSICALLY_RESERVED",
                exclusive_capacity_present=True,
                high_priority_queue=queue_flag,
            )
            is True
        )
        assert (
            priority_is_not_reserve(
                "PRIORITIZED_ONLY",
                exclusive_capacity_present=True,
                high_priority_queue=queue_flag,
            )
            is False
        )


# ---------------------------------------------------------------------------
# §6.5 — materiality + currentness invalidation (AFG-EV-009)
# ---------------------------------------------------------------------------


def test_unknown_materiality_is_material() -> None:
    """(Gap-7 §5.10:149 verbatim) Unknown / undeclared materiality => material."""
    assert is_material(MaterialChangeKind.POLICY, None) is True
    assert is_material(None, None) is True
    assert is_material("SOME_UNDECLARED_CHANGE", None) is True


def test_enumerated_change_with_known_materiality_is_material() -> None:
    """(§19:413) Every enumerated change kind is material when materiality is known."""
    for kind in MaterialChangeKind:
        assert is_material(kind, True) is True


def test_absent_change_is_material_even_when_materiality_is_known() -> None:
    """(§8:248) An omitted change cannot be declared immaterial by omission."""
    assert is_material(None, True) is True


def test_non_enumerated_change_with_known_materiality_is_immaterial() -> None:
    """(both-ways) A positively assessed, non-enumerated change is not material."""
    assert is_material("COSMETIC_LOG_LABEL", True) is False


def _currentness(**overrides: object) -> bool:
    base: dict[str, object] = {
        "triggers": (),
        "decision": issue_decision(),
        "permit": issue_permit(),
        "currentness_positively_established": True,
        "cache_ttl_heartbeat_health_or_prior_success_only": False,
        "egress_recalculated_favorably_or_widened": False,
        "egress_invented_cause_or_changed_action_class": False,
    }
    base.update(overrides)
    triggers = base.pop("triggers")
    decision = base.pop("decision")
    permit = base.pop("permit")
    return currentness_invalidation(triggers, decision, permit, **base)  # type: ignore[arg-type]


def test_positively_established_currentness_stays_current() -> None:
    """(canary +) No material trigger + positive currentness + no cache-only => stays current."""
    assert _currentness() is False


def test_material_change_invalidates() -> None:
    """(canary - §19:413) A material change invalidates the affected decision / permit."""
    assert _currentness(triggers=(trigger(),)) is True


def test_unknown_materiality_trigger_invalidates() -> None:
    """(Gap-7) A trigger with unknown materiality invalidates (unknown is material)."""
    assert _currentness(triggers=(trigger(materiality_known=None),)) is True


def test_absence_of_invalidation_is_not_a_currentness_proof() -> None:
    """(canary - §17:391) Currentness must be POSITIVELY established; absence invalidates."""
    for value in (False, None):
        assert _currentness(currentness_positively_established=value) is True


def test_cache_ttl_heartbeat_or_prior_success_is_not_currentness() -> None:
    """(canary - §17:391) Currentness resting only on a cache / TTL / heartbeat invalidates."""
    for value in (True, None):
        assert (
            _currentness(cache_ttl_heartbeat_health_or_prior_success_only=value) is True
        )


def test_egress_may_not_recalculate_favorably_or_widen() -> None:
    """(canary 'recalculate-favorable' §17:397) An egress widening / recalculation invalidates."""
    for value in (True, None):
        assert _currentness(egress_recalculated_favorably_or_widened=value) is True


def test_egress_may_not_invent_a_cause_or_change_the_action_class() -> None:
    """(canary 'invent-cause / change-class' §17:397) Either attempt invalidates."""
    for value in (True, None):
        assert _currentness(egress_invented_cause_or_changed_action_class=value) is True


def test_nothing_to_keep_current_invalidates() -> None:
    """(∅ canary) A ``None`` decision AND ``None`` permit => nothing provable => invalidate."""
    assert _currentness(decision=None, permit=None) is True
    # ...but one of the two present is enough to be evaluated.
    assert _currentness(decision=None) is False
    assert _currentness(permit=None) is False


def test_empty_trigger_sequence_is_not_proof_of_currentness() -> None:
    """(∅ both-ways) An empty trigger list alone never establishes currentness."""
    assert (
        currentness_invalidation(
            (),
            issue_decision(),
            issue_permit(),
            currentness_positively_established=None,
            cache_ttl_heartbeat_health_or_prior_success_only=False,
            egress_recalculated_favorably_or_widened=False,
            egress_invented_cause_or_changed_action_class=False,
        )
        is True
    )


# ---------------------------------------------------------------------------
# §6.6 — partition / stale writer / protective lease (AFG-EV-010)
# ---------------------------------------------------------------------------


def _lease(**overrides: object) -> bool:
    base: dict[str, object] = {
        "lease_admissible": ADMISSIBILITY_ADMISSIBLE,
        "remaining_budget": 3,
        "monotonic_continuity_id": "cont-1",
        "reference_continuity_id": "cont-1",
        "new_normal_permit_during_partition": False,
        "lease_refilled_remotely_or_by_wall_clock": False,
        "exclusivity_retained": True,
        "stale_writer_hard_fenced": True,
    }
    base.update(overrides)
    admissible = base.pop("lease_admissible")
    budget = base.pop("remaining_budget")
    continuity = base.pop("monotonic_continuity_id")
    return partition_lease_exclusive(admissible, budget, continuity, **base)  # type: ignore[arg-type]


def test_admissible_exclusive_lease_may_be_consumed() -> None:
    """(canary + §20:427) ADMISSIBLE + positive budget + same continuity + fenced => True."""
    assert _lease() is True


def test_only_the_admissible_token_passes() -> None:
    """(M2 truthy seal) TRAPPED / PROHIBITED / ``None`` all deny — every token is truthy."""
    for token in ("TRAPPED", "PROHIBITED", None, "", "ADMISSIBLE_LOOKALIKE"):
        assert _lease(lease_admissible=token) is False


def test_exhausted_or_unknown_lease_budget_denies() -> None:
    """(Gap-5 ∅ / None canary) ``None`` / ``<= 0`` remaining budget => False."""
    for value in (None, 0, -5):
        assert _lease(remaining_budget=value) is False


def test_cross_continuity_lease_denies() -> None:
    """(canary - §18:403) A different / missing monotonic continuity => False."""
    assert _lease(monotonic_continuity_id="cont-2") is False
    assert _lease(monotonic_continuity_id=None) is False
    assert _lease(reference_continuity_id=None) is False


def test_new_normal_permit_during_partition_is_forbidden() -> None:
    """(canary - §20:425) Issuing a new normal permit during a partition => False."""
    for value in (True, None):
        assert _lease(new_normal_permit_during_partition=value) is False


def test_lease_cannot_be_refilled_remotely_or_by_wall_clock() -> None:
    """(canary - §20:427) A remote / wall-clock lease refill => False."""
    for value in (True, None):
        assert _lease(lease_refilled_remotely_or_by_wall_clock=value) is False


def test_loss_of_exclusivity_or_unfenced_stale_writer_denies() -> None:
    """(canary - §20:429) Lost exclusivity, or a stale writer not hard-fenced => False."""
    for field in ("exclusivity_retained", "stale_writer_hard_fenced"):
        for value in (False, None):
            assert _lease(**{field: value}) is False


# ---------------------------------------------------------------------------
# §6.7 — authority separation (AFG-EV-011; AFG-INV-011)
# ---------------------------------------------------------------------------


def test_governor_grants_no_authority_positive_side() -> None:
    """(canary +) A default governor effect grants nothing => True."""
    assert governor_grants_no_authority(ActionFlowGovernorEffect()) is True


def test_governor_holds_no_broker_credential_field_can_ever_be_true() -> None:
    """(canary 'issue-authority / hold-credential' §7:220/229) Any True flag is unconstructable."""
    for field in ActionFlowGovernorEffect.model_fields:
        try:
            ActionFlowGovernorEffect(**{field: True})
        except Exception:
            continue
        raise AssertionError(f"ActionFlowGovernorEffect({field}=True) must be rejected")


# ---------------------------------------------------------------------------
# §6.8 — non-revival + economic continuity (AFG-EV-012; AFG-INV-012/014)
# ---------------------------------------------------------------------------


def test_non_revival_is_unconditional() -> None:
    """(canary 'revive / auto-re-arm' AFG-INV-014:209) Nothing revives — unconditionally True."""
    assert non_revival_holds() is True


def test_no_recovery_input_can_revive_anything() -> None:
    """(Gap-5 ∅ / None canary) Every recovery input, in every combination, still yields True."""
    for value in (True, False, None):
        assert (
            non_revival_holds(
                restart=value,
                rollback_or_restore=value,
                failover_or_reconnect=value,
                backoff_expiry_or_queue_drain=value,
                counter_refill_or_throttle_recovery=value,
                matching_replay_or_improved_health=value,
                recovery_generation_revives_nothing=value,
            )
            is True
        )


def test_expiry_never_expires_a_possible_economic_effect() -> None:
    """(canary 'release' AFG-INV-012:201) Permit / decision / policy expiry => effect persists."""
    for field in (
        "permit_expired",
        "decision_expired",
        "policy_or_retry_window_expired",
        "queue_item_expired",
    ):
        assert (
            economic_effect_persists(final_quantity_proof_present=None, **{field: True})
            is True
        )


def test_missing_ack_or_cancel_ack_does_not_release_capacity() -> None:
    """(canary 'release' §14:350 / §15:358) A missing ACK or cancel ACK => effect persists."""
    assert (
        economic_effect_persists(final_quantity_proof_present=None, ack_missing=True)
        is True
    )
    assert (
        economic_effect_persists(
            final_quantity_proof_present=False, cancel_ack_observed=True
        )
        is True
    )


def test_positive_final_quantity_proof_ends_persistence() -> None:
    """(canary + §13:342) Only a positively present Final Quantity Proof ends persistence."""
    assert economic_effect_persists(final_quantity_proof_present=True) is False
