"""§5.2 split polarity + units/rounding + residual (NT-EV-001 substrate).

*Discipline tag: predicate / coordinate substrate only. NT-EV-001 is ``EV-L1/3+Broker`` —
this authors the L1 slice and closes **nothing**; the ``/3`` integration-fault evidence, the
``+Broker`` Broker-Capability-Profile evidence, and the independent review remain
outstanding. No EV-L1-complete claim.*

The 3x3 truth table A is walked **exhaustively** and every cell's verdict is asserted, and
truth table B is walked over the declared-kind x derived-direction product. The directions
are never declared by the fixtures — :func:`spec_for_directions` moves the underlying
magnitudes and the predicate derives, which is the whole point of the M2 structural
promotion: **there is no direction field to forge**.

**No ratio constant appears in this module.** The fixtures move a magnitude up or down; no
test asserts a specific multiplier, because none exists in the implementation (design #21
§8.0).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.nontrade import (
    RECIPROCAL_DIRECTION_PAIRS,
    SPLIT_KIND_DIRECTIONS,
    SplitTransformationKind,
    SplitTransformationSpec,
    TransformationDirection,
    split_polarity_coherent,
    transformation_residual_conservative,
    transformation_units_and_rounding_explicit,
)
from tos.nontrade.predicates import _derive_direction

from ._nontrade_strategies import (
    MAGNITUDE_SLOT,
    clean_spec,
    spec_for_directions,
)

_ALL_CELLS = [
    (quantity, basis)
    for quantity in TransformationDirection
    for basis in TransformationDirection
]

# ---------------------------------------------------------------------------
# The derivation itself (M2 — direction is structural, not declared)
# ---------------------------------------------------------------------------


def test_the_direction_is_derived_from_the_magnitudes() -> None:
    """(M2) ``post > pre`` amplifies, ``post < pre`` attenuates, equal is identity."""
    assert (
        _derive_direction(Decimal("10"), Decimal("30"))
        is TransformationDirection.AMPLIFY
    )
    assert (
        _derive_direction(Decimal("30"), Decimal("10"))
        is TransformationDirection.ATTENUATE
    )
    assert (
        _derive_direction(Decimal("10"), Decimal("10"))
        is TransformationDirection.IDENTITY
    )
    # scale normalization: 10 and 10.00 are one magnitude, not an amplification
    assert (
        _derive_direction(Decimal("10"), Decimal("10.00"))
        is TransformationDirection.IDENTITY
    )


@given(MAGNITUDE_SLOT, MAGNITUDE_SLOT)
def test_an_underivable_direction_is_none_not_a_guess(
    pre: Decimal | None, post: Decimal | None
) -> None:
    """(§4.7 row 3) Absent or negative magnitudes ⇒ ``None``, which fails the predicate."""
    derived = _derive_direction(pre, post)
    if pre is None or post is None or pre < 0 or post < 0:
        assert derived is None
    else:
        assert derived is not None


def test_a_non_finite_magnitude_cannot_masquerade_as_a_direction() -> None:
    """(fail-closed) NaN makes every comparison ``False`` — it must not read as IDENTITY.

    ``CanonicalDecimal`` makes a NaN unconstructable inside a model, but the predicate is a
    plain function and a raw ``Decimal`` can reach it from an un-validated payload.
    """
    nan = Decimal("NaN")
    assert _derive_direction(nan, Decimal("1")) is None
    assert _derive_direction(Decimal("1"), nan) is None
    assert _derive_direction(Decimal("Infinity"), Decimal("1")) is None


# ---------------------------------------------------------------------------
# Truth table A — the whole 3x3, exhaustively
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("quantity", "basis"), _ALL_CELLS)
def test_truth_table_a_is_walked_exhaustively(
    quantity: TransformationDirection, basis: TransformationDirection
) -> None:
    """(§4.5 table A) All 9 derived cells; only the 3 reciprocal ones can be coherent.

    Each cell is built by **moving magnitudes**, so the derived directions are genuinely
    computed rather than declared. A cell outside the reciprocal set must be ``False``
    whatever the declared kind claims.
    """
    for kind in (*SplitTransformationKind, None):
        spec = spec_for_directions(quantity, basis, kind=kind)
        result = split_polarity_coherent(spec)
        reciprocal = (quantity, basis) in RECIPROCAL_DIRECTION_PAIRS
        if not reciprocal:
            assert result is False, "a non-reciprocal cell can never be coherent"
            continue
        if kind is None:
            expected = (quantity, basis) == (
                TransformationDirection.IDENTITY,
                TransformationDirection.IDENTITY,
            )
        else:
            expected = SPLIT_KIND_DIRECTIONS[kind] == (quantity, basis)
        assert result is expected


def test_both_amplify_and_both_attenuate_are_rejected_in_both_directions() -> None:
    """(§4.5 fail-open canary) The sign error is blocked whichever way it leans.

    Both-attenuate *under*-estimates notional and loses risk; both-amplify *over*-estimates
    and is conservative — but its direction is unproven, so a mis-specification is rejected
    either way rather than accepted "because it errs safe".
    """
    both_amplify = spec_for_directions(
        TransformationDirection.AMPLIFY,
        TransformationDirection.AMPLIFY,
        kind=SplitTransformationKind.FORWARD_SPLIT,
    )
    both_attenuate = spec_for_directions(
        TransformationDirection.ATTENUATE,
        TransformationDirection.ATTENUATE,
        kind=SplitTransformationKind.REVERSE_SPLIT,
    )
    assert split_polarity_coherent(both_amplify) is False
    assert split_polarity_coherent(both_attenuate) is False


def test_an_asymmetric_cell_is_rejected() -> None:
    """(§4.5) One axis moving while the other does not is a mis-specification."""
    for quantity, basis in (
        (TransformationDirection.AMPLIFY, TransformationDirection.IDENTITY),
        (TransformationDirection.IDENTITY, TransformationDirection.ATTENUATE),
    ):
        for kind in (*SplitTransformationKind, None):
            assert (
                split_polarity_coherent(spec_for_directions(quantity, basis, kind=kind))
                is False
            )


# ---------------------------------------------------------------------------
# Truth table B — declared kind vs derived direction (the M2 forgery canary)
# ---------------------------------------------------------------------------


def test_a_genuine_forward_split_is_coherent() -> None:
    """(availability side) The clean fixture is a real forward split."""
    assert split_polarity_coherent(clean_spec()) is True


def test_a_genuine_reverse_split_is_coherent() -> None:
    """(availability side) Quantity down, basis up, declared REVERSE_SPLIT."""
    reverse = spec_for_directions(
        TransformationDirection.ATTENUATE,
        TransformationDirection.AMPLIFY,
        kind=SplitTransformationKind.REVERSE_SPLIT,
    )
    assert split_polarity_coherent(reverse) is True


def test_forward_magnitudes_declared_reverse_are_rejected() -> None:
    """(M2 forgery canary) The declared kind cannot override the derived magnitudes."""
    mislabelled = clean_spec(kind=SplitTransformationKind.REVERSE_SPLIT)
    assert split_polarity_coherent(mislabelled) is False


def test_reverse_magnitudes_declared_forward_are_rejected() -> None:
    """(M2 forgery canary, the mirror case) Mis-labelling is caught both ways."""
    mislabelled = spec_for_directions(
        TransformationDirection.ATTENUATE,
        TransformationDirection.AMPLIFY,
        kind=SplitTransformationKind.FORWARD_SPLIT,
    )
    assert split_polarity_coherent(mislabelled) is False


def test_a_real_split_with_an_omitted_kind_is_rejected() -> None:
    """(table B ``None`` row) ``kind is None`` declares a no-op; real magnitudes contradict it."""
    assert split_polarity_coherent(clean_spec(kind=None)) is False


def test_the_identity_no_op_is_coherent_only_with_no_declared_kind() -> None:
    """(§10.4 G2) The ``(IDENTITY, IDENTITY)`` cell is the kind-less no-op row."""
    no_op = spec_for_directions(
        TransformationDirection.IDENTITY, TransformationDirection.IDENTITY, kind=None
    )
    assert split_polarity_coherent(no_op) is True
    for kind in SplitTransformationKind:
        labelled = spec_for_directions(
            TransformationDirection.IDENTITY,
            TransformationDirection.IDENTITY,
            kind=kind,
        )
        assert split_polarity_coherent(labelled) is False


@pytest.mark.parametrize(
    "forged", ["FORWARD_SPLIT", "REVERSE_SPLIT", "BANANA", "", 1, True, [1]]
)
def test_a_forged_kind_token_matches_no_truth_table_row(forged: object) -> None:
    """(fall-through ban) A raw string / truthy non-enum kind is not a declared kind.

    ``StrEnum`` compares equal to its value, so a bare ``"FORWARD_SPLIT"`` would satisfy an
    ``==`` lookup; the predicate demands the real member (``isinstance``) and a
    ``model_construct`` payload cannot slip past it.
    """
    spec = SplitTransformationSpec.model_construct(
        kind=forged,
        pre_quantity=Decimal("10"),
        post_quantity=Decimal("30"),
        pre_basis=Decimal("9"),
        post_basis=Decimal("3"),
        unit_spec="u",
        rounding_rule="r",
        fractional_residual=Decimal("0"),
        cash_in_lieu=Decimal("0"),
    )
    assert split_polarity_coherent(spec) is False


def test_a_none_spec_is_false_everywhere() -> None:
    """(fail-closed) No spec proves no polarity, no units, and no residual."""
    assert split_polarity_coherent(None) is False
    assert transformation_units_and_rounding_explicit(None) is False
    assert transformation_residual_conservative(None) is False


@given(MAGNITUDE_SLOT, MAGNITUDE_SLOT, MAGNITUDE_SLOT, MAGNITUDE_SLOT)
def test_any_missing_polarity_magnitude_fails_closed(
    pre_quantity: Decimal | None,
    post_quantity: Decimal | None,
    pre_basis: Decimal | None,
    post_basis: Decimal | None,
) -> None:
    """(§4.7 row 3) Four magnitude slots; any ``None`` / negative ⇒ no derivation ⇒ ``False``."""
    spec = clean_spec(
        pre_quantity=pre_quantity,
        post_quantity=post_quantity,
        pre_basis=pre_basis,
        post_basis=post_basis,
    )
    if any(
        value is None or value < 0
        for value in (pre_quantity, post_quantity, pre_basis, post_basis)
    ):
        assert split_polarity_coherent(spec) is False


# ---------------------------------------------------------------------------
# §11 line 227 — exact units and rounding (M1, a SEPARATE conjunct)
# ---------------------------------------------------------------------------


def test_explicit_units_and_rounding_pass() -> None:
    """(availability side) Both tokens declared ⇒ ``True``."""
    assert transformation_units_and_rounding_explicit(clean_spec()) is True


@pytest.mark.parametrize("field", ["unit_spec", "rounding_rule"])
@pytest.mark.parametrize("blank", [None, "", "   ", "\t\n"])
def test_a_missing_or_blank_unit_or_rounding_token_fails(
    field: str, blank: str | None
) -> None:
    """(§11 line 227 / §4.7 row 4) "Every transformation SHALL specify exact units...".

    A blank token specifies nothing, so it is rejected alongside ``None`` — a strictly
    narrower reading of "not-``None``" that can only fail closed.
    """
    assert transformation_units_and_rounding_explicit(clean_spec(**{field: blank})) is (
        False
    )


def test_units_and_rounding_is_independent_of_polarity() -> None:
    """(§5.2 M1) A coherent polarity must never promote an unspecified transformation."""
    unspecified = clean_spec(unit_spec=None, rounding_rule=None)
    assert split_polarity_coherent(unspecified) is True
    assert transformation_units_and_rounding_explicit(unspecified) is False


# ---------------------------------------------------------------------------
# §11 line 240 — explicit conservative residual
# ---------------------------------------------------------------------------


def test_explicit_non_negative_residuals_pass() -> None:
    """(availability side) Both residuals declared and non-negative ⇒ ``True``."""
    assert transformation_residual_conservative(clean_spec()) is True
    # an exact transformation declares an explicit zero rather than omitting the field
    exact = clean_spec(fractional_residual=Decimal("0"), cash_in_lieu=Decimal("0"))
    assert transformation_residual_conservative(exact) is True


@pytest.mark.parametrize("field", ["fractional_residual", "cash_in_lieu"])
def test_a_hidden_or_negative_residual_fails(field: str) -> None:
    """(§11 line 240 / §4.7 row 5) ``None`` hides the residual; a negative one credits it."""
    assert transformation_residual_conservative(clean_spec(**{field: None})) is False
    assert (
        transformation_residual_conservative(clean_spec(**{field: Decimal("-1")}))
        is False
    )


def test_residual_is_independent_of_polarity_and_units() -> None:
    """(§5.2) The three verdicts are separate conjuncts, never a fall-through chain."""
    hidden = clean_spec(fractional_residual=None)
    assert split_polarity_coherent(hidden) is True
    assert transformation_units_and_rounding_explicit(hidden) is True
    assert transformation_residual_conservative(hidden) is False


@given(st.sampled_from(list(SplitTransformationKind)))
def test_no_predicate_asserts_a_specific_ratio(kind: SplitTransformationKind) -> None:
    """(§8.0) Polarity holds for *any* magnitude pair in the right direction.

    If a ratio were hardcoded anywhere, only one particular pair would pass. Several
    unrelated pairs in the same direction all pass, which is the observable signature of a
    ratio-free implementation.
    """
    quantity, basis = SPLIT_KIND_DIRECTIONS[kind]
    for scale in ("2", "3", "7", "101"):
        factor = Decimal(scale)
        up, down = Decimal("1") * factor, Decimal("1")
        pre_quantity, post_quantity = (
            (down, up) if quantity is TransformationDirection.AMPLIFY else (up, down)
        )
        pre_basis, post_basis = (
            (down, up) if basis is TransformationDirection.AMPLIFY else (up, down)
        )
        spec = clean_spec(
            kind=kind,
            pre_quantity=pre_quantity,
            post_quantity=post_quantity,
            pre_basis=pre_basis,
            post_basis=post_basis,
        )
        assert split_polarity_coherent(spec) is True
