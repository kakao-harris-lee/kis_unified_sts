"""Ledger-citizen records — required-covered, ISSUED-reachability, append-only (§2, §4).

Each record drops one required covered path and asserts issuance is rejected; an
authorization is still ISSUED-reachable with numeric bounds null (bounds are excluded
from the required set, §2.2); records are frozen with no lifecycle mutator (append-only);
the mutable lifecycle state is NOT covered (coordinate non-collapse); and non-revival is a
structural absence. [REARM-EV-004/012 substrate]
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import tos.liveauth as liveauth
from pydantic import ValidationError
from tos.canonical import RecordPairKind, classify_record_pair
from tos.liveauth import (
    ArtifactStatus,
    LiveAuthorization,
    LiveAuthorizationTransitionRecord,
    ReArmApprovalRecord,
    authorization_revived_by_nothing,
)

from ._liveauth_strategies import (
    SCHEME,
    approval_required_kwargs,
    authorization_required_kwargs,
    full_scope,
    issue_approval,
    issue_authorization,
    issue_transition,
    transition_required_kwargs,
    wide_scope,
)

_ARTIFACTS: list[tuple[type, Callable[..., dict[str, Any]]]] = [
    (LiveAuthorization, authorization_required_kwargs),
    (LiveAuthorizationTransitionRecord, transition_required_kwargs),
    (ReArmApprovalRecord, approval_required_kwargs),
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
    """No ledger citizen has an empty _REQUIRED_COVERED (fail-open guard)."""
    for cls, _ in _ARTIFACTS:
        assert cls._REQUIRED_COVERED, f"{cls.__name__} has a vacuous _REQUIRED_COVERED"


def test_authorization_issued_under_null_numeric_bounds() -> None:
    """An authorization ISSUES with numeric bounds null (bounds excluded from required, §2.2).

    ISSUED-reachability keeps the §5.2 / §6.1 consumption preconditions meaningful: the
    authorization reaches the ledger, then fails closed at *consumption*, not issuance.
    """
    auth = issue_authorization(
        maximum_validity=None,
        maximum_quantity_notional_risk_margin_concentration_rate_constraints=None,
    )
    assert auth.status is ArtifactStatus.ISSUED
    assert auth.canonical_digest is not None


def test_issued_record_requires_independent_id() -> None:
    """An issued authorization needs a concrete independent id (never null / 'TBD') (§2.1/§3.1)."""
    with pytest.raises(ValidationError):
        LiveAuthorization.issue(
            scheme=SCHEME, **authorization_required_kwargs(authorization_id=None)
        )
    with pytest.raises(ValidationError):
        LiveAuthorization.issue(
            scheme=SCHEME, **authorization_required_kwargs(authorization_id="TBD")
        )


def test_lifecycle_state_is_not_covered() -> None:
    """(canary coordinate non-collapse §2.2) The mutable lifecycle state is NOT a covered field.

    The record carries only immutable §7 claims in its digest preimage, so a legitimate
    transition never changes the digest and is never mis-flagged as a CRITICAL_CONFLICT.
    """
    covered = LiveAuthorization._COVERED_FIELDS
    assert "live_authorization_state" not in covered
    assert "current_state" not in covered
    # The record does not even declare a mutable lifecycle-state field.
    assert "live_authorization_state" not in LiveAuthorization.model_fields
    # safety_authority_epoch and revocation_generation are distinct covered coordinates.
    assert "safety_authority_epoch" in covered
    assert "revocation_generation" in covered


def _classify_transition(a, b) -> RecordPairKind:
    return classify_record_pair(
        a.transition_id, a.canonical_digest, b.transition_id, b.canonical_digest
    )


def test_transition_same_id_diff_bytes_conflicts() -> None:
    """(canary) A same-transition-id / different-bytes pair is a CRITICAL_CONFLICT."""
    a = issue_transition(transition_id="tr-1", transition_reason="activation")
    b = issue_transition(transition_id="tr-1", transition_reason="operator-override")
    assert a.canonical_digest != b.canonical_digest
    assert _classify_transition(a, b) is RecordPairKind.CRITICAL_CONFLICT


def test_approval_same_id_diff_scope_conflicts() -> None:
    """(canary §13 line 431) A same-approval-id / different-scope pair is a CRITICAL_CONFLICT.

    Changed scope changes the digest and invalidates a prior approval (approval bound to
    the exact requested scope).
    """
    a = issue_approval(approval_record_id="appr-1", requested_scope=full_scope())
    b = issue_approval(approval_record_id="appr-1", requested_scope=wide_scope())
    assert a.canonical_digest != b.canonical_digest
    kind = classify_record_pair(
        a.approval_record_id,
        a.canonical_digest,
        b.approval_record_id,
        b.canonical_digest,
    )
    assert kind is RecordPairKind.CRITICAL_CONFLICT


def test_records_are_frozen() -> None:
    """An issued record cannot be mutated in place (frozen; append-only §2.0)."""
    auth = issue_authorization()
    with pytest.raises(ValidationError):
        auth.issuer_identity = "other"  # type: ignore[misc]


def test_no_update_or_delete_methods_on_records() -> None:
    """No record exposes a lifecycle-mutation method (append-only §2.0/§18)."""
    for record in (issue_authorization(), issue_transition(), issue_approval()):
        forbidden = [
            name
            for name in dir(record)
            if not name.startswith("_")
            and any(
                token in name.lower()
                for token in ("delete", "mutate", "revoke", "revive", "expand", "rearm")
            )
        ]
        assert forbidden == [], f"{type(record).__name__} mutation surface: {forbidden}"


def test_authorization_revived_by_nothing_is_always_true() -> None:
    """(canary §4.3) A later generation never revives an invalidated authorization."""
    assert (
        authorization_revived_by_nothing(
            invalidated_under_generation=1, new_generation=5
        )
        is True
    )
    assert (
        authorization_revived_by_nothing(
            invalidated_under_generation=None, new_generation=None
        )
        is True
    )


def test_no_revive_or_reactivate_operation_exists() -> None:
    """(canary §4.3) The package exposes no 'invalidation => ACTIVE restored' operation.

    The only name mentioning revival is ``authorization_revived_by_nothing`` — the
    predicate that documents the absence (returns True) — not a revive / reactivate op.
    """
    revive_names = [
        name
        for name in dir(liveauth)
        if name != "authorization_revived_by_nothing"
        and any(
            token in name.lower()
            for token in (
                "revive",
                "reactivate",
                "restore_authorization",
                "uninvalidate",
            )
        )
    ]
    assert revive_names == []
