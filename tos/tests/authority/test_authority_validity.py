"""Permissive capability validity — 6-part, type-gated (M2), numeric-claim (Gap) (§5.2).

The central fail-open seams the v1.1 design closed: (M2) a NORMAL_RISK_INCREASING
capability requires an ONLINE currentness witness — a degraded lease cannot substitute;
(Gap) a capability with a null numeric claim is invalid at consumption even though it is
ISSUED-reachable. The egress condition 6 is NOT claimed — a ``True`` here is necessary,
not sufficient (§0.2/§4.1). SA-EV-001/003 substrate.
"""

from __future__ import annotations

import pytest
from tos.authority import (
    CapabilityType,
    permissive_capability_valid,
)

from ._authority_strategies import (
    epoch_state,
    fresh_witness,
    issue_capability,
    valid_inputs,
)

STATE = epoch_state(authority_domain="acct-1", current_epoch_floor=5)


def test_valid_normal_capability_with_online_witness() -> None:
    """A complete NORMAL_RISK_INCREASING capability + current epoch + fresh witness is valid.

    Guard-not-const-False: the positive path returns True (necessary conditions 1-5 met).
    """
    cap = issue_capability(capability_type=CapabilityType.NORMAL_RISK_INCREASING)
    assert (
        permissive_capability_valid(cap, STATE, valid_inputs(), lease_ok=False) is True
    )


def test_m2_normal_risk_increasing_lease_cannot_substitute_for_witness() -> None:
    """(canary M2) NORMAL_RISK_INCREASING + lease_ok=True + witness absent => INVALID.

    A degraded lease NEVER satisfies condition 4 for a normal risk-increasing capability
    (§9.4 line 366; SA-INV-005) — the online-currentness-only gate removes the fail-open.
    """
    cap = issue_capability(capability_type=CapabilityType.NORMAL_RISK_INCREASING)
    inputs = valid_inputs(currentness=fresh_witness(present=False))
    assert permissive_capability_valid(cap, STATE, inputs, lease_ok=True) is False


def test_m2_degraded_protective_lease_path_valid_without_witness() -> None:
    """DEGRADED_PROTECTIVE satisfies condition 4 via lease_ok (the only lease-eligible type)."""
    cap = issue_capability(capability_type=CapabilityType.DEGRADED_PROTECTIVE)
    inputs = valid_inputs(currentness=fresh_witness(present=False))
    assert permissive_capability_valid(cap, STATE, inputs, lease_ok=True) is True


def test_m2_degraded_protective_invalid_without_lease() -> None:
    """DEGRADED_PROTECTIVE with lease_ok=False and no witness is invalid (no substitute)."""
    cap = issue_capability(capability_type=CapabilityType.DEGRADED_PROTECTIVE)
    inputs = valid_inputs(currentness=fresh_witness(present=False))
    assert permissive_capability_valid(cap, STATE, inputs, lease_ok=False) is False


@pytest.mark.parametrize(
    "captype",
    [
        CapabilityType.NORMAL_RISK_INCREASING,
        CapabilityType.NORMAL_RISK_REDUCING,
        CapabilityType.CANCEL_REQUEST,
        CapabilityType.RECONCILIATION_ONLY,
        CapabilityType.LIMIT_ACTIVATION,
    ],
)
def test_non_degraded_types_require_online_currentness(captype: CapabilityType) -> None:
    """(canary M2) Every non-DEGRADED_PROTECTIVE type requires an online witness — lease_ok ignored."""
    cap = issue_capability(capability_type=captype)
    inputs = valid_inputs(currentness=fresh_witness(present=False))
    assert permissive_capability_valid(cap, STATE, inputs, lease_ok=True) is False


def test_gap_none_maximum_quantity_is_invalid() -> None:
    """(canary Gap) An ISSUED capability with maximum_quantity=None is invalid at consumption (§5.2)."""
    cap = issue_capability(maximum_quantity=None)
    assert (
        permissive_capability_valid(cap, STATE, valid_inputs(), lease_ok=False) is False
    )


def test_gap_none_risk_vector_link_is_invalid() -> None:
    """(canary Gap) A null risk-vector / reservation link is invalid at consumption (§5.2)."""
    cap = issue_capability(maximum_risk_vector_effect_or_reservation_identity=None)
    assert (
        permissive_capability_valid(cap, STATE, valid_inputs(), lease_ok=False) is False
    )


def test_condition1_revoked_or_unknown_issuer_key_invalid() -> None:
    """(canary §1-1) issuer_key_status not 'valid' (revoked / unknown / None) => invalid (§18.2)."""
    cap = issue_capability()
    for status in ("revoked", "unknown", None):
        inputs = valid_inputs(issuer_key_status=status)
        assert permissive_capability_valid(cap, STATE, inputs, lease_ok=False) is False


def test_condition2_stale_epoch_invalid_even_with_all_else_valid() -> None:
    """(canary §1-2) A stale epoch invalidates even when every other claim is present."""
    cap = issue_capability(safety_authority_epoch=3)  # below floor 5
    assert (
        permissive_capability_valid(cap, STATE, valid_inputs(), lease_ok=False) is False
    )


def test_condition3_env_mode_mismatch_invalid() -> None:
    """(canary §1-3 / §18.4) environment_and_mode_matches None/False => invalid (cross-env)."""
    cap = issue_capability()
    for match in (False, None):
        inputs = valid_inputs(environment_and_mode_matches=match)
        assert permissive_capability_valid(cap, STATE, inputs, lease_ok=False) is False


@pytest.mark.parametrize("field", ["consumed", "superseded"])
@pytest.mark.parametrize("bad", [True, None])
def test_condition5_consumed_or_superseded_invalid(field: str, bad: object) -> None:
    """(canary §1-5) consumed / superseded True or None => invalid (fail-closed)."""
    cap = issue_capability()
    inputs = valid_inputs(**{field: bad})
    assert permissive_capability_valid(cap, STATE, inputs, lease_ok=False) is False


def test_condition5_revocation_status_must_positively_attest() -> None:
    """(canary §1-5) revocation_status None / any non-'not_revoked' => invalid."""
    cap = issue_capability()
    for status in (None, "revoked", "unknown", ""):
        inputs = valid_inputs(revocation_status=status)
        assert permissive_capability_valid(cap, STATE, inputs, lease_ok=False) is False


def test_condition5_dominating_restriction_invalidates() -> None:
    """(canary §1-5) A dominating safer state invalidates a permissive capability."""
    cap = issue_capability()
    inputs = valid_inputs(dominating_restriction=True)
    assert permissive_capability_valid(cap, STATE, inputs, lease_ok=False) is False


def test_draft_capability_is_invalid() -> None:
    """A DRAFT (unissued) capability grants nothing (signature/possession != authority, §4.1)."""
    from tos.authority import SafetyAuthorityCapability

    draft = SafetyAuthorityCapability(capability_id="cap-1")
    assert (
        permissive_capability_valid(draft, STATE, valid_inputs(), lease_ok=False)
        is False
    )


def test_possession_without_currentness_is_invalid() -> None:
    """(canary §4.1) A fully-signed ISSUED capability with witness absent is invalid.

    Holding / signing is not current authority (§1 line 17; §5.3 line 121) — currentness
    comes only from the injected witness, never from possession.
    """
    cap = issue_capability(capability_type=CapabilityType.NORMAL_RISK_INCREASING)
    inputs = valid_inputs(currentness=fresh_witness(present=False))
    assert permissive_capability_valid(cap, STATE, inputs, lease_ok=False) is False
