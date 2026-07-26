"""§5.6 statement coverage, source independence, absence-as-negative-evidence (PTF-EV-008).

Both directions of all three guards:

* **coverage** — each of the five set axes is individually load-bearing; a manifest that
  expects nothing is ``False`` (the ∅ guard that stops "perfect coverage of nothing"); record
  counts must match exactly; a missing interval, an absent revision / cutoff / period
  boundary, or a ``PRELIMINARY`` classification all fail closed;
* **independence** — an empty declared dependency set on **either** side is ``False``
  (``∅.isdisjoint(x)`` is vacuously ``True``); a shared book / parser / administrator /
  transport is common mode; only disjoint declared sets corroborate;
* **absence** — the four-way positive conjunction, with each premise individually load
  bearing, and the explicit assertion that **no time-based signal exists** (design #24 M6:
  ``correction_horizon_passed`` was exactly the PTF-INV-004-forbidden "cutoff passage"
  signal, and the parameter is the correction-**semantics** one instead).

[PTF-EV-008 coordinate; ``/2``, ``/3``, ``+Broker``, and ``+Security`` remain open. Closing
PTF-EV = 0.]
"""

from __future__ import annotations

import inspect

import pytest
from hypothesis import given
from tos.posttrade import (
    STATEMENT_COVERAGE_SET_AXES,
    StatementClass,
    absence_is_negative_evidence_only,
    statement_coverage_complete,
    statement_sources_independent,
)

from ._posttrade_strategies import (
    DEPENDENCY_SETS,
    FORGED_FLAG,
    TRIBOOL,
    clean_statement_manifest,
)

# --- §19 line 443 statement_coverage_complete --------------------------------


def test_a_complete_final_manifest_passes() -> None:
    """(positive side) Every expected set received, counts equal, identity complete."""
    assert statement_coverage_complete(clean_statement_manifest()) is True


def test_a_revised_manifest_can_also_carry_complete_coverage() -> None:
    """(§19 line 442) A restatement is a first-class class, not a defect."""
    assert (
        statement_coverage_complete(
            clean_statement_manifest(statement_class=StatementClass.REVISED)
        )
        is True
    )


def test_an_absent_manifest_proves_nothing() -> None:
    """(fail-closed) No manifest ⇒ no coverage."""
    assert statement_coverage_complete(None) is False


@pytest.mark.parametrize(
    ("expected_field", "received_field"), STATEMENT_COVERAGE_SET_AXES
)
def test_each_coverage_axis_is_individually_load_bearing(
    expected_field: str, received_field: str
) -> None:
    """(§19 line 443) Truncating any one of the five axes is incomplete coverage."""
    truncated = clean_statement_manifest(**{received_field: frozenset()})
    assert statement_coverage_complete(truncated) is False
    del expected_field


def test_a_manifest_that_expects_nothing_proves_nothing() -> None:
    """(∅ guard, §4.8 row 8) ``∅ <= received`` holds on all five axes — the vacuous pass."""
    empty = clean_statement_manifest(
        expected_pages=frozenset(),
        expected_files=frozenset(),
        expected_sections=frozenset(),
        expected_cursors=frozenset(),
        expected_checksums=frozenset(),
    )
    assert statement_coverage_complete(empty) is False


def test_receiving_more_than_expected_is_still_coverage() -> None:
    """(positive side) Coverage is ``expected <= received``, not equality of the sets."""
    generous = clean_statement_manifest(
        received_pages=frozenset({"p1", "p2", "p3"}),
    )
    assert statement_coverage_complete(generous) is True


@pytest.mark.parametrize(
    ("expected_count", "received_count"), [(2, 1), (1, 2), (None, 2), (2, None)]
)
def test_record_counts_must_be_present_and_equal(
    expected_count: int | None, received_count: int | None
) -> None:
    """(§19 line 443, sixth axis) A count mismatch or an absent count is incomplete."""
    manifest = clean_statement_manifest(
        expected_record_count=expected_count, received_record_count=received_count
    )
    assert statement_coverage_complete(manifest) is False


def test_a_missing_interval_is_incomplete_coverage() -> None:
    """(§19 line 443) A declared gap is a gap."""
    assert (
        statement_coverage_complete(
            clean_statement_manifest(missing_intervals=("GAP-1",))
        )
        is False
    )


@pytest.mark.parametrize(
    "field", ["source_identity", "period_start", "period_end", "revision", "cutoff"]
)
def test_each_identity_component_is_individually_load_bearing(field: str) -> None:
    """(§19 line 443) Revision, cutoff, and period boundary must all be present."""
    assert (
        statement_coverage_complete(clean_statement_manifest(**{field: None})) is False
    )


def test_a_preliminary_statement_is_never_complete_coverage() -> None:
    """(§19 line 450) A preliminary statement is subject to restatement by construction."""
    assert (
        statement_coverage_complete(
            clean_statement_manifest(statement_class=StatementClass.PRELIMINARY)
        )
        is False
    )


def test_an_undeclared_statement_class_fails_closed() -> None:
    """(§19 line 442) An unclassified statement has not declared what it is."""
    assert (
        statement_coverage_complete(clean_statement_manifest(statement_class=None))
        is False
    )


def test_final_alone_is_not_sufficient() -> None:
    """(§19 line 448) "``FINAL`` ... does not make it unconditional truth outside the
    approved proof recipe" — the whole conjunction still has to hold."""
    final_but_truncated = clean_statement_manifest(
        statement_class=StatementClass.FINAL, received_pages=frozenset({"p1"})
    )
    assert final_but_truncated.statement_class is StatementClass.FINAL
    assert statement_coverage_complete(final_but_truncated) is False


# --- §19 line 445 statement_sources_independent ------------------------------


def test_disjoint_declared_dependencies_corroborate() -> None:
    """(positive side) Two sources with no shared book / parser / administrator / transport."""
    assert (
        statement_sources_independent(
            frozenset({"book-a", "transport-a"}), frozenset({"book-b", "transport-b"})
        )
        is True
    )


@pytest.mark.parametrize("shared", ["book", "parser", "administrator", "transport"])
def test_any_shared_dependency_is_common_mode(shared: str) -> None:
    """(§19 line 445 / PTF-INV-014) One shared dependency of any kind defeats independence."""
    assert (
        statement_sources_independent(
            frozenset({shared, "own-a"}), frozenset({shared, "own-b"})
        )
        is False
    )


def test_an_undeclared_dependency_set_proves_no_independence() -> None:
    """(∅ guard, both sides) ``∅.isdisjoint(anything)`` is vacuously ``True`` — the exact
    pass PTF-INV-014 is about. A source that declares nothing has not been shown to be
    independent, it has merely not been described."""
    assert statement_sources_independent(frozenset(), frozenset({"book-b"})) is False
    assert statement_sources_independent(frozenset({"book-a"}), frozenset()) is False
    assert statement_sources_independent(frozenset(), frozenset()) is False


@given(first=DEPENDENCY_SETS, second=DEPENDENCY_SETS)
def test_independence_is_non_empty_disjointness(
    first: frozenset[str], second: frozenset[str]
) -> None:
    """(§5.6) The proposition, over arbitrary declared sets."""
    expected = bool(first) and bool(second) and first.isdisjoint(second)
    assert statement_sources_independent(first, second) is expected


def test_independence_is_symmetric() -> None:
    """(structural) Swapping the two sources cannot change the verdict."""
    first = frozenset({"book-a"})
    second = frozenset({"book-a", "parser-b"})
    assert statement_sources_independent(
        first, second
    ) is statement_sources_independent(second, first)


# --- §19 line 448 absence_is_negative_evidence_only --------------------------


def test_the_four_way_conjunction_admits_absence_as_negative_evidence() -> None:
    """(positive side) Exact coverage **and** correction semantics **and** source capability
    positively supporting a proven absence."""
    assert absence_is_negative_evidence_only(True, True, True, True) is True


@pytest.mark.parametrize("position", range(4))
@pytest.mark.parametrize("bad", [False, None])
def test_each_premise_is_individually_load_bearing(
    position: int, bad: bool | None
) -> None:
    """(§19 line 448) Any one premise unproven ⇒ the absence stays UNKNOWN."""
    premises: list[bool | None] = [True, True, True, True]
    premises[position] = bad
    assert absence_is_negative_evidence_only(*premises) is False


def test_an_unproven_absence_is_not_an_absence() -> None:
    """(PTF-INV-004) ``line_item_absent is None`` means "we do not know" — the antecedent
    fails and the answer is UNKNOWN, never "no obligation"."""
    assert absence_is_negative_evidence_only(None, True, True, True) is False


@given(
    absent=TRIBOOL,
    coverage=TRIBOOL,
    semantics=TRIBOOL,
    capability=TRIBOOL,
)
def test_absence_gate_is_exactly_the_four_way_positive_conjunction(
    absent: bool | None,
    coverage: bool | None,
    semantics: bool | None,
    capability: bool | None,
) -> None:
    """(§5.6) The proposition, over the full tri-bool cube."""
    expected = (
        absent is True and coverage is True and semantics is True and capability is True
    )
    assert (
        absence_is_negative_evidence_only(absent, coverage, semantics, capability)
        is expected
    )


@given(forged=FORGED_FLAG)
def test_only_real_trues_open_the_absence_gate(forged: object) -> None:
    """(polarity) Truthy **and falsy** non-``bool`` values pass none of the four gates."""
    assert absence_is_negative_evidence_only(
        forged, True, True, True
    ) is (  # type: ignore[arg-type]
        forged is True
    )


def test_no_time_based_signal_exists_in_the_absence_gate() -> None:
    """(design #24 M6 / PTF-INV-004) The gate takes **correction semantics**, not a horizon.

    ADR line 164: "cutoff passage ... never proves that an obligation does not exist". A
    ``correction_horizon_passed`` parameter would have been exactly that forbidden signal, so
    the signature must not contain one — nor any other time / age / deadline parameter.
    """
    parameters = set(inspect.signature(absence_is_negative_evidence_only).parameters)
    assert parameters == {
        "line_item_absent",
        "coverage_complete",
        "correction_semantics_support",
        "source_capability_supports",
    }
    for forbidden in (
        "horizon",
        "elapsed",
        "deadline",
        "cutoff",
        "clock",
        "timestamp",
        "duration",
        "_age",
        "expiry",
    ):
        assert not any(
            forbidden in name for name in parameters
        ), f"a {forbidden!r} parameter would reintroduce the PTF-INV-004 time signal"
