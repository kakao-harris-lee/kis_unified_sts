"""Seam: ``tos.posttrade`` <-> ``tos.recon`` — confidence is not finality.

**Proposition identity (design #24 §3.5 verdict 2).** PTF-INV-005 verbatim: "One global
``SETTLED``, ``CLOSED``, **confidence score**, statement flag, or operator decision cannot
replace exact per-field proof." recon owns **per-field evidence confidence**
(``classify_field`` / ``FieldConfidenceClass``); this package owns **field-specific finality
proof**. A ``CORROBORATED`` grade is a *necessary input* to a finality claim and never a
substitute for one.

**Grain identity (design #24 §3.5, the §19 row).** recon's common-mode rule
(``recon/predicates.py:127``, RECON-EV-001: "common-mode paths (shared ``independence_class``)
cannot corroborate each other") works at the **per-field** grain; this package's
:func:`~tos.posttrade.statement_sources_independent` works at the **statement-source** grain
(book / parser / administrator / transport). Complementary, never substitutes — and the
coverage-completeness judgment has no recon counterpart at all.

recon additionally already owns the post-trade safety fields, which is exactly why this
package consumes their confidence rather than re-deriving it.

Locks **3** of the 19 injected tokens: ``CORROBORATED``, ``UNKNOWN``, ``CONFLICTED``.
Test-only sibling imports are not runtime package edges.
"""

from __future__ import annotations

import tos.posttrade.predicates as posttrade_predicates
from tos.posttrade import (
    FIELD_CONFIDENCE_CONFLICTED,
    FIELD_CONFIDENCE_CORROBORATED,
    FIELD_CONFIDENCE_UNKNOWN,
    PostTradeDisposition,
    post_trade_disposition,
    statement_sources_independent,
)

from ._posttrade_strategies import clean_disposition_kwargs, clean_finality_proof


def test_field_confidence_token_drift_locks() -> None:
    """(tokens 8-10 of 19) The three recon ``FieldConfidenceClass`` members read here."""
    from tos.recon import FieldConfidenceClass

    assert FieldConfidenceClass.CORROBORATED.value == FIELD_CONFIDENCE_CORROBORATED
    assert FieldConfidenceClass.UNKNOWN.value == FIELD_CONFIDENCE_UNKNOWN
    assert FieldConfidenceClass.CONFLICTED.value == FIELD_CONFIDENCE_CONFLICTED


def test_the_two_confidence_grades_this_package_does_not_treat_as_corroboration() -> (
    None
):
    """(recon 5-member enum) ``SINGLE_SOURCE`` and ``STALE`` are truthy strings, not proof.

    A truthiness-based gate would have admitted both; the ``==`` comparison against the exact
    ``CORROBORATED`` token does not.
    """
    from tos.recon import FieldConfidenceClass

    assert len(list(FieldConfidenceClass)) == 5
    for grade in (FieldConfidenceClass.SINGLE_SOURCE, FieldConfidenceClass.STALE):
        assert grade.value not in (
            FIELD_CONFIDENCE_CORROBORATED,
            FIELD_CONFIDENCE_UNKNOWN,
            FIELD_CONFIDENCE_CONFLICTED,
        )
        verdict = post_trade_disposition(
            **clean_disposition_kwargs(field_confidence=grade.value)
        )
        assert verdict is PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK


def test_corroborated_confidence_is_necessary_but_not_sufficient_for_finality() -> None:
    """(PTF-INV-005) Confidence is an input to the fold; the proof is a separate premise.

    A ``CORROBORATED`` grade with a non-class-specific proof still yields
    ``POST_TRADE_CONFLICTED`` — the grade did not substitute for the proof.
    """
    verdict = post_trade_disposition(
        **clean_disposition_kwargs(
            field_confidence=FIELD_CONFIDENCE_CORROBORATED,
            proof_class_specific=False,
        )
    )
    assert verdict is PostTradeDisposition.POST_TRADE_CONFLICTED


def test_this_package_does_not_classify_field_confidence() -> None:
    """(§3.5 verdict 2) recon owns ``classify_field``; there is no counterpart here."""
    for forbidden in (
        "classify_field",
        "field_confidence",
        "merge_conservative",
        "any_field_conflicted",
    ):
        assert not hasattr(posttrade_predicates, forbidden)


def test_recon_owns_the_post_trade_safety_fields_this_package_consumes() -> None:
    """(§3.5) The post-trade fields already have a per-field confidence owner."""
    from tos.recon import SafetyRelevantField

    assert hasattr(SafetyRelevantField, "POST_TRADE_OBLIGATION_IDENTITY_AND_VERSION")
    assert hasattr(
        SafetyRelevantField, "SETTLEMENT_CASH_AVAILABILITY_COLLATERAL_ELIGIBILITY"
    )
    assert hasattr(SafetyRelevantField, "CASH_MARGIN_COLLATERAL")


def test_the_two_common_mode_rules_are_at_different_grains() -> None:
    """(§3.5, §19 row) recon: per-field independence class. Ours: statement-source set.

    Both are real, both are necessary, and neither is a substitute for the other. Ours is
    exercised on a source-dependency set that recon's per-field classifier would never see.
    """
    from tos.recon import classify_field

    assert callable(classify_field)
    assert (
        statement_sources_independent(frozenset({"book-a"}), frozenset({"book-a"}))
        is False
    )
    assert (
        statement_sources_independent(frozenset({"book-a"}), frozenset({"book-b"}))
        is True
    )


def test_a_finality_proof_carries_no_confidence_score_field() -> None:
    """(PTF-INV-005 structural) There is no field in which a score could substitute."""
    proof = clean_finality_proof()
    assert not hasattr(proof, "confidence_score")
    assert not hasattr(proof, "field_confidence")
