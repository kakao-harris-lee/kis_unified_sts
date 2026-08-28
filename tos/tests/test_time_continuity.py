"""Monotonic continuity — non-subtraction + anchor invalidation (time design §3).

EV-L1 predicate substrate only; TIME-EV-004/-005 remain NOT_IMPLEMENTED pending
EV-L2/L3 fault injection. No real clock is read; ``monotonic_continuity_id`` /
``local_monotonic_value`` are opaque injected coordinates (time design §3).
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.time import (
    MonotonicReading,
    TimeContinuityIdentity,
    anchor_valid,
    elapsed_within_continuity,
)


@given(v1=st.integers(-(10**6), 10**6), v2=st.integers(-(10**6), 10**6))
def test_same_continuity_elapsed_subtracts(v1: int, v2: int) -> None:
    """Within one continuity, elapsed is exactly ``b - a`` (§3(1))."""
    a = MonotonicReading(monotonic_continuity_id="c1", local_monotonic_value=v1)
    b = MonotonicReading(monotonic_continuity_id="c1", local_monotonic_value=v2)
    assert elapsed_within_continuity(a, b) == v2 - v1


@given(v1=st.integers(0, 10**6), v2=st.integers(0, 10**6))
def test_cross_continuity_never_subtracts(v1: int, v2: int) -> None:
    """Different continuities return None — no subtraction is performed (§3(1))."""
    a = MonotonicReading(monotonic_continuity_id="c1", local_monotonic_value=v1)
    b = MonotonicReading(monotonic_continuity_id="c2", local_monotonic_value=v2)
    assert elapsed_within_continuity(a, b) is None


def test_missing_continuity_or_value_returns_none() -> None:
    """A missing continuity id or value yields None (fail-closed, §3(1))."""
    a = MonotonicReading(monotonic_continuity_id=None, local_monotonic_value=1)
    b = MonotonicReading(monotonic_continuity_id="c1", local_monotonic_value=2)
    assert elapsed_within_continuity(a, b) is None
    c = MonotonicReading(monotonic_continuity_id="c1", local_monotonic_value=None)
    d = MonotonicReading(monotonic_continuity_id="c1", local_monotonic_value=2)
    assert elapsed_within_continuity(c, d) is None


def _identity(**overrides: object) -> TimeContinuityIdentity:
    base = {
        "host_or_runtime_id": "h1",
        "boot_id": "b1",
        "process_id": "p1",
        "monotonic_anchor_id": "a1",
        "monotonic_anchor_value": 1000,
    }
    base.update(overrides)
    return TimeContinuityIdentity(**base)  # type: ignore[arg-type]


@given(now_value=st.integers(1000, 10**6), susp=st.integers(0, 2000))
def test_valid_anchor_when_continuous_and_in_bound(now_value: int, susp: int) -> None:
    """A same-identity, non-decreasing, in-bound-suspension anchor is valid (§3(2))."""
    now = _identity(monotonic_anchor_value=now_value)
    anchor = _identity(monotonic_anchor_value=1000)
    assert anchor_valid(now, anchor, suspension_ms=susp, max_suspension_ms=2000) is True


def test_continuity_id_change_invalidates() -> None:
    """A changed monotonic_anchor_id (new continuity) invalidates the anchor (§5 124)."""
    now = _identity(monotonic_anchor_id="a2")
    anchor = _identity(monotonic_anchor_id="a1")
    assert not anchor_valid(now, anchor, suspension_ms=0, max_suspension_ms=2000)


def test_restart_invalidates() -> None:
    """A changed boot_id / process_id (restart/reboot) invalidates (§5 124)."""
    anchor = _identity()
    assert not anchor_valid(
        _identity(boot_id="b2"), anchor, suspension_ms=0, max_suspension_ms=2000
    )
    assert not anchor_valid(
        _identity(process_id="p2"), anchor, suspension_ms=0, max_suspension_ms=2000
    )


def test_non_monotone_value_is_discontinuity() -> None:
    """A now-value below the anchor value is a discontinuity => invalid (§5 124)."""
    now = _identity(monotonic_anchor_value=999)
    anchor = _identity(monotonic_anchor_value=1000)
    assert not anchor_valid(now, anchor, suspension_ms=0, max_suspension_ms=2000)


@given(susp=st.integers(2001, 10**6))
def test_suspension_over_bound_invalidates(susp: int) -> None:
    """Suspension above the injected bound invalidates (§11.2 277)."""
    now, anchor = _identity(monotonic_anchor_value=2000), _identity()
    assert not anchor_valid(now, anchor, suspension_ms=susp, max_suspension_ms=2000)


def test_unknown_suspension_or_bound_fails_closed() -> None:
    """Unknown suspension or unestablished bound is invalid (fail-closed, §3(2))."""
    now, anchor = _identity(monotonic_anchor_value=2000), _identity()
    assert not anchor_valid(now, anchor, suspension_ms=None, max_suspension_ms=2000)
    assert not anchor_valid(now, anchor, suspension_ms=0, max_suspension_ms=None)


def test_missing_identity_component_fails_closed() -> None:
    """A null identity component cannot prove continuity => invalid (§3(2))."""
    now = _identity(boot_id=None)
    anchor = _identity()
    assert not anchor_valid(now, anchor, suspension_ms=0, max_suspension_ms=2000)
