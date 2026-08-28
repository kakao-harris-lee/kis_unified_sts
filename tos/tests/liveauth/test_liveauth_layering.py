"""Limit layering + atomic activation (§6.1, §6.2; REARM-AC-006).

The four limits must be non-decreasing from per-action (tightest) to Hard Safety Envelope
(widest); any inner > outer, or any None limit, fails closed. Atomic activation requires
all four positive conditions (fully active, single-version, unit-compatible, envelope-
bounded). [REARM-EV-006 substrate]
"""

from __future__ import annotations

import pytest
from tos.liveauth import LimitLayering, atomic_activation_ok, layering_within_bounds

from ._liveauth_strategies import valid_layering


def test_valid_chain_is_within_bounds() -> None:
    """(guard fires True) A non-decreasing per-action <= ... <= hard-envelope chain holds."""
    assert layering_within_bounds(valid_layering()) is True


def test_equal_limits_are_within_bounds() -> None:
    """Equal limits at every layer are within bounds (<= is reflexive)."""
    layering = valid_layering(
        per_action_limit=2,
        live_authorization_limit=2,
        runtime_safety_profile_limit=2,
        hard_safety_envelope_limit=2,
    )
    assert layering_within_bounds(layering) is True


def test_live_auth_over_runtime_profile_fails() -> None:
    """(canary) Live Authorization exceeding the Runtime Safety Profile is an expansion."""
    layering = valid_layering(
        live_authorization_limit=5, runtime_safety_profile_limit=3
    )
    assert layering_within_bounds(layering) is False


def test_runtime_profile_over_hard_envelope_fails() -> None:
    """(canary) Runtime Safety Profile exceeding the Hard Safety Envelope fails closed."""
    layering = valid_layering(
        runtime_safety_profile_limit=9, hard_safety_envelope_limit=4
    )
    assert layering_within_bounds(layering) is False


def test_per_action_over_live_auth_fails() -> None:
    """(canary) A per-action limit exceeding Live Authorization fails closed."""
    layering = valid_layering(per_action_limit=3, live_authorization_limit=2)
    assert layering_within_bounds(layering) is False


@pytest.mark.parametrize(
    "limit_field",
    [
        "per_action_limit",
        "live_authorization_limit",
        "runtime_safety_profile_limit",
        "hard_safety_envelope_limit",
    ],
)
def test_any_none_limit_fails(limit_field: str) -> None:
    """(canary) Any None (unestablished) limit fails closed — an unusable bound."""
    assert layering_within_bounds(valid_layering(**{limit_field: None})) is False


def test_default_layering_fails() -> None:
    """A default (all-None) layering is never within bounds (no vacuous permit)."""
    assert layering_within_bounds(LimitLayering()) is False


# ---------------------------------------------------------------------------
# Atomic activation
# ---------------------------------------------------------------------------


def test_atomic_activation_all_positive_ok() -> None:
    """(guard fires True) Fully-active, single-version, unit-compatible, bounded => ok."""
    assert (
        atomic_activation_ok(
            version_fully_active=True,
            mixed_versions_present=False,
            units_compatible=True,
            envelope_bounded=True,
        )
        is True
    )


@pytest.mark.parametrize(
    "override",
    [
        {"version_fully_active": None},
        {"version_fully_active": False},
        {"mixed_versions_present": True},
        {"mixed_versions_present": None},
        {"units_compatible": None},
        {"units_compatible": False},
        {"envelope_bounded": None},
        {"envelope_bounded": False},
    ],
)
def test_atomic_activation_fails_closed(override: dict[str, object]) -> None:
    """(canary) Partial / mixed / unknown / incompatible activation fails closed (§6.4)."""
    base: dict[str, object] = {
        "version_fully_active": True,
        "mixed_versions_present": False,
        "units_compatible": True,
        "envelope_bounded": True,
    }
    base.update(override)
    assert atomic_activation_ok(**base) is False  # type: ignore[arg-type]
