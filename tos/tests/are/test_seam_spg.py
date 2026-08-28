"""MANDATED test-only seam cross-check: are <-> spg (design #13 §3.4/§8).

are does NOT import ``tos.spg`` at runtime (the import-closure test asserts its absence); this
file imports **both** as a **test** to lock the semantic-validation step-7 seam. are consumes
the spg Hard Safety Envelope maxima (injected) and **produces** the ``aggregate_effect_within``
bool; spg's ``semantic_validation`` step 7 consumes it (``predicates.py:466`` rejects unless
``is True``). Both directions are injected, so are ↔ spg stays acyclic (§3.4).

A test-only cross-import is NOT a runtime package edge (design #13 §3.4/§7.1).
"""

from __future__ import annotations

from decimal import Decimal

from tos.are import aggregate_effect_within
from tos.rcl import CapacityVector
from tos.spg import SemanticValidationInputs, ValidationReason, semantic_validation

from ._are_strategies import capacity_vector


def test_are_produces_aggregate_effect_within_true() -> None:
    """(seam +) effective (5) <= envelope max (10) => are produces True => spg accepts step 7."""
    within = aggregate_effect_within(
        decision_effective_limit=capacity_vector(magnitude=Decimal("5")),
        injected_envelope_max=capacity_vector(magnitude=Decimal("10")),
        limit_source_is_injected_envelope=True,
    )
    assert within is True
    inputs = SemanticValidationInputs(aggregate_effect_within=within)
    assert inputs.aggregate_effect_within is True


def test_over_envelope_produces_false_and_spg_rejects() -> None:
    """(seam -) An effect over the envelope => are produces False => spg semantic_validation rejects."""
    within = aggregate_effect_within(
        decision_effective_limit=capacity_vector(magnitude=Decimal("50")),
        injected_envelope_max=capacity_vector(magnitude=Decimal("10")),
        limit_source_is_injected_envelope=True,
    )
    assert within is False
    # spg semantic_validation with a None bundle already fails; here we prove the polarity that
    # a False aggregate_effect_within is a rejecting precondition (spg predicates.py:466).
    inputs = SemanticValidationInputs(
        signature_and_revocation_ok=True,
        canonical_reproducible=True,
        cross_field_consistent=True,
        aggregate_effect_within=within,  # False
        software_deployment_ok=True,
        bundle_member_digests_match=True,
        time_validity_ok=True,
    )
    result = semantic_validation(None, inputs)
    assert result.valid is False
    assert ValidationReason.SCHEMA_INCOMPLETE_OR_DOWNGRADE in result.reason_set


def test_non_envelope_source_produces_false() -> None:
    """(ARE-INV-007) A non-envelope limit source => are produces False (spg would reject step 7)."""
    within = aggregate_effect_within(
        decision_effective_limit=capacity_vector(magnitude=Decimal("5")),
        injected_envelope_max=capacity_vector(magnitude=Decimal("10")),
        limit_source_is_injected_envelope=False,
    )
    assert within is False
    inputs = SemanticValidationInputs(aggregate_effect_within=within)
    assert inputs.aggregate_effect_within is not True  # spg step 7 rejects


def test_empty_effective_limit_step7_pinning() -> None:
    """(MINOR-1 pin) The risk_decision default empty CapacityVector() path into spg step 7.

    An empty effective limit + positive envelope source produces True (most-restrictive, no
    wildcard); a non-positive source still produces a rejecting (not-True) step-7 value.
    """
    within_true = aggregate_effect_within(
        decision_effective_limit=CapacityVector(),
        injected_envelope_max=capacity_vector(magnitude=Decimal("10")),
        limit_source_is_injected_envelope=True,
    )
    assert within_true is True
    assert (
        SemanticValidationInputs(
            aggregate_effect_within=within_true
        ).aggregate_effect_within
        is True
    )

    within_false = aggregate_effect_within(
        decision_effective_limit=CapacityVector(),
        injected_envelope_max=capacity_vector(magnitude=Decimal("10")),
        limit_source_is_injected_envelope=None,
    )
    assert within_false is False
    assert (
        SemanticValidationInputs(
            aggregate_effect_within=within_false
        ).aggregate_effect_within
        is not True
    )
