"""Truthy-sentinel structural seal — __bool__ raises + is-gate regression (design #19 §4.7/§7)."""

from __future__ import annotations

import pytest
from tos.venue import OrderAdmissibilityResult, TradabilityState

from .._truthiness_scan import package_truthiness_offenders

_SUSPICIOUS = frozenset({"result", "admissibility", "tradability", "state", "verdict"})

_SEALED_ENUMS = (OrderAdmissibilityResult, TradabilityState)


def test_every_sealed_enum_member_raises_on_bool() -> None:
    """(§4.7 structural seal) bool(member) raises TypeError for EVERY member of each sealed enum."""
    for enum in _SEALED_ENUMS:
        for member in enum:
            with pytest.raises(TypeError):
                bool(member)
            with pytest.raises(TypeError):
                if member:  # pragma: no cover - the branch never executes
                    pass


def test_restricted_protective_only_cannot_be_read_as_permission() -> None:
    """(§0.4d — the catastrophic case) RESTRICTED_PROTECTIVE_ONLY is not truthy-testable."""
    with pytest.raises(TypeError):
        bool(OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY)
    with pytest.raises(TypeError):
        if OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY:  # pragma: no cover
            pass


def test_every_admissibility_value_including_restricted_raises() -> None:
    """(§4.7, all four) INADMISSIBLE / UNKNOWN / RESTRICTED_PROTECTIVE_ONLY / ADMISSIBLE all raise on bool."""
    for member in OrderAdmissibilityResult:
        with pytest.raises(TypeError):
            bool(member)


def test_is_identity_gate_still_works() -> None:
    """(the mandated gate) Explicit `is` identity comparison is unaffected by the seal."""
    assert (
        OrderAdmissibilityResult.ADMISSIBLE is OrderAdmissibilityResult.ADMISSIBLE
    ) is True
    assert (
        OrderAdmissibilityResult.INADMISSIBLE is OrderAdmissibilityResult.ADMISSIBLE
    ) is False
    assert (TradabilityState.TRADABLE is TradabilityState.TRADABLE) is True
    assert OrderAdmissibilityResult.UNKNOWN in {OrderAdmissibilityResult.UNKNOWN}
    assert OrderAdmissibilityResult.ADMISSIBLE.value == "ADMISSIBLE"
    assert hash(TradabilityState.NOT_TRADABLE) == hash(TradabilityState.NOT_TRADABLE)


def test_denial_values_would_have_failed_open_under_bare_truthiness() -> None:
    """(the trap itself) The denial + protective-only .value strings are non-empty (would be truthy)."""
    assert bool(str(OrderAdmissibilityResult.INADMISSIBLE.value)) is True
    assert bool(str(OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY.value)) is True
    assert bool(str(TradabilityState.NOT_TRADABLE.value)) is True


def test_no_venue_source_uses_bare_truthiness_on_a_result() -> None:
    """(source seal) No venue module tests a result-shaped value for bare truthiness."""
    offenders = package_truthiness_offenders("venue", _SUSPICIOUS)
    assert offenders == [], f"truthy-sentinel trap reachable: {offenders}"
