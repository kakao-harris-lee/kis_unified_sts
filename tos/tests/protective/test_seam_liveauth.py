"""MANDATED test-only seam cross-check: protective <-> liveauth (design #11 §3.4).

protective does NOT import ``tos.liveauth`` at runtime (the import-closure test asserts its
absence); this file imports **both** as a **test** to lock the produced-value seam. liveauth
already declared the injected coordinates protective fills:

* ``protective_coverage_valid`` — one of the ten injected continuous-validity conditions
  (``liveauth/state.py:138``; ``_INJECTED_CONTINUOUS_CONDITIONS`` at ``liveauth/predicates.py:96``).
  protective's :func:`~tos.protective.predicates.reserve_sufficiency` produces the ``bool`` it
  consumes; a ``False`` fails ``continuous_validity`` closed.
* ``protective_coverage_added`` — one of the ten §14.1 proportional-expansion flags
  (``liveauth/state.py:204``; ``_PROPORTIONAL_EXPANSION_FLAGS`` at ``liveauth/predicates.py:150``),
  filled by :func:`~tos.protective.predicates.protective_coverage_added`.
* ``protective_leases_reconciled`` — the re-arm variant environmental prerequisite
  (``liveauth/predicates.py:135``) + the authority ``RearmChecklist`` field (``authority/
  state.py:129``), filled by :func:`~tos.protective.predicates.protective_leases_reconciled`.

Both directions are asserted with causal isolation (the #10 MINOR-2 lesson): a fully-valid
authorization + all other inputs are held fixed and **only** the protective-produced flag is
flipped — so the ``False`` result is attributable to the injected condition, not to an absent
authorization. This test is NOT a runtime package edge (design #11 §3.4/§7.1).
"""

from __future__ import annotations

from tos.authority import RearmChecklist
from tos.liveauth import (
    ContinuousValidityInputs,
    InPlaceExpansionInputs,
    continuous_validity,
    in_place_expansion_admissible,
)
from tos.liveauth.predicates import (
    _INJECTED_CONTINUOUS_CONDITIONS,
    _PROPORTIONAL_EXPANSION_FLAGS,
    _VARIANT_ENVIRONMENTAL_PREREQUISITES,
)
from tos.protective import (
    protective_coverage_added,
    protective_leases_reconciled,
    reserve_sufficiency,
)

from ..liveauth._liveauth_strategies import (
    issue_authorization,
    valid_continuous_validity_inputs,
    valid_expansion_inputs,
)
from ._protective_strategies import (
    approved_minimum,
    issue_profile,
    sufficient_forecast,
)

# ---------------------------------------------------------------------------
# signature integrity
# ---------------------------------------------------------------------------


def test_liveauth_declares_the_three_injected_protective_coordinates() -> None:
    """(§3.4) liveauth declares coverage_valid / coverage_added / leases_reconciled slots."""
    assert "protective_coverage_valid" in _INJECTED_CONTINUOUS_CONDITIONS
    assert "protective_coverage_valid" in ContinuousValidityInputs.model_fields
    assert "protective_coverage_added" in _PROPORTIONAL_EXPANSION_FLAGS
    assert "protective_coverage_added" in InPlaceExpansionInputs.model_fields
    assert "protective_leases_reconciled" in _VARIANT_ENVIRONMENTAL_PREREQUISITES
    assert "protective_leases_reconciled" in RearmChecklist.model_fields


# ---------------------------------------------------------------------------
# reserve_sufficiency (protective_coverage_valid) -> continuous_validity (causal isolation)
# ---------------------------------------------------------------------------


def test_reserve_sufficiency_causally_flips_continuous_validity() -> None:
    """(MINOR-2 causal isolation) Flipping ONLY protective_coverage_valid flips continuous_validity.

    A fully-valid authorization + all other inputs are held fixed (reused from liveauth's own
    ``valid_continuous_validity_inputs``); only the protective-produced coverage flag differs.
    """
    auth = issue_authorization()  # a fully-valid, ISSUED Live Authorization
    coverage_true = reserve_sufficiency(
        issue_profile(),
        forecast_capacity=sufficient_forecast(),
        approved_minimum=approved_minimum(),
    )
    coverage_false = reserve_sufficiency(
        issue_profile(), forecast_capacity={}, approved_minimum={}
    )
    assert coverage_true is True and coverage_false is False

    valid_true = valid_continuous_validity_inputs(
        protective_coverage_valid=coverage_true
    )
    valid_false = valid_continuous_validity_inputs(
        protective_coverage_valid=coverage_false
    )
    # Baseline: the True wiring is genuinely continuously valid (the guard fires True).
    assert continuous_validity(auth, valid_true) is True
    # Flipping ONLY the protective-produced condition to False flips the result to invalid.
    assert continuous_validity(auth, valid_false) is False


def test_reserve_sufficiency_false_fails_continuous_validity_closed() -> None:
    """protective coverage insufficient => continuous_validity False (fail-closed side)."""
    coverage = reserve_sufficiency(
        issue_profile(), forecast_capacity={}, approved_minimum={}
    )
    assert coverage is False
    inputs = ContinuousValidityInputs(protective_coverage_valid=coverage)
    assert continuous_validity(None, inputs) is False


# ---------------------------------------------------------------------------
# protective_coverage_added -> in_place_expansion_admissible (causal isolation)
# ---------------------------------------------------------------------------


def test_coverage_added_causally_flips_expansion() -> None:
    """(MINOR-2 causal isolation) Flipping ONLY protective_coverage_added flips the §14.1 expansion."""
    existing = issue_authorization(authorization_id="existing-1")
    added_true = protective_coverage_added(
        issue_profile(),
        envelope_not_expanded=True,
        forecast_capacity=sufficient_forecast(),
        approved_minimum=approved_minimum(),
    )
    added_false = protective_coverage_added(
        issue_profile(),
        envelope_not_expanded=False,
        forecast_capacity=sufficient_forecast(),
        approved_minimum=approved_minimum(),
    )
    assert added_true is True and added_false is False

    valid_true = valid_expansion_inputs(protective_coverage_added=added_true)
    valid_false = valid_expansion_inputs(protective_coverage_added=added_false)
    assert in_place_expansion_admissible(valid_true, existing) is True
    assert in_place_expansion_admissible(valid_false, existing) is False


# ---------------------------------------------------------------------------
# protective_leases_reconciled -> authority RearmChecklist field (type + polarity)
# ---------------------------------------------------------------------------


def test_leases_reconciled_is_plain_bool_accepted_by_rearm_checklist() -> None:
    """protective_leases_reconciled emits a plain bool the authority RearmChecklist field accepts."""
    reconciled = protective_leases_reconciled(
        all_protective_leases_accounted=True,
        reconciliation_evidence_current=True,
        no_unresolved_protective_lease_conflicts=True,
    )
    assert reconciled is True
    checklist = RearmChecklist(protective_leases_reconciled=reconciled)
    assert checklist.protective_leases_reconciled is True

    # And a fail-closed False is likewise accepted (a None input yields False, never a pass).
    not_reconciled = protective_leases_reconciled(
        all_protective_leases_accounted=None,
        reconciliation_evidence_current=True,
        no_unresolved_protective_lease_conflicts=True,
    )
    assert not_reconciled is False
    assert (
        RearmChecklist(
            protective_leases_reconciled=not_reconciled
        ).protective_leases_reconciled
        is False
    )


def test_coverage_valid_is_plain_bool() -> None:
    """reserve_sufficiency emits a plain ``bool`` (type-matches liveauth's ``bool | None`` slot)."""
    coverage = reserve_sufficiency(
        issue_profile(),
        forecast_capacity=sufficient_forecast(),
        approved_minimum=approved_minimum(),
    )
    assert isinstance(coverage, bool)
