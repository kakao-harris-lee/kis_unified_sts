"""core §5.4 — refill integrity, counter integrity, and the generation fence.

AFG-EV-008 substrate (ADR-002-022 §18 line 403-407; **AFG-INV-004 line 169 "replenishes"
+ AFG-INV-007 line 181**) plus the separate AFG-INV-013 line 205 generation fence (design
#16 M6: "Stale Generations Are Fenced" is a *different axis* from the refill rule, and the
v1.0 draft mis-anchored §18 to INV-013).

Both-ways canaries (design #16 §4.4): a wall-clock jump, a clock recovery, a restart, a
broker timestamp, a cross-host monotonic comparison, a negative age, and an unestablished
continuity all refuse; approved trustworthy time + committed RCL history + one continuity
+ a finite non-negative age permits.

Closes **no** AFG-EV: predicate / coordinate substrate only (design #16 §1).
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from tos.afg import (
    ActionFlowResult,
    Ordering,
    OrderingEvent,
    action_flow_generation_monotone,
    compare_order,
    generation_fenced,
    refill_conservative,
    restart_counter_assumption_admissible,
)


def _refill(**overrides: object) -> ActionFlowResult:
    """A fully-proven refill call (the clean fixture — genuinely permissible)."""
    base: dict[str, object] = {
        "time_valid": True,
        "monotonic_continuity_id": "cont-1",
        "age": Decimal("10"),
        "reference_continuity_id": "cont-1",
        "rcl_committed_history_present": True,
        "wall_clock_or_recovery_or_restart_basis": False,
        "broker_timestamp_or_new_source_basis": False,
        "continuity_established": True,
        "snapshot_age_admissible": True,
    }
    base.update(overrides)
    time_valid = base.pop("time_valid")
    continuity = base.pop("monotonic_continuity_id")
    age = base.pop("age")
    return refill_conservative(time_valid, continuity, age, **base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# refill_conservative (§18 line 403-407)
# ---------------------------------------------------------------------------


def test_approved_time_plus_rcl_history_permits_refill() -> None:
    """(canary + §18:404) Trustworthy time + committed RCL history + finite age => GRANT."""
    assert _refill() is ActionFlowResult.GRANT


def test_wall_clock_recovery_or_restart_cannot_manufacture_headroom() -> None:
    """(canary 'manufacture-headroom' §18:405) A wall-clock / recovery / restart basis => DENY."""
    for value in (True, None):
        assert (
            _refill(wall_clock_or_recovery_or_restart_basis=value)
            is ActionFlowResult.DENY
        )


def test_broker_timestamp_or_newly_healthy_source_cannot_refill() -> None:
    """(canary - §18:405) A broker timestamp / newly-healthy source basis => DENY."""
    for value in (True, None):
        assert (
            _refill(broker_timestamp_or_new_source_basis=value) is ActionFlowResult.DENY
        )


def test_invalid_or_unknown_time_is_restrictive() -> None:
    """(fail-closed §18:404) Time not positively valid => UNKNOWN, never a refill."""
    for value in (False, None):
        assert _refill(time_valid=value) is ActionFlowResult.UNKNOWN


def test_missing_rcl_history_is_restrictive() -> None:
    """(canary - §18:404) Only committed RCL history may replenish => UNKNOWN without it."""
    for value in (False, None):
        assert _refill(rcl_committed_history_present=value) is ActionFlowResult.UNKNOWN


def test_cross_host_continuity_is_never_subtracted() -> None:
    """(canary - §18:403) A different monotonic continuity => UNKNOWN (no subtraction at all)."""
    assert _refill(monotonic_continuity_id="cont-2") is ActionFlowResult.UNKNOWN


def test_unestablished_or_unknown_continuity_is_restrictive() -> None:
    """(∅ §4.7) An unestablished / ``None`` continuity => UNKNOWN."""
    for value in (False, None):
        assert _refill(continuity_established=value) is ActionFlowResult.UNKNOWN
    assert _refill(monotonic_continuity_id=None) is ActionFlowResult.UNKNOWN
    assert _refill(reference_continuity_id=None) is ActionFlowResult.UNKNOWN


def test_negative_age_clamps_toward_restriction() -> None:
    """(canary - §18:405) A negative age (a future issue time) => UNKNOWN, never a refill."""
    assert _refill(age=Decimal("-1")) is ActionFlowResult.UNKNOWN


def test_non_finite_or_missing_age_is_restrictive() -> None:
    """(fail-closed §3.1) A NaN / infinite / ``None`` age => UNKNOWN."""
    assert _refill(age=None) is ActionFlowResult.UNKNOWN
    assert _refill(age=Decimal("NaN")) is ActionFlowResult.UNKNOWN
    assert _refill(age=Decimal("Infinity")) is ActionFlowResult.UNKNOWN


def test_inadmissible_snapshot_age_is_restrictive() -> None:
    """(time seam) The injected ``snapshot_age_admissible`` verdict gates the refill."""
    for value in (False, None):
        assert _refill(snapshot_age_admissible=value) is ActionFlowResult.UNKNOWN


@given(age=st.integers(min_value=-50, max_value=50))
def test_refill_is_granted_exactly_on_non_negative_finite_age(age: int) -> None:
    """(property) With every other premise proven, only a non-negative age refills."""
    verdict = _refill(age=Decimal(age))
    expected = ActionFlowResult.GRANT if age >= 0 else ActionFlowResult.UNKNOWN
    assert verdict is expected


def test_all_none_refill_inputs_are_denied_or_unknown_never_granted() -> None:
    """(∅ / None canary) With every input ``None`` the verdict is never ``GRANT``."""
    verdict = refill_conservative(
        None,
        None,
        None,
        reference_continuity_id=None,
        rcl_committed_history_present=None,
        wall_clock_or_recovery_or_restart_basis=None,
        broker_timestamp_or_new_source_basis=None,
        continuity_established=None,
        snapshot_age_admissible=None,
    )
    assert verdict is not ActionFlowResult.GRANT


# ---------------------------------------------------------------------------
# generation_fenced (AFG-INV-013 line 205 — a separate axis from §18 refill)
# ---------------------------------------------------------------------------


def test_current_generation_passes_the_fence() -> None:
    """(canary +) An artifact on the current generation => True (not fenced)."""
    assert generation_fenced(7, 7) is True


def test_stale_generation_is_fenced() -> None:
    """(canary - AFG-INV-013:205) A strictly older generation cannot allocate / transmit."""
    assert generation_fenced(6, 7) is False


def test_unrecognized_future_generation_is_fenced() -> None:
    """(fail-closed) A strictly newer, unrecognized generation also fails closed."""
    assert generation_fenced(8, 7) is False


def test_none_generation_is_fenced() -> None:
    """(∅ / None canary) A ``None`` on either side is UNKNOWN => fenced."""
    assert generation_fenced(None, 7) is False
    assert generation_fenced(7, None) is False
    assert generation_fenced(None, None) is False


@given(
    artifact=st.integers(min_value=0, max_value=10),
    current=st.integers(min_value=0, max_value=10),
)
def test_fence_passes_only_on_equality(artifact: int, current: int) -> None:
    """(property) The fence admits exactly the equal-generation case."""
    assert generation_fenced(artifact, current) is (artifact == current)


# ---------------------------------------------------------------------------
# action_flow_generation_monotone (§3.2 tos.ordering REUSE — no wall clock)
# ---------------------------------------------------------------------------


def test_generation_ordering_is_monotone() -> None:
    """(canary +) An earlier quorum index provably precedes a later one (append-only)."""
    a = OrderingEvent(event_id="a", quorum_commit_index=1)
    b = OrderingEvent(event_id="b", quorum_commit_index=2)
    assert action_flow_generation_monotone(a, b) is True
    assert compare_order(a, b) is Ordering.BEFORE


def test_ambiguous_ordering_fails_closed() -> None:
    """(fail-closed §17:391 / §18:405) An unorderable pair => not monotone (no clock orders)."""
    a = OrderingEvent(event_id="a")
    b = OrderingEvent(event_id="b")
    assert action_flow_generation_monotone(a, b) is False


# ---------------------------------------------------------------------------
# restart_counter_assumption_admissible (§22 line 463 — "assume-zero-counter")
# ---------------------------------------------------------------------------


def test_restart_making_no_zero_state_assumption_passes() -> None:
    """(canary +) All three assumptions positively refused => True."""
    assert (
        restart_counter_assumption_admissible(
            assumed_zero_counter=False,
            assumed_empty_queue=False,
            assumed_unused_permit=False,
        )
        is True
    )


def test_assume_zero_counter_on_restart_is_rejected() -> None:
    """(canary 'assume-zero-counter' §22:463) Any zero-state assumption (or unknown) => False."""
    for field in (
        "assumed_zero_counter",
        "assumed_empty_queue",
        "assumed_unused_permit",
    ):
        for value in (True, None):
            kwargs = {
                "assumed_zero_counter": False,
                "assumed_empty_queue": False,
                "assumed_unused_permit": False,
            }
            kwargs[field] = value
            assert restart_counter_assumption_admissible(**kwargs) is False
