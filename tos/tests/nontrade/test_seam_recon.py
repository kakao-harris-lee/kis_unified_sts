"""MANDATED test-only seam cross-check: nontrade <-> recon / ADR-002-006 (§3.4(d)).

ADR-002-010 §7 defers explicitly: "The Reconciliation Service SHALL evaluate each material
field independently." So per-field evidence confidence is **recon's** (``classify_field``),
and ``tos.nontrade`` consumes the produced class as an injected token without re-authoring
any part of the classification (design #21 §3.5).

The two recon propositions this file drives live are the ones NT depends on most:

* **0 usable paths ⇒ ``UNKNOWN``** (never a vacuous ``CORROBORATED``) — which nontrade folds
  to ``NONTRADE_QUARANTINED_UNKNOWN``;
* **common-mode is not corroboration** (§7 line 159) and **majority vote resolves nothing**
  (§7 line 161) — two paths sharing an independence class stay ``SINGLE_SOURCE``, which
  nontrade blocks rather than admits.

A test-only cross-import is **not** a runtime package edge (design #21 §3.4(d)/§7.1).
"""

from __future__ import annotations

from tos.nontrade import (
    FIELD_CONFIDENCE_CONFLICTED,
    FIELD_CONFIDENCE_CORROBORATED,
    FIELD_CONFIDENCE_UNKNOWN,
    NonTradeDisposition,
    NonTradeEventWorkflowState,
    nontrade_disposition,
)
from tos.recon import (
    EvidencePathObservation,
    FieldConfidenceClass,
    FreshnessMarker,
    SafetyRelevantField,
    classify_field,
)

from ._nontrade_strategies import clean_disposition_inputs

_FRESH = FreshnessMarker(
    fresh_within_horizon=True,
    time_confidence_held=True,
    time_generation=1,
    anchored_generation=1,
)


def _path(
    independence_class: str | None, *, agrees: bool | None = True
) -> EvidencePathObservation:
    """One evidence path for the instrument-identity field."""
    return EvidencePathObservation(
        field=SafetyRelevantField.INSTRUMENT_IDENTITY,
        source_ref=f"src-{independence_class}",
        independence_class=independence_class,
        agrees_within_tolerance=agrees,
        freshness_marker=_FRESH,
    )


# ---------------------------------------------------------------------------
# recon's classification, driven live
# ---------------------------------------------------------------------------


def test_zero_usable_paths_is_unknown_and_nontrade_quarantines() -> None:
    """(§7 / §4.7 row 14) No evidence is UNKNOWN, never a vacuous corroboration."""
    verdict = classify_field([], _FRESH)
    assert verdict is FieldConfidenceClass.UNKNOWN
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(field_confidences=frozenset({verdict.value}))
        )
        is NonTradeDisposition.NONTRADE_QUARANTINED_UNKNOWN
    )


def test_common_mode_paths_do_not_corroborate_and_nontrade_blocks() -> None:
    """(§7 line 159) Two paths sharing an independence class are one source.

    "More observations" is not "more independence": a shared parser / source / clock /
    transport defect corrupts both the same way, so the class stays ``SINGLE_SOURCE`` and
    nontrade blocks rather than admitting.
    """
    verdict = classify_field([_path("feed-a"), _path("feed-a")], _FRESH)
    assert verdict is FieldConfidenceClass.SINGLE_SOURCE
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(field_confidences=frozenset({verdict.value}))
        )
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )


def test_independent_agreeing_paths_corroborate_and_nontrade_admits() -> None:
    """(availability side) Two genuinely independent agreeing paths are corroboration."""
    verdict = classify_field([_path("feed-a"), _path("feed-b")], _FRESH)
    assert verdict is FieldConfidenceClass.CORROBORATED
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(field_confidences=frozenset({verdict.value}))
        )
        is NonTradeDisposition.NONTRADE_ADMISSIBLE
    )


def test_disagreeing_independent_paths_conflict_and_nontrade_reports_conflicted() -> (
    None
):
    """(§7 line 101 / §4.7 row 14) Disagreement beyond tolerance is CONFLICTED.

    §7 line 161: majority vote SHALL NOT resolve conflicting semantics, which is why
    nontrade returns its most conservative member instead of picking a side.
    """
    verdict = classify_field([_path("feed-a"), _path("feed-b", agrees=False)], _FRESH)
    assert verdict is FieldConfidenceClass.CONFLICTED
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(field_confidences=frozenset({verdict.value}))
        )
        is NonTradeDisposition.NONTRADE_CONFLICTED
    )


def test_an_absence_observation_never_raises_confidence() -> None:
    """(§7 line 102) An absence may lower confidence; it never establishes anything."""
    absent = EvidencePathObservation(
        field=SafetyRelevantField.EXTERNAL_UNATTRIBUTED_ACTIVITY,
        source_ref="src-absent",
        independence_class="feed-c",
        agrees_within_tolerance=True,
        is_absence=True,
        freshness_marker=_FRESH,
    )
    verdict = classify_field([_path("feed-a"), absent], _FRESH)
    assert verdict is not FieldConfidenceClass.CORROBORATED
    assert (
        nontrade_disposition(
            **clean_disposition_inputs(field_confidences=frozenset({verdict.value}))
        )
        is not NonTradeDisposition.NONTRADE_ADMISSIBLE
    )


# ---------------------------------------------------------------------------
# Token drift + ownership boundaries
# ---------------------------------------------------------------------------


def test_the_local_field_confidence_tokens_are_drift_locked() -> None:
    """(§3.4 drift lock) A recon rename breaks here, not silently downgrades a comparison."""
    assert FieldConfidenceClass.CORROBORATED.value == FIELD_CONFIDENCE_CORROBORATED
    assert FieldConfidenceClass.UNKNOWN.value == FIELD_CONFIDENCE_UNKNOWN
    assert FieldConfidenceClass.CONFLICTED.value == FIELD_CONFIDENCE_CONFLICTED


def test_the_weaker_grades_are_recognized_as_non_corroboration() -> None:
    """(§5.5) ``SINGLE_SOURCE`` / ``STALE`` are truthy strings that must **not** pass."""
    for weaker in (FieldConfidenceClass.SINGLE_SOURCE, FieldConfidenceClass.STALE):
        assert weaker.value != FIELD_CONFIDENCE_CORROBORATED
        assert (
            nontrade_disposition(
                **clean_disposition_inputs(field_confidences=frozenset({weaker.value}))
            )
            is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
        )


def test_the_two_non_closed_safety_fields_nontrade_leans_on_exist() -> None:
    """(§3.4) recon's minimum set names the two fields ADR-002-010 §12 / §16 care about."""
    assert SafetyRelevantField.INSTRUMENT_IDENTITY is not None
    assert SafetyRelevantField.EXTERNAL_UNATTRIBUTED_ACTIVITY is not None


def test_nontrade_re_authors_no_part_of_the_classification() -> None:
    """(§0.2/§3.5) The classifier, the classes, and the field vocabulary are all recon's."""
    from tos import nontrade as nontrade_pkg

    for forbidden in (
        "classify_field",
        "FieldConfidenceClass",
        "SafetyRelevantField",
        "ConservativeBound",
        "merge_conservative",
        "any_field_conflicted",
        "freshness_ok",
    ):
        assert not hasattr(nontrade_pkg, forbidden), (
            f"{forbidden} is recon-owned — ADR-002-010 §7 defers per-field evaluation "
            "explicitly to the Reconciliation Service"
        )


def test_the_field_confidence_axis_is_not_the_event_workflow_axis() -> None:
    """(§2.2-5) ``CONFLICTED`` on two axes is two types, never one meaning."""
    assert NonTradeEventWorkflowState.CONFLICTED is not FieldConfidenceClass.CONFLICTED
    assert (
        NonTradeEventWorkflowState.QUARANTINED_UNKNOWN
        is not FieldConfidenceClass.UNKNOWN
    )
