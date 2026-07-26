"""decision_binding_exact + no_decision_union — exact binding / no widen (design #19 §5.4; VTG-EV-006).

Every stage binds the same exact decision identity; a mutated field breaks the chain; a shape
maps to exactly one decision (no union / widen).

Regime tag: predicate / model substrate only; VTG-EV-006 NOT_IMPLEMENTED (`/3` + Security
residue); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.venue import (
    BindingChain,
    StageBinding,
    decision_binding_exact,
    no_decision_union,
)

from ._venue_strategies import clean_binding_chain


def test_exact_chain_is_bound_positive_side() -> None:
    """(§16 canary b) A chain binding the exact decision identity on every stage holds."""
    assert decision_binding_exact(clean_binding_chain()) is True


def test_mutated_stage_id_breaks_the_chain() -> None:
    """(§16 line 377) A stage binding a different decision id is rejected (mutation => new chain)."""
    chain = clean_binding_chain()
    broken = chain.model_copy(
        update={
            "stage_bindings": (
                chain.stage_bindings[0],
                StageBinding(
                    stage="egress",
                    bound_decision_id="venue-dec-OTHER",
                    bound_decision_digest="venue-dec-digest",
                ),
            )
        }
    )
    assert decision_binding_exact(broken) is False


def test_mutated_stage_digest_breaks_the_chain() -> None:
    """(§14 line 342-343) A stage binding a different digest (mutation) is rejected."""
    chain = clean_binding_chain()
    broken = chain.model_copy(
        update={
            "stage_bindings": (
                StageBinding(
                    stage="approval",
                    bound_decision_id="venue-dec-1",
                    bound_decision_digest="DIGEST-OTHER",
                ),
            )
        }
    )
    assert decision_binding_exact(broken) is False


def test_missing_identity_is_rejected() -> None:
    """(∅) A chain with a null decision id / digest fails closed."""
    assert (
        decision_binding_exact(
            BindingChain(decision_id=None, decision_digest="d", stage_bindings=())
        )
        is False
    )


def test_empty_stage_bindings_is_rejected() -> None:
    """(§4.7 ∅) An empty stage set is not "exact binding" — fail-closed."""
    empty = BindingChain(
        decision_id="venue-dec-1", decision_digest="d", stage_bindings=()
    )
    assert decision_binding_exact(empty) is False


def test_none_chain_is_rejected() -> None:
    """(∅) A None chain proves nothing."""
    assert decision_binding_exact(None) is False


def test_no_union_exactly_one_decision_passes() -> None:
    """(§14 line 343) Exactly one decision digest for one shape passes (no union)."""
    assert no_decision_union(frozenset({"venue-dec-digest"})) is True


def test_no_union_multiple_decisions_is_rejected() -> None:
    """(§14 line 343) A multi-digest set (a union / widen attempt) is rejected."""
    assert no_decision_union(frozenset({"dec-a", "dec-b"})) is False


def test_no_union_empty_set_is_rejected() -> None:
    """(§4.7 ∅) An empty decision set (nothing bound) fails closed."""
    assert no_decision_union(frozenset()) is False
