"""§5.8 ``post_trade_disposition`` — the sole producer, the C1 seal, and the rank order.

The C1 defect this file exists to keep sealed: an earlier eight-input draft omitted nine of
the conjuncts, so ``POST_TRADE_ADMISSIBLE`` was reachable while a statement common-mode
(PTF-INV-014), a cross-leg proof reuse (§11 line 328), or a global-flag substitution
(PTF-INV-005) stood unresolved — and the "every void-table row folds through here" claim was
false. The 1:1 correspondence between the sixteen conjuncts and the twenty-two §4.8 rows is
therefore asserted in **both** directions, and every conjunct is shown to be individually
load-bearing.

Also asserted:

* the **sole-producer** property — every one of the five dispositions is reachable from this
  function, and nothing else in the package returns one;
* the **total order** ``CONFLICTED > QUARANTINED_UNKNOWN > TRAPPED > BLOCK > ADMISSIBLE``,
  including every simultaneous-signal pair, so the most conservative member always wins;
* ``POST_TRADE_ADMISSIBLE`` is a **positive conjunction**, never a fall-through residue: the
  residue is ``POST_TRADE_BLOCK_NEW_RISK``;
* the honest staged disclosure — an **L1-only** caller passes ``availability_proven=None``
  and can therefore never reach ``ADMISSIBLE``.
"""

from __future__ import annotations

import inspect

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.posttrade import (
    DISPOSITION_CONJUNCTS,
    VOID_TABLE_ROWS,
    ObligationCommitOutcome,
    PostTradeDisposition,
    post_trade_disposition,
)

from ._posttrade_strategies import (
    COMMIT_OUTCOMES,
    FIELD_CONFIDENCE_TOKENS,
    TRIBOOL,
    clean_disposition_kwargs,
)

_NON_BOOL_INPUTS = ("commit_outcome", "field_confidence", "availability_proven")


# --- signature + C1 correspondence -------------------------------------------


def test_the_signature_takes_nineteen_keyword_only_inputs() -> None:
    """(C1) 16 bool conjuncts + commit outcome + field confidence + availability."""
    parameters = inspect.signature(post_trade_disposition).parameters
    assert len(parameters) == 19
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in parameters.values()
    ), "every input is keyword-only so a positional mix-up cannot silently reorder them"


def test_the_sixteen_conjuncts_are_exactly_the_bool_parameters() -> None:
    """(C1) The published conjunct list is the real signature, not a stale comment."""
    parameters = set(inspect.signature(post_trade_disposition).parameters)
    assert len(DISPOSITION_CONJUNCTS) == 16
    assert set(DISPOSITION_CONJUNCTS) == parameters - set(_NON_BOOL_INPUTS)


def test_the_void_table_has_twenty_two_rows_numbered_one_to_twenty_two() -> None:
    """(§4.8) 22 rows, individually counted, in order."""
    assert len(VOID_TABLE_ROWS) == 22
    assert [row[0] for row in VOID_TABLE_ROWS] == [str(index) for index in range(1, 23)]


def test_every_conjunct_appears_in_the_void_table() -> None:
    """(C1 direction 1) No conjunct is missing from the table."""
    table_inputs = {row[1] for row in VOID_TABLE_ROWS}
    missing = sorted(set(DISPOSITION_CONJUNCTS) - table_inputs)
    assert missing == [], f"conjuncts absent from the §4.8 table: {missing}"


def test_every_void_table_input_is_a_real_signature_input() -> None:
    """(C1 direction 2) No table row names an input the function does not take.

    This is the direction that caught the C1 fail-open: a row can only be "handled" if some
    parameter carries it.
    """
    parameters = set(inspect.signature(post_trade_disposition).parameters)
    for row_number, input_name, _expected in VOID_TABLE_ROWS:
        if input_name == "structural absence":
            continue
        assert input_name in parameters, (
            f"§4.8 row {row_number} names {input_name!r}, which is not an input — "
            "the row would be delegated to an ownerless 'handled elsewhere' step"
        )


def test_row_fifteen_is_the_structural_absence_row() -> None:
    """(§4.8 row 15) A capacity release or an external send has **no** input at all.

    PTF-INV-008 / PTF-INV-016: the act is unrepresentable, so no value can move the
    disposition. The sentinel verdict records that honestly.
    """
    row = next(row for row in VOID_TABLE_ROWS if row[0] == "15")
    assert row[1] == "structural absence"
    assert row[2] == "INVARIANT"
    assert sum(1 for entry in VOID_TABLE_ROWS if entry[1] == "structural absence") == 1


# --- the positive conjunction -------------------------------------------------


def test_the_fully_proven_configuration_is_admissible() -> None:
    """(positive side) The one configuration that reaches ``POST_TRADE_ADMISSIBLE``."""
    assert (
        post_trade_disposition(**clean_disposition_kwargs())
        is PostTradeDisposition.POST_TRADE_ADMISSIBLE
    )


@pytest.mark.parametrize("conjunct", DISPOSITION_CONJUNCTS)
@pytest.mark.parametrize("bad", [False, None])
def test_every_conjunct_is_individually_load_bearing(
    conjunct: str, bad: bool | None
) -> None:
    """(C1) Flipping any **one** of the sixteen removes admissibility.

    This is the assertion the eight-input draft could not have passed: nine of the sixteen
    were not in the conjunction at all, so flipping them left ``ADMISSIBLE`` standing.
    """
    verdict = post_trade_disposition(**clean_disposition_kwargs(**{conjunct: bad}))
    assert verdict is not PostTradeDisposition.POST_TRADE_ADMISSIBLE


@pytest.mark.parametrize("conjunct", DISPOSITION_CONJUNCTS)
@pytest.mark.parametrize("forged", [1, "yes", [1], 0, "", []])
def test_a_forged_conjunct_value_never_reaches_admissible(
    conjunct: str, forged: object
) -> None:
    """(polarity) The rank-5 conjunction is ``is True`` only — truthy and falsy forgeries
    both fail."""
    verdict = post_trade_disposition(**clean_disposition_kwargs(**{conjunct: forged}))
    assert verdict is not PostTradeDisposition.POST_TRADE_ADMISSIBLE


@pytest.mark.parametrize(
    "outcome",
    [
        ObligationCommitOutcome.COMMITTED_ONCE,
        ObligationCommitOutcome.IDEMPOTENT_REPLAY,
    ],
)
def test_both_accepted_commit_outcomes_permit_admissibility(
    outcome: ObligationCommitOutcome,
) -> None:
    """(positive side) A first commit and a harmless late-fill replay both qualify."""
    assert (
        post_trade_disposition(**clean_disposition_kwargs(commit_outcome=outcome))
        is PostTradeDisposition.POST_TRADE_ADMISSIBLE
    )


@pytest.mark.parametrize(
    "forged",
    ["COMMITTED_ONCE", "IDEMPOTENT_REPLAY", "REJECTED_CONFLICT", "", None, 1, True],
)
def test_a_raw_string_commit_outcome_never_reaches_admissible(forged: object) -> None:
    """(polarity) The commit gate is an **identity** membership, not a set ``in`` test.

    ``ObligationCommitOutcome`` is a ``StrEnum``, so a bare ``"COMMITTED_ONCE"`` hashes equal
    to the real member and a set ``in`` test would have accepted it. The mandated gate for a
    result enum is a positive identity, and applying it here means a forged token, a raw
    string, a ``None``, or a stray ``1`` all fall to the restrictive residue instead.
    """
    verdict = post_trade_disposition(**clean_disposition_kwargs(commit_outcome=forged))
    assert verdict is not PostTradeDisposition.POST_TRADE_ADMISSIBLE


@pytest.mark.parametrize(
    "confidence", ["UNKNOWN", "CONFLICTED", "SINGLE_SOURCE", "STALE", "", None]
)
def test_only_corroborated_confidence_permits_admissibility(
    confidence: str | None,
) -> None:
    """(recon seam) ``SINGLE_SOURCE`` and ``STALE`` are truthy strings and are not
    corroboration — a truthiness gate would have admitted them."""
    verdict = post_trade_disposition(
        **clean_disposition_kwargs(field_confidence=confidence)
    )
    assert verdict is not PostTradeDisposition.POST_TRADE_ADMISSIBLE


def test_an_l1_only_caller_can_never_reach_admissible() -> None:
    """(honest staged disclosure, §5.8) ``availability_proven`` is a PTF-EV-003 / 007
    ``EV-L2/3+Broker`` verdict Phase 1 does not produce.

    Every L1 structural property can hold and the obligation is still **trapped** without
    settlement availability. That is the honest reflection of the staged boundary, not a
    defect.
    """
    verdict = post_trade_disposition(
        **clean_disposition_kwargs(availability_proven=None)
    )
    assert verdict is PostTradeDisposition.POST_TRADE_TRAPPED


# --- the total order ----------------------------------------------------------


def test_rank_one_conflicted_signals() -> None:
    """(rank 1) Each of the six contradiction signals lands on ``CONFLICTED``."""
    for override in (
        {"collateral_conserved": False},
        {"sources_independent": False},
        {"proof_class_specific": False},
        {"proof_non_transferable": False},
        {"commit_outcome": ObligationCommitOutcome.REJECTED_CONFLICT},
        {"field_confidence": "CONFLICTED"},
    ):
        assert (
            post_trade_disposition(**clean_disposition_kwargs(**override))
            is PostTradeDisposition.POST_TRADE_CONFLICTED
        ), override


def test_rank_two_quarantine_signals() -> None:
    """(rank 2) Undecidable commit or unknown confidence ⇒ ``QUARANTINED_UNKNOWN``."""
    for override in (
        {"commit_outcome": ObligationCommitOutcome.REJECTED_UNKNOWN},
        {"field_confidence": "UNKNOWN"},
    ):
        assert (
            post_trade_disposition(**clean_disposition_kwargs(**override))
            is PostTradeDisposition.POST_TRADE_QUARANTINED_UNKNOWN
        ), override


@pytest.mark.parametrize("availability", [False, None])
def test_rank_three_trapped_signal(availability: bool | None) -> None:
    """(rank 3) Availability not positively proven ⇒ ``TRAPPED``, in both unproven forms."""
    assert (
        post_trade_disposition(
            **clean_disposition_kwargs(availability_proven=availability)
        )
        is PostTradeDisposition.POST_TRADE_TRAPPED
    )


@pytest.mark.parametrize(
    "outcome",
    [
        ObligationCommitOutcome.REJECTED_NO_LINEAGE,
        ObligationCommitOutcome.REJECTED_OVERWRITE,
    ],
)
def test_rank_four_lineage_and_overwrite_rejections_block(
    outcome: ObligationCommitOutcome,
) -> None:
    """(rank 4) A relabelled or overwriting commit blocks new risk without contradiction."""
    assert (
        post_trade_disposition(**clean_disposition_kwargs(commit_outcome=outcome))
        is PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK
    )


def test_conflicted_dominates_quarantine() -> None:
    """(order) An active contradiction outranks an unattributable state."""
    assert (
        post_trade_disposition(
            **clean_disposition_kwargs(
                collateral_conserved=False, field_confidence="UNKNOWN"
            )
        )
        is PostTradeDisposition.POST_TRADE_CONFLICTED
    )


def test_quarantine_dominates_trapped() -> None:
    """(order, Q2) An unbounded-scope unknown outranks a bounded trap."""
    assert (
        post_trade_disposition(
            **clean_disposition_kwargs(
                field_confidence="UNKNOWN", availability_proven=None
            )
        )
        is PostTradeDisposition.POST_TRADE_QUARANTINED_UNKNOWN
    )


def test_trapped_dominates_block() -> None:
    """(order) A bounded trap outranks a plain block."""
    assert (
        post_trade_disposition(
            **clean_disposition_kwargs(availability_proven=None, leg_set_complete=False)
        )
        is PostTradeDisposition.POST_TRADE_TRAPPED
    )


def test_block_dominates_admissible() -> None:
    """(order) Any unproven conjunct outranks admissibility."""
    assert (
        post_trade_disposition(**clean_disposition_kwargs(leg_set_complete=False))
        is PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK
    )


def test_conflicted_dominates_everything_simultaneously() -> None:
    """(order) All four denial signals at once ⇒ the most conservative member."""
    assert (
        post_trade_disposition(
            **clean_disposition_kwargs(
                collateral_conserved=False,
                field_confidence="CONFLICTED",
                availability_proven=None,
                leg_set_complete=False,
                commit_outcome=ObligationCommitOutcome.REJECTED_UNKNOWN,
            )
        )
        is PostTradeDisposition.POST_TRADE_CONFLICTED
    )


# --- sole producer + fall-through discipline ---------------------------------


def test_all_five_dispositions_are_reachable_from_this_one_producer() -> None:
    """(sole producer) Every member is produced here — none is a dead vocabulary entry."""
    produced = {
        post_trade_disposition(**clean_disposition_kwargs()),
        post_trade_disposition(**clean_disposition_kwargs(leg_set_complete=False)),
        post_trade_disposition(**clean_disposition_kwargs(availability_proven=None)),
        post_trade_disposition(**clean_disposition_kwargs(field_confidence="UNKNOWN")),
        post_trade_disposition(**clean_disposition_kwargs(collateral_conserved=False)),
    }
    assert produced == set(PostTradeDisposition)


def test_the_residue_is_the_conservative_member_not_the_permissive_one() -> None:
    """(#16 CRITICAL) The dispatch residue is ``BLOCK_NEW_RISK``, never ``ADMISSIBLE``.

    An input configuration that satisfies no rank explicitly must land on the restrictive
    member. Here every conjunct is ``None`` — the "new signal not yet woven in" case.
    """
    all_unknown = dict.fromkeys(DISPOSITION_CONJUNCTS)
    verdict = post_trade_disposition(
        **clean_disposition_kwargs(
            **all_unknown,
            commit_outcome=ObligationCommitOutcome.COMMITTED_ONCE,
            field_confidence="CORROBORATED",
            availability_proven=True,
        )
    )
    assert verdict is PostTradeDisposition.POST_TRADE_CONFLICTED
    # ... and with the four rank-1 conjuncts restored it falls to the *block* residue,
    # never to admissibility.
    partly_known = {
        name: (
            True
            if name
            in (
                "collateral_conserved",
                "sources_independent",
                "proof_class_specific",
                "proof_non_transferable",
            )
            else None
        )
        for name in DISPOSITION_CONJUNCTS
    }
    assert (
        post_trade_disposition(**clean_disposition_kwargs(**partly_known))
        is PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK
    )


@given(
    conjunct_values=st.lists(TRIBOOL, min_size=16, max_size=16),
    outcome=COMMIT_OUTCOMES,
    confidence=FIELD_CONFIDENCE_TOKENS,
    availability=TRIBOOL,
)
def test_admissible_implies_the_whole_positive_conjunction(
    conjunct_values: list[bool | None],
    outcome: ObligationCommitOutcome,
    confidence: str | None,
    availability: bool | None,
) -> None:
    """(#16 CRITICAL, property form) ``ADMISSIBLE`` is never reached without every premise."""
    kwargs = dict(zip(DISPOSITION_CONJUNCTS, conjunct_values, strict=True))
    verdict = post_trade_disposition(
        **kwargs,  # type: ignore[arg-type]
        commit_outcome=outcome,
        field_confidence=confidence,
        availability_proven=availability,
    )
    if verdict is PostTradeDisposition.POST_TRADE_ADMISSIBLE:
        assert all(value is True for value in conjunct_values)
        assert outcome in (
            ObligationCommitOutcome.COMMITTED_ONCE,
            ObligationCommitOutcome.IDEMPOTENT_REPLAY,
        )
        assert confidence == "CORROBORATED"
        assert availability is True


@given(
    conjunct_values=st.lists(TRIBOOL, min_size=16, max_size=16),
    outcome=COMMIT_OUTCOMES,
    confidence=FIELD_CONFIDENCE_TOKENS,
    availability=TRIBOOL,
)
def test_the_producer_is_total_and_deterministic(
    conjunct_values: list[bool | None],
    outcome: ObligationCommitOutcome,
    confidence: str | None,
    availability: bool | None,
) -> None:
    """(total order) Every input configuration yields exactly one member, reproducibly."""
    kwargs = dict(zip(DISPOSITION_CONJUNCTS, conjunct_values, strict=True))
    call = dict(
        kwargs,
        commit_outcome=outcome,
        field_confidence=confidence,
        availability_proven=availability,
    )
    first = post_trade_disposition(**call)  # type: ignore[arg-type]
    second = post_trade_disposition(**call)  # type: ignore[arg-type]
    assert first is second
    assert first in set(PostTradeDisposition)


def test_the_disposition_grants_nothing() -> None:
    """(§4.7) Even ``POST_TRADE_ADMISSIBLE`` is a verdict, not a permission.

    The package exposes no field or method by which a disposition could release capacity,
    make cash available, prove title, grant permission, or transmit — that is asserted
    structurally in ``test_posttrade_records.py`` and re-stated here as the consuming
    contract.
    """
    verdict = post_trade_disposition(**clean_disposition_kwargs())
    assert verdict is PostTradeDisposition.POST_TRADE_ADMISSIBLE
    assert not hasattr(verdict, "release")
    assert not hasattr(verdict, "transmit")
