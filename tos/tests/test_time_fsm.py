"""Health FSM conservatism, non-revival, authority absence, session (time design §6/§12).

EV-L1 predicate substrate only; TIME-EV-008/-009 remain NOT_IMPLEMENTED pending
EV-L2/L3 fault injection.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.time import (
    HealthState,
    SessionContext,
    TimeAuthorityEffect,
    UncertaintyInterval,
    health_transition_allowed,
    recovery_generation_revives_nothing,
    session_open_positively,
    snapshot_grants_no_authority,
    state_permits_new_normal_risk,
    transition_to_trusted_requires_new_generation,
)

from ._time_strategies import issue_time_snapshot

_ALLOWED = frozenset(
    {
        (HealthState.UNINITIALIZED, HealthState.SYNCHRONIZING),
        (HealthState.SYNCHRONIZING, HealthState.TRUSTED),
        (HealthState.TRUSTED, HealthState.DEGRADED_HOLDOVER),
        (HealthState.TRUSTED, HealthState.UNTRUSTED),
        (HealthState.DEGRADED_HOLDOVER, HealthState.UNTRUSTED),
        (HealthState.DEGRADED_HOLDOVER, HealthState.SYNCHRONIZING),
        (HealthState.UNTRUSTED, HealthState.SYNCHRONIZING),
    }
)


@given(frm=st.sampled_from(list(HealthState)), to=st.sampled_from(list(HealthState)))
def test_only_the_seven_transitions_allowed(frm: HealthState, to: HealthState) -> None:
    """Exactly the 7 ADR §6 transitions are allowed; every other pair is denied."""
    assert health_transition_allowed(frm, to) is ((frm, to) in _ALLOWED)


def test_transition_count_is_seven() -> None:
    """The FSM has 5 states and 7 directed transitions (§6 134-145)."""
    assert len(HealthState) == 5
    allowed = [
        (a, b)
        for a in HealthState
        for b in HealthState
        if health_transition_allowed(a, b)
    ]
    assert len(allowed) == 7


@given(frm=st.integers(0, 100), to=st.integers(0, 100))
def test_return_to_trusted_requires_strictly_new_generation(frm: int, to: int) -> None:
    """Returning to TRUSTED requires a strictly greater generation (§6.4/§16 401)."""
    assert transition_to_trusted_requires_new_generation(frm, to) is (to > frm)


def test_trusted_generation_fail_closed_on_unknown() -> None:
    """An unknown generation cannot justify a return to TRUSTED (fail-closed)."""
    assert transition_to_trusted_requires_new_generation(None, 5) is False
    assert transition_to_trusted_requires_new_generation(5, None) is False


@given(old=st.integers(0, 100), new=st.integers(0, 100))
def test_recovery_generation_revives_nothing(old: int, new: int) -> None:
    """A new generation never revives an earlier invalidation (§6.4/§16 406-409)."""
    assert (
        recovery_generation_revives_nothing(
            invalidated_under_generation=old, new_generation=new
        )
        is True
    )


@given(state=st.sampled_from(list(HealthState)))
def test_only_trusted_permits_new_normal_risk(state: HealthState) -> None:
    """Only TRUSTED permits new normal risk (§6.1-6.3)."""
    assert state_permits_new_normal_risk(state) is (state is HealthState.TRUSTED)


def test_snapshot_grants_no_authority() -> None:
    """An issued snapshot's authority effect is all-false (SAFE-044)."""
    assert snapshot_grants_no_authority(issue_time_snapshot()) is True


def test_authority_true_is_unconstructable() -> None:
    """Any True authority flag makes the block unconstructable (SAFE-044)."""
    for field in TimeAuthorityEffect.model_fields:
        try:
            TimeAuthorityEffect(**{field: True})
        except ValueError:
            continue
        raise AssertionError(f"authority flag {field}=True was accepted")


# ---- session-boundary uncertainty (§12 line 319) ---------------------------


def _open_ctx(**overrides: object) -> SessionContext:
    base: dict[str, object] = {
        "trading_calendar_version": "cal-1",
        "phase": "REGULAR",
        "is_open": True,
        "tz_version_conflict": False,
        "boundary_value": 5,
    }
    base.update(overrides)
    return SessionContext(**base)  # type: ignore[arg-type]


def test_positively_open_with_boundary_outside_window() -> None:
    """Positively open, clean epistemics, boundary outside window => open (§12)."""
    ctx = _open_ctx(boundary_value=100)
    assert session_open_positively(ctx, UncertaintyInterval(lo=10, hi=20)) is True


def test_boundary_inside_uncertainty_denies() -> None:
    """A boundary inside the uncertainty interval straddles the session => deny (§12)."""
    ctx = _open_ctx(boundary_value=15)
    assert session_open_positively(ctx, UncertaintyInterval(lo=10, hi=20)) is False


def test_unbounded_uncertainty_is_ambiguous_local_time() -> None:
    """An unbounded (None-endpoint) uncertainty interval => ambiguous => deny (§12)."""
    ctx = _open_ctx(boundary_value=100)
    assert session_open_positively(ctx, UncertaintyInterval(lo=None, hi=20)) is False


def test_not_open_or_unknown_phase_or_missing_calendar_denies() -> None:
    """Not-open / unknown phase / missing calendar / tz conflict all deny (§12)."""
    good = UncertaintyInterval(lo=10, hi=20)
    assert not session_open_positively(_open_ctx(is_open=False), good)
    assert not session_open_positively(_open_ctx(phase=None), good)
    assert not session_open_positively(_open_ctx(trading_calendar_version=None), good)
    assert not session_open_positively(_open_ctx(tz_version_conflict=True), good)
