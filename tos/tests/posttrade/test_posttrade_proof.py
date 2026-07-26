"""§5.7 finality-proof class specificity, non-transferability, currency + grants-nothing.

The §4.5-B monotonicity truth table, cell by cell — and in particular its ninth row, the one
that makes "finality is monotone" mean something other than "once proven, always proven":

* rows 1-3 (``UNKNOWN -> PROVEN`` with proof; without proof; cross-dimension implication) are
  :func:`finality_dimensions_orthogonal`'s and live in ``test_posttrade_finality.py``;
* row 4 (``PROVEN`` does not imply a consequence) is
  :func:`post_trade_consequence_all_false`, asserted here with **no positive side** — no
  input ever grants a consequence;
* rows 5-6 (generation monotone, no revert) are the ``tos.ordering`` coordinate, asserted in
  ``test_posttrade_state.py``;
* rows 7-8 (destructive overwrite; non-destructive supersede) are
  :func:`obligation_commit_idempotent`'s, in ``test_posttrade_commit.py``;
* **row 9** (a correction advances the generation, so the prior proof is no longer current —
  finality **reopens**) is :func:`finality_proof_current`, asserted here.

Plus PTF-INV-005 (a global ``SETTLED`` / confidence score / statement flag / operator
decision cannot replace exact per-field proof — realized by structural absence plus the
class-specific conjunction) and §11 line 328 (non-transferable and non-unionable).
"""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.canonical import ArtifactStatus
from tos.posttrade import (
    AllFalsePostTradeConsequence,
    FinalityDimensionKind,
    ObligationLegDirection,
    ObligationLegScope,
    PostTradeFinalityProof,
    PostTradeObligationLifecycleState,
    finality_proof_class_specific,
    finality_proof_current,
    finality_proof_non_transferable,
    post_trade_consequence_all_false,
)

from ._posttrade_strategies import (
    clean_finality_proof,
    clean_obligation_record,
    clean_scope,
)

_SCOPE_COMPONENTS = (
    "leg",
    "account",
    "currency",
    "value_date",
    "source_revision",
    "finality_class",
)


# --- §11 line 320-326 finality_proof_class_specific --------------------------


def test_an_exact_class_specific_proof_passes() -> None:
    """(positive side) Identity, version, full scope, amount, class, generation, limits."""
    assert finality_proof_class_specific(clean_finality_proof()) is True


def test_an_absent_proof_proves_nothing() -> None:
    """(fail-closed) No proof ⇒ no class-specific claim."""
    assert finality_proof_class_specific(None) is False


@pytest.mark.parametrize("component", _SCOPE_COMPONENTS)
def test_each_of_the_six_scope_components_is_load_bearing(component: str) -> None:
    """(§11 line 328) An under-specified scope describes a *set* of legs — the union the
    ADR forbids."""
    under_specified = clean_finality_proof(leg_scope=clean_scope(**{component: None}))
    assert finality_proof_class_specific(under_specified) is False


@pytest.mark.parametrize(
    "component", ["account", "currency", "value_date", "source_revision"]
)
def test_an_empty_string_scope_component_is_not_a_specification(component: str) -> None:
    """(§11 line 328) An empty token is an undescribed component, not a narrow one."""
    empty = clean_finality_proof(leg_scope=clean_scope(**{component: ""}))
    assert finality_proof_class_specific(empty) is False


def test_an_absent_scope_is_rejected() -> None:
    """(§11 line 328) A proof with no scope at all is a global claim."""
    assert finality_proof_class_specific(clean_finality_proof(leg_scope=None)) is False


@pytest.mark.parametrize("field", ["obligation_ref", "obligation_version"])
def test_the_obligation_binding_is_load_bearing(field: str) -> None:
    """(§11 line 320) A proof that does not name its obligation and version is not exact."""
    assert finality_proof_class_specific(clean_finality_proof(**{field: None})) is False


def test_an_absent_finality_class_is_a_global_claim() -> None:
    """(PTF-INV-005) A proof without a class is the global ``SETTLED`` in disguise."""
    assert (
        finality_proof_class_specific(clean_finality_proof(finality_class=None))
        is False
    )


def test_a_class_that_disagrees_with_its_scope_is_incoherent() -> None:
    """(§11 line 320-328) Claiming one class while scoping another is not an exact proof."""
    incoherent = clean_finality_proof(
        finality_class=FinalityDimensionKind.CASH_AVAILABILITY,
        leg_scope=clean_scope(finality_class=FinalityDimensionKind.SETTLEMENT),
    )
    assert finality_proof_class_specific(incoherent) is False


def test_an_absent_bound_generation_is_rejected() -> None:
    """(§11 line 330) Without a bound generation the reopen rule has nothing to compare.

    ``bound_generation`` is in ``_REQUIRED_COVERED``, so an unbound proof cannot reach
    ISSUED at all; the guard is exercised on a genuinely pre-issuance DRAFT.
    """
    unbound = PostTradeFinalityProof(
        proof_id=None,
        status=ArtifactStatus.DRAFT,
        obligation_ref="OBL-1",
        obligation_version="V1",
        leg_scope=clean_scope(),
        amount=Decimal("10.00"),
        finality_class=FinalityDimensionKind.SETTLEMENT,
        bound_generation=None,
        does_not_prove=("CASH_AVAILABILITY",),
    )
    assert finality_proof_class_specific(unbound) is False


@pytest.mark.parametrize("amount", [None, Decimal("-1.00")])
def test_an_absent_or_negative_amount_is_rejected(amount: Decimal | None) -> None:
    """(§11 line 320) The amount is part of the exact binding, and it is a gross magnitude."""
    assert finality_proof_class_specific(clean_finality_proof(amount=amount)) is False


def test_an_empty_does_not_prove_is_rejected() -> None:
    """(§11 line 320-326) The negative space is **part of the proof**.

    A proof that never declared its own limits is exactly how a single-dimension proof gets
    read as global finality.
    """
    assert (
        finality_proof_class_specific(clean_finality_proof(does_not_prove=())) is False
    )


def test_the_global_flag_substitution_fails_the_conjunction() -> None:
    """(PTF-INV-005) What a "global ``SETTLED``" looks like here: no class, no scope, no
    declared limits. It has no field to travel in and it fails the conjunction anyway.
    """
    global_claim = clean_finality_proof(
        finality_class=None, leg_scope=None, does_not_prove=()
    )
    assert finality_proof_class_specific(global_claim) is False


# --- §11 line 328 finality_proof_non_transferable ----------------------------


def test_a_proof_applies_to_its_own_scope() -> None:
    """(positive side) Whole-scope structural equality."""
    assert (
        finality_proof_non_transferable(clean_finality_proof(), clean_scope()) is True
    )


@pytest.mark.parametrize(
    ("component", "other"),
    [
        ("leg", ObligationLegDirection.CREDIT),
        ("account", "ACCOUNT-B"),
        ("currency", "CUR-B"),
        ("value_date", "VD-2"),
        ("source_revision", "REV-2"),
        ("finality_class", FinalityDimensionKind.CASH_AVAILABILITY),
    ],
)
def test_each_component_blocks_a_cross_scope_transfer(
    component: str, other: object
) -> None:
    """(§11 line 328) "non-transferable and non-unionable" — on every one of the six axes."""
    target = clean_scope(**{component: other})
    assert finality_proof_non_transferable(clean_finality_proof(), target) is False


def test_two_under_specified_scopes_do_not_match() -> None:
    """(∅ guard) Agreeing only by being equally undescribed is not the same leg.

    Without this guard a pair of empty scopes would compare equal and certify the transfer of
    a proof about nothing onto anything.
    """
    empty = ObligationLegScope()
    proof = clean_finality_proof(leg_scope=empty)
    assert finality_proof_non_transferable(proof, empty) is False


def test_an_absent_proof_or_target_is_rejected() -> None:
    """(fail-closed) Nothing to compare ⇒ no transfer is authorized."""
    assert finality_proof_non_transferable(None, clean_scope()) is False
    assert finality_proof_non_transferable(clean_finality_proof(), None) is False


def test_a_scope_tuple_does_not_name_the_obligation() -> None:
    """(§11 line 320; v1.2 erratum) The premise behind the cross-obligation seal.

    Two distinct obligations can legitimately share one six-component scope — the same account
    settling the same currency on the same value date. The scope names a **leg**, not an
    obligation, which is exactly why a scope-only comparison was insufficient.
    """
    first = clean_finality_proof(obligation_ref="OBL-1")
    second = clean_finality_proof(obligation_ref="OBL-2")
    assert first.leg_scope == second.leg_scope
    assert first.obligation_ref != second.obligation_ref


def test_a_supplied_obligation_identity_narrows_the_verdict() -> None:
    """(§11 line 320) Supplying the target identity can only turn ``True`` into ``False``."""
    proof = clean_finality_proof(obligation_ref="OBL-1", obligation_version="V1")
    scope = clean_scope()
    assert finality_proof_non_transferable(proof, scope) is True
    assert (
        finality_proof_non_transferable(proof, scope, target_obligation_ref="OBL-1")
        is True
    )
    assert (
        finality_proof_non_transferable(proof, scope, target_obligation_ref="OBL-2")
        is False
    )


@pytest.mark.parametrize(
    ("target_ref", "target_version", "expected"),
    [
        (None, None, True),  # legacy scope-only call — backwards compatible
        ("OBL-1", None, True),
        (None, "V1", True),
        ("OBL-1", "V1", True),
        ("OBL-2", None, False),
        ("OBL-1", "V2", False),
        ("OBL-2", "V2", False),
    ],
)
def test_the_cross_obligation_gate_truth_table(
    target_ref: str | None, target_version: str | None, expected: bool
) -> None:
    """(v1.2 erratum) Every combination of supplied / withheld identity components."""
    proof = clean_finality_proof(obligation_ref="OBL-1", obligation_version="V1")
    assert (
        finality_proof_non_transferable(
            proof,
            clean_scope(),
            target_obligation_ref=target_ref,
            target_obligation_version=target_version,
        )
        is expected
    )


def test_an_unbound_proof_cannot_be_waved_onto_a_named_obligation() -> None:
    """(§11 line 320) A proof that carries no obligation identity matches no supplied one.

    ``None != "OBL-1"``, so the mismatch branch fires rather than the comparison being
    skipped — the failure mode a "compare only when both are present" reading would create.
    """
    from tos.canonical import ArtifactStatus

    unbound = PostTradeFinalityProof(
        proof_id=None,
        status=ArtifactStatus.DRAFT,
        obligation_ref=None,
        obligation_version=None,
        leg_scope=clean_scope(),
        amount=Decimal("10.00"),
        finality_class=FinalityDimensionKind.SETTLEMENT,
        bound_generation=1,
        does_not_prove=("CASH_AVAILABILITY",),
    )
    assert (
        finality_proof_non_transferable(
            unbound, clean_scope(), target_obligation_ref="OBL-1"
        )
        is False
    )


def test_the_cross_obligation_arguments_are_keyword_only() -> None:
    """(v1.2 erratum) Keyword-only, so no positional call can accidentally supply them."""
    parameters = inspect.signature(finality_proof_non_transferable).parameters
    assert parameters["target_obligation_ref"].kind is inspect.Parameter.KEYWORD_ONLY
    assert (
        parameters["target_obligation_version"].kind is inspect.Parameter.KEYWORD_ONLY
    )
    assert parameters["target_obligation_ref"].default is None
    assert parameters["target_obligation_version"].default is None


def test_transferability_is_symmetric_in_its_scope_comparison() -> None:
    """(structural) A proof scoped to X applies to X and to nothing else, whichever way the
    caller frames the target."""
    proof_on_credit = clean_finality_proof(
        leg_scope=clean_scope(leg=ObligationLegDirection.CREDIT)
    )
    assert (
        finality_proof_non_transferable(
            proof_on_credit, clean_scope(leg=ObligationLegDirection.CREDIT)
        )
        is True
    )
    assert (
        finality_proof_non_transferable(
            proof_on_credit, clean_scope(leg=ObligationLegDirection.DEBIT)
        )
        is False
    )


# --- §4.5-B row 9: finality_proof_current ------------------------------------


def test_a_proof_bound_to_the_active_generation_is_current() -> None:
    """(positive side) The proof binds the generation that is still active."""
    assert finality_proof_current(clean_finality_proof(bound_generation=7), 7) is True


def test_a_correction_that_advances_the_generation_reopens_finality() -> None:
    """(§4.5-B row 9 / §11 line 330 / PTF-INV-013) The stale-proof seal.

    "A later correction supersedes the proof, **advances generation** ... it does not erase
    history." So "finality is monotone" is emphatically **not** "once proven, always proven".
    """
    proof = clean_finality_proof(bound_generation=1)
    assert finality_proof_current(proof, 1) is True
    # a correction lands; the active generation advances
    assert finality_proof_current(proof, 2) is False


def test_a_proof_ahead_of_the_active_generation_is_also_not_current() -> None:
    """(§11 line 330) Currency is an equality, not a "at least as new as" ordering: a proof
    claiming a generation that is not the active one is not current in either direction.
    """
    assert finality_proof_current(clean_finality_proof(bound_generation=3), 2) is False


@pytest.mark.parametrize("missing", ["proof", "bound", "active"])
def test_an_unknown_generation_fails_closed(missing: str) -> None:
    """(fail-closed) A proof that never declared its generation can never be shown current."""
    if missing == "proof":
        assert finality_proof_current(None, 1) is False
    elif missing == "bound":
        unbound = PostTradeFinalityProof(
            proof_id=None, status=ArtifactStatus.DRAFT, bound_generation=None
        )
        assert finality_proof_current(unbound, 1) is False
    else:
        assert (
            finality_proof_current(clean_finality_proof(bound_generation=1), None)
            is False
        )


@given(
    bound=st.integers(min_value=0, max_value=50),
    active=st.integers(min_value=0, max_value=50),
)
def test_currency_is_exactly_generation_equality(bound: int, active: int) -> None:
    """(§5.7 M2) A pure integer comparison — no bound, no duration, no clock."""
    assert finality_proof_current(
        clean_finality_proof(bound_generation=bound), active
    ) is (bound == active)


# --- §10 line 312 post_trade_consequence_all_false ---------------------------


def test_the_default_consequence_block_passes_the_re_check() -> None:
    """(defence in depth) A constructible block is all-false."""
    assert post_trade_consequence_all_false(AllFalsePostTradeConsequence()) is True


def test_an_absent_consequence_block_proves_nothing() -> None:
    """(∅ guard) Nothing to prove is not a proof of nothing."""
    assert post_trade_consequence_all_false(None) is False


@pytest.mark.parametrize("flag", sorted(AllFalsePostTradeConsequence.model_fields))
@pytest.mark.parametrize("forged", [True, 1, "yes", [1]])
def test_a_forged_consequence_flag_is_rejected_by_the_re_check(
    flag: str, forged: object
) -> None:
    """(defence in depth) ``model_construct`` skips validators — the predicate does not.

    Every declared flag must be the singleton ``False``, so a truthy non-``bool`` smuggled
    past the schema is caught here.
    """
    forged_block = AllFalsePostTradeConsequence.model_construct(**{flag: forged})
    assert post_trade_consequence_all_false(forged_block) is False


@pytest.mark.parametrize("flag", sorted(AllFalsePostTradeConsequence.model_fields))
@pytest.mark.parametrize("falsy", [0, "", [], None, 0.0])
def test_a_falsy_non_bool_consequence_flag_is_also_rejected(
    flag: str, falsy: object
) -> None:
    """(review MINOR-5) The re-check demands the **singleton** ``False``, not falsiness.

    A ``releases_capacity=0`` block is not a proof that capacity is not released — it is a
    block whose type discipline was bypassed, and an ``is False`` gate says so while a
    ``not getattr(...)`` or ``== False`` gate would have waved ``0`` through. This closes the
    falsy half of the forgery axis; the truthy half is covered above.
    """
    forged_block = AllFalsePostTradeConsequence.model_construct(**{flag: falsy})
    assert post_trade_consequence_all_false(forged_block) is False


def test_a_zero_field_consequence_block_proves_nothing() -> None:
    """(∅ guard; the #21 M26 zero-field lesson) A block declaring no flag proves no absence.

    ``all(...)`` over an empty field set is vacuously ``True``, which would have made an
    empty block the strongest possible "grants nothing" claim.
    """

    from tos.posttrade import FrozenModel

    class _NoFlagsAtAll(FrozenModel):
        """A model whose field set really is empty — the vacuous ``all(...)`` case."""

    class _InheritsTheFive(AllFalsePostTradeConsequence):
        """A subclass declaring no *new* flag; it still inherits the five, so it passes."""

    assert post_trade_consequence_all_false(_NoFlagsAtAll()) is False  # type: ignore[arg-type]
    assert post_trade_consequence_all_false(_InheritsTheFive()) is True


@pytest.mark.parametrize("state", list(PostTradeObligationLifecycleState))
def test_no_lifecycle_state_creates_a_consequence(
    state: PostTradeObligationLifecycleState,
) -> None:
    """(§10 line 312) "No lifecycle state creates capacity release, available cash, legal
    title, or permission" — asserted on **all twelve**, including ``FINALITY_PROVEN``.

    There is deliberately **no positive side** to canary here: no input makes a consequence
    ``True``, because no consequence is ever granted.
    """
    record = clean_obligation_record(lifecycle_state=state)
    assert post_trade_consequence_all_false(record.consequence) is True
    assert record.consequence.releases_capacity is False
    assert record.consequence.makes_cash_available is False
    assert record.consequence.proves_legal_title is False
    assert record.consequence.grants_permission is False
    assert record.consequence.authorizes_transmission is False


def test_a_finality_proof_grants_nothing_either() -> None:
    """(§21 line 492) Finality proves the LEG, not the CONSEQUENCE."""
    proof = clean_finality_proof()
    assert finality_proof_class_specific(proof) is True
    assert post_trade_consequence_all_false(proof.consequence) is True
