"""Default non-live + authorization != enforcement (§4.1, §4.2, §5.1; REARM-AC-001).

An absent authorization is non-live (the zero-value case), an issued-but-not-ACTIVE
authorization is non-live (issued != active), no restart / failover / recovery flag can
synthesize live without an authorization, and every ledger citizen's authority_effect is
all-false (issuing / holding grants no runtime effect).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.liveauth import (
    ContinuousValidityInputs,
    LiveAuthorizationEffect,
    LiveAuthorizationState,
    continuous_validity,
    is_live,
)

from ._liveauth_strategies import (
    issue_approval,
    issue_authorization,
    valid_continuous_validity_inputs,
)


def test_is_live_none_is_false() -> None:
    """(zero-value canary §4.2) An absent authorization is non-live by default."""
    assert (
        is_live(None, LiveAuthorizationState.ACTIVE, ContinuousValidityInputs())
        is False
    )


def test_is_live_none_state_is_false() -> None:
    """A None current state is non-live (fail-closed)."""
    assert (
        is_live(issue_authorization(), None, valid_continuous_validity_inputs())
        is False
    )


def test_issued_is_not_active() -> None:
    """(canary §8.1) An ISSUED authorization is not live — issued != active."""
    auth = issue_authorization()
    inputs = valid_continuous_validity_inputs()
    assert is_live(auth, LiveAuthorizationState.ISSUED, inputs) is False


def test_active_with_valid_inputs_is_live() -> None:
    """(guard fires True) ACTIVE + passing continuous validity => live (existence)."""
    auth = issue_authorization()
    inputs = valid_continuous_validity_inputs()
    assert is_live(auth, LiveAuthorizationState.ACTIVE, inputs) is True


@pytest.mark.parametrize(
    "state",
    [
        LiveAuthorizationState.REQUESTED,
        LiveAuthorizationState.VALIDATED,
        LiveAuthorizationState.APPROVED,
        LiveAuthorizationState.ISSUED,
        LiveAuthorizationState.DENIED,
        LiveAuthorizationState.SUSPENDED,
        LiveAuthorizationState.REVOKED,
        LiveAuthorizationState.EXPIRED,
        LiveAuthorizationState.SUPERSEDED,
    ],
)
def test_no_non_active_state_is_live(state: LiveAuthorizationState) -> None:
    """(canary) Only ACTIVE can be live — every other state is non-live even when valid."""
    auth = issue_authorization()
    inputs = valid_continuous_validity_inputs()
    assert is_live(auth, state, inputs) is False


def test_continuous_validity_none_authorization_is_false() -> None:
    """(canary) continuous_validity of an absent authorization is False (fail-closed)."""
    assert continuous_validity(None, valid_continuous_validity_inputs()) is False


def test_default_inputs_never_live() -> None:
    """A default (all-UNKNOWN) inputs instance is never valid — no vacuous live."""
    auth = issue_authorization()
    assert continuous_validity(auth, ContinuousValidityInputs()) is False
    assert (
        is_live(auth, LiveAuthorizationState.ACTIVE, ContinuousValidityInputs())
        is False
    )


def test_live_authorization_effect_rejects_any_true_flag() -> None:
    """(canary §4.1) Any True authority flag makes the effect block unconstructable."""
    for flag in (
        "is_live_by_possession",
        "self_transmits",
        "self_arms",
        "self_activates",
        "self_expands_scope",
        "self_revives",
    ):
        with pytest.raises(ValidationError):
            LiveAuthorizationEffect(**{flag: True})


def test_records_carry_all_false_effect() -> None:
    """(canary §4.1) Authorization + approval carry an all-false authority effect."""
    for record in (issue_authorization(), issue_approval()):
        effect = record.authority_effect
        assert all(getattr(effect, name) is False for name in type(effect).model_fields)


def test_default_effect_all_false() -> None:
    """A default LiveAuthorizationEffect is all-false (the non-transmitting datum)."""
    effect = LiveAuthorizationEffect()
    assert all(getattr(effect, name) is False for name in type(effect).model_fields)
