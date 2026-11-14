"""MANDATED test-only seam cross-check: brokercap fqp_adequate <-> recon token (design #10 §3.4)."""

from __future__ import annotations

from tos.brokercap import ProhibitedProof, fqp_adequate
from tos.recon import (
    CAPACITY_RELEASING_FIELDS,
    FieldConfidence,
    FieldConfidenceClass,
    FreshnessMarker,
    ReleaseProofInputs,
    SafetyRelevantField,
    field_specific_release_proof_ok,
)

from ._brokercap_strategies import complete_fqp_evidence, fqp_rule

_CAP = SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY


def _fresh_marker() -> FreshnessMarker:
    return FreshnessMarker(
        fresh_within_horizon=True,
        time_confidence_held=True,
        time_generation=1,
        anchored_generation=1,
    )


def _corroborated_confidence() -> FieldConfidence:
    return FieldConfidence(
        field=_CAP,
        confidence_class=FieldConfidenceClass.CORROBORATED,
        freshness_marker=_fresh_marker(),
    )


def test_cap_field_is_capacity_releasing() -> None:
    """Precondition: the cumulative-filled-quantity field is a capacity-releasing field."""
    assert _CAP in CAPACITY_RELEASING_FIELDS


def test_fqp_adequate_true_enables_recon_release_proof() -> None:
    """brokercap fqp_adequate True => recon final_quantity_proof_token True => release proof holds."""
    token = fqp_adequate(fqp_rule(), complete_fqp_evidence())
    assert token is True
    inputs = ReleaseProofInputs(
        final_quantity_proof_token=token, freshness=_fresh_marker()
    )
    assert (
        field_specific_release_proof_ok(_CAP, _corroborated_confidence(), inputs)
        is True
    )


def test_fqp_adequate_false_fails_recon_release_proof() -> None:
    """brokercap fqp_adequate False (cancel-ACK sole basis) => token False => release proof fails closed."""
    token = fqp_adequate(
        fqp_rule(),
        complete_fqp_evidence(
            sole_prohibited_basis=ProhibitedProof.CANCEL_ACKNOWLEDGEMENT
        ),
    )
    assert token is False
    inputs = ReleaseProofInputs(
        final_quantity_proof_token=token, freshness=_fresh_marker()
    )
    assert (
        field_specific_release_proof_ok(_CAP, _corroborated_confidence(), inputs)
        is False
    )


def test_none_token_fails_closed_matches_brokercap_false() -> None:
    """recon's None token fails closed — brokercap's definite False is at least as safe."""
    inputs = ReleaseProofInputs(
        final_quantity_proof_token=None, freshness=_fresh_marker()
    )
    assert (
        field_specific_release_proof_ok(_CAP, _corroborated_confidence(), inputs)
        is False
    )


def test_fqp_adequate_is_plain_bool() -> None:
    """brokercap emits a plain ``bool`` (type-matches recon's ``bool | None`` token field)."""
    assert isinstance(fqp_adequate(fqp_rule(), complete_fqp_evidence()), bool)
