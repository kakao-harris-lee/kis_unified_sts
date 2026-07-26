"""evidence_package_complete yolk (RLP-EV-005) + negative-retention coexistence seal (design #25 §5.2).

The yolk 2 property suite: ∅ both-ways, drop-one element-class incompleteness, negative-result
retention gate, selection-fixed / no-selective-reporting polarity, injected integrity verdicts — plus
the coexistence seal (``promotion_complete_claim is True`` ∧ a negative class absent ⇒ unconstructable,
v1.1 MINOR-3) and the EvidenceClass anchor.

Regime tag: structural / completeness predicate substrate only; RLP-EV-005 NOT_IMPLEMENTED
(``EV-L1/3``); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given
from tos.rlp import (
    MANDATED_EVIDENCE_FLOOR,
    NEGATIVE_RESULT_CLASSES,
    ArtifactIntegrityError,
    EvidenceClass,
    TrialEvidencePackage,
    evidence_package_complete,
    negative_results_retained,
    no_selective_reporting,
)

from ._rlp_strategies import TRIBOOL, clean_package, clean_policy

#: The §16 line 417-424 element catalogue, transcribed by hand (NOT derived; design #25 §0.4h).
_EVIDENCE_ANCHOR: frozenset[str] = frozenset(
    {
        # event classes (§16 line 417)
        "PROPOSED",
        "DENIED",
        "COMMITTED",
        "TRANSMITTED",
        "ACKNOWLEDGED",
        "FILLED",
        "CANCELLED",
        "CORRECTED",
        "EXTERNAL",
        "PROTECTIVE",
        "ABORT",
        "RECOVERY",
        # capacity / flow (§16 line 418)
        "RCL_TRANSITIONS",
        "ACTION_FLOW_TRANSITIONS",
        "POTENTIALLY_LIVE_INTERVALS",
        "FINAL_QUANTITY_EVIDENCE",
        # coverage / negative (§16 line 419-422)
        "COVERAGE_CLAIMS",
        "UNEXERCISED_CONDITIONS",
        "DEVIATIONS",
        "COMMON_MODES",
        "NEGATIVE_RESULTS",
        "FAILED_RESULTS",
        "INCONCLUSIVE_RESULTS",
        "ABORTED_RESULTS",
        "CONFLICTING_RESULTS",
        "SUPERSEDED_RESULTS",
        # broker evidence (§16 line 420)
        "RAW_BROKER_EVIDENCE",
        "NORMALIZED_BROKER_EVIDENCE",
        "SOURCE_CONTINUITY",
        "GAPS",
        # generations / review (§16 line 423-424)
        "SOFTWARE_GENERATION",
        "CONFIGURATION_GENERATION",
        "BROKER_PROFILE",
        "IDENTITIES",
        "REVIEWER_DECISIONS",
        "INDEPENDENT_REPRODUCTION",
        "INDEPENDENT_REVIEW",
    }
)


def test_evidence_class_matches_the_section16_anchor() -> None:
    """(§7.2 anchor drift) EvidenceClass == the §16 line 417-424 reference set — a drift is caught."""
    assert {c.value for c in EvidenceClass} == _EVIDENCE_ANCHOR
    assert frozenset(EvidenceClass) == MANDATED_EVIDENCE_FLOOR
    assert frozenset(EvidenceClass) >= NEGATIVE_RESULT_CLASSES


def test_empty_seal_both_ways() -> None:
    """(§5.2 point 1) None package / None policy / ∅ mandate all deny."""
    package = clean_package()
    policy = clean_policy()
    assert evidence_package_complete(None, policy, MANDATED_EVIDENCE_FLOOR) is False
    assert evidence_package_complete(package, None, MANDATED_EVIDENCE_FLOOR) is False
    assert evidence_package_complete(package, policy, frozenset()) is False


def test_clean_package_is_complete() -> None:
    """(§5.2 positive) A genuinely complete package (all classes + negatives + integrity) passes."""
    assert (
        evidence_package_complete(
            clean_package(), clean_policy(), MANDATED_EVIDENCE_FLOOR
        )
        is True
    )


@given(dropped=st.sampled_from(list(EvidenceClass)))
def test_drop_one_element_class_denies(dropped: EvidenceClass) -> None:
    """(§5.2 point 2 / drop-one) A package missing any one mandated element class is incomplete."""
    package = clean_package(present_element_classes=MANDATED_EVIDENCE_FLOOR - {dropped})
    assert (
        evidence_package_complete(package, clean_policy(), MANDATED_EVIDENCE_FLOOR)
        is False
    )


@given(dropped=st.sampled_from(list(NEGATIVE_RESULT_CLASSES)))
def test_negative_class_absence_denies_retention(dropped: EvidenceClass) -> None:
    """(§5.2 point 3 / RLP-INV-009) Dropping any negative-result class fails the retention gate."""
    package = clean_package(present_element_classes=MANDATED_EVIDENCE_FLOOR - {dropped})
    assert negative_results_retained(package) is False
    assert (
        evidence_package_complete(package, clean_policy(), MANDATED_EVIDENCE_FLOOR)
        is False
    )


def test_negative_results_retained_positive() -> None:
    """(§5.2 point 3) A full manifest retains every negative-result class."""
    assert negative_results_retained(clean_package()) is True


@given(fixed=TRIBOOL)
def test_selection_fixed_before_start_positive_polarity(fixed: bool | None) -> None:
    """(§5.2 point 4 / §4.3) selection_fixed_before_start: only True clears; None / False deny."""
    package = clean_package(selection_fixed_before_start=fixed)
    assert no_selective_reporting(package) is (fixed is True)
    assert evidence_package_complete(
        package, clean_policy(), MANDATED_EVIDENCE_FLOOR
    ) is (fixed is True)


@given(
    optional_stopping=TRIBOOL,
    discarded_runs=TRIBOOL,
    selected_windows=TRIBOOL,
    removed_adverse=TRIBOOL,
)
def test_post_hoc_selection_negative_polarity(
    optional_stopping: bool | None,
    discarded_runs: bool | None,
    selected_windows: bool | None,
    removed_adverse: bool | None,
) -> None:
    """(§5.2 point 4 / §4.3) Any post-hoc selection flag not-False invalidates the claim."""
    package = clean_package(
        optional_stopping=optional_stopping,
        discarded_runs=discarded_runs,
        selected_windows=selected_windows,
        removed_adverse=removed_adverse,
    )
    expected = (
        optional_stopping is False
        and discarded_runs is False
        and selected_windows is False
        and removed_adverse is False
    )
    assert no_selective_reporting(package) is expected


@given(causal=TRIBOOL, gap=TRIBOOL)
def test_injected_integrity_verdicts(causal: bool | None, gap: bool | None) -> None:
    """(§5.2 point 5 / §0.4d) causal_chain_complete positive + has_unresolved_gap negative polarity."""
    package = clean_package(causal_chain_complete=causal, has_unresolved_gap=gap)
    expected = causal is True and gap is False
    assert (
        evidence_package_complete(package, clean_policy(), MANDATED_EVIDENCE_FLOOR)
        is expected
    )


def test_coexistence_seal_blocks_complete_claim_without_negatives() -> None:
    """(§2.3 v1.1 MINOR-3) promotion_complete_claim=True with a negative class absent is unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_package(
            promotion_complete_claim=True,
            present_element_classes=MANDATED_EVIDENCE_FLOOR
            - {EvidenceClass.NEGATIVE_RESULTS},
        )


def test_superseded_results_is_a_retained_negative_class() -> None:
    """(#25 MINOR-1 / §16 line 422) SUPERSEDED_RESULTS is one of the six retained negative classes."""
    assert EvidenceClass.SUPERSEDED_RESULTS in NEGATIVE_RESULT_CLASSES
    assert len(NEGATIVE_RESULT_CLASSES) == 6
    # dropping SUPERSEDED_RESULTS fails the retention gate ...
    package = clean_package(
        present_element_classes=MANDATED_EVIDENCE_FLOOR
        - {EvidenceClass.SUPERSEDED_RESULTS}
    )
    assert negative_results_retained(package) is False
    assert (
        evidence_package_complete(package, clean_policy(), MANDATED_EVIDENCE_FLOOR)
        is False
    )
    # ... and a promotion-complete claim that omits it is unconstructable (coexistence seal).
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_package(
            promotion_complete_claim=True,
            present_element_classes=MANDATED_EVIDENCE_FLOOR
            - {EvidenceClass.SUPERSEDED_RESULTS},
        )


def test_coexistence_seal_allows_complete_claim_with_negatives() -> None:
    """(§2.3) promotion_complete_claim=True WITH every negative class present is constructable."""
    package = clean_package(promotion_complete_claim=True)
    assert package.promotion_complete_claim is True


def test_model_construct_bypass_recaught_by_predicate() -> None:
    """(§2.3 defence in depth) A model_construct malformed package is re-caught by the predicate."""
    malformed = TrialEvidencePackage.model_construct(
        package_id="p",
        promotion_complete_claim=True,
        present_element_classes=MANDATED_EVIDENCE_FLOOR
        - {EvidenceClass.FAILED_RESULTS},
        selection_fixed_before_start=True,
        optional_stopping=False,
        discarded_runs=False,
        selected_windows=False,
        removed_adverse=False,
        causal_chain_complete=True,
        has_unresolved_gap=False,
    )
    assert negative_results_retained(malformed) is False
    assert (
        evidence_package_complete(malformed, clean_policy(), MANDATED_EVIDENCE_FLOOR)
        is False
    )
