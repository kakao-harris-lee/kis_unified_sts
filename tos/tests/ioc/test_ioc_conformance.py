"""command_conforms — §10-§12 exact-axis conformance (design #14 §5.1; IOC-EV-001/002 substrate)."""

from __future__ import annotations

import pytest
from tos.ioc import AxisBinding, ConformanceAxis, ConformanceResult, command_conforms

from ._ioc_strategies import (
    AUTHORIZED_AXES,
    issue_command,
    issue_envelope,
    issue_intent,
    issue_policy,
)


def _full_bindings() -> tuple[AxisBinding, ...]:
    """The full clean axis binding tuple (one binding per AUTHORIZED_AXES entry)."""
    return tuple(
        AxisBinding(axis=axis, value=value) for axis, value in AUTHORIZED_AXES.items()
    )


def _with_duplicate_side() -> tuple[AxisBinding, ...]:
    """The full clean bindings + a second SIDE=BUY binding (a duplicate semantic axis)."""
    return _full_bindings() + (AxisBinding(axis=ConformanceAxis.SIDE, value="BUY"),)


def test_exact_match_on_every_axis_is_conformant() -> None:
    """(canary +) Intent / command / envelope agree on every axis => CONFORMANT."""
    result = command_conforms(
        issue_intent(), issue_command(), issue_policy(), issue_envelope()
    )
    assert result is ConformanceResult.CONFORMANT


def test_side_flip_is_non_conformant() -> None:
    """(canary - §11 line 301) A silently flipped SIDE (BUY -> SELL) => NON_CONFORMANT."""
    flipped = {**AUTHORIZED_AXES, ConformanceAxis.SIDE: "SELL"}
    result = command_conforms(
        issue_intent(), issue_command(flipped), issue_policy(), issue_envelope()
    )
    assert result is ConformanceResult.NON_CONFORMANT


def test_direction_side_position_effect_are_independent_axes() -> None:
    """(§11 line 301) A flip of direction OR position-effect alone is each a distinct mismatch."""
    for axis, wrong in (
        (ConformanceAxis.DIRECTION, "SHORT"),
        (ConformanceAxis.POSITION_EFFECT, "CLOSE"),
    ):
        command = issue_command({**AUTHORIZED_AXES, axis: wrong})
        result = command_conforms(
            issue_intent(), command, issue_policy(), issue_envelope()
        )
        assert result is ConformanceResult.NON_CONFORMANT, axis


def test_default_account_substitute_is_non_conformant() -> None:
    """(forbidden-verb 'default'/'substitute' §10 line 284) A defaulted account => NON_CONFORMANT."""
    substituted = {**AUTHORIZED_AXES, ConformanceAxis.ACCOUNT: "PRIMARY-DEFAULT"}
    result = command_conforms(
        issue_intent(), issue_command(substituted), issue_policy(), issue_envelope()
    )
    assert result is ConformanceResult.NON_CONFORMANT


def test_symbol_alias_is_non_conformant() -> None:
    """(forbidden-verb 'alias' §10 line 284) An aliased broker symbol => NON_CONFORMANT."""
    aliased = {**AUTHORIZED_AXES, ConformanceAxis.INSTRUMENT: "INSTR-1-ALIAS"}
    result = command_conforms(
        issue_intent(), issue_command(aliased), issue_policy(), issue_envelope()
    )
    assert result is ConformanceResult.NON_CONFORMANT


@pytest.mark.parametrize("axis", list(AUTHORIZED_AXES))
def test_drop_one_command_axis_is_unknown(axis: ConformanceAxis) -> None:
    """(drop-one per axis) A command with one axis value dropped to None => UNKNOWN."""
    dropped = {**AUTHORIZED_AXES, axis: None}
    result = command_conforms(
        issue_intent(), issue_command(dropped), issue_policy(), issue_envelope()
    )
    assert result is ConformanceResult.UNKNOWN


@pytest.mark.parametrize("axis", list(AUTHORIZED_AXES))
def test_drop_one_intent_axis_is_unknown(axis: ConformanceAxis) -> None:
    """(drop-one per axis) An intent with one axis value dropped to None => UNKNOWN."""
    dropped = {**AUTHORIZED_AXES, axis: None}
    result = command_conforms(
        issue_intent(dropped), issue_command(), issue_policy(), issue_envelope()
    )
    assert result is ConformanceResult.UNKNOWN


def test_missing_policy_is_unknown() -> None:
    """(fail-closed) A None governing policy => UNKNOWN (cannot decide without policy)."""
    result = command_conforms(issue_intent(), issue_command(), None, issue_envelope())
    assert result is ConformanceResult.UNKNOWN


def test_none_intent_or_command_is_unknown() -> None:
    """(fail-closed) A None intent / command => UNKNOWN (missing determination input)."""
    assert (
        command_conforms(None, issue_command(), issue_policy(), issue_envelope())
        is ConformanceResult.UNKNOWN
    )
    assert (
        command_conforms(issue_intent(), None, issue_policy(), issue_envelope())
        is ConformanceResult.UNKNOWN
    )


def test_absent_envelope_permits_no_construction() -> None:
    """(∅ §5.3 line 125) A None envelope => NON_CONFORMANT (permits no construction)."""
    result = command_conforms(issue_intent(), issue_command(), issue_policy(), None)
    assert result is ConformanceResult.NON_CONFORMANT


def test_open_ended_empty_envelope_is_non_conformant() -> None:
    """(∅ §5.3 line 125 / §4.7) An envelope with no authorized axes => NON_CONFORMANT."""
    empty = issue_envelope(values={})
    result = command_conforms(issue_intent(), issue_command(), issue_policy(), empty)
    assert result is ConformanceResult.NON_CONFORMANT


def test_mismatch_dominates_missing_axis() -> None:
    """A definite mismatch on one axis dominates a missing value on another => NON_CONFORMANT."""
    command = issue_command(
        {**AUTHORIZED_AXES, ConformanceAxis.SIDE: "SELL", ConformanceAxis.ACCOUNT: None}
    )
    result = command_conforms(issue_intent(), command, issue_policy(), issue_envelope())
    assert result is ConformanceResult.NON_CONFORMANT


def test_surplus_axis_outside_envelope_is_non_conformant() -> None:
    """(canary - MAJOR-1) A command declaring POST_ONLY outside the closed envelope => NON_CONFORMANT."""
    surplus = issue_command({**AUTHORIZED_AXES, ConformanceAxis.POST_ONLY: "YES"})
    result = command_conforms(issue_intent(), surplus, issue_policy(), issue_envelope())
    assert result is ConformanceResult.NON_CONFORMANT


def test_command_declaring_subset_of_axes_is_unknown_not_surplus() -> None:
    """(direction check) A command omitting an authorized axis entirely => UNKNOWN (not surplus)."""
    subset: dict[ConformanceAxis, str | None] = {
        k: v for k, v in AUTHORIZED_AXES.items() if k is not ConformanceAxis.ACCOUNT
    }
    result = command_conforms(
        issue_intent(), issue_command(subset), issue_policy(), issue_envelope()
    )
    assert result is ConformanceResult.UNKNOWN


def test_duplicate_axis_on_command_is_non_conformant() -> None:
    """(canary - MAJOR-1 §14 line 406) A command repeating SIDE (BUY + BUY) => NON_CONFORMANT."""
    dup = issue_command(axis_bindings=_with_duplicate_side())
    result = command_conforms(issue_intent(), dup, issue_policy(), issue_envelope())
    assert result is ConformanceResult.NON_CONFORMANT


def test_duplicate_axis_with_conflicting_values_is_non_conformant() -> None:
    """(§14 line 406) A command with SIDE=BUY + SIDE=SELL (conflicting duplicate) => NON_CONFORMANT."""
    conflicting = _full_bindings() + (
        AxisBinding(axis=ConformanceAxis.SIDE, value="SELL"),
    )
    dup = issue_command(axis_bindings=conflicting)
    result = command_conforms(issue_intent(), dup, issue_policy(), issue_envelope())
    assert result is ConformanceResult.NON_CONFORMANT


def test_duplicate_axis_on_intent_is_non_conformant() -> None:
    """(canary - §14 line 406 symmetry) An intent repeating a semantic axis => NON_CONFORMANT."""
    dup_intent = issue_intent(authorized_axis_bindings=_with_duplicate_side())
    result = command_conforms(
        dup_intent, issue_command(), issue_policy(), issue_envelope()
    )
    assert result is ConformanceResult.NON_CONFORMANT


def test_duplicate_axis_on_envelope_is_non_conformant() -> None:
    """(canary - §10 line 284 ambiguity) An envelope repeating an authorized axis => NON_CONFORMANT."""
    dup_env = issue_envelope(authorized_axis_bindings=_with_duplicate_side())
    result = command_conforms(issue_intent(), issue_command(), issue_policy(), dup_env)
    assert result is ConformanceResult.NON_CONFORMANT


def test_clean_command_still_conformant_after_guards() -> None:
    """(양성측) The guards do not break the clean path — an exact-match command stays CONFORMANT."""
    result = command_conforms(
        issue_intent(), issue_command(), issue_policy(), issue_envelope()
    )
    assert result is ConformanceResult.CONFORMANT
