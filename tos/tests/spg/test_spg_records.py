"""spg records: digest / id / append-only / conflict / rich-verdict invariant (§2.1/§2.3/§3.1).

Reuses the core ``tos.canonical`` digest substrate. Identity is independent of the digest
(id != f(digest)), so a same-id / different-bytes re-issuance (a forged re-publish of a
generation) is a detectable ``classify_record_pair`` CRITICAL_CONFLICT, while a legitimate
revalidation (fresh id) is DISTINCT.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError
from tos.canonical import RecordPairKind, classify_record_pair
from tos.spg import (
    ArtifactStatus,
    HardSafetyEnvelope,
    RuntimeSafetyProfile,
    SafetyConfigurationBundle,
    SemanticValidationResult,
    ValidationReason,
)

from ._spg_strategies import (
    SCHEME,
    envelope_dimension,
    envelope_required_kwargs,
    issue_activation,
    issue_bundle,
    issue_envelope,
    issue_manifest,
    issue_profile,
    profile_required_kwargs,
)

# ---------------------------------------------------------------------------
# CanonicalDecimal digest regression lock (vs tos.canonical PROMOTE target)
# ---------------------------------------------------------------------------


def _env_with_max(value: Decimal | None) -> HardSafetyEnvelope:
    return issue_envelope(governed_dimensions=(envelope_dimension(envelope_max=value),))


def test_limit_scale_equal_values_share_digest() -> None:
    """1.0 == 1.00 inside a governed dimension => equal envelope digest (PROMOTE lock; §3.1)."""
    assert (
        _env_with_max(Decimal("1.0")).canonical_digest
        == _env_with_max(Decimal("1.00")).canonical_digest
    )
    assert (
        _env_with_max(Decimal("100")).canonical_digest
        == _env_with_max(Decimal("1E+2")).canonical_digest
    )


def test_limit_distinct_values_differ_in_digest() -> None:
    """Numerically-distinct maxima yield different envelope digests (not collapsed)."""
    assert (
        _env_with_max(Decimal("1.0")).canonical_digest
        != _env_with_max(Decimal("1.5")).canonical_digest
    )


# ---------------------------------------------------------------------------
# Issuance / status / id ⊥ digest — every digest-bound citizen
# ---------------------------------------------------------------------------


def test_all_five_artifacts_issue_with_digest() -> None:
    """Each of the five digest-bound citizens ISSUES with a concrete digest + independent id."""
    for artifact, id_value in (
        (issue_envelope(), "env-1"),
        (issue_profile(), "prof-1"),
        (issue_bundle(), "b-1"),
        (issue_activation(), "act-1"),
        (issue_manifest(), "man-1"),
    ):
        assert artifact.status is ArtifactStatus.ISSUED
        assert artifact.canonical_digest is not None
        assert getattr(artifact, artifact._ID_FIELD) == id_value


def test_envelope_id_is_independent_of_digest() -> None:
    """(§3.1) envelope_id is not f(digest): same id can carry different content."""
    a = issue_envelope(permitted_scope=("acct-1",))
    b = issue_envelope(permitted_scope=("acct-2",))
    assert a.envelope_id == b.envelope_id == "env-1"
    assert a.canonical_digest != b.canonical_digest


def test_issued_reachable_under_null_bounds() -> None:
    """(§2.3) An envelope ISSUES with a governed dimension carrying a null max."""
    e = issue_envelope(governed_dimensions=(envelope_dimension(envelope_max=None),))
    assert e.status is ArtifactStatus.ISSUED
    assert e.canonical_digest is not None


# ---------------------------------------------------------------------------
# classify_record_pair reachability (same-id / different-bytes => CRITICAL_CONFLICT)
# ---------------------------------------------------------------------------


def test_same_id_different_bytes_is_critical_conflict() -> None:
    """(§3.1 / §4.6) A re-issued same-id / different-bytes envelope is CRITICAL_CONFLICT."""
    a = issue_envelope(permitted_scope=("acct-1",))
    b = issue_envelope(permitted_scope=("acct-2",))
    assert (
        classify_record_pair(
            a.envelope_id, a.canonical_digest, b.envelope_id, b.canonical_digest
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
    """(§2.3) A legitimate revalidation (fresh id) is DISTINCT — never mis-flagged."""
    a = issue_envelope(envelope_id="env-1")
    b = issue_envelope(envelope_id="env-2", permitted_scope=("acct-2",))
    assert (
        classify_record_pair(
            a.envelope_id, a.canonical_digest, b.envelope_id, b.canonical_digest
        )
        is RecordPairKind.DISTINCT
    )


# ---------------------------------------------------------------------------
# Append-only / frozen / extra=forbid / ledger-order excluded
# ---------------------------------------------------------------------------


def test_artifacts_are_frozen() -> None:
    """(§2.0) Every artifact is immutable — in-place mutation is rejected."""
    e = issue_envelope()
    with pytest.raises(ValidationError):
        e.envelope_generation = 9  # type: ignore[misc]


def test_extra_field_forbidden() -> None:
    """(§2.0 / §7 line 226) extra='forbid' — an unknown authority-affecting field is rejected."""
    with pytest.raises(ValidationError):
        HardSafetyEnvelope(unexpected_field=1)  # type: ignore[call-arg]


def test_envelope_order_excluded_from_digest() -> None:
    """(§2.3) envelope_order is self-excluded — it does not change the digest."""
    a = issue_envelope()
    b = issue_envelope(envelope_order=7)
    assert a.canonical_digest == b.canonical_digest


def test_bundle_binds_nested_envelope_and_profile_digest() -> None:
    """(§5.3) A changed nested profile changes the bundle digest (the bundle binds them)."""
    a = issue_bundle(profile=issue_profile(scope=("acct-1",)))
    b = issue_bundle(profile=issue_profile(profile_id="prof-2", scope=("acct-2",)))
    assert a.canonical_digest != b.canonical_digest


# ---------------------------------------------------------------------------
# Required-covered drop-one (every digest-bound citizen)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", list(HardSafetyEnvelope._REQUIRED_COVERED))
def test_envelope_missing_required_covered_rejects(path: str) -> None:
    """(§3.2) Dropping any required covered path makes an ISSUED envelope unconstructable."""
    kwargs = envelope_required_kwargs()
    kwargs[path] = None
    with pytest.raises(ValidationError):
        HardSafetyEnvelope.issue(scheme=SCHEME, **kwargs)


@pytest.mark.parametrize("path", list(RuntimeSafetyProfile._REQUIRED_COVERED))
def test_profile_missing_required_covered_rejects(path: str) -> None:
    """(§3.2) Dropping any required covered path makes an ISSUED profile unconstructable."""
    kwargs = profile_required_kwargs()
    kwargs[path] = None
    with pytest.raises(ValidationError):
        RuntimeSafetyProfile.issue(scheme=SCHEME, **kwargs)


def test_required_covered_sets_are_non_vacuous() -> None:
    """Each artifact's required-covered set is not empty (fail-open guard)."""
    assert HardSafetyEnvelope._REQUIRED_COVERED
    assert RuntimeSafetyProfile._REQUIRED_COVERED
    assert SafetyConfigurationBundle._REQUIRED_COVERED


def test_issued_requires_independent_id() -> None:
    """(§3.1) An issued envelope needs a concrete independent id (never null / 'TBD')."""
    for bad in (None, "TBD"):
        kwargs: dict[str, Any] = envelope_required_kwargs(envelope_id=bad)
        with pytest.raises(ValidationError):
            HardSafetyEnvelope.issue(scheme=SCHEME, **kwargs)


# ---------------------------------------------------------------------------
# SemanticValidationResult valid <-> reason-set coupling invariant (§4.2 ∅-seal)
# ---------------------------------------------------------------------------


def test_valid_result_must_have_empty_reason_set() -> None:
    """(§4.2) A VALID result with a non-empty reason set is unconstructable."""
    SemanticValidationResult(valid=True)  # ok
    with pytest.raises(ValidationError):
        SemanticValidationResult(
            valid=True, reason_set=frozenset({ValidationReason.EXCEEDS_ENVELOPE})
        )


def test_invalid_result_must_have_nonempty_reason_set() -> None:
    """(§4.2 ∅-seal) A vacuous INVALID result (no reason) is unconstructable."""
    SemanticValidationResult(
        valid=False, reason_set=frozenset({ValidationReason.EXCEEDS_ENVELOPE})
    )  # ok
    with pytest.raises(ValidationError):
        SemanticValidationResult(valid=False)
