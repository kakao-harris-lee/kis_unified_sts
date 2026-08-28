"""Required-covered issuance guards + ISSUED-reachable-under-null-bounds (§2.2/§3.2).

Each record drops one required covered path and asserts issuance is rejected. A
companion test proves a reservation is still ISSUED-reachable with all numeric
bounds null (the design §2.2 reason numeric bounds are excluded from the required
set — else every Phase-1 snapshot would fall to DRAFT).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError
from tos.rcl import (
    ArtifactStatus,
    AuthoritativeSnapshot,
    LedgerCommandRecord,
    ProtectiveLease,
    ProtectivePool,
    RclTransitionRecord,
    ReservationRecord,
    TransmissionCapability,
)

from ._rcl_strategies import (
    SCHEME,
    capability_required_kwargs,
    command_required_kwargs,
    issue_reservation,
    lease_required_kwargs,
    pool_required_kwargs,
    reservation_required_kwargs,
    snapshot_required_kwargs,
    transition_required_kwargs,
)

_ARTIFACTS: list[tuple[type, Callable[..., dict[str, Any]]]] = [
    (ReservationRecord, reservation_required_kwargs),
    (LedgerCommandRecord, command_required_kwargs),
    (RclTransitionRecord, transition_required_kwargs),
    (TransmissionCapability, capability_required_kwargs),
    (ProtectivePool, pool_required_kwargs),
    (ProtectiveLease, lease_required_kwargs),
    (AuthoritativeSnapshot, snapshot_required_kwargs),
]


def _cases() -> list[Any]:
    cases: list[Any] = []
    for cls, kwargs_fn in _ARTIFACTS:
        for path in cls._REQUIRED_COVERED:  # type: ignore[attr-defined]
            cases.append(
                pytest.param(cls, kwargs_fn, path, id=f"{cls.__name__}:{path}")
            )
    return cases


@pytest.mark.parametrize("cls,kwargs_fn,path", _cases())
def test_missing_required_covered_rejects_issuance(
    cls: type, kwargs_fn: Callable[..., dict[str, Any]], path: str
) -> None:
    """Dropping any required covered path makes an ISSUED record unconstructable (§3.2)."""
    kwargs = kwargs_fn()
    kwargs[path] = None
    with pytest.raises(ValidationError):
        cls.issue(scheme=SCHEME, **kwargs)  # type: ignore[attr-defined]


def test_every_record_has_non_vacuous_required_covered() -> None:
    """No digest-bound RCL record has an empty _REQUIRED_COVERED (fail-open guard)."""
    for cls, _ in _ARTIFACTS:
        assert cls._REQUIRED_COVERED, f"{cls.__name__} has a vacuous _REQUIRED_COVERED"


def test_reservation_issued_reachable_under_null_numeric_bounds() -> None:
    """A reservation ISSUES with all numeric bounds null (bounds excluded from required, §2.2)."""
    reservation = issue_reservation(
        approved_quantity_upper_bound=None,
        filled_quantity_lower_bound=None,
        filled_quantity_upper_bound=None,
        remaining_executable_quantity_upper_bound=None,
    )
    assert reservation.status is ArtifactStatus.ISSUED
    assert reservation.canonical_digest is not None


def test_issued_record_requires_independent_id() -> None:
    """An issued record needs a concrete independent id (never null / 'TBD') (§2.1/§3.1)."""
    kwargs = reservation_required_kwargs(reservation_id=None)
    with pytest.raises(ValidationError):
        ReservationRecord.issue(scheme=SCHEME, **kwargs)
    kwargs = reservation_required_kwargs(reservation_id="TBD")
    with pytest.raises(ValidationError):
        ReservationRecord.issue(scheme=SCHEME, **kwargs)
