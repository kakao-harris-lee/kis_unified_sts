"""FieldReconciliationAssessment: digest / id / append-only / conflict (§2.1/§2.3/§3.1).

Reuses the core ``tos.canonical`` digest substrate. The CanonicalDecimal digest
regression lock is now against ``tos.canonical`` (the PROMOTE target, design #9 §0.4c):
``1.0`` and ``1.00`` inside a FieldConfidence bound must share the assessment digest.
Identity is independent of the digest (id != f(digest)), so a same-id / different-bytes
re-submission is a detectable ``classify_record_pair`` CRITICAL_CONFLICT.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pydantic
import pytest
from pydantic import ValidationError
from tos.canonical import RecordPairKind, classify_record_pair
from tos.recon import (
    ArtifactStatus,
    ConservativeBound,
    FieldConfidence,
    FieldConfidenceClass,
    FieldReconciliationAssessment,
    SafetyRelevantField,
)

from ._recon_strategies import SCHEME, assessment_required_kwargs, issue_assessment


def _assessment_with_upper(value: Decimal | None) -> FieldReconciliationAssessment:
    fc = FieldConfidence(
        field=SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY,
        confidence_class=FieldConfidenceClass.CORROBORATED,
        bound=ConservativeBound(upper=value),
    )
    return issue_assessment(field_confidences=(fc,))


# ---------------------------------------------------------------------------
# CanonicalDecimal digest regression lock (vs tos.canonical PROMOTE target)
# ---------------------------------------------------------------------------


def test_bound_scale_equal_values_share_digest() -> None:
    """1.0 == 1.00 inside a FieldConfidence bound => equal assessment digest (PROMOTE lock)."""
    assert (
        _assessment_with_upper(Decimal("1.0")).canonical_digest
        == _assessment_with_upper(Decimal("1.00")).canonical_digest
    )
    assert (
        _assessment_with_upper(Decimal("100")).canonical_digest
        == _assessment_with_upper(Decimal("1E+2")).canonical_digest
    )


def test_bound_distinct_values_differ_in_digest() -> None:
    """Numerically-distinct bounds yield different assessment digests (not collapsed)."""
    assert (
        _assessment_with_upper(Decimal("1.0")).canonical_digest
        != _assessment_with_upper(Decimal("1.5")).canonical_digest
    )


def test_none_bound_differs_from_finite() -> None:
    """An unbounded (None) upper differs at the digest from a finite upper."""
    assert (
        _assessment_with_upper(None).canonical_digest
        != _assessment_with_upper(Decimal("1")).canonical_digest
    )


# ---------------------------------------------------------------------------
# Issuance / status / id⊥digest
# ---------------------------------------------------------------------------


def test_issue_reaches_issued_with_digest() -> None:
    """A fully-specified assessment ISSUES with a concrete digest and independent id."""
    a = issue_assessment()
    assert a.status is ArtifactStatus.ISSUED
    assert a.canonical_digest is not None
    assert a.assessment_id == "asmt-1"


def test_id_is_independent_of_digest() -> None:
    """(§3.1) The assessment_id is not f(digest): same id can carry different content."""
    a = issue_assessment(scope_ref="scope-1")
    b = issue_assessment(scope_ref="scope-2")
    assert a.assessment_id == b.assessment_id == "asmt-1"
    assert a.canonical_digest != b.canonical_digest  # id fixed, digest tracks content


def test_issued_reachable_under_null_bounds() -> None:
    """(§2.3) An assessment ISSUES with field confidences carrying all-null bounds."""
    fc = FieldConfidence(
        field=SafetyRelevantField.POSITION_QUANTITY,
        confidence_class=FieldConfidenceClass.UNKNOWN,
        bound=ConservativeBound(),  # lower=None, upper=None
    )
    a = issue_assessment(field_confidences=(fc,))
    assert a.status is ArtifactStatus.ISSUED
    assert a.canonical_digest is not None


def test_empty_field_confidences_still_issues() -> None:
    """An assessment with no per-field confidences still issues (revision-0 shape)."""
    a = issue_assessment(field_confidences=())
    assert a.status is ArtifactStatus.ISSUED


# ---------------------------------------------------------------------------
# classify_record_pair reachability (same-id / different-bytes => CRITICAL_CONFLICT)
# ---------------------------------------------------------------------------


def test_same_id_different_bytes_is_critical_conflict() -> None:
    """(§3.1 / §4.6) A forged / re-submitted same-id / different-bytes pair is CRITICAL_CONFLICT."""
    a = issue_assessment(scope_ref="scope-1")
    b = issue_assessment(scope_ref="scope-2")  # same assessment_id, different bytes
    assert (
        classify_record_pair(
            a.assessment_id, a.canonical_digest, b.assessment_id, b.canonical_digest
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_same_id_same_bytes_is_idempotent_dup() -> None:
    """A legitimate identical re-emission is an idempotent duplicate, not a conflict."""
    a = issue_assessment()
    b = issue_assessment()
    assert (
        classify_record_pair(
            a.assessment_id, a.canonical_digest, b.assessment_id, b.canonical_digest
        )
        is RecordPairKind.IDEMPOTENT_DUP
    )


def test_distinct_ids_are_distinct() -> None:
    """A legitimate re-assessment (fresh id) is DISTINCT — never mis-flagged as a conflict."""
    a = issue_assessment(assessment_id="asmt-1")
    b = issue_assessment(assessment_id="asmt-2", scope_ref="scope-2")
    assert (
        classify_record_pair(
            a.assessment_id, a.canonical_digest, b.assessment_id, b.canonical_digest
        )
        is RecordPairKind.DISTINCT
    )


# ---------------------------------------------------------------------------
# Append-only / frozen (no update / delete / mutate)
# ---------------------------------------------------------------------------


def test_assessment_is_frozen() -> None:
    """(§2.0) An assessment is immutable — in-place mutation is rejected."""
    a = issue_assessment()
    with pytest.raises(ValidationError):
        a.scope_ref = "mutated"  # type: ignore[misc]


def test_no_mutate_methods() -> None:
    """(§2.0/§4.7) recon adds no public update / delete / mutate / release / capacity method."""
    banned = ("update", "delete", "mutate", "release", "free_capacity", "overwrite")
    # Scope to the recon/canonical-authored surface: subtract the pydantic framework API
    # (which carries the deprecated ``update_forward_refs`` etc. — not recon's).
    inherited = set(dir(pydantic.BaseModel))
    authored = [
        n
        for n in dir(FieldReconciliationAssessment)
        if not n.startswith("_") and n not in inherited
    ]
    for name in authored:
        for token in banned:
            assert token not in name.lower(), f"unexpected mutating method: {name}"


# ---------------------------------------------------------------------------
# Required-covered drop-one
# ---------------------------------------------------------------------------


def _required_cases() -> list[Any]:
    return [
        pytest.param(path, id=path)
        for path in FieldReconciliationAssessment._REQUIRED_COVERED
    ]


@pytest.mark.parametrize("path", _required_cases())
def test_missing_required_covered_rejects_issuance(path: str) -> None:
    """(§3.2) Dropping any required covered path makes an ISSUED assessment unconstructable."""
    kwargs = assessment_required_kwargs()
    kwargs[path] = None
    with pytest.raises(ValidationError):
        FieldReconciliationAssessment.issue(scheme=SCHEME, **kwargs)


def test_required_covered_is_non_vacuous() -> None:
    """The assessment's required-covered set is not empty (fail-open guard)."""
    assert FieldReconciliationAssessment._REQUIRED_COVERED


def test_issued_requires_independent_id() -> None:
    """(§3.1) An issued assessment needs a concrete independent id (never null / 'TBD')."""
    with pytest.raises(ValidationError):
        FieldReconciliationAssessment.issue(
            scheme=SCHEME, **assessment_required_kwargs(assessment_id=None)
        )
    with pytest.raises(ValidationError):
        FieldReconciliationAssessment.issue(
            scheme=SCHEME, **assessment_required_kwargs(assessment_id="TBD")
        )


def test_assessment_revision_excluded_from_digest() -> None:
    """(§2.3) assessment_revision is self-excluded — it does not change the digest."""
    a = issue_assessment()
    b = issue_assessment(assessment_revision=7)
    assert a.canonical_digest == b.canonical_digest
