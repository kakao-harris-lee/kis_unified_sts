"""Group reconcile + the two opposite-polarity empty sets (design #30 §4.4; the #22 MAJOR-1 seal).

Three disciplines:

* **all entries, never the first** — the coverage judgement and the determinism relation are
  order-independent and conservative over the whole group;
* **no favorable union** (§9 line 292) — a wider claim cannot be assembled from narrow parts, and a
  completeness *score* can never replace item-level closure;
* **MAX generation** (§5.5; §12 line 337) — a group's reconciled fence is the newest generation, and a
  single unknown makes the whole group's fence unprovable rather than silently maximising over the
  known subset.

Plus the contract's signature ∅ rule (§4.4 / §10.2-⑨): the same ``()`` is **denying** for the coverage
completeness predicate (after checking the applicable side) and **valid ``True``** for the determinism
relation, because the two are different kinds of predicate.

Regime tag: predicate substrate only; closes **no** STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.stm import (
    AggregateConformanceResult,
    CoverageDimension,
    critical_coverage_complete_or_gap,
    evaluation_is_deterministic,
    max_monitor_generation,
    monitor_generation_advances,
    no_self_exemption,
    stale_writer_fenced,
)

from ._stm_strategies import (
    CLEAN_APPLICABLE_DIMENSIONS,
    CLEAN_APPLICABLE_OBLIGATIONS,
    CLEAN_ASSUMPTION_OBLIGATION,
    CLEAN_KEY_B,
    CLEAN_OBLIGATION,
    CLEAN_SUBMITTED_ASSUMPTION_IDS,
    clean_coverage_item,
    clean_coverage_manifest,
    clean_evaluation,
    clean_evaluation_corpus,
)


def _judge(manifest, obligations=None, dimensions=None) -> bool:
    return critical_coverage_complete_or_gap(
        manifest,
        CLEAN_APPLICABLE_OBLIGATIONS if obligations is None else obligations,
        CLEAN_APPLICABLE_DIMENSIONS if dimensions is None else dimensions,
        CLEAN_SUBMITTED_ASSUMPTION_IDS,
    )


# --- all entries, never the first -----------------------------------------


@given(order=st.permutations(range(4)))
def test_a_single_bad_item_sinks_the_group_in_any_position(order: list[int]) -> None:
    """(#22 MAJOR-1) A conservative entry dominates wherever it sits — never first-entry."""
    items = [
        clean_coverage_item(),
        clean_coverage_item(obligation_ref=CLEAN_ASSUMPTION_OBLIGATION),
        clean_coverage_item(obligation_ref="obl-spare"),
        clean_coverage_item(obligation_ref="obl-bad", excluded=True),
    ]
    manifest = clean_coverage_manifest(coverage_items=tuple(items[i] for i in order))
    assert no_self_exemption(manifest) is False
    assert (
        _judge(
            manifest,
            obligations=frozenset(
                {CLEAN_OBLIGATION, CLEAN_ASSUMPTION_OBLIGATION, "obl-spare"}
            ),
        )
        is False
    )


@given(order=st.permutations(range(3)))
def test_a_clean_group_clears_in_any_order(order: list[int]) -> None:
    """(both-ways +) Order independence holds on the clearing side too."""
    corpus = clean_evaluation_corpus()
    assert evaluation_is_deterministic(tuple(corpus[i] for i in order)) is True


# --- no favorable union ----------------------------------------------------


def test_two_narrow_manifests_cannot_be_unioned_into_broader_coverage() -> None:
    """(§9 line 292) Each manifest is judged against the whole applicable set, never a favorable slice.

    Two manifests that each cover exactly half the applicable obligations both deny; there is no
    combining operation in the surface that could turn the pair into a pass.
    """
    left = clean_coverage_manifest(
        coverage_items=(clean_coverage_item(),), submitted_monitored_assumptions=()
    )
    right = clean_coverage_manifest(
        coverage_items=(
            clean_coverage_item(obligation_ref=CLEAN_ASSUMPTION_OBLIGATION),
        )
    )
    assert _judge(left) is False
    assert _judge(right) is False
    combined = clean_coverage_manifest(
        coverage_items=left.coverage_items + right.coverage_items
    )
    assert _judge(combined) is True  # only a genuinely complete manifest clears


def test_a_narrow_dependency_closure_cannot_be_unioned_across_items() -> None:
    """(§9 item 2) Every mapped item must carry the applicable closure — not the union of all items."""
    manifest = clean_coverage_manifest(
        coverage_items=(
            clean_coverage_item(
                dependency_closure_dimensions=frozenset({CoverageDimension.ACCOUNT})
            ),
            clean_coverage_item(
                obligation_ref=CLEAN_ASSUMPTION_OBLIGATION,
                dependency_closure_dimensions=frozenset({CoverageDimension.CLOCK}),
            ),
        )
    )
    both = frozenset({CoverageDimension.ACCOUNT, CoverageDimension.CLOCK})
    assert _judge(manifest, dimensions=both) is False


def test_a_completeness_score_never_substitutes_for_closure() -> None:
    """(§9 line 292) The score coordinate is negative polarity and cannot buy a pass."""
    assert _judge(clean_coverage_manifest(coverage_score_present=True)) is False


# --- MAX generation --------------------------------------------------------


def test_the_reconciled_fence_is_the_newest_generation() -> None:
    """(§5.5; §4.4) MAX, never first."""
    assert max_monitor_generation((3, 9, 5)) == 9
    assert max_monitor_generation((9, 3, 5)) == 9


@given(
    generations=st.lists(st.integers(min_value=0, max_value=50), min_size=1, max_size=6)
)
def test_max_generation_is_order_independent(generations: list[int]) -> None:
    """(§4.4) The reconciled fence does not depend on entry order."""
    assert max_monitor_generation(tuple(generations)) == max_monitor_generation(
        tuple(reversed(generations))
    )
    assert max_monitor_generation(tuple(generations)) == max(generations)


def test_one_unknown_generation_makes_the_whole_group_unprovable() -> None:
    """(fail-closed) A single ``None`` denies the group rather than maximising over the known subset."""
    assert max_monitor_generation((3, None, 9)) is None
    assert max_monitor_generation(()) is None


def test_generation_advance_requires_a_strict_proof() -> None:
    """(§5.5) Equal, regressing or unknown generations fail closed."""
    assert monitor_generation_advances(3, 9) is True
    assert monitor_generation_advances(9, 3) is False
    assert monitor_generation_advances(5, 5) is False
    assert monitor_generation_advances(None, 9) is False
    assert monitor_generation_advances(3, None) is False


def test_a_stale_writer_is_fenced_only_on_proof() -> None:
    """(§12 line 337; STM-INV-016 line 219) An unproven pair is not a clearance either."""
    assert stale_writer_fenced(9, 3) is True
    assert stale_writer_fenced(3, 9) is False
    assert stale_writer_fenced(5, 5) is False
    assert stale_writer_fenced(None, 3) is False


# --- the two opposite-polarity empty sets ---------------------------------


def test_the_completeness_empty_set_checks_the_applicable_side_first() -> None:
    """(§4.4 left) ∅ coverage denies against a non-empty applicable set, clears against an empty one."""
    empty = clean_coverage_manifest(
        coverage_items=(), submitted_monitored_assumptions=()
    )
    assert _judge(empty) is False
    assert (
        critical_coverage_complete_or_gap(empty, frozenset(), frozenset(), frozenset())
        is True
    )


def test_the_relational_empty_set_is_valid_true() -> None:
    """(§4.4 right) ∅ evaluations means no conflicting pair — a sound vacuous ``True``."""
    assert evaluation_is_deterministic(()) is True


def test_the_two_empty_sets_have_opposite_polarity() -> None:
    """(§4.4 signature rule / §10.2-⑨) The same ``()`` denies on the left and clears on the right."""
    empty_manifest = clean_coverage_manifest(
        coverage_items=(), submitted_monitored_assumptions=()
    )
    assert _judge(empty_manifest) is False
    assert evaluation_is_deterministic(()) is True


def test_the_relational_true_asserts_nothing_about_existence() -> None:
    """(§4.4) The relation's ``True`` never claims an evaluation exists — that is the presence gate."""
    conflicting = (
        clean_evaluation(),
        clean_evaluation(result=AggregateConformanceResult.RESTRICTED),
    )
    assert evaluation_is_deterministic(()) is True
    assert evaluation_is_deterministic(conflicting) is False
    # a corpus that exists and agrees is the only shape that means "checked and consistent"
    assert (
        evaluation_is_deterministic(
            (
                clean_evaluation(),
                clean_evaluation(
                    evaluator_digest=CLEAN_KEY_B[0],
                    canonical_input_digest=CLEAN_KEY_B[1],
                ),
            )
        )
        is True
    )
