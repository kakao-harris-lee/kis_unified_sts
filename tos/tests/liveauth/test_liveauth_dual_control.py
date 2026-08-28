"""Two-lawful-paths dual control — type-gated disjunction (§6.3; REARM-AC-005; SAFE-053).

Path 1 (quorum) needs two distinct principals + a count >= 2; Path 2 (SAFE-053 solo
variant) needs a present variant with all seven compensating controls True. A single
operator with an absent / incomplete variant opens neither path. Each of the seven
controls is individually load-bearing (a parametrized None / False sweep). The external
Independent Reviewer configuration routes to Path 1 (genuine second principal), not Path 2.
[REARM-EV-005 substrate]
"""

from __future__ import annotations

import pytest
from tos.liveauth import DualControlAttestation, rearm_dual_control_satisfied
from tos.liveauth.predicates import _SAFE053_CONTROLS

from ._liveauth_strategies import (
    full_variant,
    quorum_attestation,
    solo_variant_attestation,
)


def test_quorum_two_distinct_principals_satisfies() -> None:
    """(guard fires True, Path 1) Two distinct principals + count >= 2 => satisfied."""
    assert rearm_dual_control_satisfied(quorum_attestation()) is True


def test_solo_variant_all_controls_satisfies() -> None:
    """(guard fires True, Path 2) A solo config with all seven controls True => satisfied."""
    assert rearm_dual_control_satisfied(solo_variant_attestation()) is True


def test_same_principal_no_variant_fails() -> None:
    """(canary) A single operator with no variant opens neither path."""
    attestation = DualControlAttestation(
        armer_principal="same", limit_change_approver_principal="same"
    )
    assert rearm_dual_control_satisfied(attestation) is False


def test_none_principal_fails() -> None:
    """(canary) A None principal fails Path 1 (and, with no variant, Path 2)."""
    assert (
        rearm_dual_control_satisfied(quorum_attestation(armer_principal=None)) is False
    )
    assert (
        rearm_dual_control_satisfied(
            quorum_attestation(limit_change_approver_principal=None)
        )
        is False
    )


def test_quorum_count_below_two_fails() -> None:
    """(canary) Two distinct principals but a count < 2 fails Path 1 (both natural persons)."""
    assert (
        rearm_dual_control_satisfied(quorum_attestation(distinct_approver_count=1))
        is False
    )


def test_quorum_count_none_fails() -> None:
    """(canary) A None distinct-approver count fails closed."""
    assert (
        rearm_dual_control_satisfied(quorum_attestation(distinct_approver_count=None))
        is False
    )


def test_distinct_principals_without_count_fails() -> None:
    """(canary) Distinct principals alone (no established count) do not open Path 1."""
    attestation = DualControlAttestation(
        armer_principal="A", limit_change_approver_principal="B"
    )
    assert rearm_dual_control_satisfied(attestation) is False


@pytest.mark.parametrize("control", _SAFE053_CONTROLS)
def test_each_variant_control_none_closes_solo_path(control: str) -> None:
    """(canary, all-but-one) Each of the 7 controls None => solo variant path closed."""
    attestation = solo_variant_attestation(variant=full_variant(**{control: None}))
    assert rearm_dual_control_satisfied(attestation) is False


@pytest.mark.parametrize("control", _SAFE053_CONTROLS)
def test_each_variant_control_false_closes_solo_path(control: str) -> None:
    """(canary, all-but-one) Each of the 7 controls False => solo variant path closed."""
    attestation = solo_variant_attestation(variant=full_variant(**{control: False}))
    assert rearm_dual_control_satisfied(attestation) is False


def test_same_principal_with_partial_variant_fails() -> None:
    """(canary) A single operator with an incomplete variant opens neither path."""
    attestation = solo_variant_attestation(
        variant=full_variant(time_separated_reauthenticated_confirmation=None)
    )
    assert rearm_dual_control_satisfied(attestation) is False


def test_variant_none_with_single_operator_fails() -> None:
    """(canary type-gate) A single operator with variant=None fails (no Path 2 to open)."""
    attestation = solo_variant_attestation(variant=None)
    assert rearm_dual_control_satisfied(attestation) is False


def test_seven_controls_present() -> None:
    """The SAFE-053 variant has exactly seven compensating controls (§6.3 5->7, M2)."""
    assert len(_SAFE053_CONTROLS) == 7
    assert "time_separated_reauthenticated_confirmation" in _SAFE053_CONTROLS
    assert "independent_nonauthorizing_attestation_current" in _SAFE053_CONTROLS


def test_external_reviewer_configuration_is_path_one() -> None:
    """The external Independent Reviewer (genuine second principal) satisfies Path 1.

    Two distinct effective principals with a count >= 2 — no variant needed; this is the
    quorum path, not the solo variant (§6.3; ADR-002-015 §17.1.4).
    """
    reviewer = DualControlAttestation(
        armer_principal="operator",
        limit_change_approver_principal="external-reviewer",
        distinct_approver_count=2,
    )
    assert rearm_dual_control_satisfied(reviewer) is True
