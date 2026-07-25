"""BrokerCapabilityProfile: digest / id / append-only / conflict (§2.1/§2.3/§3.1/§4.7).

Reuses the core ``tos.canonical`` digest substrate. Identity is independent of the digest
(id != f(digest)), so a same-id / different-bytes re-issuance (a forged re-publish of a
profile version) is a detectable ``classify_record_pair`` CRITICAL_CONFLICT, while a
legitimate revalidation (fresh id) is DISTINCT.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pydantic
import pytest
from pydantic import ValidationError
from tos.brokercap import (
    ArtifactStatus,
    BrokerCapabilityProfile,
    CapabilityDimension,
    ConformanceClass,
    LiveScope,
)
from tos.canonical import RecordPairKind, classify_record_pair

from ._brokercap_strategies import (
    SCHEME,
    issue_profile,
    profile_required_kwargs,
    verified_declaration,
)


def _profile_with_qty(value: Decimal | None) -> BrokerCapabilityProfile:
    return issue_profile(live_scope=LiveScope(quantity_risk_limit=value))


# ---------------------------------------------------------------------------
# CanonicalDecimal digest regression lock (vs tos.canonical PROMOTE target)
# ---------------------------------------------------------------------------


def test_qty_scale_equal_values_share_digest() -> None:
    """1.0 == 1.00 inside a LiveScope limit => equal profile digest (PROMOTE lock; §3.1)."""
    assert (
        _profile_with_qty(Decimal("1.0")).canonical_digest
        == _profile_with_qty(Decimal("1.00")).canonical_digest
    )
    assert (
        _profile_with_qty(Decimal("100")).canonical_digest
        == _profile_with_qty(Decimal("1E+2")).canonical_digest
    )


def test_qty_distinct_values_differ_in_digest() -> None:
    """Numerically-distinct limits yield different profile digests (not collapsed)."""
    assert (
        _profile_with_qty(Decimal("1.0")).canonical_digest
        != _profile_with_qty(Decimal("1.5")).canonical_digest
    )


def test_frozenset_prohibited_proofs_digest_is_deterministic() -> None:
    """(§2.1) The frozenset[ProhibitedProof] FQP field yields a stable digest across issues."""
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
    a = issue_profile(conformance_class=ConformanceClass.CLASS_A_DETERMINISTIC_LIVE)
    b = issue_profile(
        conformance_class=ConformanceClass.CLASS_B_RESTRICTED_SERIALIZED_LIVE
    )
    assert a.profile_id == b.profile_id == "prof-1"
    assert a.canonical_digest != b.canonical_digest


def test_issued_reachable_under_null_bounds() -> None:
    """(§2.3) A profile ISSUES with a live scope carrying a null quantity limit."""
    p = issue_profile(live_scope=LiveScope(quantity_risk_limit=None))
    assert p.status is ArtifactStatus.ISSUED
    assert p.canonical_digest is not None


# ---------------------------------------------------------------------------
# classify_record_pair reachability (same-id / different-bytes => CRITICAL_CONFLICT)
# ---------------------------------------------------------------------------


def test_same_id_different_bytes_is_critical_conflict() -> None:
    """(§3.1 / §4.7) A re-issued same-id / different-bytes profile is CRITICAL_CONFLICT."""
    a = issue_profile(conformance_class=ConformanceClass.CLASS_A_DETERMINISTIC_LIVE)
    b = issue_profile(
        conformance_class=ConformanceClass.CLASS_B_RESTRICTED_SERIALIZED_LIVE
    )
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
    b = issue_profile(
        profile_id="prof-2",
        conformance_class=ConformanceClass.CLASS_B_RESTRICTED_SERIALIZED_LIVE,
    )
    assert (
        classify_record_pair(
            a.profile_id, a.canonical_digest, b.profile_id, b.canonical_digest
        )
        is RecordPairKind.DISTINCT
    )


# ---------------------------------------------------------------------------
# Append-only / frozen (no update / delete / mutate)
# ---------------------------------------------------------------------------


def test_profile_is_frozen() -> None:
    """(§2.0) A profile is immutable — in-place mutation is rejected."""
    p = issue_profile()
    with pytest.raises(ValidationError):
        p.conformance_class = ConformanceClass.CLASS_D_NON_LIVE  # type: ignore[misc]


def test_declaration_for_lookup() -> None:
    """declaration_for returns the declaration for a declared dimension, None otherwise."""
    p = issue_profile(declarations=(verified_declaration(),))
    assert p.declaration_for(CapabilityDimension.ORDER_IDENTITY) is not None  # declared
    assert p.declaration_for(CapabilityDimension.CANCELLATION) is None  # undeclared


# ---------------------------------------------------------------------------
# Required-covered drop-one
# ---------------------------------------------------------------------------


def _required_cases() -> list[Any]:
    return [
        pytest.param(path, id=path)
        for path in BrokerCapabilityProfile._REQUIRED_COVERED
    ]


@pytest.mark.parametrize("path", _required_cases())
def test_missing_required_covered_rejects_issuance(path: str) -> None:
    """(§3.2) Dropping any required covered path makes an ISSUED profile unconstructable."""
    kwargs = profile_required_kwargs()
    kwargs[path] = None
    with pytest.raises(ValidationError):
        BrokerCapabilityProfile.issue(scheme=SCHEME, **kwargs)


def test_required_covered_is_non_vacuous() -> None:
    """The profile's required-covered set is not empty (fail-open guard)."""
    assert BrokerCapabilityProfile._REQUIRED_COVERED


def test_issued_requires_independent_id() -> None:
    """(§3.1) An issued profile needs a concrete independent id (never null / 'TBD')."""
    with pytest.raises(ValidationError):
        BrokerCapabilityProfile.issue(
            scheme=SCHEME, **profile_required_kwargs(profile_id=None)
        )
    with pytest.raises(ValidationError):
        BrokerCapabilityProfile.issue(
            scheme=SCHEME, **profile_required_kwargs(profile_id="TBD")
        )


def test_profile_order_excluded_from_digest() -> None:
    """(§2.3) profile_order is self-excluded — it does not change the digest."""
    a = issue_profile()
    b = issue_profile(profile_order=7)
    assert a.canonical_digest == b.canonical_digest


def test_extra_field_forbidden() -> None:
    """(§2.0) extra='forbid' — an unknown field is rejected."""
    with pytest.raises(ValidationError):
        BrokerCapabilityProfile(unexpected_field=1)  # type: ignore[call-arg]


def test_no_mutate_methods() -> None:
    """(§2.0/§4.5) brokercap adds no update / delete / mutate / release / capacity method."""
    banned = ("update", "delete", "mutate", "release", "free_capacity", "overwrite")
    inherited = set(dir(pydantic.BaseModel))
    authored = [
        n
        for n in dir(BrokerCapabilityProfile)
        if not n.startswith("_") and n not in inherited
    ]
    for name in authored:
        for token in banned:
            assert token not in name.lower(), f"unexpected mutating method: {name}"
