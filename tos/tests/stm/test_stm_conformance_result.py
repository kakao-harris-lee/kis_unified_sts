"""§12 aggregate conformance result — 4-token drift + the ``is CONFORMING`` gate (design #30 §7.2).

``AggregateConformanceResult`` is the truthy-sentinel's **first-priority** defence (design #30 §4.2):
``RESTRICTED`` / ``NON_CONFORMING`` / ``UNKNOWN`` all "deny dependent new risk for the affected scope"
(§12 line 335) and all three are non-empty strings, so ``if snapshot.aggregate_result:`` would read a
denial as a go. This file locks the four-token transcription against the ADR, asserts the mandated
positive-identity gate, and asserts that even ``CONFORMING`` grants nothing (§1 line 25).

Regime tag: predicate substrate only; closes **no** STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
from tos.stm import (
    DENYING_AGGREGATE_RESULTS,
    AggregateConformanceResult,
    all_false_monitoring_authority,
    conformance_requires_complete_current_valid,
)

from ._stm_strategies import clean_snapshot


def test_the_four_token_anchor_is_exact() -> None:
    """(§7.2 drift, appendix A) §12 line 335 names exactly four results (過 0 · 不 0)."""
    assert {member.value for member in AggregateConformanceResult} == {
        "CONFORMING",
        "RESTRICTED",
        "NON_CONFORMING",
        "UNKNOWN",
    }
    assert len(AggregateConformanceResult) == 4


def test_the_denying_set_is_derived_and_complete() -> None:
    """(§12 line 335) Everything but ``CONFORMING`` denies dependent new risk — derived, never listed."""
    assert (
        frozenset(AggregateConformanceResult) - {AggregateConformanceResult.CONFORMING}
        == DENYING_AGGREGATE_RESULTS
    )
    assert len(DENYING_AGGREGATE_RESULTS) == 3


@pytest.mark.parametrize("result", sorted(AggregateConformanceResult))
def test_no_result_is_truthy_testable(result: AggregateConformanceResult) -> None:
    """(§4.2) ``bool(result)`` raises — a denial can never be misread as a go."""
    with pytest.raises(TypeError):
        bool(result)


def test_the_mandated_gate_is_positive_identity() -> None:
    """(§4.2) Only ``result is CONFORMING`` clears; every other member is denial."""
    assert (
        AggregateConformanceResult.CONFORMING is AggregateConformanceResult.CONFORMING
    )
    for denial in DENYING_AGGREGATE_RESULTS:
        assert denial is not AggregateConformanceResult.CONFORMING


def test_conforming_grants_nothing() -> None:
    """(§1 line 25) Even a ``CONFORMING`` snapshot carries an all-false authority block."""
    snapshot = clean_snapshot()
    assert snapshot.aggregate_result is AggregateConformanceResult.CONFORMING
    assert all_false_monitoring_authority(snapshot.authority_effect) is True


def test_a_clean_conforming_snapshot_is_structurally_backed() -> None:
    """(both-ways +, §12 line 335) A complete, current, valid snapshot clears the supporting gate."""
    assert conformance_requires_complete_current_valid(clean_snapshot()) is True


@pytest.mark.parametrize("result", sorted(DENYING_AGGREGATE_RESULTS))
def test_a_non_conforming_snapshot_needs_no_backing(
    result: AggregateConformanceResult,
) -> None:
    """(§12 line 335) The gate judges the honesty of a ``CONFORMING`` claim, not the desirability."""
    snapshot = clean_snapshot(
        aggregate_result=result,
        monitor_results=(),
        source_continuity_present=None,
        active_violations=("violation-a",),
    )
    assert conformance_requires_complete_current_valid(snapshot) is True


def test_an_unjudged_snapshot_denies() -> None:
    """(fail-closed) A snapshot with no aggregate result proves nothing."""
    snapshot = clean_snapshot(aggregate_result=None)
    assert conformance_requires_complete_current_valid(snapshot) is False


def test_absent_snapshot_denies() -> None:
    """(∅-seal) ``None`` is undecidable, therefore denied."""
    assert conformance_requires_complete_current_valid(None) is False
