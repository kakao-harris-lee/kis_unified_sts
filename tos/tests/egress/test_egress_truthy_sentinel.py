"""Truthy-sentinel structural seal — __bool__ raises + is-gate regression (design #22 §2.2/§4.7/§7)."""

from __future__ import annotations

import pytest
from tos.egress import CommitProofValidity, EgressAdmission, RestrictiveLatchState

from .._truthiness_scan import package_truthiness_offenders

_SUSPICIOUS = frozenset(
    {"admission", "validity", "state", "latch_state", "verdict", "result"}
)

_SEALED_ENUMS = (EgressAdmission, CommitProofValidity, RestrictiveLatchState)


def test_every_sealed_enum_member_raises_on_bool() -> None:
    """(§4.7 structural seal) bool(member) raises TypeError for EVERY member of each sealed enum."""
    for enum in _SEALED_ENUMS:
        for member in enum:
            with pytest.raises(TypeError):
                bool(member)
            with pytest.raises(TypeError):
                if member:  # pragma: no cover - the branch never executes
                    pass


def test_deny_members_cannot_be_read_as_admission() -> None:
    """(§4.7 — the catastrophic case) DENY / INVALID / UNKNOWN / DENY_LATCHED are not truthy."""
    for member in (
        EgressAdmission.DENY,
        CommitProofValidity.INVALID,
        CommitProofValidity.UNKNOWN,
        RestrictiveLatchState.DENY_LATCHED,
    ):
        with pytest.raises(TypeError):
            bool(member)


def test_is_identity_gate_still_works() -> None:
    """(the mandated gate) Explicit `is` identity comparison is unaffected by the seal."""
    assert (EgressAdmission.ADMIT is EgressAdmission.ADMIT) is True
    assert (EgressAdmission.DENY is EgressAdmission.ADMIT) is False
    assert (CommitProofValidity.VALID is CommitProofValidity.VALID) is True
    assert (RestrictiveLatchState.CLEAR is RestrictiveLatchState.CLEAR) is True
    assert EgressAdmission.ADMIT in {EgressAdmission.ADMIT}
    assert CommitProofValidity.VALID.value == "VALID"
    assert hash(RestrictiveLatchState.DENY_LATCHED) == hash(
        RestrictiveLatchState.DENY_LATCHED
    )


def test_denial_values_would_have_failed_open_under_bare_truthiness() -> None:
    """(the trap itself) The denial .value strings are non-empty (would be truthy)."""
    assert bool(str(EgressAdmission.DENY.value)) is True
    assert bool(str(CommitProofValidity.UNKNOWN.value)) is True
    assert bool(str(RestrictiveLatchState.DENY_LATCHED.value)) is True


def test_no_egress_source_uses_bare_truthiness_on_a_verdict() -> None:
    """(source seal) No egress module tests a verdict-shaped value for bare truthiness."""
    offenders = package_truthiness_offenders("egress", _SUSPICIOUS)
    assert offenders == [], f"truthy-sentinel trap reachable: {offenders}"
