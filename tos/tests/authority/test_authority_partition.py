"""Partition authority deny-table + registry-unavailable (§6.5; SA-EV-003/014).

When the safety control plane is unverifiable (False OR None), every new-authority action
is DENIED while existing economic effect is preserved; automatic re-arm is denied
unconditionally (rejoin never auto-restores live mode).
"""

from __future__ import annotations

from tos.authority import partition_authority_verdict

_DENIED_FLAGS = (
    "new_normal_risk_increasing_denied",
    "new_aggregate_capacity_commitment_denied",
    "normal_capability_renewal_denied",
    "live_rearm_denied",
    "limit_enlargement_denied",
    "automatic_rearm_denied",
)
_PRESERVED_FLAGS = (
    "existing_orders_preserved",
    "existing_fills_preserved",
    "existing_positions_preserved",
    "existing_reservations_preserved",
)


def test_unverifiable_control_plane_none_denies_everything() -> None:
    """(canary) control_plane_verifiable=None => every new-authority action DENIED (no vacuous permit)."""
    verdict = partition_authority_verdict(None)
    assert all(getattr(verdict, flag) is True for flag in _DENIED_FLAGS)


def test_unverifiable_control_plane_false_denies_everything() -> None:
    """control_plane_verifiable=False => every new-authority action DENIED (§13.1; SA-EV-014)."""
    verdict = partition_authority_verdict(False)
    assert all(getattr(verdict, flag) is True for flag in _DENIED_FLAGS)


def test_existing_effects_always_preserved() -> None:
    """Existing orders / fills / positions / reservations preserved for every input (§13.1)."""
    for verifiable in (None, False, True):
        verdict = partition_authority_verdict(verifiable)
        assert all(getattr(verdict, flag) is True for flag in _PRESERVED_FLAGS)


def test_rejoin_never_auto_rearms() -> None:
    """(canary §13.5) Automatic re-arm is denied even when the control plane is verifiable."""
    verdict = partition_authority_verdict(True)
    assert verdict.automatic_rearm_denied is True
    # But the other new-authority actions are permitted with a verifiable control plane.
    assert verdict.new_normal_risk_increasing_denied is False
    assert verdict.normal_capability_renewal_denied is False
    assert verdict.limit_enlargement_denied is False


def test_guard_fires_both_ways() -> None:
    """The deny verdict differs between verifiable and unverifiable (not constant)."""
    denied = partition_authority_verdict(None).new_normal_risk_increasing_denied
    allowed = partition_authority_verdict(True).new_normal_risk_increasing_denied
    assert denied is True and allowed is False
