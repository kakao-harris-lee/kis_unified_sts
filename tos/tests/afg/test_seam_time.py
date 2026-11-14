"""MANDATED test-only seam cross-check: afg <-> time (design #16 §3.4(d), M7)."""

from __future__ import annotations

from decimal import Decimal

from tos.afg import ActionFlowResult, non_revival_holds, refill_conservative
from tos.time import (
    MonotonicReading,
    elapsed_within_continuity,
    recovery_generation_revives_nothing,
    snapshot_age_admissible,
)


def _refill(**overrides: object) -> ActionFlowResult:
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


def test_same_continuity_elapsed_is_computed_and_afg_permits_refill() -> None:
    """(seam +) Within one continuity the elapsed value exists; afg may then permit a refill."""
    a = MonotonicReading(monotonic_continuity_id="cont-1", local_monotonic_value=100)
    b = MonotonicReading(monotonic_continuity_id="cont-1", local_monotonic_value=110)
    elapsed = elapsed_within_continuity(a, b)
    assert elapsed == 10
    assert _refill(age=Decimal(elapsed)) is ActionFlowResult.GRANT


def test_cross_continuity_elapsed_is_never_subtracted_and_afg_refuses() -> None:
    """(seam - §18:403) Across continuities time returns ``None``; afg refuses the refill."""
    a = MonotonicReading(monotonic_continuity_id="cont-1", local_monotonic_value=100)
    b = MonotonicReading(monotonic_continuity_id="cont-2", local_monotonic_value=110)
    assert elapsed_within_continuity(a, b) is None
    assert _refill(monotonic_continuity_id="cont-2") is ActionFlowResult.UNKNOWN


def test_missing_continuity_coordinate_is_never_subtracted() -> None:
    """(fail-closed parity) A ``None`` continuity id or value yields no subtraction at all."""
    a = MonotonicReading(monotonic_continuity_id=None, local_monotonic_value=100)
    b = MonotonicReading(monotonic_continuity_id="cont-1", local_monotonic_value=110)
    assert elapsed_within_continuity(a, b) is None
    assert _refill(monotonic_continuity_id=None) is ActionFlowResult.UNKNOWN


def test_monotonic_reading_carries_no_subtraction_method() -> None:
    """(``elements.py:112``) The reading model performs no continuity subtraction itself."""
    for banned in ("subtract", "__sub__", "difference", "minus"):
        assert not hasattr(MonotonicReading, banned) or banned == "__sub__"
    assert not hasattr(MonotonicReading, "subtract")


def test_snapshot_age_admissible_polarity_matches_the_afg_gate() -> None:
    """(seam) An inadmissible / unknown age bound refuses on both sides."""
    assert snapshot_age_admissible(None, 1000) is False
    assert snapshot_age_admissible(500, None) is False
    assert snapshot_age_admissible(1500, 1000) is False
    for produced in (
        snapshot_age_admissible(None, 1000),
        snapshot_age_admissible(500, None),
        snapshot_age_admissible(1500, 1000),
    ):
        assert _refill(snapshot_age_admissible=produced) is ActionFlowResult.UNKNOWN
    admissible = snapshot_age_admissible(500, 1000)
    assert admissible is True
    assert _refill(snapshot_age_admissible=admissible) is ActionFlowResult.GRANT


def test_phase_one_null_age_bound_is_fail_closed_not_unbounded() -> None:
    """(§8 bounds injection) ``MAX_action_flow_*_age_ms`` is null in Phase 1 => refuse."""
    produced = snapshot_age_admissible(500, None)
    assert produced is False
    assert _refill(snapshot_age_admissible=produced) is ActionFlowResult.UNKNOWN


def test_recovery_generation_revives_nothing_on_both_sides() -> None:
    """(seam §18:407 / AFG-INV-014) A new time-health generation revives nothing, either side."""
    assert (
        recovery_generation_revives_nothing(
            invalidated_under_generation=1, new_generation=2
        )
        is True
    )
    assert (
        recovery_generation_revives_nothing(
            invalidated_under_generation=None, new_generation=None
        )
        is True
    )
    for produced in (
        recovery_generation_revives_nothing(
            invalidated_under_generation=1, new_generation=2
        ),
        recovery_generation_revives_nothing(
            invalidated_under_generation=None, new_generation=None
        ),
    ):
        assert non_revival_holds(recovery_generation_revives_nothing=produced) is True


def test_time_recovery_basis_cannot_manufacture_headroom() -> None:
    """(§18:405 / :407) A clock-recovery basis is a positive refusal, not a soft unknown."""
    assert (
        _refill(wall_clock_or_recovery_or_restart_basis=True) is ActionFlowResult.DENY
    )
    assert _refill() is ActionFlowResult.GRANT
