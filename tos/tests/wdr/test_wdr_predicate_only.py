"""Predicate-only §6 substrate — closes NO WDR-EV (design #26 §6).

The §6 substrate is L1-decidable structural / polarity judgement that supports the ≥ L2 rows (003 / 004
/ 005 / 008 / 009 / 011) but closes **no** WDR-EV — the real effectiveness / independence / broker /
recovery verification is +Security / +Broker / runtime. Both-ways canaries for each.

Regime tag: predicate substrate only; WDR-EV-003/004/005/008/009/011 NOT_IMPLEMENTED (≥ L2);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
import tos.wdr as w

from ._wdr_strategies import clean_control, clean_decision

# --- §6.1 compensating_control_not_observation (WDR-EV-003·+Security) ---------


def test_compensating_control_positive() -> None:
    """(§6.1) A genuine preventive/containment control (all positive, observation False) ⇒ True."""
    assert w.compensating_control_not_observation(clean_control()) is True


def test_compensating_control_none_denies() -> None:
    """(§6.1 ∅-seal) A None control ⇒ deny."""
    assert w.compensating_control_not_observation(None) is False


def test_observation_only_is_not_a_control() -> None:
    """(§5.5 / §11 item 8) observation_only True / None ⇒ not-a-control (negative polarity)."""
    for bad in (True, None):
        assert (
            w.compensating_control_not_observation(clean_control(observation_only=bad))
            is False
        )


@pytest.mark.parametrize(
    "field",
    [
        "is_preventive_or_containment",
        "objective_evidence",
        "fails_closed",
        "independent_of_failed_control",
    ],
)
def test_positive_control_fields_required(field: str) -> None:
    """(§11 item 1/3/4/5) Each positive-polarity control field None / False ⇒ deny."""
    for bad in (None, False):
        assert (
            w.compensating_control_not_observation(clean_control(**{field: bad}))
            is False
        )


# --- §6.2 independent_effective_person_approval (WDR-EV-004·+Security) --------


def test_independent_approval_positive() -> None:
    """(§6.2) All-false authority + hag verdict True + no common-mode ⇒ True (structural independence)."""
    assert (
        w.independent_effective_person_approval(
            w.AllFalseDeviationAuthority(), True, False
        )
        is True
    )


def test_independent_approval_polarity_and_none() -> None:
    """(§6.2) None authority / verdict None-or-False / common-mode True-or-None ⇒ deny."""
    assert w.independent_effective_person_approval(None, True, False) is False
    for verdict in (None, False):
        assert (
            w.independent_effective_person_approval(
                w.AllFalseDeviationAuthority(), verdict, False
            )
            is False
        )
    for common in (True, None):
        assert (
            w.independent_effective_person_approval(
                w.AllFalseDeviationAuthority(), True, common
            )
            is False
        )


# --- §6.3 deviation_single_use_non_authorizing (WDR-EV-005·+Security) ---------


def test_single_use_positive() -> None:
    """(§6.3) Fresh (consumed False) + eligible + all-false authority ⇒ True."""
    assert w.deviation_single_use_non_authorizing(clean_decision()) is True


def test_single_use_none_and_polarity() -> None:
    """(§6.3) None decision / consumed True-or-None / non-eligible result ⇒ deny."""
    assert w.deviation_single_use_non_authorizing(None) is False
    for consumed in (True, None):
        assert (
            w.deviation_single_use_non_authorizing(
                clean_decision(single_use_consumed=consumed)
            )
            is False
        )
    for result in (w.DecisionResult.DENY, w.DecisionResult.HOLD):
        assert (
            w.deviation_single_use_non_authorizing(clean_decision(result=result))
            is False
        )


# --- §6.4 broker_finality_unchanged + economic_effect_persists (WDR-EV-008·+Broker) ---


def test_broker_finality_and_economic_effect() -> None:
    """(§6.4) broker finality known ⇒ True; economic effect persists under all-false authority ⇒ True."""
    assert w.broker_finality_unchanged(False, False) is True
    assert w.broker_finality_unchanged(True, False) is False
    assert w.broker_finality_unchanged(None, False) is False
    assert w.economic_effect_persists(w.AllFalseDeviationAuthority()) is True
    assert w.economic_effect_persists(None) is False


# --- §6.5 expiry_recovery_revives_nothing (WDR-EV-009·+Security) --------------


def test_expiry_recovery_revives_nothing() -> None:
    """(§6.5) Nothing re-armed / self-reverted / recovered-without-chain ⇒ True; any True/None ⇒ deny."""
    assert w.expiry_recovery_revives_nothing(False, False, False) is True
    assert w.expiry_recovery_revives_nothing(True, False, False) is False
    assert w.expiry_recovery_revives_nothing(None, False, False) is False
    assert w.expiry_recovery_revives_nothing(False, None, False) is False
    assert w.expiry_recovery_revives_nothing(False, False, None) is False


# --- §6.6 break_glass_no_authority + deviation_service_no_route (WDR-EV-011·+Broker+Security) ---


def test_break_glass_and_service_no_route() -> None:
    """(§6.6) Break-glass / deviation service confer no authority (all-false) ⇒ True; None ⇒ deny."""
    assert w.break_glass_no_authority(w.AllFalseDeviationAuthority()) is True
    assert w.break_glass_no_authority(None) is False
    assert w.deviation_service_no_route(w.AllFalseDeviationAuthority()) is True
    assert w.deviation_service_no_route(None) is False


# --- §6b not-Phase-1 revocation send-race (WDR-EV-006·EV-L3+Security) ---------


def test_revocation_dominates_send_order_model() -> None:
    """(§6b) revoke < send ⇒ dominates (deny); otherwise the attempt is potentially-live."""
    assert w.revocation_dominates_send(1, 5) is True
    assert w.attempt_potentially_live(1, 5) is False
    # send before revoke ⇒ potentially live
    assert w.revocation_dominates_send(5, 1) is False
    assert w.attempt_potentially_live(5, 1) is True
    # equal / ambiguous ⇒ potentially live (not a clean denial)
    assert w.revocation_dominates_send(3, 3) is False
    assert w.attempt_potentially_live(3, 3) is True
    # None generation ⇒ potentially live (fail-closed conservative)
    assert w.revocation_dominates_send(None, 5) is False
    assert w.attempt_potentially_live(None, 5) is True
    assert w.attempt_potentially_live(5, None) is True
