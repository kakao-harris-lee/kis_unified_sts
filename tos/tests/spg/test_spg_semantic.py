"""Semantic validation rich verdict + per-reason regressions (design #12 §5.2; SPG-EV-002/003).

Every defect maps to a specific reason; a VALID result has an empty reason set; the ∅-void
(absent / incomplete bundle) is invalid. Explicit regressions for units mismatch, cross-field
contradiction, UNORDERABLE_DIRECTION, NaN, duplicate field, and schema downgrade.
"""

from __future__ import annotations

from decimal import Decimal

from tos.spg import (
    ChangeDirection,
    SafetyConfigurationBundle,
    ValidationReason,
    semantic_validation,
    units_compatible,
)

from ._spg_strategies import (
    SCHEME,
    envelope_dimension,
    issue_bundle,
    issue_envelope,
    issue_profile,
    over_envelope_profile,
    profile_dimension,
    valid_semantic_inputs,
)

# ---------------------------------------------------------------------------
# Positive side — a clean bundle validates with an empty reason set
# ---------------------------------------------------------------------------


def test_valid_bundle_has_empty_reason_set() -> None:
    """(canary +) A within-envelope, unit-compatible, restrictive bundle is VALID."""
    result = semantic_validation(issue_bundle(), valid_semantic_inputs())
    assert result.valid is True
    assert result.reason_set == frozenset()
    assert result.bundle_digest is not None


# ---------------------------------------------------------------------------
# ∅-void — absent / incomplete bundle is invalid
# ---------------------------------------------------------------------------


def test_absent_bundle_is_invalid() -> None:
    """(∅-seal §4.2) A None bundle is invalid with SCHEMA_INCOMPLETE_OR_DOWNGRADE."""
    result = semantic_validation(None, valid_semantic_inputs())
    assert result.valid is False
    assert ValidationReason.SCHEMA_INCOMPLETE_OR_DOWNGRADE in result.reason_set


def test_bundle_missing_profile_is_invalid() -> None:
    """(∅-seal) A bundle without a nested profile cannot be vacuously valid."""
    bundle = SafetyConfigurationBundle.issue(
        scheme=SCHEME, bundle_id="b-x", bundle_generation=1, envelope=issue_envelope()
    )
    result = semantic_validation(bundle, valid_semantic_inputs())
    assert result.valid is False
    assert ValidationReason.SCHEMA_INCOMPLETE_OR_DOWNGRADE in result.reason_set


# ---------------------------------------------------------------------------
# Per-reason regressions
# ---------------------------------------------------------------------------


def test_exceeds_envelope_reason() -> None:
    """(step 6) An over-envelope profile => EXCEEDS_ENVELOPE."""
    bundle = issue_bundle(profile=over_envelope_profile())
    result = semantic_validation(bundle, valid_semantic_inputs())
    assert result.valid is False
    assert ValidationReason.EXCEEDS_ENVELOPE in result.reason_set


def test_empty_profile_omit_propagates_to_semantic_validation() -> None:
    """(step 6 propagation, "omit" limb) An empty profile omitting a mandatory dim => invalid.

    The envelope->profile coverage limb (SPG-INV-001 "omit") flows through
    profile_within_envelope into semantic_validation step 6 => EXCEEDS_ENVELOPE, so a
    vacuously empty profile can never validate a bundle.
    """
    bundle = issue_bundle(profile=issue_profile(governed_dimensions=()))
    result = semantic_validation(bundle, valid_semantic_inputs())
    assert result.valid is False
    assert ValidationReason.EXCEEDS_ENVELOPE in result.reason_set
    assert "qty" in result.rejected_dimensions


def test_unit_mismatch_reason() -> None:
    """(step 3 units) A same-dimension unit mismatch => UNIT_OR_MULTIPLIER_MISMATCH."""
    env = issue_envelope(
        governed_dimensions=(envelope_dimension(dimension="qty", unit="shares"),)
    )
    prof = issue_profile(
        governed_dimensions=(profile_dimension(dimension="qty", unit="lots"),)
    )
    bundle = issue_bundle(envelope=env, profile=prof)
    result = semantic_validation(bundle, valid_semantic_inputs())
    assert result.valid is False
    assert ValidationReason.UNIT_OR_MULTIPLIER_MISMATCH in result.reason_set
    assert "qty" in result.rejected_dimensions


def test_cross_field_contradiction_reason() -> None:
    """(step 5) cross_field_consistent not True => CROSS_FIELD_CONSTRAINT_VIOLATION."""
    result = semantic_validation(
        issue_bundle(), valid_semantic_inputs(cross_field_consistent=False)
    )
    assert result.valid is False
    assert ValidationReason.CROSS_FIELD_CONSTRAINT_VIOLATION in result.reason_set


def test_cross_field_none_fails_closed() -> None:
    """(fail-closed) A None cross-field observation also fails closed."""
    result = semantic_validation(
        issue_bundle(), valid_semantic_inputs(cross_field_consistent=None)
    )
    assert result.valid is False
    assert ValidationReason.CROSS_FIELD_CONSTRAINT_VIOLATION in result.reason_set


def test_unorderable_direction_reason() -> None:
    """(step 11 §11 line 317) A non-RESTRICTIVE direction => UNORDERABLE_DIRECTION."""
    for direction in (
        ChangeDirection.PERMISSIVE,
        ChangeDirection.AUTHORITY_INCREASING,
        None,
    ):
        result = semantic_validation(
            issue_bundle(), valid_semantic_inputs(change_direction=direction)
        )
        assert result.valid is False
        assert ValidationReason.UNORDERABLE_DIRECTION in result.reason_set


def test_nan_limit_rejected_at_construction() -> None:
    """(step 3 numeric, structural §5.2 deviation) A non-finite (NaN) limit is unconstructable.

    pydantic v2's default ``Decimal`` inf/nan rejection (``allow_inf_nan=False``) rejects NaN
    / infinity at construction (the core ``CanonicalDecimal`` only scale-normalizes) — strictly
    stronger than a post-hoc ``OVERFLOW_UNDERFLOW_NAN_INFINITY`` reason: a non-finite envelope
    maximum can never enter an artifact in the first place.
    """
    import pytest
    from pydantic import ValidationError

    for bad in (Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(ValidationError):
            envelope_dimension(dimension="qty", envelope_max=bad)
    # The reason remains in the vocabulary for any future non-model-sourced input.
    assert ValidationReason.OVERFLOW_UNDERFLOW_NAN_INFINITY in set(ValidationReason)


def test_duplicate_dimension_reason() -> None:
    """(step 12) A duplicate governed dimension => UNKNOWN_OR_DUPLICATE_FIELD."""
    prof = issue_profile(
        governed_dimensions=(
            profile_dimension(dimension="qty", profile_value=Decimal("5")),
            profile_dimension(dimension="qty", profile_value=Decimal("6")),
        )
    )
    bundle = issue_bundle(profile=prof)
    result = semantic_validation(bundle, valid_semantic_inputs())
    assert result.valid is False
    assert ValidationReason.UNKNOWN_OR_DUPLICATE_FIELD in result.reason_set


def test_canonical_irreproducible_reason() -> None:
    """(step 2) canonical_reproducible not True => CANONICAL_DIGEST_IRREPRODUCIBLE."""
    result = semantic_validation(
        issue_bundle(), valid_semantic_inputs(canonical_reproducible=False)
    )
    assert result.valid is False
    assert ValidationReason.CANONICAL_DIGEST_IRREPRODUCIBLE in result.reason_set


def test_floating_member_reason() -> None:
    """(step 9) bundle_member_digests_match not True => FLOATING_REFERENCE."""
    result = semantic_validation(
        issue_bundle(), valid_semantic_inputs(bundle_member_digests_match=False)
    )
    assert result.valid is False
    assert ValidationReason.FLOATING_REFERENCE in result.reason_set


def test_schema_downgrade_reason() -> None:
    """(SPG-AC-003) An injected precondition failure => SCHEMA_INCOMPLETE_OR_DOWNGRADE."""
    result = semantic_validation(
        issue_bundle(), valid_semantic_inputs(software_deployment_ok=False)
    )
    assert result.valid is False
    assert ValidationReason.SCHEMA_INCOMPLETE_OR_DOWNGRADE in result.reason_set


def test_default_semantic_inputs_fail_every_fold_step() -> None:
    """(fail-closed) A bare SemanticValidationInputs (all None) invalidates a clean bundle."""
    from tos.spg import SemanticValidationInputs

    result = semantic_validation(issue_bundle(), SemanticValidationInputs())
    assert result.valid is False
    assert result.reason_set  # non-empty


# ---------------------------------------------------------------------------
# units_compatible seam bool
# ---------------------------------------------------------------------------


def test_units_compatible_seam_bool() -> None:
    """units_compatible is True for a clean bundle, False on a unit mismatch / absent bundle."""
    assert units_compatible(issue_bundle(), valid_semantic_inputs()) is True
    env = issue_envelope(
        governed_dimensions=(envelope_dimension(dimension="qty", unit="shares"),)
    )
    prof = issue_profile(
        governed_dimensions=(profile_dimension(dimension="qty", unit="lots"),)
    )
    assert (
        units_compatible(
            issue_bundle(envelope=env, profile=prof), valid_semantic_inputs()
        )
        is False
    )
    assert units_compatible(None, valid_semantic_inputs()) is False
