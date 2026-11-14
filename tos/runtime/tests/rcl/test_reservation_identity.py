"""#966 — the RCL reservation identity formula and its inverse."""

from __future__ import annotations

from tos.engine.records import AttemptRequest, InstrumentKey
from tos_runtime.rcl.reservation_identity import (
    attempt_request_reservation_id,
    permit_identity_of,
    permit_reservation_id,
    reservation_id_in_scope,
    scope_reservation_id,
)

_ACCOUNT = "88888888-01"
_INSTRUMENT = "005930"
_KEY = InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT)
_PERMIT = "afg-permit-0a1b2c3d"


def _attempt(permit_identity: str = _PERMIT) -> AttemptRequest:
    return AttemptRequest(
        attempt_id="attempt-for-identity-test",
        conformance_proof_digest="proof-digest",
        action_flow_permit_identity=permit_identity,
        reference_coordinate_digest="ref-digest",
    )


def test_two_attempts_in_one_scope_get_two_reservation_ids() -> None:
    """The whole point of #966: the id is per attempt, not per scope."""
    first = permit_reservation_id(_ACCOUNT, _INSTRUMENT, "afg-permit-entry")
    second = permit_reservation_id(_ACCOUNT, _INSTRUMENT, "afg-permit-exit")
    assert first != second
    assert first.startswith(scope_reservation_id(_ACCOUNT, _INSTRUMENT))
    assert second.startswith(scope_reservation_id(_ACCOUNT, _INSTRUMENT))


def test_the_formula_is_deterministic() -> None:
    """Same inputs, same id — a replay reproduces it (no clock, no RNG anywhere on this path)."""
    assert permit_reservation_id(
        _ACCOUNT, _INSTRUMENT, _PERMIT
    ) == permit_reservation_id(_ACCOUNT, _INSTRUMENT, _PERMIT)


def test_scope_id_is_the_prefix_of_every_per_attempt_id() -> None:
    """What lets a scope-wide evidence scan match both forms with one prefix test."""
    scope_id = scope_reservation_id(_ACCOUNT, _INSTRUMENT)
    assert (
        permit_reservation_id(_ACCOUNT, _INSTRUMENT, _PERMIT) == f"{scope_id}-{_PERMIT}"
    )


def test_reservation_id_in_scope_refuses_an_absent_permit_identity() -> None:
    """Steps 10 and 14 must not invent an id for an unbound permit — they read back whatever"""
    assert reservation_id_in_scope(_KEY, None) is None
    assert reservation_id_in_scope(_KEY, "") is None
    assert reservation_id_in_scope(_KEY, _PERMIT) == permit_reservation_id(
        _ACCOUNT, _INSTRUMENT, _PERMIT
    )


def test_attempt_request_reservation_id_reads_the_permit_the_attempt_carries() -> None:
    assert attempt_request_reservation_id(_KEY, None) is None
    assert attempt_request_reservation_id(_KEY, _attempt()) == permit_reservation_id(
        _ACCOUNT, _INSTRUMENT, _PERMIT
    )


def test_permit_identity_of_round_trips_through_an_account_containing_a_dash() -> None:
    """The concrete failing input a split-based parse gets wrong."""
    reservation_id = permit_reservation_id(_ACCOUNT, _INSTRUMENT, _PERMIT)
    assert (
        permit_identity_of(reservation_id, account=_ACCOUNT, instrument=_INSTRUMENT)
        == _PERMIT
    )


def test_permit_identity_of_rejects_a_pre_966_scope_level_row() -> None:
    """A legacy row carries no attempt identity at all — ``None``, never a guess."""
    legacy = scope_reservation_id(_ACCOUNT, _INSTRUMENT)
    assert permit_identity_of(legacy, account=_ACCOUNT, instrument=_INSTRUMENT) is None


def test_permit_identity_of_rejects_another_scopes_row() -> None:
    other = permit_reservation_id("99999999-02", _INSTRUMENT, _PERMIT)
    assert permit_identity_of(other, account=_ACCOUNT, instrument=_INSTRUMENT) is None
