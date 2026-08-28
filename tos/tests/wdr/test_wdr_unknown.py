"""unknown_denies_and_confines yolk 3 — UNKNOWN⇒deny, budget≠capacity, protective≠bypass (design #26 §5.3).

Both-ways canary. The nine §16 line 423-431 UNKNOWN flags are negative-polarity: only an explicit
``False`` (all-known) admits; a ``True`` or a ``None`` (unknown-unknown) both deny + confine (the
#18/#22 MAJOR-2 seal — ``is not True`` would admit the ``None``).

Regime tag: UNKNOWN predicate substrate only; WDR-EV-007 NOT_IMPLEMENTED (EV-L1/3+Broker);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
import tos.wdr as w

from ._wdr_strategies import clean_unknown_request

_UNKNOWN_FIELDS = (
    "broker_state_unknown",
    "order_state_unknown",
    "exposure_unknown",
    "residual_risk_unknown",
    "control_state_unknown",
    "evidence_unknown",
    "scope_unknown",
    "currentness_unknown",
    "materiality_unknown",
)


def test_all_known_proceeds() -> None:
    """(§5.3 positive) Every UNKNOWN flag False + all-false budget + no protective bypass ⇒ True."""
    assert (
        w.unknown_denies_and_confines(
            clean_unknown_request(), w.AllFalseDeviationAuthority()
        )
        is True
    )


def test_none_request_or_budget_denies() -> None:
    """(§5.3 ∅-seal) None request or None budget authority ⇒ deny."""
    assert w.unknown_denies_and_confines(None, w.AllFalseDeviationAuthority()) is False
    assert w.unknown_denies_and_confines(clean_unknown_request(), None) is False


@pytest.mark.parametrize("field", _UNKNOWN_FIELDS)
@pytest.mark.parametrize("bad", [True, None])
def test_any_unknown_true_or_none_denies(field: str, bad: bool | None) -> None:
    """(§4.3 negative polarity) Any UNKNOWN flag True OR None ⇒ deny + confine (never fail-open)."""
    req = clean_unknown_request(**{field: bad})
    assert (
        w.unknown_denies_and_confines(req, w.AllFalseDeviationAuthority()) is False
    ), f"{field}={bad} fail-opened"


def test_unresolved_applicability_denies_in_unknown_yolk() -> None:
    """(INV-010 line 184 / MINOR-1 fix) applicability_resolved None / False ⇒ deny (positive polarity).

    WDR-INV-010 line 184 lists "Unknown applicability" first among the axes that block new risk; it is a
    positive-polarity axis not covered by the negative-polarity UNKNOWN flags. The UNKNOWN yolk now gates
    it explicitly (deliberately multi-layered with the EV-001 / EV-002 yolks).
    """
    for bad in (None, False):
        req = clean_unknown_request(applicability_resolved=bad)
        assert (
            w.unknown_denies_and_confines(req, w.AllFalseDeviationAuthority()) is False
        ), f"applicability_resolved={bad} fail-opened"


def test_budget_is_not_capacity() -> None:
    """(§7 line 217) budget_is_not_capacity: all-false ⇒ True; None / any True flag ⇒ False."""
    assert w.budget_is_not_capacity(w.AllFalseDeviationAuthority()) is True
    assert w.budget_is_not_capacity(None) is False


def test_capacity_authority_denies() -> None:
    """(§16 line 434) A budget authority claiming capacity is unconstructable — the all-false validator.

    A deviation budget can never free capacity: any ``True`` authority flag is rejected at construction
    (WDR-INV-001), so a capacity-granting budget cannot even be built to pass into the yolk.
    """
    with pytest.raises((w.ArtifactIntegrityError, ValueError)):
        w.AllFalseDeviationAuthority(creates_capacity=True)


def test_protective_label_bypass_denies() -> None:
    """(§11 line 331 / §17 line 442) protective_label_bypass True / None ⇒ deny (negative polarity)."""
    for bad in (True, None):
        req = clean_unknown_request(protective_label_bypass=bad)
        assert (
            w.unknown_denies_and_confines(req, w.AllFalseDeviationAuthority()) is False
        )
    assert w.protective_label_no_bypass(None) is False
    assert w.protective_label_no_bypass(clean_unknown_request()) is True
