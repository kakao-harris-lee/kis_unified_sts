"""RCL reservation identity — one reservation per *attempt*, named by its permit (#966)."""

from __future__ import annotations

from tos.engine.records import AttemptRequest, InstrumentKey

__all__ = [
    "attempt_request_reservation_id",
    "permit_identity_of",
    "permit_reservation_id",
    "reservation_id_in_scope",
    "scope_reservation_id",
]

_PREFIX = "resv"


def scope_reservation_id(account: str, instrument: str) -> str:
    """The pre-#966 scope-level reservation id — **read-only now**."""
    return f"{_PREFIX}-{account}-{instrument}"


def permit_reservation_id(account: str, instrument: str, permit_identity: str) -> str:
    """This attempt's own RCL reservation id (module docstring)."""
    return f"{scope_reservation_id(account, instrument)}-{permit_identity}"


def reservation_id_in_scope(
    key: InstrumentKey, permit_identity: str | None
) -> str | None:
    """:func:`permit_reservation_id` over ``key``, ``None``-safe in the permit identity."""
    if not permit_identity:
        return None
    return permit_reservation_id(key.account, key.instrument, permit_identity)


def attempt_request_reservation_id(
    key: InstrumentKey, attempt: AttemptRequest | None
) -> str | None:
    """The reservation id of a bound attempt request, from the permit identity it carries."""
    if attempt is None:
        return None
    return reservation_id_in_scope(key, attempt.action_flow_permit_identity)


def permit_identity_of(
    reservation_id: str, *, account: str, instrument: str
) -> str | None:
    """The permit identity :func:`permit_reservation_id` wrote into ``reservation_id``."""
    prefix = f"{scope_reservation_id(account, instrument)}-"
    if not reservation_id.startswith(prefix):
        return None
    permit_identity = reservation_id[len(prefix) :]
    return permit_identity or None
