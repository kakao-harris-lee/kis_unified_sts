"""Capability drift — restrict-only, widen structurally impossible (design #10 §6.2; BC-EV-016)."""

from __future__ import annotations

from tos.brokercap import (
    AssuranceLevel,
    CapabilityDimension,
    CapabilityStatus,
    ObservedBehavior,
    apply_drift,
    drift_detected,
)

from ._brokercap_strategies import observed_clean, observed_drift, verified_declaration

_IDEMPO = CapabilityDimension.SUBMISSION_IDEMPOTENCY


def _verified_idempotency():
    return verified_declaration(
        dimension=_IDEMPO, level=AssuranceLevel.LEVEL_3_RESTRICTED_PRODUCTION
    )


def test_contradiction_is_drift() -> None:
    """(§6.2 canary a) VERIFIED idempotency + duplicate-order-despite-idempotency => drift."""
    decl = _verified_idempotency()
    observed = observed_drift(dimension=_IDEMPO)
    assert drift_detected(decl, observed) is True


def test_consistent_observation_is_no_drift() -> None:
    """(§6.2 canary b) A consistent observation => no drift (no unnecessary restriction)."""
    decl = _verified_idempotency()
    assert drift_detected(decl, observed_clean()) is False


def test_observation_about_other_dimension_is_no_drift() -> None:
    """(§6.2 coherence) A contradiction about ANOTHER dimension does not drift this one."""
    decl = _verified_idempotency()
    other = ObservedBehavior(
        dimension=CapabilityDimension.CANCELLATION,
        duplicate_order_despite_idempotency=True,
    )
    assert drift_detected(decl, other) is False


def test_apply_drift_moves_to_contradictory_and_lowers_level() -> None:
    """(§20.2) On drift => status CONTRADICTORY, level LEVEL_0_UNKNOWN (restrictive)."""
    decl = _verified_idempotency()
    result = apply_drift(decl, observed_drift(dimension=_IDEMPO))
    assert result.status is CapabilityStatus.CONTRADICTORY
    assert result.assurance_level is AssuranceLevel.LEVEL_0_UNKNOWN


def test_apply_drift_no_drift_leaves_unchanged() -> None:
    """(§6.2) With no drift, the declaration is returned unchanged."""
    decl = _verified_idempotency()
    assert apply_drift(decl, observed_clean()) == decl


def test_apply_drift_never_widens() -> None:
    """(§4.3 structural) apply_drift never raises status/level — a would-be 'better' observation cannot lift it."""
    documented = verified_declaration(dimension=_IDEMPO).model_copy(
        update={
            "status": CapabilityStatus.DOCUMENTED_NOT_VERIFIED,
            "assurance_level": AssuranceLevel.LEVEL_1_DOCUMENTED,
        }
    )
    result = apply_drift(documented, observed_drift(dimension=_IDEMPO))
    assert result.status is CapabilityStatus.CONTRADICTORY
    assert result.status is not CapabilityStatus.VERIFIED
    assert result.assurance_level is AssuranceLevel.LEVEL_0_UNKNOWN
