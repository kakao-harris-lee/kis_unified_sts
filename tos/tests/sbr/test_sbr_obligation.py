"""obligation_graph_closed — closure + acyclicity both-ways + property (design #17 §5.2; SBR-EV-004).

Regime tag: predicate / model substrate only; SBR-EV-004 NOT_IMPLEMENTED (`/3` residue);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from hypothesis import given
from tos.sbr import ObligationResult, obligation_graph_closed

from ._sbr_strategies import acyclic_obligation_set, clean_obligation_set, obligation


def test_clean_acyclic_all_satisfied_is_closed_positive_side() -> None:
    """(§5.2 positive) An acyclic, all-SATISFIED, complete-prerequisite set is closed."""
    assert obligation_graph_closed(clean_obligation_set()) is True


def test_empty_set_is_not_closed() -> None:
    """(∅ / §4.7) An empty obligation set is not "nothing to prove" — the minimum set is mandatory."""
    assert obligation_graph_closed(frozenset()) is False


def test_dangling_prerequisite_is_not_closed() -> None:
    """(§13 line 372) A prerequisite not in the set (dangling) => not closed."""
    graph = frozenset({obligation("a", prerequisites=("missing",))})
    assert obligation_graph_closed(graph) is False


def test_cycle_is_not_closed() -> None:
    """(§13 line 372) A prerequisite cycle => not closed (topological sort fails)."""
    graph = frozenset(
        {obligation("a", prerequisites=("b",)), obligation("b", prerequisites=("a",))}
    )
    assert obligation_graph_closed(graph) is False


def test_non_satisfied_result_is_not_closed() -> None:
    """(§2.2(5)) Only SATISFIED passes — UNKNOWN / FAILED / TIMED_OUT / CONFLICTED / MISSING_SOURCE fail."""
    for result in (
        ObligationResult.UNKNOWN,
        ObligationResult.FAILED,
        ObligationResult.TIMED_OUT,
        ObligationResult.CONFLICTED,
        ObligationResult.MISSING_SOURCE,
    ):
        graph = frozenset(
            {
                obligation(
                    "a",
                    result=result,
                    acceptable=(ObligationResult.SATISFIED, result),
                )
            }
        )
        assert obligation_graph_closed(graph) is False


def test_result_outside_acceptable_set_is_not_closed() -> None:
    """(§13 line 346) A SATISFIED result not declared acceptable => not closed (fail-closed)."""
    graph = frozenset(
        {
            obligation(
                "a",
                result=ObligationResult.SATISFIED,
                acceptable=(ObligationResult.FAILED,),
            )
        }
    )
    assert obligation_graph_closed(graph) is False


def test_self_satisfy_is_forbidden() -> None:
    """(§13 line 372) An independent-review obligation not independently reviewed => not closed."""
    unreviewed = frozenset(
        {
            obligation(
                "a",
                independent_review_required=True,
                independent_review_satisfied=None,
            )
        }
    )
    assert obligation_graph_closed(unreviewed) is False
    reviewed = frozenset(
        {
            obligation(
                "a",
                independent_review_required=True,
                independent_review_satisfied=True,
            )
        }
    )
    assert obligation_graph_closed(reviewed) is True


def test_duplicate_id_is_not_closed() -> None:
    """(both-ways set comparison) Two obligations with the same id => not closed (no de-dup)."""
    graph = frozenset(
        {
            obligation("a", result=ObligationResult.SATISFIED),
            obligation("a", prerequisites=("a",)),
        }
    )
    # frozenset keeps both distinct records (different content) but they share obligation_id "a".
    assert obligation_graph_closed(graph) is False


@given(acyclic_obligation_set())
def test_property_acyclic_all_satisfied_is_closed(
    obligations: frozenset,
) -> None:
    """(property) A genuinely-acyclic, complete, all-SATISFIED set is always closed (no escape)."""
    assert obligation_graph_closed(obligations) is True


@given(acyclic_obligation_set())
def test_property_injecting_a_cycle_breaks_closure(
    obligations: frozenset,
) -> None:
    """(property, both-ways) Adding a back-edge that forms a cycle always breaks closure."""
    ids = sorted(o.obligation_id for o in obligations if o.obligation_id is not None)
    if len(ids) < 2:
        return
    # Re-point the FIRST obligation's prerequisite to the LAST id and the last to the first =>
    # guaranteed cycle between the two endpoints.
    first, last = ids[0], ids[-1]
    rebuilt = set()
    for o in obligations:
        if o.obligation_id == first:
            rebuilt.add(o.model_copy(update={"prerequisite_ids": frozenset({last})}))
        elif o.obligation_id == last:
            rebuilt.add(o.model_copy(update={"prerequisite_ids": frozenset({first})}))
        else:
            rebuilt.add(o)
    assert obligation_graph_closed(frozenset(rebuilt)) is False
