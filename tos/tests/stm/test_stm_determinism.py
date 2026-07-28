"""**Mandated L1 property test #2** — ``deterministic_evaluation_bound_integrity`` (STM-EV-005; §11).

design #30 §13: STM-AC-005 ↔ STM-EV-005 is the second of only two rows with an ``EV-L1`` slice, and this
file is its mandated model / property verification. **Determinism is the core** (design #30 §5.2): stm
does not run an evaluator, so the L1-decidable form of §11 line 312's "deterministic for identical
inputs" is the *relation* over the evaluation record corpus — identical
``(evaluator_digest, canonical_input_digest)`` ⇒ identical judgement. That is the direct realization of
VER-002-001's EV-L1 definition ("property-based testing, and deterministic simulation").

It verifies the L1-decidable part and **closes nothing**: STM-EV-005 is ``EV-L1/3+Security``, so the
``/3`` integration axis plus the whole ``+Security`` evaluator-differential / parser-drift /
threshold-weakening resistance axis remain (§30 gate 4).

The four **mandated fixtures** design #30 §5.2 names are each asserted explicitly: "empty corpus +
non-empty required ⇒ ``False``", "an evaluation referencing an unsubmitted bound ⇒ ``False``", "same key
different result ⇒ ``False``", and "hard-approved + weak-implemented ⇒ ``False``".

Regime tag: deterministic-evaluation predicate substrate only; closes **no** STM-EV; EV-L1-complete
claim forbidden.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.stm import (
    HARD_BOUND_KINDS,
    MALFORMED_NUMERIC_STATES,
    NEUTRAL_BOUND_KINDS,
    WEAK_BOUND_KINDS,
    AggregateConformanceResult,
    BoundSemanticKind,
    NumericInputState,
    bound_integrity_preserved,
    deterministic_evaluation_bound_integrity,
    evaluation_is_deterministic,
    numeric_result_not_conforming_by_default,
)

from ._stm_strategies import (
    CLEAN_APPLICABLE_BOUND_REFS,
    CLEAN_KEY_A,
    CLEAN_KEY_B,
    CLEAN_REQUIRED_EVALUATION_KEYS,
    TRIBOOL,
    clean_bound,
    clean_evaluation,
    clean_evaluation_corpus,
)


def _judge(evaluations=None, bounds=None, required=None, refs=None) -> bool:
    """Run the composite yolk against the clean coordinates unless overridden."""
    return deterministic_evaluation_bound_integrity(
        clean_evaluation_corpus() if evaluations is None else evaluations,
        (clean_bound(),) if bounds is None else bounds,
        CLEAN_REQUIRED_EVALUATION_KEYS if required is None else required,
        CLEAN_APPLICABLE_BOUND_REFS if refs is None else refs,
    )


# --- direction 1: the clean corpus clears ---------------------------------


def test_clean_corpus_clears() -> None:
    """(both-ways +) A deterministic corpus over an exactly preserved hard bound clears."""
    assert _judge() is True


def test_clean_fixture_is_not_vacuous() -> None:
    """(anti-vacuity) Two distinct keys **plus a lawful repeat** — the relation is really exercised."""
    corpus = clean_evaluation_corpus()
    assert len(corpus) == 3
    keys = [(e.evaluator_digest, e.canonical_input_digest) for e in corpus]
    assert len(set(keys)) == 2
    assert (
        keys.count(CLEAN_KEY_A) == 2
    )  # a genuine repeated key, not a singleton corpus
    assert frozenset({CLEAN_KEY_A, CLEAN_KEY_B}) == CLEAN_REQUIRED_EVALUATION_KEYS


# --- (0) presence + ∅ both-ways (the C2 seal) -----------------------------


def test_empty_corpus_against_non_empty_required_keys_denies() -> None:
    """(**C2 mandated**) "An empty query proves safety" is the fail-open STM-INV-004 line 171 names."""
    assert _judge(evaluations=()) is False


def test_empty_corpus_against_empty_required_keys_is_valid_empty() -> None:
    """(C2, #26 MAJOR-1) A scope with no required monitor is a real state — rejecting it over-seals."""
    assert (
        _judge(evaluations=(), bounds=(), required=frozenset(), refs=frozenset())
        is True
    )


def test_non_empty_corpus_against_empty_required_keys_denies_as_surplus() -> None:
    """(C2, both ways) A corpus against no requirement denies."""
    assert _judge(required=frozenset(), refs=frozenset()) is False


def test_a_missing_required_key_denies() -> None:
    """(C2) Every required key must actually be present in the corpus."""
    assert (
        _judge(
            evaluations=(clean_evaluation(),),
            required=CLEAN_REQUIRED_EVALUATION_KEYS,
        )
        is False
    )


@pytest.mark.parametrize(
    "field", ["evaluator_digest", "canonical_input_digest", "bound_binding_digest"]
)
def test_an_unattributable_evaluation_denies(field: str) -> None:
    """(fail-closed) A record missing an identifying digest cannot establish determinism."""
    corpus = clean_evaluation_corpus() + (clean_evaluation(**{field: None}),)
    assert _judge(evaluations=corpus) is False


def test_an_unattributable_bound_denies() -> None:
    """(fail-closed) A bound with no binding digest cannot be referenced or reconciled."""
    assert _judge(bounds=(clean_bound(bound_binding_digest=None),)) is False


def test_an_applicable_bound_that_was_never_submitted_denies() -> None:
    """(M4) Every applicable bound reference must be among the submitted bounds."""
    assert _judge(refs=frozenset({"bound-binding-never-submitted"})) is False


def test_evaluation_referencing_an_unsubmitted_bound_denies() -> None:
    """(**M4 mandated**) Judging under an undisclosed bound is the favorable-subset bypass (#22)."""
    corpus = clean_evaluation_corpus() + (
        clean_evaluation(
            evaluator_digest="evaluator-digest-c",
            canonical_input_digest="canonical-input-c",
            bound_binding_digest="bound-binding-undisclosed",
        ),
    )
    assert _judge(evaluations=corpus) is False


def test_a_surplus_bound_is_harmless() -> None:
    """(M4, both ways) A submitted bound nothing references is surplus, not a violation."""
    bounds = (clean_bound(), clean_bound(bound_binding_digest="bound-binding-spare"))
    assert _judge(bounds=bounds) is True


# --- (a) the determinism relation -----------------------------------------


def test_same_key_different_result_denies() -> None:
    """(**mandated**, §11 line 312) Identical inputs must yield an identical judgement."""
    corpus = (
        clean_evaluation(),
        clean_evaluation(result=AggregateConformanceResult.RESTRICTED),
    )
    assert evaluation_is_deterministic(corpus) is False


def test_same_key_different_numeric_state_denies() -> None:
    """(§11 line 316) The numeric input state is part of the judgement, not a side note."""
    corpus = (
        clean_evaluation(result=AggregateConformanceResult.UNKNOWN),
        clean_evaluation(
            result=AggregateConformanceResult.UNKNOWN,
            numeric_input_state=NumericInputState.NAN,
        ),
    )
    assert evaluation_is_deterministic(corpus) is False


def test_different_keys_may_disagree() -> None:
    """(both-ways +) Different inputs are allowed to yield different judgements."""
    corpus = (
        clean_evaluation(),
        clean_evaluation(
            evaluator_digest=CLEAN_KEY_B[0],
            canonical_input_digest=CLEAN_KEY_B[1],
            result=AggregateConformanceResult.RESTRICTED,
            numeric_input_state=NumericInputState.NAN,
        ),
    )
    assert evaluation_is_deterministic(corpus) is True


@pytest.mark.parametrize("size", [0, 1])
def test_the_relation_alone_is_vacuously_true_on_an_empty_or_singleton_corpus(
    size: int,
) -> None:
    """(§4.4 — the **opposite**-polarity ∅) No pair, no contradiction: the relation's ∅ is ``True``.

    This is the contract's signature ∅ rule (design #30 §4.4/§10.2-⑨): the same ``()`` is **valid** for
    a relational-consistency predicate and **denying** for a completeness predicate. The relation
    asserts only "no determinism violation"; it asserts nothing about existence, which is why the
    composite's presence gate exists and is tested separately above.
    """
    assert evaluation_is_deterministic(clean_evaluation_corpus()[:size]) is True


def test_the_two_empty_sets_really_have_opposite_polarity() -> None:
    """(§4.4 signature rule) The same empty corpus is ``True`` alone and ``False`` in the composite."""
    assert evaluation_is_deterministic(()) is True
    assert _judge(evaluations=()) is False


@given(order=st.permutations([0, 1, 2]))
def test_the_relation_is_order_independent(order: list[int]) -> None:
    """(§4.4 reconcile) Pairwise, over the whole corpus — never first-pair."""
    corpus = clean_evaluation_corpus()
    assert evaluation_is_deterministic(tuple(corpus[i] for i in order)) is True
    broken = (
        clean_evaluation(),
        clean_evaluation(result=AggregateConformanceResult.NON_CONFORMING),
        clean_evaluation(
            evaluator_digest=CLEAN_KEY_B[0], canonical_input_digest=CLEAN_KEY_B[1]
        ),
    )
    assert evaluation_is_deterministic(tuple(broken[i] for i in order)) is False


# --- (b) bound integrity, whitelist form ----------------------------------


def test_hard_approved_hard_implemented_identical_clears() -> None:
    """(both-ways +) Exact preservation of a hard bound clears."""
    assert bound_integrity_preserved(clean_bound()) is True


@pytest.mark.parametrize("weak", sorted(WEAK_BOUND_KINDS))
def test_hard_approved_weak_implemented_denies(weak: BoundSemanticKind) -> None:
    """(**mandated**, §11 line 314 / INV-007 line 183) None of the six weak forms may carry a hard bound."""
    assert bound_integrity_preserved(clean_bound(implemented_as_kind=weak)) is False


@pytest.mark.parametrize("neutral", sorted(NEUTRAL_BOUND_KINDS))
def test_hard_approved_neutral_implemented_denies(neutral: BoundSemanticKind) -> None:
    """(whitelist) A neutral kind is not a hard bound either — only the identical kind clears."""
    assert bound_integrity_preserved(clean_bound(implemented_as_kind=neutral)) is False


@pytest.mark.parametrize("other", sorted(HARD_BOUND_KINDS))
def test_a_different_hard_kind_still_denies(other: BoundSemanticKind) -> None:
    """(whitelist) "Inside HARD" is not enough — the implemented kind must be the approved one."""
    expected = other is BoundSemanticKind.HARD_MAXIMUM
    assert bound_integrity_preserved(clean_bound(implemented_as_kind=other)) is expected


def test_a_classified_non_hard_bound_must_also_survive_exactly() -> None:
    """(whitelist) Reinterpreting a ``PERCENTILE`` as a ``RANGE`` is a semantics change too."""
    assert (
        bound_integrity_preserved(
            clean_bound(
                approved_bound_kind=BoundSemanticKind.PERCENTILE,
                implemented_as_kind=BoundSemanticKind.RANGE,
            )
        )
        is False
    )
    assert (
        bound_integrity_preserved(
            clean_bound(
                approved_bound_kind=BoundSemanticKind.PERCENTILE,
                implemented_as_kind=BoundSemanticKind.PERCENTILE,
            )
        )
        is True
    )


def test_the_partition_covers_the_enum_exactly() -> None:
    """(whitelist, §7.2 drift) HARD ∪ NEUTRAL ∪ WEAK == the enum, pairwise disjoint (過 0 · 不 0)."""
    assert (
        frozenset(BoundSemanticKind)
        == HARD_BOUND_KINDS | NEUTRAL_BOUND_KINDS | WEAK_BOUND_KINDS
    )
    assert not HARD_BOUND_KINDS & NEUTRAL_BOUND_KINDS
    assert not HARD_BOUND_KINDS & WEAK_BOUND_KINDS
    assert not NEUTRAL_BOUND_KINDS & WEAK_BOUND_KINDS
    assert (len(HARD_BOUND_KINDS), len(NEUTRAL_BOUND_KINDS), len(WEAK_BOUND_KINDS)) == (
        4,
        2,
        6,
    )


@pytest.mark.parametrize("field", ["approved_bound_kind", "implemented_as_kind"])
def test_an_unclassified_bound_kind_denies(field: str) -> None:
    """(whitelist residue) An absent kind is never admitted — the auto-deny an unknown member gets."""
    assert bound_integrity_preserved(clean_bound(**{field: None})) is False


@pytest.mark.parametrize("value", [True, None])
def test_individual_exceedance_denies(value: bool | None) -> None:
    """(§11 line 314, negative polarity) ``is not False`` denies — including an unknown ``None``."""
    assert (
        bound_integrity_preserved(clean_bound(permits_individual_exceedance=value))
        is False
    )


@pytest.mark.parametrize(
    "field", ["units_exact", "window_inside_bound", "uncertainty_treated"]
)
@pytest.mark.parametrize("value", [False, None])
def test_each_positive_bound_flag_denies_individually(
    field: str, value: bool | None
) -> None:
    """(§11 line 312-314, positive polarity) ``is not True`` denies on each of the three."""
    assert bound_integrity_preserved(clean_bound(**{field: value})) is False


def test_absent_bound_denies() -> None:
    """(∅-seal) ``None`` is undecidable, therefore denied."""
    assert bound_integrity_preserved(None) is False


# --- (c) numeric fail-closure ---------------------------------------------


@pytest.mark.parametrize("state", sorted(MALFORMED_NUMERIC_STATES))
def test_malformed_numeric_never_yields_conforming(state: NumericInputState) -> None:
    """(§11 line 316) Each of the eleven malformed states denies a ``CONFORMING`` claim."""
    assert (
        numeric_result_not_conforming_by_default(
            clean_evaluation(numeric_input_state=state)
        )
        is False
    )


@pytest.mark.parametrize("state", sorted(MALFORMED_NUMERIC_STATES))
@pytest.mark.parametrize(
    "result",
    [
        AggregateConformanceResult.RESTRICTED,
        AggregateConformanceResult.NON_CONFORMING,
        AggregateConformanceResult.UNKNOWN,
    ],
)
def test_malformed_numeric_with_a_restrictive_result_is_admissible(
    state: NumericInputState, result: AggregateConformanceResult
) -> None:
    """(both-ways +) §11 line 316 requires ``UNKNOWN`` **or a restrictive result** — all three clear."""
    assert (
        numeric_result_not_conforming_by_default(
            clean_evaluation(numeric_input_state=state, result=result)
        )
        is True
    )


@pytest.mark.parametrize("field", ["result", "numeric_input_state"])
def test_an_unjudged_evaluation_denies(field: str) -> None:
    """(fail-closed) A record with no result or no numeric state is not a passing one."""
    assert (
        numeric_result_not_conforming_by_default(clean_evaluation(**{field: None}))
        is False
    )


def test_absent_evaluation_denies() -> None:
    """(∅-seal) ``None`` is undecidable, therefore denied."""
    assert numeric_result_not_conforming_by_default(None) is False


def test_the_malformed_set_is_derived_and_complete() -> None:
    """(§7.2 drift) The eleven malformed states are everything but ``WELL_FORMED`` (過 0 · 不 0)."""
    assert len(MALFORMED_NUMERIC_STATES) == 11
    assert NumericInputState.WELL_FORMED not in MALFORMED_NUMERIC_STATES
    assert MALFORMED_NUMERIC_STATES | {NumericInputState.WELL_FORMED} == frozenset(
        NumericInputState
    )


# --- composite properties -------------------------------------------------


def test_composite_denies_when_any_single_part_fails() -> None:
    """(both-ways) Each of the four parts individually sinks the composite."""
    # (a) determinism
    assert (
        _judge(
            evaluations=(
                clean_evaluation(),
                clean_evaluation(result=AggregateConformanceResult.RESTRICTED),
                clean_evaluation(
                    evaluator_digest=CLEAN_KEY_B[0],
                    canonical_input_digest=CLEAN_KEY_B[1],
                ),
            )
        )
        is False
    )
    # (b) bound integrity
    assert (
        _judge(bounds=(clean_bound(implemented_as_kind=BoundSemanticKind.PERCENTILE),))
        is False
    )
    # (c) numeric fail-closure
    assert (
        _judge(
            evaluations=(
                clean_evaluation(numeric_input_state=NumericInputState.NAN),
                clean_evaluation(
                    evaluator_digest=CLEAN_KEY_B[0],
                    canonical_input_digest=CLEAN_KEY_B[1],
                ),
            )
        )
        is False
    )


@given(exceedance=TRIBOOL, units=TRIBOOL)
def test_bound_integrity_clears_only_on_the_exact_positive_shape(
    exceedance: bool | None, units: bool | None
) -> None:
    """(property) Negative clears on ``is False`` only; positive on ``is True`` only."""
    bound = clean_bound(permits_individual_exceedance=exceedance, units_exact=units)
    assert bound_integrity_preserved(bound) is (exceedance is False and units is True)


def test_the_whitelist_residue_denies_an_unclassified_bound_kind(monkeypatch) -> None:
    """(whitelist residue, mutation-witness) An *unclassified* member auto-denies in **either** role.

    Today every :class:`~tos.stm.vocabulary.BoundSemanticKind` member sits in exactly one partition, so
    the ``else`` residue in :func:`~tos.stm.predicates.bound_integrity_preserved` has no natural
    witness — a mutation that deletes it would survive purely because no input reaches it. That is the
    whole point of the residue: it is the guard for a member **nobody has classified yet**. This test
    manufactures that future by shrinking the partitions the predicate reads, so the branch is really
    exercised and the guard is really load-bearing.
    """
    import tos.stm.predicates as predicates

    orphan = BoundSemanticKind.HARD_MAXIMUM
    monkeypatch.setattr(
        predicates, "HARD_BOUND_KINDS", HARD_BOUND_KINDS - {orphan}, raising=True
    )
    monkeypatch.setattr(predicates, "NEUTRAL_BOUND_KINDS", NEUTRAL_BOUND_KINDS)
    monkeypatch.setattr(predicates, "WEAK_BOUND_KINDS", WEAK_BOUND_KINDS)
    # an unclassified approved kind denies even when the implementation preserves it exactly
    assert (
        predicates.bound_integrity_preserved(
            clean_bound(approved_bound_kind=orphan, implemented_as_kind=orphan)
        )
        is False
    )
    # ... and a still-classified pair keeps clearing, so the shrink is not a blanket denial
    assert (
        predicates.bound_integrity_preserved(
            clean_bound(
                approved_bound_kind=BoundSemanticKind.HARD_MINIMUM,
                implemented_as_kind=BoundSemanticKind.HARD_MINIMUM,
            )
        )
        is True
    )
