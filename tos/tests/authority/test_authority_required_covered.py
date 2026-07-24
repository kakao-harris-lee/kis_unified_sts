"""Required-covered issuance guards + ISSUED-reachable-under-null-bounds (§2.2/§3.2).

Each record drops one required covered path and asserts issuance is rejected. A
companion test proves a capability is still ISSUED-reachable with the numeric claims
null (the design §2.2 reason numeric bounds are excluded from the required set — else
every Phase-1 capability would fall to DRAFT and be unrepresentable), while the
epoch-transition record additionally rejects a non-increasing epoch (§10.5).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError
from tos.authority import (
    ArtifactStatus,
    AuthorityEpochTransitionRecord,
    AuthorityTransitionReason,
    DegradedLeaseOwnershipRecord,
    SafetyAuthorityCapability,
)

from ._authority_strategies import (
    SCHEME,
    capability_required_kwargs,
    issue_capability,
    lease_required_kwargs,
    transition_required_kwargs,
)

_ARTIFACTS: list[tuple[type, Callable[..., dict[str, Any]]]] = [
    (SafetyAuthorityCapability, capability_required_kwargs),
    (AuthorityEpochTransitionRecord, transition_required_kwargs),
    (DegradedLeaseOwnershipRecord, lease_required_kwargs),
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
    """No digest-bound authority record has an empty _REQUIRED_COVERED (fail-open guard)."""
    for cls, _ in _ARTIFACTS:
        assert cls._REQUIRED_COVERED, f"{cls.__name__} has a vacuous _REQUIRED_COVERED"


def test_capability_issued_reachable_under_null_numeric_bounds() -> None:
    """A capability ISSUES with both numeric claims null (bounds excluded from required, §2.2).

    ISSUED-reachability is what keeps the §5.2 numeric-claim precondition meaningful:
    the capability reaches the ledger, then fails closed at *consumption*, not issuance.
    """
    capability = issue_capability(
        maximum_quantity=None,
        maximum_risk_vector_effect_or_reservation_identity=None,
    )
    assert capability.status is ArtifactStatus.ISSUED
    assert capability.canonical_digest is not None


def test_issued_record_requires_independent_id() -> None:
    """An issued capability needs a concrete independent id (never null / 'TBD') (§2.1/§3.1)."""
    with pytest.raises(ValidationError):
        SafetyAuthorityCapability.issue(
            scheme=SCHEME, **capability_required_kwargs(capability_id=None)
        )
    with pytest.raises(ValidationError):
        SafetyAuthorityCapability.issue(
            scheme=SCHEME, **capability_required_kwargs(capability_id="TBD")
        )


def test_epoch_transition_rejects_non_increasing_epoch() -> None:
    """(canary) A transition whose new_epoch <= old_epoch is unconstructable (§5.2/§10.5).

    Rejects epoch reuse / reset / wraparound structurally — the model provides no path
    to decrease or reuse an epoch.
    """
    # equal (reuse)
    with pytest.raises(ValidationError):
        AuthorityEpochTransitionRecord.issue(
            scheme=SCHEME, **transition_required_kwargs(old_epoch=5, new_epoch=5)
        )
    # decrease (reset / wraparound)
    with pytest.raises(ValidationError):
        AuthorityEpochTransitionRecord.issue(
            scheme=SCHEME, **transition_required_kwargs(old_epoch=6, new_epoch=5)
        )


def test_epoch_transition_strictly_increasing_is_issuable() -> None:
    """The strictly-increasing guard is not constant-reject: a real advance issues."""
    record = AuthorityEpochTransitionRecord.issue(
        scheme=SCHEME,
        **transition_required_kwargs(
            old_epoch=5,
            new_epoch=6,
            transition_reason=AuthorityTransitionReason.SAFETY_AUTHORITY_FAILOVER,
        ),
    )
    assert record.status is ArtifactStatus.ISSUED
    assert record.new_epoch > record.old_epoch
