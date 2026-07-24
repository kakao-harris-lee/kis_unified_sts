"""HALT restrictive precedence — authority REUSE, order-independent (§6.7; REARM-AC-011).

HALT dominates outstanding permissive capabilities and Live Authorization regardless of
issue order, and denies new risk-increasing / re-arm / limit-activation capability types.
The predicate is pure ``tos.authority`` REUSE (``restrictive_dominates`` ∨ ``halt_denies``)
— no new precedence logic, no blind cancel-all. [REARM-EV-011 substrate]
"""

from __future__ import annotations

import pytest
from tos.authority import AuthorityState, CapabilityType
from tos.liveauth import halt_dominates_authorization

from ._liveauth_strategies import SCHEME

_BENIGN_TYPE = CapabilityType.NORMAL_RISK_REDUCING


def _halt_capability():
    """An outstanding HALT capability."""
    from tos.authority import SafetyAuthorityCapability

    return SafetyAuthorityCapability.issue(
        scheme=SCHEME,
        capability_id="halt-1",
        capability_type=CapabilityType.HALT,
        issuer_identity="iss",
        authority_domain="acct-1",
        safety_authority_epoch=5,
        subject_service_identity="svc",
        environment_and_mode="live",
        account_scope="acct-1",
        permitted_action_class="HALT",
        issue_sequence=1,
        hard_safety_envelope_version="h",
        runtime_safety_profile_version="r",
        maximum_quantity=0,
        maximum_risk_vector_effect_or_reservation_identity="rsv",
        nonce="n",
    )


def test_halt_state_dominates() -> None:
    """(canary) A HALTED authority state dominates any permissive grant."""
    assert halt_dominates_authorization(AuthorityState.HALTED, (), _BENIGN_TYPE) is True


def test_contained_state_dominates() -> None:
    """(canary) A CONTAINED state also dominates (restrictive precedence)."""
    assert (
        halt_dominates_authorization(AuthorityState.CONTAINED, (), _BENIGN_TYPE) is True
    )


def test_outstanding_halt_capability_dominates() -> None:
    """(canary, order-independent) An outstanding HALT capability dominates a LIVE_NORMAL state."""
    assert (
        halt_dominates_authorization(
            AuthorityState.LIVE_NORMAL, (_halt_capability(),), _BENIGN_TYPE
        )
        is True
    )


@pytest.mark.parametrize(
    "denied_type",
    [
        CapabilityType.NORMAL_RISK_INCREASING,
        CapabilityType.REARM,
        CapabilityType.LIMIT_ACTIVATION,
    ],
)
def test_halt_denies_risk_increasing_types(denied_type: CapabilityType) -> None:
    """(canary) HALT denies new risk-increasing / re-arm / limit-activation types."""
    assert (
        halt_dominates_authorization(AuthorityState.LIVE_NORMAL, (), denied_type)
        is True
    )


def test_no_dominance_when_live_normal_and_benign() -> None:
    """(guard fires False) LIVE_NORMAL + no outstanding restriction + benign type => no dominance."""
    assert (
        halt_dominates_authorization(AuthorityState.LIVE_NORMAL, (), _BENIGN_TYPE)
        is False
    )


def test_order_independent_both_directions() -> None:
    """(canary, order-independent) HALT dominates whether it raced ahead of or behind grants."""
    halt = _halt_capability()
    # HALT capability present with a benign type + LIVE_NORMAL state — dominance holds.
    assert (
        halt_dominates_authorization(AuthorityState.LIVE_NORMAL, (halt,), _BENIGN_TYPE)
        is True
    )
    # And a HALTED state with no outstanding capability likewise dominates.
    assert halt_dominates_authorization(AuthorityState.HALTED, (), _BENIGN_TYPE) is True


def test_no_cancel_all_operation() -> None:
    """(canary §17) The module derives no blind cancel-all from HALT (constructive absence)."""
    import tos.liveauth as liveauth

    forbidden = [
        name
        for name in dir(liveauth)
        if "cancel_all" in name.lower() or "cancel_everything" in name.lower()
    ]
    assert forbidden == []
