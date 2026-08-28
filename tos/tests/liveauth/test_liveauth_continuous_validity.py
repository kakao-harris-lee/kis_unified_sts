"""Continuous validity — authority + time compose, each condition load-bearing (§5.2).

Every composed condition (epoch currentness, online witness, TRUSTED time, no dominating
restriction, positive freshness) and every one of the ten injected runtime conditions is
individually load-bearing: removing any single one makes continuous_validity fail closed.
The egress condition is NOT claimed (a True result is necessary, not authorization
completion). [REARM-EV-008 substrate]
"""

from __future__ import annotations

import pytest
from tos.authority import (
    AuthorityEpochState,
    AuthorityState,
    CapabilityType,
    CurrentnessWitness,
)
from tos.liveauth import continuous_validity
from tos.liveauth.predicates import _INJECTED_CONTINUOUS_CONDITIONS
from tos.time import HealthState

from ._liveauth_strategies import (
    SCHEME,
    issue_authorization,
    valid_continuous_validity_inputs,
)


def test_valid_inputs_are_valid() -> None:
    """(guard fires True) The fully-established inputs pass continuous validity."""
    assert (
        continuous_validity(issue_authorization(), valid_continuous_validity_inputs())
        is True
    )


def test_stale_epoch_invalidates() -> None:
    """(canary) A claimed epoch below the current floor fails closed (epoch stale)."""
    auth = issue_authorization(safety_authority_epoch=4)
    inputs = valid_continuous_validity_inputs(
        authority_epoch_state=AuthorityEpochState(
            authority_domain="acct-1", current_epoch_floor=5
        )
    )
    assert continuous_validity(auth, inputs) is False


def test_domain_mismatch_invalidates() -> None:
    """(canary §4.4 coordinate non-collapse) A domain mismatch fails closed."""
    auth = issue_authorization(authority_domain="acct-OTHER")
    assert continuous_validity(auth, valid_continuous_validity_inputs()) is False


def test_none_epoch_invalidates() -> None:
    """(canary) A None claimed epoch on the authorization fails closed.

    A None epoch cannot reach ISSUED via ``issue()`` (required-covered), so a DRAFT
    authorization is used — it too must never be continuously valid.
    """
    from tos.liveauth import LiveAuthorization

    draft = LiveAuthorization(authorization_id="a", authority_domain="acct-1")
    assert draft.safety_authority_epoch is None
    assert continuous_validity(draft, valid_continuous_validity_inputs()) is False


def test_absent_witness_invalidates() -> None:
    """(canary) An absent online currentness witness fails closed (cache != current)."""
    inputs = valid_continuous_validity_inputs(currentness_witness=CurrentnessWitness())
    assert continuous_validity(issue_authorization(), inputs) is False


@pytest.mark.parametrize(
    "state",
    [
        HealthState.UNINITIALIZED,
        HealthState.SYNCHRONIZING,
        HealthState.DEGRADED_HOLDOVER,
        HealthState.UNTRUSTED,
    ],
)
def test_time_not_trusted_invalidates(state: HealthState) -> None:
    """(canary) Any non-TRUSTED time-health state fails closed (§9 line 261)."""
    inputs = valid_continuous_validity_inputs(time_health_state=state)
    assert continuous_validity(issue_authorization(), inputs) is False


@pytest.mark.parametrize(
    "dominating",
    [
        AuthorityState.HALTED,
        AuthorityState.CONTAINED,
        AuthorityState.DEGRADED_PROTECTIVE,
    ],
)
def test_dominating_restrictive_state_invalidates(dominating: AuthorityState) -> None:
    """(canary) A dominating restrictive state fails closed (§9 line 275)."""
    inputs = valid_continuous_validity_inputs(dominating_state=dominating)
    assert continuous_validity(issue_authorization(), inputs) is False


def test_dominating_halt_capability_invalidates() -> None:
    """(canary, order-independent) An outstanding HALT capability dominates (§9 line 275)."""
    from tos.authority import SafetyAuthorityCapability

    halt_cap = SafetyAuthorityCapability.issue(
        scheme=SCHEME,
        capability_id="halt-1",
        capability_type=CapabilityType.HALT,
        issuer_identity="iss",
        authority_domain="acct-1",
        safety_authority_epoch=5,
        subject_service_identity="svc",
        environment_and_mode="live",
        account_scope="acct-1",
        permitted_action_class="HALT",
        issue_sequence=1,
        hard_safety_envelope_version="h",
        runtime_safety_profile_version="r",
        maximum_quantity=0,
        maximum_risk_vector_effect_or_reservation_identity="rsv",
        nonce="n",
    )
    inputs = valid_continuous_validity_inputs(
        dominating_state=AuthorityState.LIVE_NORMAL,
        outstanding_capabilities=(halt_cap,),
    )
    assert continuous_validity(issue_authorization(), inputs) is False


@pytest.mark.parametrize(
    "override",
    [
        {"snapshot_age_bound": None},
        {"max_consumer_age_ms": None},
        {"snapshot_age_bound": 5000, "max_consumer_age_ms": 1000},  # age > max
        {"max_live_authorization_validity": None},
        {"authorization_elapsed": None},
        {"safety_margin": None},
        {"source_transport_uncertainty": -1},  # negative term fail-closed guard
        {"max_live_authorization_validity": 100, "authorization_elapsed": 100},  # <= 0
    ],
)
def test_freshness_failures_invalidate(override: dict[str, object]) -> None:
    """(canary) Missing / stale / non-positive freshness terms fail closed (§9 line 262/282)."""
    inputs = valid_continuous_validity_inputs(**override)
    assert continuous_validity(issue_authorization(), inputs) is False


@pytest.mark.parametrize("condition", _INJECTED_CONTINUOUS_CONDITIONS)
def test_each_injected_condition_none_invalidates(condition: str) -> None:
    """(canary, all-but-one) Each of the 10 injected conditions None => invalid."""
    inputs = valid_continuous_validity_inputs(**{condition: None})
    assert continuous_validity(issue_authorization(), inputs) is False


@pytest.mark.parametrize("condition", _INJECTED_CONTINUOUS_CONDITIONS)
def test_each_injected_condition_false_invalidates(condition: str) -> None:
    """(canary, all-but-one) Each of the 10 injected conditions False => invalid."""
    inputs = valid_continuous_validity_inputs(**{condition: False})
    assert continuous_validity(issue_authorization(), inputs) is False


def test_ten_injected_conditions_present() -> None:
    """The injected-condition set is the ADR §9 line 263-276 ten (no silent shrinkage)."""
    assert len(_INJECTED_CONTINUOUS_CONDITIONS) == 10
