"""Truthy-sentinel structural seal regression (design #14 §4.7(나)/§2.2(1)/M1 — the critical seal)."""

from __future__ import annotations

import pytest
from tos.ioc import (
    ConformanceResult,
    command_conforms,
    economic_effect_dominated,
    no_silent_widening,
)
from tos.rcl import CapacityVector

from ._ioc_strategies import (
    AUTHORIZED_AXES,
    issue_command,
    issue_envelope,
    issue_intent,
    issue_policy,
)


@pytest.mark.parametrize(
    "result",
    [
        ConformanceResult.CONFORMANT,
        ConformanceResult.NON_CONFORMANT,
        ConformanceResult.UNKNOWN,
    ],
)
def test_bool_raises_for_every_member(result: ConformanceResult) -> None:
    """(§4.7 canary iii-a) bool(r) raises TypeError for CONFORMANT / NON_CONFORMANT / UNKNOWN."""
    with pytest.raises(TypeError):
        bool(result)


@pytest.mark.parametrize(
    "result",
    [
        ConformanceResult.CONFORMANT,
        ConformanceResult.NON_CONFORMANT,
        ConformanceResult.UNKNOWN,
    ],
)
def test_if_result_would_raise_not_fail_open(result: ConformanceResult) -> None:
    """(§4.7 catastrophic-seal) A bare `if result:` raises rather than silently reading truthy."""
    with pytest.raises(TypeError):
        if result:  # noqa: SIM102 — the point is that this must raise, not pass
            pass


def test_is_comparison_works_both_ways() -> None:
    """(§4.7 canary iii-b) `is` identity comparison is intact in both directions."""
    assert ConformanceResult.CONFORMANT is ConformanceResult.CONFORMANT
    assert ConformanceResult.NON_CONFORMANT is not ConformanceResult.CONFORMANT
    assert ConformanceResult.UNKNOWN is not ConformanceResult.CONFORMANT
    assert ConformanceResult.CONFORMANT.value == "CONFORMANT"


def test_is_conformant_gate_rejects_denials() -> None:
    """(§4.7 consume gate) Only CONFORMANT passes `result is ConformanceResult.CONFORMANT`."""
    conformant = command_conforms(
        issue_intent(), issue_command(), issue_policy(), issue_envelope()
    )
    non_conformant = command_conforms(
        issue_intent(),
        issue_command({**AUTHORIZED_AXES, list(AUTHORIZED_AXES)[0]: "WRONG"}),
        issue_policy(),
        issue_envelope(),
    )
    unknown = command_conforms(issue_intent(), issue_command(), None, issue_envelope())

    assert (conformant is ConformanceResult.CONFORMANT) is True
    assert (non_conformant is ConformanceResult.CONFORMANT) is False
    assert (unknown is ConformanceResult.CONFORMANT) is False


def test_bool_predicate_is_true_gate() -> None:
    """(§4.7(나)) A `bool | None` predicate is gated `is True` — None / False both reject."""
    dominated = economic_effect_dominated(
        CapacityVector(components=()),
        CapacityVector(components=()),
    )
    assert (dominated is True) is False

    widened = no_silent_widening(
        exact_bounded_within_envelope=None, every_dependent_gate_evaluated=True
    )
    assert (widened is True) is False
