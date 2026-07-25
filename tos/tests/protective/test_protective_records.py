"""ProtectiveCapacityProfile: digest / id / append-only / conflict (§2.1/§2.3/§3.1/§4.6).

Reuses the core ``tos.canonical`` digest substrate. Identity is independent of the digest
(``id != f(digest)``), so a same-id / different-bytes re-issuance (a forged re-publish of a
profile version) is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``, while a
legitimate revalidation (fresh id) is ``DISTINCT``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pydantic
import pytest
from pydantic import ValidationError
from tos.canonical import RecordPairKind, classify_record_pair
from tos.protective import (
    ArtifactStatus,
    ProtectiveActionEnvelope,
    ProtectiveCapacityProfile,
    ProtectiveResourceDomain,
)

from ._protective_strategies import (
    SCHEME,
    action_envelope,
    all_domains_declared,
    issue_profile,
    profile_required_kwargs,
)


def _profile_with_qty(value: Decimal | None) -> ProtectiveCapacityProfile:
    return issue_profile(action_envelope=action_envelope(max_quantity=value))


# ---------------------------------------------------------------------------
# CanonicalDecimal digest regression lock (PROMOTE reuse; §3.1)
# ---------------------------------------------------------------------------


def test_qty_scale_equal_values_share_digest() -> None:
    """1.0 == 1.00 inside an envelope axis => equal profile digest (PROMOTE lock; §3.1)."""
    assert (
        _profile_with_qty(Decimal("1.0")).canonical_digest
        == _profile_with_qty(Decimal("1.00")).canonical_digest
    )


def test_qty_distinct_values_differ_in_digest() -> None:
    """Numerically-distinct magnitudes yield different profile digests (not collapsed)."""
    assert (
        _profile_with_qty(Decimal("1.0")).canonical_digest
        != _profile_with_qty(Decimal("1.5")).canonical_digest
    )


def test_declarations_digest_is_deterministic() -> None:
    """(§2.1) The declarations tuple yields a stable digest across repeated issues."""
    digests = {issue_profile().canonical_digest for _ in range(16)}
    assert len(digests) == 1


# ---------------------------------------------------------------------------
# Issuance / status / id⊥digest
# ---------------------------------------------------------------------------


def test_issue_reaches_issued_with_digest() -> None:
    """A fully-specified profile ISSUES with a concrete digest and independent id."""
    p = issue_profile()
    assert p.status is ArtifactStatus.ISSUED
    assert p.canonical_digest is not None
    assert p.profile_id == "prof-1"


def test_id_is_independent_of_digest() -> None:
    """(§3.1) profile_id is not f(digest): same id can carry different content."""
    a = issue_profile(profile_version="v1")
    b = issue_profile(profile_version="v2")
    assert a.profile_id == b.profile_id == "prof-1"
    assert a.canonical_digest != b.canonical_digest


def test_issued_reachable_under_null_bounds() -> None:
    """(§2.3) A profile ISSUES with an envelope carrying null magnitude axes."""
    p = issue_profile(action_envelope=ProtectiveActionEnvelope())
    assert p.status is ArtifactStatus.ISSUED
    assert p.canonical_digest is not None


# ---------------------------------------------------------------------------
# classify_record_pair reachability (same-id / different-bytes => CRITICAL_CONFLICT)
# ---------------------------------------------------------------------------


def test_same_id_different_bytes_is_critical_conflict() -> None:
    """(§4.6 / §3.1) A re-issued same-id / different-bytes profile is CRITICAL_CONFLICT."""
    a = issue_profile(profile_version="v1")
    b = issue_profile(profile_version="v2")
    assert (
        classify_record_pair(
            a.profile_id, a.canonical_digest, b.profile_id, b.canonical_digest
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_same_id_same_bytes_is_idempotent_dup() -> None:
    """A legitimate identical re-emission is an idempotent duplicate, not a conflict."""
    a = issue_profile()
    b = issue_profile()
    assert (
        classify_record_pair(
            a.profile_id, a.canonical_digest, b.profile_id, b.canonical_digest
        )
        is RecordPairKind.IDEMPOTENT_DUP
    )


def test_distinct_ids_are_distinct() -> None:
    """(§2.3) A legitimate revalidation (fresh profile_id) is DISTINCT — never mis-flagged."""
    a = issue_profile(profile_id="prof-1")
    b = issue_profile(profile_id="prof-2", profile_version="v2")
    assert (
        classify_record_pair(
            a.profile_id, a.canonical_digest, b.profile_id, b.canonical_digest
        )
        is RecordPairKind.DISTINCT
    )


def test_null_digest_draft_is_not_comparable() -> None:
    """(§4.6) A pre-issuance DRAFT (null digest) is NOT_COMPARABLE, never a false conflict."""
    issued = issue_profile()
    assert (
        classify_record_pair("prof-1", None, issued.profile_id, issued.canonical_digest)
        is RecordPairKind.NOT_COMPARABLE
    )


# ---------------------------------------------------------------------------
# Append-only / frozen (no update / delete / mutate)
# ---------------------------------------------------------------------------


def test_profile_is_frozen() -> None:
    """(§2.0) A profile is immutable — in-place mutation is rejected."""
    p = issue_profile()
    with pytest.raises(ValidationError):
        p.profile_version = "v9"  # type: ignore[misc]


def test_declaration_for_lookup() -> None:
    """declaration_for returns the declaration for a declared domain, None otherwise."""
    p = issue_profile(
        declarations=(
            *(
                d
                for d in all_domains_declared()
                if d.domain is not ProtectiveResourceDomain.OPERATOR_EMERGENCY_PATH
            ),
        )
    )
    assert (
        p.declaration_for(ProtectiveResourceDomain.EXECUTION_WORKERS_AND_QUEUES)
        is not None
    )
    assert p.declaration_for(ProtectiveResourceDomain.OPERATOR_EMERGENCY_PATH) is None


def test_extra_field_forbidden() -> None:
    """(§2.0) extra='forbid' — an unknown field is rejected."""
    with pytest.raises(ValidationError):
        ProtectiveCapacityProfile(unexpected_field=1)  # type: ignore[call-arg]


def test_profile_order_excluded_from_digest() -> None:
    """(§2.3) profile_order is self-excluded — it does not change the digest."""
    a = issue_profile()
    b = issue_profile(profile_order=7)
    assert a.canonical_digest == b.canonical_digest


# ---------------------------------------------------------------------------
# Required-covered drop-one
# ---------------------------------------------------------------------------


def _required_cases() -> list[Any]:
    return [
        pytest.param(path, id=path)
        for path in ProtectiveCapacityProfile._REQUIRED_COVERED
    ]


@pytest.mark.parametrize("path", _required_cases())
def test_missing_required_covered_rejects_issuance(path: str) -> None:
    """(§3.2) Dropping any required covered path makes an ISSUED profile unconstructable."""
    kwargs = profile_required_kwargs()
    kwargs[path] = None
    with pytest.raises(ValidationError):
        ProtectiveCapacityProfile.issue(scheme=SCHEME, **kwargs)


def test_required_covered_is_non_vacuous() -> None:
    """The profile's required-covered set is not empty (fail-open guard)."""
    assert ProtectiveCapacityProfile._REQUIRED_COVERED


def test_issued_requires_independent_id() -> None:
    """(§3.1) An issued profile needs a concrete independent id (never null / 'TBD')."""
    with pytest.raises(ValidationError):
        ProtectiveCapacityProfile.issue(
            scheme=SCHEME, **profile_required_kwargs(profile_id=None)
        )
    with pytest.raises(ValidationError):
        ProtectiveCapacityProfile.issue(
            scheme=SCHEME, **profile_required_kwargs(profile_id="TBD")
        )


def test_no_mutate_methods() -> None:
    """(§2.0/§4.5) protective adds no update / delete / mutate / release / capacity method."""
    banned = ("update", "delete", "mutate", "release", "free_capacity", "overwrite")
    inherited = set(dir(pydantic.BaseModel))
    authored = [
        n
        for n in dir(ProtectiveCapacityProfile)
        if not n.startswith("_") and n not in inherited
    ]
    for name in authored:
        for token in banned:
            assert token not in name.lower(), f"unexpected mutating method: {name}"
