"""Truthy-sentinel structural seal — __bool__ raises + is-gate regression (design #23 §2.2/§4.2/§7)."""

from __future__ import annotations

import pytest
from tos.cur import CurrentnessAdmission, DimensionKey, ProofResult

from .._truthiness_scan import package_truthiness_offenders

_SUSPICIOUS = frozenset({"admission", "result", "verdict", "proof_result", "latch"})

_SEALED_ENUMS = (ProofResult, CurrentnessAdmission)


def test_every_sealed_enum_member_raises_on_bool() -> None:
    """(§4.2 structural seal) bool(member) raises TypeError for EVERY member of each sealed enum."""
    for enum in _SEALED_ENUMS:
        for member in enum:
            with pytest.raises(TypeError):
                bool(member)


def test_denial_members_cannot_be_read_as_conformance() -> None:
    """(§4.2 — the catastrophic case) RESTRICTED / UNKNOWN / DENY are not truthy."""
    for member in (
        ProofResult.RESTRICTED,
        ProofResult.UNKNOWN,
        CurrentnessAdmission.DENY,
    ):
        with pytest.raises(TypeError):
            bool(member)


def test_is_identity_gate_still_works() -> None:
    """(the mandated gate) Explicit `is` identity comparison is unaffected by the seal."""
    assert (ProofResult.CURRENT is ProofResult.CURRENT) is True
    assert (ProofResult.RESTRICTED is ProofResult.CURRENT) is False
    assert (CurrentnessAdmission.ADMIT is CurrentnessAdmission.ADMIT) is True
    assert ProofResult.CURRENT in {ProofResult.CURRENT}
    assert ProofResult.CURRENT.value == "CURRENT"
    assert hash(ProofResult.UNKNOWN) == hash(ProofResult.UNKNOWN)


def test_dimension_key_is_not_sealed() -> None:
    """(§2.2) DimensionKey is a plain closed membership token — truthiness is fine (not a verdict)."""
    assert bool(DimensionKey.CONTEXT) is True


def test_denial_values_would_have_failed_open_under_bare_truthiness() -> None:
    """(the trap itself) The denial .value strings are non-empty (would be truthy)."""
    assert bool(str(ProofResult.RESTRICTED.value)) is True
    assert bool(str(ProofResult.UNKNOWN.value)) is True
    assert bool(str(CurrentnessAdmission.DENY.value)) is True


def test_no_cur_source_uses_bare_truthiness_on_a_verdict() -> None:
    """(source seal) No cur module tests a verdict-shaped value for bare truthiness."""
    offenders = package_truthiness_offenders("cur", _SUSPICIOUS)
    assert offenders == [], f"truthy-sentinel trap reachable: {offenders}"
