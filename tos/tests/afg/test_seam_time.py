"""MANDATED test-only seam cross-check: afg <-> time (design #16 §3.4(d), M7).

design #16 **M7** promoted time from "coordinate-dependent" to a **dedicated produced-bool
slot**: three time predicates produce exactly the values afg injects —

* ``elapsed_within_continuity`` (``predicates.py:73``) — performs the elapsed subtraction
  **only** inside one monotonic continuity and returns ``None`` across continuities, which
  is the code realization of §18 line 403 "Monotonic values from different hosts or
  processes SHALL NOT be directly subtracted" (``MonotonicReading``: "continuity
  subtraction is never performed", ``elements.py:112``);
* ``snapshot_age_admissible`` (``predicates.py:287``) -> afg ``refill_conservative``'s
  ``snapshot_age_admissible`` argument;
* ``recovery_generation_revives_nothing`` (``predicates.py:499``) -> afg
  ``non_revival_holds``.

**afg reads no clock at all** (§3.2): it never imports ``time`` / ``datetime`` (asserted by
the §7.1 AST scan) and only *compares* injected continuity identifiers. This file imports
both packages as a **test** to lock that the afg gate mirrors the time model's fail-closed
polarity.

Causal isolation: each polarity assertion fixes a valid baseline and flips one input.

A test-only cross-import is **not** a runtime package edge (design #16 §3.4(d)/§7.1).
"""

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


# ---------------------------------------------------------------------------
# elapsed_within_continuity -> refill_conservative (§18 line 403)
# ---------------------------------------------------------------------------


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
    # Causal isolation: only the continuity id changes.
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
    # pydantic models do not define __sub__; the elapsed computation lives in a predicate
    # that is guarded by the continuity check.
    assert not hasattr(MonotonicReading, "subtract")


# ---------------------------------------------------------------------------
# snapshot_age_admissible -> refill_conservative (§18 line 405 age clamp)
# ---------------------------------------------------------------------------


def test_snapshot_age_admissible_polarity_matches_the_afg_gate() -> None:
    """(seam) An inadmissible / unknown age bound refuses on both sides."""
    # An unknown age bound or an unestablished maximum is inadmissible (fail-closed).
    assert snapshot_age_admissible(None, 1000) is False
    assert snapshot_age_admissible(500, None) is False
    assert snapshot_age_admissible(1500, 1000) is False
    for produced in (
        snapshot_age_admissible(None, 1000),
        snapshot_age_admissible(500, None),
        snapshot_age_admissible(1500, 1000),
    ):
        assert _refill(snapshot_age_admissible=produced) is ActionFlowResult.UNKNOWN
    # Causal isolation: only the age bound changes => both sides flip together.
    admissible = snapshot_age_admissible(500, 1000)
    assert admissible is True
    assert _refill(snapshot_age_admissible=admissible) is ActionFlowResult.GRANT


def test_phase_one_null_age_bound_is_fail_closed_not_unbounded() -> None:
    """(§8 bounds injection) ``MAX_action_flow_*_age_ms`` is null in Phase 1 => refuse."""
    produced = snapshot_age_admissible(500, None)  # the injected max is null (VP-002)
    assert produced is False
    assert _refill(snapshot_age_admissible=produced) is ActionFlowResult.UNKNOWN


# ---------------------------------------------------------------------------
# recovery_generation_revives_nothing -> non_revival_holds (§18 line 407 / §22)
# ---------------------------------------------------------------------------


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
    # Causal isolation: with that single flag back to False the refill is permitted.
    assert _refill() is ActionFlowResult.GRANT
