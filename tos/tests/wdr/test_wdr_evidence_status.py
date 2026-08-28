"""evidence_status_honest yolk 4 — no deviation-driven PASS flip, WAIVED exact-current (design #26 §5.4).

Both-ways canary. WDR owns the ``WaivedEvidenceStatus`` verification-status honesty vocabulary
(``tos.evidence`` does not — §0.4d, seam conflict 0). A deviation existing never flips an item to
``PASS``; a measured failure stays visible; ``WAIVED_WITH_RESIDUAL_RISK`` needs the exact-current gate.

Regime tag: evidence-status predicate substrate only; WDR-EV-010 NOT_IMPLEMENTED (EV-L1/3);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import tos.wdr as w

from ._wdr_strategies import clean_waived_item

WS = w.WaivedEvidenceStatus


def test_clean_waived_item_is_honest() -> None:
    """(§5.4 positive) A WAIVED item with the exact-current gate satisfied ⇒ honest."""
    assert w.evidence_status_honest(clean_waived_item()) is True


def test_none_item_denies() -> None:
    """(§5.4 ∅-seal) A None item ⇒ deny (never vacuously honest)."""
    assert w.evidence_status_honest(None) is False


def test_deviation_present_pass_relabel_is_dishonest() -> None:
    """(§19 line 490 / WDR-INV-004) A deviation existing while relabeled PASS ⇒ dishonest (deny)."""
    item = clean_waived_item(
        measured_status=WS.FAIL,
        deviation_exists=True,
        relabeled_status=WS.PASS,
    )
    assert w.evidence_status_honest(item) is False


def test_unknown_deviation_pass_relabel_is_dishonest() -> None:
    """(§4.3 negative polarity) An unknown (None) deviation while relabeled PASS ⇒ dishonest (deny).

    ``deviation_exists`` is negative-polarity — a ``None`` (unknown-deviation) still blocks the PASS
    relabel (``is not False`` covers True AND None); a fail-open here would let an unknown deviation
    launder a FAIL into a PASS.
    """
    item = clean_waived_item(
        measured_status=WS.FAIL,
        deviation_exists=None,
        relabeled_status=WS.PASS,
    )
    assert w.evidence_status_honest(item) is False


def test_measured_failure_must_stay_visible() -> None:
    """(§19 line 490) A measured FAIL relabeled to anything but FAIL / WAIVED ⇒ dishonest (deny)."""
    for measured in w.MEASURED_FAILURE_STATUSES:
        # relabel to PASS is dishonest
        bad = clean_waived_item(
            measured_status=measured,
            deviation_exists=False,
            relabeled_status=WS.PASS,
        )
        assert w.evidence_status_honest(bad) is False, measured
        # relabel to itself is honest
        same = clean_waived_item(
            measured_status=measured,
            deviation_exists=False,
            relabeled_status=measured,
        )
        assert w.evidence_status_honest(same) is True, measured
        # relabel to WAIVED requires the exact-current gate — with it satisfied it is honest
        waived = clean_waived_item(
            measured_status=measured,
            deviation_exists=True,
            relabeled_status=WS.WAIVED_WITH_RESIDUAL_RISK,
        )
        assert w.evidence_status_honest(waived) is True, measured


def test_waived_requires_exact_current_gate() -> None:
    """(§19 line 488) WAIVED_WITH_RESIDUAL_RISK measured needs all four positive-polarity fields True."""
    for field in (
        "exact_current_decision_present",
        "reduced_scope_present",
        "compensation_present",
        "review_record_present",
    ):
        for bad in (None, False):
            item = clean_waived_item(**{field: bad})
            assert w.evidence_status_honest(item) is False, f"{field}={bad}"


def test_approval_is_not_verification() -> None:
    """(§1 line 25) approval_is_not_verification: only ELIGIBLE reaches the gate (still not a PASS)."""
    assert (
        w.approval_is_not_verification(
            w.DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION
        )
        is True
    )
    for r in (w.DecisionResult.DENY, w.DecisionResult.HOLD, None):
        assert w.approval_is_not_verification(r) is False
