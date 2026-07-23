"""Append-only ledger discipline (RCL design §4.2; ADR-002-002 §28; ADR-012 §17).

Records are frozen with no update / delete method; a lifecycle change (resize /
transfer / release / quarantine / correction) is expressed by APPENDING a new
committed command / transition — existing records' covered fields never mutate.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.rcl import ApplyReason, LedgerState, apply_committed

from ._rcl_strategies import commit_reservation_command, issue_reservation, vec

DIMS = ["gross_notional"]
LIMITS = vec(gross_notional=100)


def test_records_are_frozen() -> None:
    """An issued record cannot be mutated in place (frozen)."""
    reservation = issue_reservation()
    with pytest.raises(ValidationError):  # frozen assignment is rejected
        reservation.action_class = "CLOSE"  # type: ignore[misc]


def test_no_update_or_delete_methods_on_records() -> None:
    """No record exposes a lifecycle-mutation method (append-only §4.2).

    Lifecycle change (resize / transfer / release / quarantine / correction) is
    expressed by appending a new committed command / transition, never by a bespoke
    mutator on the record. (Pydantic's own ``update_forward_refs`` /``model_copy``
    are not domain mutators and are not flagged.)
    """
    reservation = issue_reservation()
    forbidden = [
        name
        for name in dir(reservation)
        if not name.startswith("_")
        and any(
            token in name.lower()
            for token in (
                "delete",
                "mutate",
                "release",
                "resize",
                "quarantine",
                "transfer",
                "reassign",
            )
        )
    ]
    assert forbidden == [], f"unexpected mutation surface: {forbidden}"


def test_lifecycle_change_is_append_not_mutation() -> None:
    """A resize/second commit appends a new committed reservation; the first is unchanged."""
    s0 = LedgerState()
    o1 = apply_committed(
        s0,
        commit_reservation_command(
            command_identity="c1",
            expected_revision=0,
            reservation_id="r1",
            increment=vec(gross_notional=10),
        ),
        limits=LIMITS,
        applicable_dimensions=DIMS,
    )
    first_reservation = o1.state.committed[0]
    o2 = apply_committed(
        o1.state,
        commit_reservation_command(
            command_identity="c2",
            expected_revision=1,
            reservation_id="r2",
            increment=vec(gross_notional=20),
        ),
        limits=LIMITS,
        applicable_dimensions=DIMS,
    )
    # The prior reservation object is preserved untouched; the change is an append.
    assert o2.state.committed[0] is first_reservation
    assert len(o2.state.committed) == 2
    assert o2.state.applied_commands[0] is o1.state.applied_commands[0]


def test_prior_state_object_is_not_mutated_by_apply() -> None:
    """apply_committed returns a new state; the input state is never mutated."""
    s0 = LedgerState()
    before_committed = s0.committed
    before_applied = s0.applied_commands
    apply_committed(
        s0,
        commit_reservation_command(
            command_identity="c1",
            expected_revision=0,
            reservation_id="r1",
            increment=vec(gross_notional=10),
        ),
        limits=LIMITS,
        applicable_dimensions=DIMS,
    )
    # The original (frozen) state tuples are unchanged.
    assert s0.committed is before_committed and len(s0.committed) == 0
    assert s0.applied_commands is before_applied and len(s0.applied_commands) == 0
    assert s0.revision == 0


def test_rejected_command_recorded_without_capacity_change() -> None:
    """A rejected command appends an idempotency record but changes no committed capacity."""
    s0 = LedgerState()
    # Stale expected revision => rejected, recorded, no committed reservation added.
    outcome = apply_committed(
        s0,
        commit_reservation_command(
            command_identity="c1",
            expected_revision=99,
            reservation_id="r1",
            increment=vec(gross_notional=10),
        ),
        limits=LIMITS,
        applicable_dimensions=DIMS,
    )
    assert (
        outcome.admitted is False
        and outcome.reason is ApplyReason.REJECTED_STALE_REVISION
    )
    assert len(outcome.state.committed) == 0
    assert len(outcome.state.applied_commands) == 1
    assert outcome.state.revision == 0
