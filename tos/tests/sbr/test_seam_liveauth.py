"""MANDATED test-only seam cross-check: sbr -> liveauth (design #17 §3.4(d) / §7).

SBR **produces** two bools the liveauth continuous-validity / SAFE-053 inputs consume by
injection (liveauth does not import ``tos.sbr`` — the liveauth ``protective_coverage_valid``
injected-bool precedent, §0.4c):

* ``recovery_current`` -> ``ContinuousValidityInputs.recovery_current``
  (``liveauth/state.py:139``);
* ``recovery_readiness_enlarged`` ->
  ``InPlaceExpansionInputs.recovery_readiness_enlarged`` (``liveauth/state.py:208`` — the
  field owner is ``InPlaceExpansionInputs``, verified against the source, not a phantom).

This file imports the real liveauth slots as a **test** to lock (a) the slot signatures are
``bool | None`` (parity with what SBR produces) and (b) the polarity — a newer generation /
missing fresh proof drops the produced bool, and the slot carries exactly that.

A test-only cross-import is **not** a runtime package edge (design #17 §3.4(d)/§7.1).
"""

from __future__ import annotations

from tos.liveauth import ContinuousValidityInputs, InPlaceExpansionInputs
from tos.sbr import ReadinessVerdict, recovery_current, recovery_readiness_enlarged

from ._sbr_strategies import issue_decision


def test_recovery_current_slot_signature_parity() -> None:
    """(seam) The liveauth recovery_current slot exists and accepts the SBR-produced bool | None."""
    assert "recovery_current" in ContinuousValidityInputs.model_fields
    inputs = ContinuousValidityInputs(recovery_current=None)
    assert inputs.recovery_current is None


def test_sbr_recovery_current_fills_the_continuous_validity_slot() -> None:
    """(seam positive) A positive, current, within-age readiness produces True into the slot."""
    decision = issue_decision(verdict=ReadinessVerdict.READY)
    produced = recovery_current(
        decision, newer_generation_observed=False, within_max_age=True
    )
    assert produced is True
    inputs = ContinuousValidityInputs(recovery_current=produced)
    assert inputs.recovery_current is True


def test_newer_generation_drops_recovery_current() -> None:
    """(seam polarity, §18 line 463) A newer generation observed => recovery_current False."""
    decision = issue_decision(verdict=ReadinessVerdict.READY)
    produced = recovery_current(
        decision, newer_generation_observed=True, within_max_age=True
    )
    assert produced is False
    assert ContinuousValidityInputs(recovery_current=produced).recovery_current is False


def test_beyond_max_age_drops_recovery_current() -> None:
    """(seam polarity, §18 line 463) Beyond max age => recovery_current not current."""
    decision = issue_decision(verdict=ReadinessVerdict.READY)
    for within in (False, None):
        produced = recovery_current(
            decision, newer_generation_observed=False, within_max_age=within
        )
        assert produced is False


def test_recovery_readiness_enlarged_slot_signature_parity() -> None:
    """(seam) The liveauth in-place-expansion recovery_readiness_enlarged slot accepts the SBR bool | None."""
    assert "recovery_readiness_enlarged" in InPlaceExpansionInputs.model_fields
    attestation = InPlaceExpansionInputs(recovery_readiness_enlarged=None)
    assert attestation.recovery_readiness_enlarged is None


def test_sbr_recovery_readiness_enlarged_requires_fresh_proof() -> None:
    """(seam polarity, SBR-INV-011) A freshly-proven enlarged scope produces True; an unproven one False."""
    decision = issue_decision(verdict=ReadinessVerdict.READY)
    proven = recovery_readiness_enlarged(decision, enlarged_scope_freshly_proven=True)
    assert proven is True
    assert (
        InPlaceExpansionInputs(
            recovery_readiness_enlarged=proven
        ).recovery_readiness_enlarged
        is True
    )
    for unproven in (False, None):
        assert (
            recovery_readiness_enlarged(
                decision, enlarged_scope_freshly_proven=unproven
            )
            is False
        )


def test_not_ready_decision_produces_neither_recovery_bool() -> None:
    """(seam, causal isolation) A NOT_READY readiness produces False into both slots."""
    not_ready = issue_decision(verdict=ReadinessVerdict.NOT_READY)
    assert (
        recovery_current(
            not_ready, newer_generation_observed=False, within_max_age=True
        )
        is False
    )
    assert (
        recovery_readiness_enlarged(not_ready, enlarged_scope_freshly_proven=True)
        is False
    )
