"""Uncertain-send / same-order-retry (design #10 §5.4; BC-EV-002/003; BC-INV-002/003).

Uncertain transmission is never blindly retried and never released by timeout; a same-order
resend is admissible only when the profile proves deterministic idempotency for the exact
identity + window.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.brokercap import (
    CapabilityDimension,
    CapabilityStatus,
    UncertainSendVerdict,
    same_order_retry_allowed,
    uncertain_send_policy,
)

from ._brokercap_strategies import issue_profile, verified_declaration

_IDEMPO = CapabilityDimension.SUBMISSION_IDEMPOTENCY


# ---------------------------------------------------------------------------
# uncertain_send_policy — structurally all-restrictive; timeout cannot release
# ---------------------------------------------------------------------------


def test_uncertain_send_verdict_is_all_restrictive() -> None:
    """(§12.4 ladder) Every uncertain-send flag is restrictive (no permissive combination)."""
    verdict = uncertain_send_policy(idempotency_proven=None)
    assert verdict.no_retry is True
    assert verdict.no_capacity_release is True
    assert verdict.no_assume_rejection is True
    assert verdict.no_new_conflicting_in_containment is True
    assert verdict.start_reconciliation is True
    assert verdict.enter_unknown_or_contained is True


@given(
    idempotency=st.sampled_from([True, False, None]),
    timeout=st.sampled_from([True, False, None]),
)
def test_timeout_never_releases(idempotency: bool | None, timeout: bool | None) -> None:
    """(BC-INV-003 / §1 line 43) No idempotency / timeout combination relaxes no_capacity_release."""
    verdict = uncertain_send_policy(
        idempotency_proven=idempotency, timeout_elapsed=timeout
    )
    assert verdict.no_capacity_release is True
    assert verdict.no_retry is True


def test_verdict_permissive_construction_is_structurally_restrictive() -> None:
    """(§4.6) The verdict defaults are restrictive — the producer emits only the ladder."""
    # The producer returns the default (all-True restrictive) verdict — no permissive path.
    assert uncertain_send_policy() == UncertainSendVerdict()


# ---------------------------------------------------------------------------
# same_order_retry_allowed — both-ways
# ---------------------------------------------------------------------------


def test_retry_allowed_only_when_idempotency_verified_and_proven() -> None:
    """(§12.5 canary b) VERIFIED idempotency + proven identity/window => retry allowed."""
    profile = issue_profile(declarations=(verified_declaration(dimension=_IDEMPO),))
    assert (
        same_order_retry_allowed(
            profile, idempotency_proven_for_identity_and_window=True
        )
        is True
    )


def test_retry_denied_when_idempotency_unproven() -> None:
    """(§12.4 canary a) Unproven identity/window => retry denied (no blind retry)."""
    profile = issue_profile(declarations=(verified_declaration(dimension=_IDEMPO),))
    assert (
        same_order_retry_allowed(
            profile, idempotency_proven_for_identity_and_window=None
        )
        is False
    )
    assert (
        same_order_retry_allowed(
            profile, idempotency_proven_for_identity_and_window=False
        )
        is False
    )


def test_retry_denied_when_idempotency_dimension_not_verified() -> None:
    """(§12.5) An UNKNOWN / undeclared idempotency dimension => retry denied."""
    unknown = verified_declaration(dimension=_IDEMPO).model_copy(
        update={"status": CapabilityStatus.UNKNOWN}
    )
    profile = issue_profile(declarations=(unknown,))
    assert (
        same_order_retry_allowed(
            profile, idempotency_proven_for_identity_and_window=True
        )
        is False
    )
    # Undeclared entirely:
    profile_bare = issue_profile(declarations=())
    assert (
        same_order_retry_allowed(
            profile_bare, idempotency_proven_for_identity_and_window=True
        )
        is False
    )


def test_retry_none_profile_fails_closed() -> None:
    """A None profile => retry denied."""
    assert (
        same_order_retry_allowed(None, idempotency_proven_for_identity_and_window=True)
        is False
    )
