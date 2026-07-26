"""§6.1-§6.3 predicate-only: instrument lineage, effective-time window, change triggers.

*Discipline tag: predicate / coordinate substrate only, and these three claim **no EV at
all**. NT-EV-003 (Instrument Identity Change) is ``EV-L2/3`` and NT-EV-007 (Conflicting
Effective-Time Window) is ``EV-L2/3`` — neither holds an ``EV-L1`` slice, so nothing here
closes or advances an evidence row; it is coordinate substrate whose real evidence is
component- and integration-fault testing. Closing NT-EV = 0.*

The three predicates consume sibling verdicts and re-author none of them: the invalidation
closure, the admissibility, the route fields, and the protective carve-out are venue's; the
freshness verdict and the source-disagreement bound are time's.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from tos.nontrade import (
    FRESHNESS_VERDICT_FRESH,
    ORDER_ADMISSIBILITY_ADMISSIBLE,
    ORDER_ADMISSIBILITY_INADMISSIBLE,
    ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY,
    ORDER_ADMISSIBILITY_UNKNOWN,
    effective_window_blocks_new_risk,
    instrument_lineage_preserved,
    material_change_trigger_nonempty,
)

from ._nontrade_strategies import (
    ADMISSIBILITY_FORGERIES,
    ADMISSIBILITY_TOKENS_OR_NONE,
    CHANGE_TRIGGER_SETS,
    NON_FALSE_VALUES,
    TRIBOOL,
    TRUTHY_NON_BOOL,
    clean_lineage_inputs,
    clean_window_inputs,
)

# ===========================================================================
# §6.1 instrument identity lineage (ADR §12)
# ===========================================================================


def test_a_clean_lineage_passes() -> None:
    """(availability side) Both identities present + an ordinary fresh decision."""
    assert instrument_lineage_preserved(**clean_lineage_inputs()) is True


@pytest.mark.parametrize("dropped", ["old_route_identity", "new_route_identity"])
def test_dropping_either_identity_before_the_transition_is_final_is_a_silent_reassign(
    dropped: str,
) -> None:
    """(§12 line 248/250) Both identities stay active until the mapping is final."""
    assert (
        instrument_lineage_preserved(**clean_lineage_inputs(**{dropped: None})) is False
    )


@pytest.mark.parametrize("not_final", [False, None, *TRUTHY_NON_BOOL])
def test_identity_transition_final_is_positive_polarity(not_final: object) -> None:
    """(§12) Only the singleton ``True`` counts as final; ``None`` is *not final*.

    A truthy non-``bool`` forged past the annotation must not count as a proof of finality,
    which is what an ``if identity_transition_final:`` gate would have allowed.
    """
    inputs = clean_lineage_inputs(
        old_route_identity=None, identity_transition_final=not_final
    )
    assert instrument_lineage_preserved(**inputs) is False


def test_a_final_transition_may_drop_the_old_identity_but_not_the_new() -> None:
    """(§12 line 248) Once the mapping is positively final the old identity may retire."""
    assert (
        instrument_lineage_preserved(
            **clean_lineage_inputs(
                old_route_identity=None, identity_transition_final=True
            )
        )
        is True
    )
    assert (
        instrument_lineage_preserved(
            **clean_lineage_inputs(
                new_route_identity=None, identity_transition_final=True
            )
        )
        is False
    )


@pytest.mark.parametrize("token", ADMISSIBILITY_TOKENS_OR_NONE)
def test_the_admissibility_fold_admits_only_the_exact_token(token: str | None) -> None:
    """(M6 three-way fold) Only ``ADMISSIBLE`` satisfies the ordinary conjunct.

    ``RESTRICTED_PROTECTIVE_ONLY`` fails **here** on purpose (it permits no ordinary new
    risk) while the disposition still lands it at ``BLOCK_NEW_RISK`` rather than trapping
    it, so the protective path stays open at the level that owns it.
    """
    result = instrument_lineage_preserved(**clean_lineage_inputs(admissibility=token))
    assert result is (token == ORDER_ADMISSIBILITY_ADMISSIBLE)


@pytest.mark.parametrize("forged", ADMISSIBILITY_FORGERIES)
def test_a_forged_admissibility_token_never_satisfies_the_conjunct(
    forged: object,
) -> None:
    """(fall-through ban) A lowercase / nonsense / truthy-non-string token is not a decision."""
    assert (
        instrument_lineage_preserved(**clean_lineage_inputs(admissibility=forged))
        is False
    )


@pytest.mark.parametrize(
    "token",
    [
        ORDER_ADMISSIBILITY_ADMISSIBLE,
        ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY,
        ORDER_ADMISSIBILITY_INADMISSIBLE,
        ORDER_ADMISSIBILITY_UNKNOWN,
        None,
    ],
)
@given(TRIBOOL)
def test_the_protective_flag_cannot_relax_the_lineage_conjunct(
    token: str | None, protective: bool | None
) -> None:
    """(§6.1 M6 / §4.4) A protective label never bypasses a constraint.

    The predicate accepts the coordinate so it travels with the decision, and is
    structurally unable to use it: the result is invariant under all three values.
    """
    baseline = instrument_lineage_preserved(
        **clean_lineage_inputs(admissibility=token, protective_action_may_proceed=None)
    )
    assert (
        instrument_lineage_preserved(
            **clean_lineage_inputs(
                admissibility=token, protective_action_may_proceed=protective
            )
        )
        is baseline
    )


# ===========================================================================
# §6.2 effective-time window (ADR §8)
# ===========================================================================


def test_a_clean_window_is_established() -> None:
    """(availability side) Both boundaries + FRESH + bounded disagreement."""
    assert effective_window_blocks_new_risk(**clean_window_inputs()) is True


@pytest.mark.parametrize(
    "dropped", ["earliest_credible_boundary", "latest_completion_boundary"]
)
def test_a_missing_boundary_leaves_the_whole_interval_restricted(dropped: str) -> None:
    """(§8 line 173) An unbounded window blocks; it never opens."""
    assert (
        effective_window_blocks_new_risk(**clean_window_inputs(**{dropped: None}))
        is False
    )


@pytest.mark.parametrize(
    "verdict", ["STALE", "UNKNOWN", "CONFLICTED", None, "fresh", ""]
)
def test_only_the_exact_fresh_verdict_establishes_the_window(
    verdict: str | None,
) -> None:
    """(§8) The time verdict is a compared **token**, never truthy-tested.

    ``STALE`` / ``UNKNOWN`` / ``CONFLICTED`` are all non-empty (truthy) strings, so a bare
    ``if time_freshness:`` would have opened the window on every one of them.
    """
    assert (
        effective_window_blocks_new_risk(**clean_window_inputs(time_freshness=verdict))
        is False
    )
    assert (
        effective_window_blocks_new_risk(
            **clean_window_inputs(time_freshness=FRESHNESS_VERDICT_FRESH)
        )
        is True
    )


@pytest.mark.parametrize("degraded", [False, None, *TRUTHY_NON_BOOL])
def test_source_disagreement_bounded_is_positive_polarity(degraded: object) -> None:
    """(§8) Only ``True`` proves the disagreement is bounded."""
    assert (
        effective_window_blocks_new_risk(
            **clean_window_inputs(source_disagreement_bounded=degraded)
        )
        is False
    )


def test_the_window_predicate_reads_no_clock() -> None:
    """(§7.2 hermetic) The boundaries are opaque injected tokens, not timestamps.

    Any string is accepted as a boundary coordinate — the predicate never parses, compares,
    or orders them, because trustworthy time is ADR-002-008's and a wall clock never orders
    (§8 line 175).
    """
    assert (
        effective_window_blocks_new_risk(
            **clean_window_inputs(
                earliest_credible_boundary="generation-7",
                latest_completion_boundary="generation-9",
            )
        )
        is True
    )


# ===========================================================================
# §6.3 material-change trigger non-emptiness (ADR §10 line 221; M3)
# ===========================================================================


def test_a_material_event_with_triggers_passes() -> None:
    """(availability side) A material event that names what to invalidate passes."""
    assert (
        material_change_trigger_nonempty(True, frozenset({"venue-snapshot-1"})) is True
    )


def test_a_material_event_with_no_triggers_is_the_fail_open_this_predicate_blocks() -> (
    None
):
    """(§10 line 221 / §4.7 row 6) An ∅ trigger set invalidates nothing on the venue side.

    venue's own docstring makes the empty closure legitimate ("no change, nothing
    invalidated — the availability side"), so the non-emptiness is **this** side's
    obligation: otherwise every stale snapshot and admissibility decision survives a
    material event.
    """
    assert material_change_trigger_nonempty(True, frozenset()) is False


def test_unknown_materiality_is_material() -> None:
    """(§6.3 / venue §5.8) ``None`` grants no exemption — the M3 self-caught fail-open.

    Exempting on ``is not True`` would let a ``None`` skip the invalidation wholesale.
    """
    assert material_change_trigger_nonempty(None, frozenset()) is False
    assert material_change_trigger_nonempty(None, frozenset({"t"})) is True


def test_only_positively_proven_non_materiality_exempts() -> None:
    """(§6.3) The relaxation requires the positive ``is False`` proof."""
    assert material_change_trigger_nonempty(False, frozenset()) is True
    assert material_change_trigger_nonempty(False, frozenset({"t"})) is True


@pytest.mark.parametrize("not_false", NON_FALSE_VALUES)
def test_a_value_that_is_not_singleton_false_never_exempts(not_false: object) -> None:
    """(§6.3 polarity) ``0`` / ``""`` / ``[]`` / ``"no"`` are falsy but are not ``False``.

    An ``if not event_is_material:`` gate would have exempted every one of them.
    """
    assert material_change_trigger_nonempty(not_false, frozenset()) is False  # type: ignore[arg-type]


@given(TRIBOOL, CHANGE_TRIGGER_SETS)
def test_the_trigger_rule_is_exactly_the_two_clause_disjunction(
    materiality: bool | None, triggers: frozenset[str]
) -> None:
    """(§6.3) ``is False`` exempts; otherwise the trigger set must be non-empty."""
    expected = materiality is False or len(triggers) > 0
    assert material_change_trigger_nonempty(materiality, triggers) is expected


def test_this_package_computes_no_closure() -> None:
    """(§3.5) The invalidation reach and the unproven-edge expansion are venue's."""
    from tos import nontrade as nontrade_pkg

    for forbidden in (
        "material_change_closure",
        "protective_label_no_bypass",
        "order_shape_admissible",
        "stale_decision_rejected_at_egress",
        "InstrumentRouteFields",
        "OrderAdmissibilityResult",
    ):
        assert not hasattr(
            nontrade_pkg, forbidden
        ), f"{forbidden} is venue-owned — §3.5 forbids re-authoring it here"
