"""``tos_runtime.safety.latch`` tests (Phase 5 W3 plan §2 decision 6) — the
restrictive-latch and worst-credible-capacity runtime owners.
"""

from __future__ import annotations

from tos.egress import RestrictiveLatchState
from tos.engine.records import InstrumentKey
from tos.rcl import CapacityState
from tos_runtime.safety.latch import (
    CapacityOwner,
    EgressOwnerFields,
    RestrictiveLatchOwner,
    egress_owner_fields,
)

from .conftest import FakeNewRiskHaltInbox

_SCOPE = InstrumentKey(account="acct-1", instrument="005930")


# ============================================================================
# RestrictiveLatchOwner
# ============================================================================


def test_clear_when_all_three_inputs_are_positive() -> None:
    owner = RestrictiveLatchOwner(
        FakeNewRiskHaltInbox(None),
        incident_clear=lambda: True,
        profile_clear=lambda: True,
    )
    assert owner.state() is RestrictiveLatchState.CLEAR


def test_deny_latched_when_the_new_risk_halt_is_held() -> None:
    owner = RestrictiveLatchOwner(
        FakeNewRiskHaltInbox({"reason": "x", "evidence_seq": 1}),
        incident_clear=lambda: True,
        profile_clear=lambda: True,
    )
    assert owner.state() is RestrictiveLatchState.DENY_LATCHED


def test_deny_latched_when_incident_clear_is_false() -> None:
    owner = RestrictiveLatchOwner(
        FakeNewRiskHaltInbox(None),
        incident_clear=lambda: False,
        profile_clear=lambda: True,
    )
    assert owner.state() is RestrictiveLatchState.DENY_LATCHED


def test_deny_latched_when_incident_clear_is_none_unknown_collapses_to_deny_latched() -> (
    None
):
    """The kernel vocabulary has no third (UNKNOWN) member — an unresolved
    incident-clear fact must collapse to the SAME non-clear value as a
    positively-denied one (module docstring)."""
    owner = RestrictiveLatchOwner(
        FakeNewRiskHaltInbox(None),
        incident_clear=lambda: None,
        profile_clear=lambda: True,
    )
    assert owner.state() is RestrictiveLatchState.DENY_LATCHED


def test_deny_latched_when_profile_clear_is_false() -> None:
    owner = RestrictiveLatchOwner(
        FakeNewRiskHaltInbox(None),
        incident_clear=lambda: True,
        profile_clear=lambda: False,
    )
    assert owner.state() is RestrictiveLatchState.DENY_LATCHED


def test_deny_latched_when_profile_clear_is_none() -> None:
    owner = RestrictiveLatchOwner(
        FakeNewRiskHaltInbox(None),
        incident_clear=lambda: True,
        profile_clear=lambda: None,
    )
    assert owner.state() is RestrictiveLatchState.DENY_LATCHED


def test_mutation_m7_latch_owner_must_not_ignore_the_inbox() -> None:
    """M7: an owner that ignored the inbox latch (always reporting CLEAR from the
    two ``clear`` callables alone) would wrongly clear a held new-risk halt — this
    must be RED under that mutation, i.e. the real owner must actually consult the
    inbox and return DENY_LATCHED here."""
    owner = RestrictiveLatchOwner(
        FakeNewRiskHaltInbox({"reason": "held", "evidence_seq": 7}),
        incident_clear=lambda: True,
        profile_clear=lambda: True,
    )
    assert owner.state() is RestrictiveLatchState.DENY_LATCHED


def test_describe_reports_no_secrets_and_the_resolved_state() -> None:
    owner = RestrictiveLatchOwner(
        FakeNewRiskHaltInbox(None),
        incident_clear=lambda: True,
        profile_clear=lambda: True,
    )
    description = owner.describe()
    assert description["state"] == "CLEAR"
    assert description["new_risk_halt_latched"] is False
    assert description["incident_clear"] is True
    assert description["profile_clear"] is True


# ============================================================================
# CapacityOwner
# ============================================================================


class _FakeProjectionReader:
    def __init__(self, state: CapacityState | None) -> None:
        self._state = state

    def instrument_state(self, key: InstrumentKey) -> CapacityState | None:
        assert key == _SCOPE
        return self._state

    def reservation_state(self, reservation_id: str) -> CapacityState | None:
        raise NotImplementedError

    def reservation_last_seq(self, reservation_id: str) -> int | None:
        raise NotImplementedError

    def all_reservations(self):  # pragma: no cover - unused by CapacityOwner
        raise NotImplementedError

    def instrument_last_seq(self, key: InstrumentKey) -> int | None:
        raise NotImplementedError


def test_capacity_zero_when_no_reservation_is_projected() -> None:
    owner = CapacityOwner(_FakeProjectionReader(None), _SCOPE)
    assert owner.worst_credible_capacity() == 0


def test_capacity_zero_when_the_reservation_is_released() -> None:
    owner = CapacityOwner(_FakeProjectionReader(CapacityState.RELEASED), _SCOPE)
    assert owner.worst_credible_capacity() == 0


def test_capacity_one_when_an_outstanding_reservation_is_held() -> None:
    owner = CapacityOwner(
        _FakeProjectionReader(CapacityState.COMMITTED_UNBOUND), _SCOPE
    )
    assert owner.worst_credible_capacity() == 1


def test_capacity_describe_reports_scope_and_count() -> None:
    owner = CapacityOwner(_FakeProjectionReader(CapacityState.ATTEMPT_BOUND), _SCOPE)
    description = owner.describe()
    assert description["account"] == "acct-1"
    assert description["instrument"] == "005930"
    assert description["worst_credible_capacity"] == 1


# ============================================================================
# egress_owner_fields
# ============================================================================


def test_egress_owner_fields_bundles_both_owners_fresh() -> None:
    latch = RestrictiveLatchOwner(
        FakeNewRiskHaltInbox(None),
        incident_clear=lambda: True,
        profile_clear=lambda: True,
    )
    capacity = CapacityOwner(_FakeProjectionReader(CapacityState.RELEASED), _SCOPE)

    fields = egress_owner_fields(latch, capacity)

    assert fields == EgressOwnerFields(
        restrictive_latch_state=RestrictiveLatchState.CLEAR,
        worst_credible_capacity=0,
    )
    assert fields.fields() == {
        "restrictive_latch_state": RestrictiveLatchState.CLEAR,
        "worst_credible_capacity": 0,
    }
