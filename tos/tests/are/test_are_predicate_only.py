"""Predicate-only temporal / authority rules (design #13 §6.3-§6.7; ARE-EV-008/010/011/012).

Both-ways canaries + the forbidden-verb canaries: "revive" (§6.6 non-revival), "release"
(§6.6 economic continuity), "create" (§6.7 all-false authority). Closes no ARE-EV.
"""

from __future__ import annotations

from tos.are import (
    AggregateRiskAuthorityEffect,
    CancellationRiskInputs,
    Ordering,
    OrderingEvent,
    cancellation_worsens_aggregate,
    compare_order,
    concurrent_not_reservation,
    continued_existence_worsens_aggregate,
    currentness_invalidation,
    decision_generation_monotone,
    economic_effect_persists,
    grants_no_authority,
    non_cyclic_binding,
    non_revival_holds,
    protective_creates_nothing,
)

from ._are_strategies import cancellation_inputs, issue_decision

# ---------------------------------------------------------------------------
# non_cyclic_binding (§6.3 / §16) — forward-only
# ---------------------------------------------------------------------------


def test_decision_is_non_cyclic_forward_only() -> None:
    """(canary +) The forward-only decision carries no reservation-binding field => True."""
    assert non_cyclic_binding(issue_decision()) is True


def test_decision_carries_no_reservation_coordinate() -> None:
    """(§16 line 413) The decision model structurally lacks bound_reservation_* fields."""
    fields = set(type(issue_decision()).model_fields)
    for forbidden in (
        "bound_reservation_revision",
        "bound_reservation_digest",
        "bound_generation",
    ):
        assert forbidden not in fields


# ---------------------------------------------------------------------------
# concurrent_not_reservation (§6.3 / §18 line 448)
# ---------------------------------------------------------------------------


def test_rcl_serialization_is_the_only_reservation() -> None:
    """(canary +) An exclusive commitment exists only when RCL serialization committed."""
    assert (
        concurrent_not_reservation(
            headroom_observed=True, rcl_serialization_committed=True
        )
        is True
    )


def test_observed_headroom_is_not_a_reservation() -> None:
    """(canary - §18 line 448) Observing headroom without RCL serialization is not a reservation."""
    assert (
        concurrent_not_reservation(
            headroom_observed=True, rcl_serialization_committed=False
        )
        is False
    )
    assert (
        concurrent_not_reservation(
            headroom_observed=True, rcl_serialization_committed=None
        )
        is False
    )


# ---------------------------------------------------------------------------
# decision_generation_monotone (§3.2 ordering REUSE)
# ---------------------------------------------------------------------------


def test_generation_ordering_is_monotone() -> None:
    """(canary +) An earlier quorum index precedes a later one (append-only order)."""
    a = OrderingEvent(event_id="a", quorum_commit_index=1)
    b = OrderingEvent(event_id="b", quorum_commit_index=2)
    assert decision_generation_monotone(a, b) is True
    assert compare_order(a, b) is Ordering.BEFORE


def test_ambiguous_ordering_fails_closed() -> None:
    """(fail-closed) An unorderable (ambiguous) pair => not monotone."""
    a = OrderingEvent(event_id="a")
    b = OrderingEvent(event_id="b")
    assert decision_generation_monotone(a, b) is False


# ---------------------------------------------------------------------------
# currentness_invalidation (§6.4 / §17)
# ---------------------------------------------------------------------------


def test_material_change_invalidates() -> None:
    """(canary - §17) A material change invalidates an unconsumed decision."""
    assert (
        currentness_invalidation(
            material_change_present=True, cache_ttl_or_heartbeat_only=False
        )
        is True
    )


def test_cache_ttl_is_not_currentness_proof() -> None:
    """(§17 line 440) Currentness resting only on a cache / TTL / heartbeat => invalidate."""
    assert (
        currentness_invalidation(
            material_change_present=False, cache_ttl_or_heartbeat_only=True
        )
        is True
    )


def test_unknown_material_change_fails_closed() -> None:
    """(fail-closed) An unknown (None) material-change status => invalidate."""
    assert (
        currentness_invalidation(
            material_change_present=None, cache_ttl_or_heartbeat_only=False
        )
        is True
    )


def test_no_change_and_positive_currentness_stays_current() -> None:
    """(canary +) Positively no material change and not cache-only => stays current (not invalidated)."""
    assert (
        currentness_invalidation(
            material_change_present=False, cache_ttl_or_heartbeat_only=False
        )
        is False
    )


# ---------------------------------------------------------------------------
# non_revival_holds (§6.6 / §21) — "revive" verb
# ---------------------------------------------------------------------------


def test_non_revival_is_unconditional() -> None:
    """(canary 'revive' §21 line 500) Nothing revives a prior decision — unconditionally True."""
    assert non_revival_holds() is True


# ---------------------------------------------------------------------------
# economic_effect_persists (§6.6 / §20) — "release" verb
# ---------------------------------------------------------------------------


def test_missing_ack_does_not_release_capacity() -> None:
    """(canary 'release' ARE-INV-011) A missing ACK / expiry (no terminal proof) => effect persists."""
    assert economic_effect_persists(terminal_release_proven=None) is True
    assert economic_effect_persists(terminal_release_proven=False) is True


def test_proven_terminal_release_ends_persistence() -> None:
    """(§20 line 482) A positively proven defined RCL transition releases (persistence ends)."""
    assert economic_effect_persists(terminal_release_proven=True) is False


# ---------------------------------------------------------------------------
# protective_creates_nothing (§6.5 / ARE-INV-012)
# ---------------------------------------------------------------------------


def test_protective_label_creates_nothing() -> None:
    """(canary +) A label claiming to create nothing (all False) => True."""
    assert (
        protective_creates_nothing(
            label_creates_capacity=False,
            label_creates_feasibility=False,
            label_creates_allocation=False,
            label_creates_transmission=False,
        )
        is True
    )


def test_protective_label_creating_capacity_rejected() -> None:
    """(canary - §19 line 470) A label claiming to create capacity => False."""
    assert (
        protective_creates_nothing(
            label_creates_capacity=True,
            label_creates_feasibility=False,
            label_creates_allocation=False,
            label_creates_transmission=False,
        )
        is False
    )


def test_protective_unknown_creation_fails_closed() -> None:
    """(fail-closed) An unknown (None) creation claim => False."""
    assert (
        protective_creates_nothing(
            label_creates_capacity=None,
            label_creates_feasibility=False,
            label_creates_allocation=False,
            label_creates_transmission=False,
        )
        is False
    )


# ---------------------------------------------------------------------------
# grants_no_authority + all-false (§6.7 / ARE-INV-009) — "create" verb
# ---------------------------------------------------------------------------


def test_default_authority_grants_nothing() -> None:
    """(canary +) A default all-false authority effect grants nothing => True."""
    assert grants_no_authority(AggregateRiskAuthorityEffect()) is True


def test_true_authority_flag_is_unconstructable() -> None:
    """(canary 'create' ARE-INV-009) Any True authority flag makes the effect unconstructable."""
    for field in (
        "creates_capacity",
        "permits_transmission",
        "issues_live_authorization",
        "grants_broker_permission",
        "may_rearm",
    ):
        try:
            AggregateRiskAuthorityEffect(**{field: True})
        except Exception:
            continue
        raise AssertionError(
            f"AggregateRiskAuthorityEffect({field}=True) must be unconstructable"
        )


# ---------------------------------------------------------------------------
# cancellation-arbiter produced flags (§3.4)
# ---------------------------------------------------------------------------


def test_cancellation_flags_polarity() -> None:
    """Continued 20 > baseline 10 => worsens True; post 5 < baseline 10 => worsens False."""
    inputs = cancellation_inputs()
    assert continued_existence_worsens_aggregate(inputs) is True
    assert cancellation_worsens_aggregate(inputs) is False


def test_cancellation_flags_none_fails_closed() -> None:
    """(fail-closed) A None magnitude makes the produced flag None (protective treats as restrictive)."""
    inputs = CancellationRiskInputs(baseline_no_action_risk=None)
    assert continued_existence_worsens_aggregate(inputs) is None
    assert cancellation_worsens_aggregate(inputs) is None
