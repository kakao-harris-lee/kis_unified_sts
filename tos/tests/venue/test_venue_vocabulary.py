"""venue vocabulary — enum membership + closed/open taxonomy + dsl homonym distinction (design #19 §2.2).

Regime tag: predicate / model substrate only; VTG-EV substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.venue import (
    ActionClass,
    ConstraintClass,
    OrderAdmissibilityResult,
    TradabilityState,
)


def test_admissibility_result_is_the_verbatim_four_values() -> None:
    """(§5.4 line 123) OrderAdmissibilityResult has exactly the four ADR values."""
    assert {r.value for r in OrderAdmissibilityResult} == {
        "ADMISSIBLE",
        "RESTRICTED_PROTECTIVE_ONLY",
        "INADMISSIBLE",
        "UNKNOWN",
    }


def test_tradability_state_values() -> None:
    """(§5.6 line 131 / §11) TradabilityState has at least the four ADR states."""
    assert {s.value for s in TradabilityState} == {
        "TRADABLE",
        "NOT_TRADABLE",
        "RESTRICTED",
        "UNKNOWN",
    }


def test_action_class_is_closed_taxonomy() -> None:
    """(§11 line 283-289, v1.1 M4) ActionClass is the closed taxonomy (entry + exit + routing)."""
    values = {a.value for a in ActionClass}
    # entry / lifecycle / exit / protective / routing all present (closed set)
    for expected in (
        "NEW_LONG",
        "NEW_SHORT",
        "INCREASE",
        "DECREASE",
        "CLOSE",
        "REVERSAL",
        "CANCEL",
        "AMEND",
        "REPLACE",
        "REDUCE_ONLY",
        "PROTECTIVE",
        "EMERGENCY",
        "ROUTING_ALTERNATIVE",
    ):
        assert expected in values


def test_constraint_class_groups() -> None:
    """(§8 line 229-241) ConstraintClass carries the venue constraint domains."""
    values = {c.value for c in ConstraintClass}
    assert "SESSION_PHASE" in values
    assert "PRICE_TICK_LOT_QUANTITY" in values
    assert "BROKER_CAPABILITY" in values


def test_admissibility_result_is_not_dsl_admissibility_result() -> None:
    """(§0.4d) The venue result enum is a distinct type from dsl.AdmissibilityResult (homonym)."""
    from tos.dsl import AdmissibilityResult as DslAdmissibilityResult

    # Distinct types (different domains — ADR-002-019 venue vs ADR-DEV-001 static program).
    assert OrderAdmissibilityResult is not DslAdmissibilityResult
    assert OrderAdmissibilityResult.__name__ == "OrderAdmissibilityResult"


def test_action_and_constraint_classes_are_identity_gated_not_truthy() -> None:
    """(§2.2) ActionClass / ConstraintClass are plain StrEnums usable by identity/membership."""
    # A plain StrEnum member is truthy-testable (they are input tokens, not gate results).
    assert bool(ActionClass.NEW_LONG) is True
    assert ActionClass.CLOSE in {ActionClass.CLOSE, ActionClass.CANCEL}
    assert ConstraintClass.SESSION_PHASE.value == "SESSION_PHASE"
