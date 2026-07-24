"""§14.1 delta-proportional in-place expansion + partial-scope narrowing (§6.5, §6.6).

An in-place expansion is admissible only via a **new delta authorization** (the old one is
never stretched), with unbroken continuity, all ten proportional flags True, preserved dual
control, and a satisfied progressive-promotion gate. Partial re-arm only narrows scope;
narrowing to the empty scope is lawful full de-authorization (Gap-2). [REARM-EV-009]
"""

from __future__ import annotations

import pytest
from tos.liveauth import (
    in_place_expansion_admissible,
    partial_rearm_scope_narrows,
    scope_covers,
)
from tos.liveauth.predicates import _PROPORTIONAL_EXPANSION_FLAGS

from ._liveauth_strategies import (
    full_scope,
    issue_authorization,
    solo_variant_attestation,
    valid_expansion_inputs,
    wide_scope,
)

_EXISTING = issue_authorization(authorization_id="existing-1")


def test_valid_expansion_admissible() -> None:
    """(guard fires True) A complete §14.1 delta expansion is admissible."""
    assert in_place_expansion_admissible(valid_expansion_inputs(), _EXISTING) is True


def test_delta_equal_to_existing_id_fails() -> None:
    """(canary core) A delta id equal to the existing id fails — the old is never stretched."""
    inputs = valid_expansion_inputs(new_delta_authorization_id="existing-1")
    assert in_place_expansion_admissible(inputs, _EXISTING) is False


def test_none_delta_id_fails() -> None:
    """(canary) A None delta authorization id fails closed."""
    inputs = valid_expansion_inputs(new_delta_authorization_id=None)
    assert in_place_expansion_admissible(inputs, _EXISTING) is False


def test_none_existing_id_fails() -> None:
    """(canary) A None existing-authorization id fails closed."""
    inputs = valid_expansion_inputs(existing_authorization_id=None)
    assert in_place_expansion_admissible(inputs, _EXISTING) is False


def test_existing_id_mismatch_fails() -> None:
    """(canary) A passed existing authorization whose id disagrees with the input fails."""
    inputs = valid_expansion_inputs(existing_authorization_id="other-id")
    assert in_place_expansion_admissible(inputs, _EXISTING) is False


def test_broken_continuity_forces_full_path() -> None:
    """(canary) Broken continuity => not admissible (take the full §12 re-arm path)."""
    for value in (False, None):
        inputs = valid_expansion_inputs(continuous_validity_unbroken=value)
        assert in_place_expansion_admissible(inputs, _EXISTING) is False


@pytest.mark.parametrize("flag", _PROPORTIONAL_EXPANSION_FLAGS)
def test_each_proportional_flag_none_fails(flag: str) -> None:
    """(canary, all-but-one) Each of the 10 proportional flags None => not admissible."""
    inputs = valid_expansion_inputs(**{flag: None})
    assert in_place_expansion_admissible(inputs, _EXISTING) is False


@pytest.mark.parametrize("flag", _PROPORTIONAL_EXPANSION_FLAGS)
def test_each_proportional_flag_false_fails(flag: str) -> None:
    """(canary, all-but-one) Each of the 10 proportional flags False => not admissible."""
    inputs = valid_expansion_inputs(**{flag: False})
    assert in_place_expansion_admissible(inputs, _EXISTING) is False


def test_ten_proportional_flags_present() -> None:
    """The proportional-flag set is the ADR §14.1 item 2 ten (no silent shrinkage)."""
    assert len(_PROPORTIONAL_EXPANSION_FLAGS) == 10


def test_failed_dual_control_fails() -> None:
    """(canary) An unmet dual control (single operator, no variant) fails expansion (§14.1 item 3)."""
    from tos.liveauth import DualControlAttestation

    inputs = valid_expansion_inputs(
        dual_control=DualControlAttestation(
            armer_principal="same", limit_change_approver_principal="same"
        )
    )
    assert in_place_expansion_admissible(inputs, _EXISTING) is False


def test_solo_variant_dual_control_admissible() -> None:
    """A lawful SAFE-053 solo variant satisfies §14.1 item 3 dual control."""
    inputs = valid_expansion_inputs(dual_control=solo_variant_attestation())
    assert in_place_expansion_admissible(inputs, _EXISTING) is True


def test_progressive_gate_unsatisfied_fails() -> None:
    """(canary) An unsatisfied progressive-promotion gate fails closed (§14.1 item 4)."""
    for value in (False, None):
        inputs = valid_expansion_inputs(progressive_promotion_gate_satisfied=value)
        assert in_place_expansion_admissible(inputs, _EXISTING) is False


# ---------------------------------------------------------------------------
# Partial re-arm scope narrowing (§6.5)
# ---------------------------------------------------------------------------


def test_narrowing_is_allowed() -> None:
    """(guard fires True) A narrowed scope (⊆ prior) is a valid partial re-arm."""
    assert partial_rearm_scope_narrows(wide_scope(), full_scope()) is True


def test_broadening_is_rejected() -> None:
    """(canary) A broader new scope than the prior is rejected (no broader fallback)."""
    assert partial_rearm_scope_narrows(full_scope(), wide_scope()) is False


def test_narrowing_to_empty_is_full_deauthorization() -> None:
    """(Gap-2) Narrowing to the empty scope is lawful full de-authorization.

    ``∅ ⊆ prior`` narrows (True), and the resulting scope then covers nothing (consistent
    with §5.3), so it validates no subsequent action.
    """
    empty = full_scope(
        accounts=frozenset(),
        strategies=frozenset(),
        instrument_classes=frozenset(),
        venues=frozenset(),
        sessions=frozenset(),
        order_types=frozenset(),
        action_classes=frozenset(),
    )
    assert partial_rearm_scope_narrows(wide_scope(), empty) is True
    assert scope_covers(empty, full_scope()) is False


def test_none_dimension_narrowing_fails() -> None:
    """(canary) A None dimension on either side fails closed."""
    assert partial_rearm_scope_narrows(wide_scope(), full_scope(accounts=None)) is False
    assert partial_rearm_scope_narrows(full_scope(accounts=None), full_scope()) is False
