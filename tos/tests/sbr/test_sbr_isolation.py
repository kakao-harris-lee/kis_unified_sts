"""restricted_isolation_proven — 8-condition positive proof both-ways (design #17 §5.5; SBR-EV-007).

Regime tag: predicate / model substrate only; SBR-EV-007 NOT_IMPLEMENTED (`/3` residue);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.sbr import IsolationFacts, RecoveryScope, restricted_isolation_proven

from ._sbr_strategies import clean_isolation_facts, clean_scope

_EIGHT_CONDITIONS = (
    "distinct_capacity_domain",
    "broker_session_isolated",
    "margin_collateral_safe",
    "no_protective_boundary_crossing",
    "config_authority_time_compatible",
    "external_non_trade_unmappable",
    "final_egress_scope_enforceable",
    "hard_safety_envelope_satisfied",
)


def test_all_eight_proven_is_ready_restricted_positive_side() -> None:
    """(§17 line 438-445 positive) All eight conditions positively proven => isolation proven."""
    assert restricted_isolation_proven(clean_scope(), clean_isolation_facts()) is True


def test_any_single_unproven_condition_drops_to_broader_not_ready() -> None:
    """(§17 line 447 / SBR-INV-008) A single None / False condition drops to a broader NOT_READY."""
    facts = clean_isolation_facts()
    for condition in _EIGHT_CONDITIONS:
        for value in (None, False):
            weakened = facts.model_copy(update={condition: value})
            assert restricted_isolation_proven(clean_scope(), weakened) is False


def test_empty_isolation_facts_is_fail_closed() -> None:
    """(∅) A default (all-None) IsolationFacts proves no condition => False."""
    assert restricted_isolation_proven(clean_scope(), IsolationFacts()) is False


def test_none_facts_or_scope_fail_closed() -> None:
    """(∅) A None scope / facts proves nothing."""
    assert restricted_isolation_proven(None, clean_isolation_facts()) is False
    assert restricted_isolation_proven(clean_scope(), None) is False


def test_unidentified_scope_is_fail_closed() -> None:
    """(§5.5) An unidentified candidate scope (None / TBD id) fails closed."""
    assert (
        restricted_isolation_proven(
            RecoveryScope(scope_id=None), clean_isolation_facts()
        )
        is False
    )
    assert (
        restricted_isolation_proven(
            RecoveryScope(scope_id="TBD"), clean_isolation_facts()
        )
        is False
    )
