"""capacity != authority — the central invariant (RCL design §4.1; RCLP-INV-001/012).

Four layers: (1) grant/decision/capability/snapshot authority flags are all-false
construction invariants; (2) only a committed transition mutates capacity (no
mutate method exists on a grant/decision/snapshot); (3) a grant authorizes only the
exact committed reservation; (4) documentation/projection is not an authorization
input.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.rcl import (
    GrantDecisionRef,
    RclAuthorityEffect,
    grant_authorizes_exact_request,
    grants_no_authority,
)

from ._rcl_strategies import committed_reservation, issue_capability, issue_snapshot

# ---- layer 1: all-false authority flags ------------------------------------


def test_default_authority_effect_grants_nothing() -> None:
    """A default RclAuthorityEffect grants no authority."""
    assert grants_no_authority(RclAuthorityEffect()) is True


@pytest.mark.parametrize(
    "flag",
    [
        "creates_capacity",
        "may_mutate_live_state",
        "may_release_capacity",
        "permits_broker_transmission",
        "may_rearm",
    ],
)
def test_any_true_authority_flag_is_unconstructable(flag: str) -> None:
    """(canary) Any True authority flag makes the block unconstructable (RCLP-INV-001)."""
    with pytest.raises(ValidationError):
        RclAuthorityEffect(**{flag: True})


def test_capability_and_snapshot_carry_all_false_authority() -> None:
    """A Transmission Capability and Snapshot both grant no authority."""
    assert grants_no_authority(issue_capability().authority_effect) is True
    assert grants_no_authority(issue_snapshot().authority_effect) is True


def test_capability_with_true_authority_flag_rejected() -> None:
    """A capability cannot be issued with a True authority flag."""
    from tos.rcl import TransmissionCapability

    from ._rcl_strategies import SCHEME

    with pytest.raises(ValidationError):
        TransmissionCapability.issue(
            scheme=SCHEME,
            capability_id="cap-x",
            reservation_identity="rsv-1",
            attempt_identity="att-1",
            account_scope="a",
            instrument_scope="ES",
            side_action_scope="BUY",
            ledger_epoch=1,
            authority_effect=RclAuthorityEffect(creates_capacity=True),
        )


# ---- layer 2: only a committed transition mutates capacity -----------------


def test_grant_and_snapshot_have_no_capacity_mutation_method() -> None:
    """No grant / decision / snapshot exposes a method returning mutated capacity."""
    grant = GrantDecisionRef()
    snapshot = issue_snapshot()
    for obj in (grant, snapshot):
        mutating = [
            name
            for name in dir(obj)
            if not name.startswith("_")
            and any(
                token in name.lower()
                for token in (
                    "mutate",
                    "commit_capacity",
                    "release",
                    "rearm",
                    "grant_capacity",
                )
            )
        ]
        assert mutating == [], f"unexpected capacity-mutation surface: {mutating}"


# ---- layer 3: a grant authorizes only the exact committed reservation ------


def test_grant_binds_exact_reservation() -> None:
    """A grant bound to the exact committed revision + digest + generation authorizes."""
    reservation = committed_reservation(revision=3, digest="rsv-digest-1")
    grant = GrantDecisionRef(
        decision_id="dec-1",
        bound_reservation_revision=3,
        bound_reservation_digest="rsv-digest-1",
        bound_generation=7,
    )
    assert (
        grant_authorizes_exact_request(grant, reservation, current_generation=7) is True
    )


@pytest.mark.parametrize(
    "grant_kwargs,current_generation",
    [
        (
            {
                "bound_reservation_revision": 2,
                "bound_reservation_digest": "rsv-digest-1",
                "bound_generation": 7,
            },
            7,
        ),
        (
            {
                "bound_reservation_revision": 3,
                "bound_reservation_digest": "other",
                "bound_generation": 7,
            },
            7,
        ),
        (
            {
                "bound_reservation_revision": 3,
                "bound_reservation_digest": "rsv-digest-1",
                "bound_generation": 6,
            },
            7,
        ),
        (
            {
                "bound_reservation_revision": None,
                "bound_reservation_digest": "rsv-digest-1",
                "bound_generation": 7,
            },
            7,
        ),
        (
            {
                "bound_reservation_revision": 3,
                "bound_reservation_digest": "rsv-digest-1",
                "bound_generation": 7,
            },
            None,
        ),
    ],
)
def test_grant_rejects_inexact_or_stale_binding(
    grant_kwargs: dict, current_generation
) -> None:
    """(canary) A grant on a different revision / digest / generation is rejected."""
    reservation = committed_reservation(revision=3, digest="rsv-digest-1")
    grant = GrantDecisionRef(decision_id="dec-1", **grant_kwargs)
    assert (
        grant_authorizes_exact_request(
            grant, reservation, current_generation=current_generation
        )
        is False
    )


def test_grant_ref_authority_is_all_false() -> None:
    """The grant reference itself grants nothing (documentation != authority, §4.1 layer 4)."""
    assert grants_no_authority(GrantDecisionRef().authority_effect) is True
