"""Capacity -> capability binding + claim nonce-once (RCLP-EV-006 L1; §6.4).

A capability authorization is valid only when bound to an already-committed
reservation revision, exact worst-case effect coverage, current generations, and no
dominating restriction — with claim nonce consumed exactly once. Send boundary /
egress is deferred (§0.2).
"""

from __future__ import annotations

from tos.rcl import (
    ClaimRecord,
    WriterFenceState,
    capability_authorization_valid,
    claim_capability,
)

from ._rcl_strategies import committed_reservation, issue_capability, vec

DIMS = ["gross_notional"]
FENCE = WriterFenceState(
    writer_epoch_floor=1, membership_generation=1, restore_generation=1, revision=5
)


def _current_fence_coords():
    return {
        "expected_writer_epoch": 1,
        "membership_generation": 1,
        "restore_generation": 1,
        "expected_revision": 5,
    }


def _valid_capability(**overrides):
    from tos.rcl import FenceCoordinates

    base = {
        "bound_reservation_revision": 3,
        "worst_case_effect": vec(gross_notional=4),
        "fence": FenceCoordinates(**_current_fence_coords()),
        "dominating_restriction": False,
    }
    base.update(overrides)
    return issue_capability(**base)


def _reservation(**overrides):
    return committed_reservation(
        revision=3, increment=vec(gross_notional=10), **overrides
    )


def test_valid_authorization() -> None:
    """An exact-bound, current, covered, unrestricted capability is valid."""
    assert (
        capability_authorization_valid(
            _valid_capability(), _reservation(), FENCE, applicable_dimensions=DIMS
        )
        is True
    )


def test_wrong_reservation_revision_rejected() -> None:
    """(canary) A capability bound to a different reservation revision is invalid."""
    cap = _valid_capability(bound_reservation_revision=2)
    assert (
        capability_authorization_valid(
            cap, _reservation(), FENCE, applicable_dimensions=DIMS
        )
        is False
    )


def test_effect_exceeding_committed_capacity_rejected() -> None:
    """(canary) A worst-case effect not covered by committed capacity is invalid."""
    cap = _valid_capability(worst_case_effect=vec(gross_notional=999))
    assert (
        capability_authorization_valid(
            cap, _reservation(), FENCE, applicable_dimensions=DIMS
        )
        is False
    )


def test_stale_generation_rejected() -> None:
    """(canary) A capability bound under a stale generation (fenced) is invalid."""
    from tos.rcl import FenceCoordinates

    cap = _valid_capability(
        fence=FenceCoordinates(
            expected_writer_epoch=1,
            membership_generation=0,
            restore_generation=1,
            expected_revision=5,
        )
    )
    assert (
        capability_authorization_valid(
            cap, _reservation(), FENCE, applicable_dimensions=DIMS
        )
        is False
    )


def test_missing_generation_fails_closed() -> None:
    """(canary) A missing (None) generation coordinate fails closed (invalid)."""
    from tos.rcl import FenceCoordinates

    cap = _valid_capability(
        fence=FenceCoordinates(
            expected_writer_epoch=None,
            membership_generation=1,
            restore_generation=1,
            expected_revision=5,
        )
    )
    assert (
        capability_authorization_valid(
            cap, _reservation(), FENCE, applicable_dimensions=DIMS
        )
        is False
    )


def test_dominating_restriction_rejected() -> None:
    """A dominating restriction / UNKNOWN blocks the authorization (§11 line 325)."""
    cap = _valid_capability(dominating_restriction=True)
    assert (
        capability_authorization_valid(
            cap, _reservation(), FENCE, applicable_dimensions=DIMS
        )
        is False
    )


def test_attempt_not_bound_or_used_rejected() -> None:
    """An unbound or already-used attempt makes the capability invalid (§11 line 322)."""
    unbound = _reservation(attempt_bound=False)
    used = _reservation(attempt_unused=False)
    cap = _valid_capability()
    assert (
        capability_authorization_valid(cap, unbound, FENCE, applicable_dimensions=DIMS)
        is False
    )
    assert (
        capability_authorization_valid(cap, used, FENCE, applicable_dimensions=DIMS)
        is False
    )


def test_empty_applicable_dimensions_rejected() -> None:
    """No applicable dimensions => coverage cannot be proven => invalid (fail-closed)."""
    assert (
        capability_authorization_valid(
            _valid_capability(), _reservation(), FENCE, applicable_dimensions=[]
        )
        is False
    )


# ---- claim nonce-once (ADR-012 §12 line 340-343) ---------------------------


def test_first_claim_consumes_nonce() -> None:
    """The first claim of a nonce consumes it exactly once."""
    outcome = claim_capability("nonce-1", ())
    assert outcome.consumed_now is True and outcome.replay is False
    assert outcome.result == "SEND_STARTED"


def test_reclaim_returns_original_result_no_new_authority() -> None:
    """A later duplicate claim returns the original committed result (no new send authority)."""
    prior = (
        ClaimRecord(nonce="nonce-1", capability_id="cap-1", result="SEND_STARTED"),
    )
    outcome = claim_capability("nonce-1", prior)
    assert outcome.consumed_now is False and outcome.replay is True
    assert outcome.result == "SEND_STARTED"


def test_missing_nonce_grants_no_authority() -> None:
    """A None nonce cannot be claimed (fail-closed — no send authority)."""
    outcome = claim_capability(None, ())
    assert (
        outcome.consumed_now is False
        and outcome.replay is False
        and outcome.result is None
    )
