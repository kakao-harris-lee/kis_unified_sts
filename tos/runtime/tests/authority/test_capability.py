"""``capability_valid`` tests (design #40 §5 order 4 item 2)."""

from __future__ import annotations

import pytest
from tos.authority import (
    AuthorityTransitionReason,
    CapabilityType,
    SafetyAuthorityCapability,
)
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.authority.capability import capability_valid
from tos_runtime.authority.epoch import SafetyAuthorityEpochService
from tos_runtime.time.service import TrustworthyTimeService

from .conftest import make_trusted

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def _issue_capability(
    *,
    epoch: int,
    capability_type: CapabilityType = CapabilityType.NORMAL_RISK_INCREASING,
):
    capability = SafetyAuthorityCapability.issue(
        scheme=_SCHEME,
        capability_id="cap-1",
        capability_type=capability_type,
        issuer_identity="issuer-1",
        authority_domain="acct-main",
        safety_authority_epoch=epoch,
        subject_service_identity="svc-1",
        environment_and_mode="paper",
        account_scope="acct-1",
        instrument_or_class_scope=None,
        permitted_action_class="ENTRY",
        maximum_quantity=100,
        maximum_risk_vector_effect_or_reservation_identity="risk-1",
        hard_safety_envelope_version="v1",
        runtime_safety_profile_version="v1",
        issue_sequence=1,
        validity_rule=None,
        use_semantics=None,
        parent_authorization_or_protective_lease_identity=None,
        integrity_evidence=None,
        nonce="nonce-1",
    )
    assert isinstance(capability, SafetyAuthorityCapability)
    return capability


def _admit_epoch(epoch_service: SafetyAuthorityEpochService) -> None:
    epoch_service.transition(
        leader_identity="leader-1",
        transition_reason=AuthorityTransitionReason.SAFETY_AUTHORITY_FAILOVER,
    )


@pytest.mark.parametrize(
    ("time_trusted", "epoch_admitted", "consumed", "issuer_key_status", "expected"),
    [
        (True, True, False, "valid", True),
        (False, True, False, "valid", False),
        (True, False, False, "valid", False),
        (True, True, False, "revoked", False),
        (True, True, True, "valid", False),
    ],
    ids=[
        "every-condition-holds",
        "time-not-trusted",
        "epoch-stale",
        "issuer-key-not-valid",
        "consumed",
    ],
)
def test_capability_valid_is_true_only_when_every_condition_holds(
    epoch_service: SafetyAuthorityEpochService,
    time_service: TrustworthyTimeService,
    time_trusted: bool,
    epoch_admitted: bool,
    consumed: bool,
    issuer_key_status: str,
    expected: bool,
) -> None:
    """``time-not-trusted``: no witness (never evaluated to TRUSTED) => not admissible."""
    if time_trusted:
        make_trusted(time_service)
    if epoch_admitted:
        _admit_epoch(epoch_service)
    capability = _issue_capability(epoch=1)

    assert (
        capability_valid(
            capability,
            epoch_service=epoch_service,
            revocation_status="not_revoked",
            superseded=False,
            consumed=consumed,
            issuer_key_status=issuer_key_status,
            environment_and_mode_matches=True,
        )
        is expected
    )
