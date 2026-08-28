"""Field release proof rule: all-must-pass conjunction + single-source ceiling (§6.1/§6.2).

RECON-EV-005 predicate substrate. The §8 generic contract is a four-conjunct all-must-
pass rule; every weaker evidence path fails closed. The ADR §2 hazard property: no
aggregate of strong fields can rescue one dangerously-wrong field (design #9 §4.1).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.recon import (
    CAPACITY_RELEASING_FIELDS,
    FieldConfidence,
    FieldConfidenceClass,
    SafetyRelevantField,
    field_reconciled_proof_ok,
    field_specific_release_proof_ok,
)

from ._recon_strategies import (
    field_confidence,
    field_confidences,
    fresh_marker,
    release_inputs,
    stale_marker,
)

_C = FieldConfidenceClass
_CAP = SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY
_NONCAP = SafetyRelevantField.ORDER_EXISTENCE


# ---------------------------------------------------------------------------
# field_reconciled_proof_ok — positive path + fail-closed conjuncts
# ---------------------------------------------------------------------------


def test_reconciled_ok_positive_capacity_field() -> None:
    """(positive) CORROBORATED + FQP + fresh => the capacity-releasing field's proof holds."""
    conf = field_confidence(field=_CAP, confidence_class=_C.CORROBORATED)
    assert field_reconciled_proof_ok(_CAP, conf, release_inputs()) is True


def test_reconciled_ok_non_capacity_field_needs_no_fqp() -> None:
    """A non-capacity-releasing field reconciles on CORROBORATED + fresh (no FQP required)."""
    conf = field_confidence(field=_NONCAP, confidence_class=_C.CORROBORATED)
    inputs = release_inputs(final_quantity_proof_token=None)  # no FQP
    assert field_reconciled_proof_ok(_NONCAP, conf, inputs) is True


@pytest.mark.parametrize(
    "weaker_class",
    [_C.UNKNOWN, _C.SINGLE_SOURCE, _C.STALE, _C.CONFLICTED],
)
def test_reconciled_fails_below_corroborated(
    weaker_class: FieldConfidenceClass,
) -> None:
    """(fail-closed) Any class below CORROBORATED fails the proof rule (incl. CONFLICTED (d))."""
    conf = field_confidence(field=_CAP, confidence_class=weaker_class)
    assert field_reconciled_proof_ok(_CAP, conf, release_inputs()) is False


def test_reconciled_fails_without_fqp_on_capacity_field() -> None:
    """(fail-closed b) A capacity-releasing field with no FQP token fails."""
    conf = field_confidence(field=_CAP, confidence_class=_C.CORROBORATED)
    assert (
        field_reconciled_proof_ok(
            _CAP, conf, release_inputs(final_quantity_proof_token=None)
        )
        is False
    )
    assert (
        field_reconciled_proof_ok(
            _CAP, conf, release_inputs(final_quantity_proof_token=False)
        )
        is False
    )


def test_reconciled_fails_when_not_fresh() -> None:
    """(fail-closed c) An aged freshness marker fails the proof rule."""
    conf = field_confidence(field=_CAP, confidence_class=_C.CORROBORATED)
    assert (
        field_reconciled_proof_ok(_CAP, conf, release_inputs(freshness=stale_marker()))
        is False
    )


# ---------------------------------------------------------------------------
# Drop-one sweep over the proof-rule conjuncts (capacity-releasing field)
# ---------------------------------------------------------------------------

_CONJUNCT_DROPS = [
    pytest.param({"confidence_class": _C.SINGLE_SOURCE}, {}, id="drop-corroborated"),
    pytest.param({}, {"final_quantity_proof_token": None}, id="drop-fqp"),
    pytest.param({}, {"freshness": stale_marker()}, id="drop-freshness"),
]


@pytest.mark.parametrize("conf_override,input_override", _CONJUNCT_DROPS)
def test_release_proof_drop_one_conjunct_fails(
    conf_override: dict, input_override: dict
) -> None:
    """(drop-one) Dropping ANY one of {CORROBORATED, FQP, fresh} fails the release proof."""
    conf = field_confidence(
        field=_CAP, **conf_override
    )  # builder default class = CORROBORATED
    inputs = release_inputs(**input_override)
    # The full positive holds; dropping one conjunct breaks it.
    assert (
        field_specific_release_proof_ok(
            _CAP, field_confidence(field=_CAP), release_inputs()
        )
        is True
    )
    assert field_specific_release_proof_ok(_CAP, conf, inputs) is False


# ---------------------------------------------------------------------------
# field_specific_release_proof_ok — capacity-releasing only + weaker-evidence table
# ---------------------------------------------------------------------------


def test_release_only_for_capacity_releasing_fields() -> None:
    """(§6.2) A non-capacity-releasing field never yields a release proof, however strong."""
    conf = field_confidence(field=_NONCAP, confidence_class=_C.CORROBORATED)
    assert field_specific_release_proof_ok(_NONCAP, conf, release_inputs()) is False


def test_release_complete_fqp_is_the_only_ok() -> None:
    """(both-ways) Only the complete proof (CORROBORATED + FQP + fresh) permits release."""
    conf = field_confidence(field=_CAP, confidence_class=_C.CORROBORATED)
    assert field_specific_release_proof_ok(_CAP, conf, release_inputs()) is True


@pytest.mark.parametrize(
    "label,conf_override,input_override",
    [
        ("cancel-ack (no FQP)", {}, {"final_quantity_proof_token": None}),
        ("terminal-no-qty (no FQP)", {}, {"final_quantity_proof_token": False}),
        ("single-source query", {"confidence_class": _C.SINGLE_SOURCE}, {}),
        ("late-correction (stale)", {}, {"freshness": stale_marker()}),
        ("conflicted", {"confidence_class": _C.CONFLICTED}, {}),
    ],
)
def test_weaker_evidence_never_releases(
    label: str, conf_override: dict, input_override: dict
) -> None:
    """(§6.2 weaker-evidence table) Every weaker evidence path preserves the conservative commitment."""
    conf = field_confidence(
        field=_CAP, **conf_override
    )  # builder default class = CORROBORATED
    inputs = release_inputs(**input_override)
    assert field_specific_release_proof_ok(_CAP, conf, inputs) is False, label


# ---------------------------------------------------------------------------
# Single-source ceiling — no input combination lifts SINGLE_SOURCE to release
# ---------------------------------------------------------------------------


@given(
    fqp=st.sampled_from([True, False, None]),
    field=st.sampled_from(sorted(CAPACITY_RELEASING_FIELDS)),
)
def test_single_source_never_releases(
    fqp: bool | None, field: SafetyRelevantField
) -> None:
    """(§4.5 ceiling) SINGLE_SOURCE + FQP + fresh never releases — no residual-lift path."""
    conf = field_confidence(field=field, confidence_class=_C.SINGLE_SOURCE)
    inputs = release_inputs(final_quantity_proof_token=fqp, freshness=fresh_marker())
    assert field_specific_release_proof_ok(field, conf, inputs) is False
    assert field_reconciled_proof_ok(field, conf, inputs) is False


# ---------------------------------------------------------------------------
# No-blended aggregate hazard (ADR §2) — a weak field is never masked by strong ones
# ---------------------------------------------------------------------------


def test_one_weak_field_blocks_release_regardless_of_others() -> None:
    """(ADR §2 hazard) A dangerously-wrong field fails release even when every other is strong."""
    weak = field_confidence(field=_CAP, confidence_class=_C.CONFLICTED)
    strong_others = [
        field_confidence(field=f, confidence_class=_C.CORROBORATED)
        for f in SafetyRelevantField
        if f is not _CAP
    ]
    # An all-must-pass conjunction over the scope: the weak capacity field is False,
    # so the conjunction is False no matter how strong every other field is.
    per_field = [
        field_specific_release_proof_ok(fc.field, fc, release_inputs())
        for fc in [weak, *strong_others]
        if fc.field in CAPACITY_RELEASING_FIELDS
    ]
    assert all(
        field_reconciled_proof_ok(fc.field, fc, release_inputs())
        for fc in strong_others
    )
    assert field_specific_release_proof_ok(_CAP, weak, release_inputs()) is False
    assert all(per_field) is False


@given(fc=field_confidences(), fqp=st.sampled_from([True, False, None]))
def test_release_requires_corroborated_property(
    fc: FieldConfidence, fqp: bool | None
) -> None:
    """(property) A release proof implies the field was CORROBORATED and fresh — never below."""
    field = fc.field if fc.field is not None else _CAP
    inputs = release_inputs(final_quantity_proof_token=fqp)
    if field_specific_release_proof_ok(field, fc, inputs):
        assert fc.confidence_class is _C.CORROBORATED
        assert field in CAPACITY_RELEASING_FIELDS


def test_field_confidence_mismatch_fails_closed() -> None:
    """(canary) A confidence object belonging to ANOTHER field cannot prove this field.

    Code-review MINOR-1 defense-in-depth: an incoherent ``(field, confidence)`` pairing
    — e.g. asking about CUMULATIVE_FILLED_QUANTITY with a fully-CORROBORATED confidence
    that belongs to POSITION_QUANTITY — fails closed even with FQP + freshness all strong.
    """
    other = field_confidence(
        field=SafetyRelevantField.POSITION_QUANTITY,
        confidence_class=_C.CORROBORATED,
    )
    inputs = release_inputs(final_quantity_proof_token=True)
    assert field_reconciled_proof_ok(_CAP, other, inputs) is False
    assert field_specific_release_proof_ok(_CAP, other, inputs) is False
    # Coherent pairing (guard fires both ways): the same strength on the RIGHT field passes.
    own = field_confidence(field=_CAP, confidence_class=_C.CORROBORATED)
    assert field_reconciled_proof_ok(_CAP, own, inputs) is True
