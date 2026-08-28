"""exact_instrument_route_bound — exact identity / route binding (design #19 §5.2; VTG-EV-003 substrate).

Alias / contract-month / account / env / route substitution is rejected; every scalar must
match exactly; the alias set is compared both-ways (missing under-count + spurious substitution).

Regime tag: predicate / model substrate only; VTG-EV-003 NOT_IMPLEMENTED (`/3` + Security
residue); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.venue import exact_instrument_route_bound

from ._venue_strategies import clean_decision, clean_instrument_route


def test_exact_match_is_bound_positive_side() -> None:
    """(§11 canary b) A candidate matching every scalar + alias set is exactly bound."""
    route = clean_instrument_route()
    decision = clean_decision(route=route)
    assert exact_instrument_route_bound(decision, route) is True


def test_symbol_alias_substitution_is_rejected() -> None:
    """(§11 AC-003 line 613) A substituted canonical instrument id is rejected."""
    decision = clean_decision(route=clean_instrument_route())
    substituted = clean_instrument_route().model_copy(
        update={"canonical_instrument_id": "INST-OTHER"}
    )
    assert exact_instrument_route_bound(decision, substituted) is False


def test_contract_month_substitution_is_rejected() -> None:
    """(§11 AC-003) A front-month substitute (different contract month) is rejected."""
    decision = clean_decision(route=clean_instrument_route())
    substituted = clean_instrument_route().model_copy(
        update={"contract_month": "2026-12"}
    )
    assert exact_instrument_route_bound(decision, substituted) is False


def test_account_or_route_substitution_is_rejected() -> None:
    """(§11 AC-003) A default-account / broker-route substitution is rejected."""
    decision = clean_decision(route=clean_instrument_route())
    for field, value in (
        ("account_mapping", "DEFAULT-ACCT"),
        ("route", "PRIMARY"),
        ("environment", "live"),
        ("broker", "BRK-OTHER"),
    ):
        substituted = clean_instrument_route().model_copy(update={field: value})
        assert exact_instrument_route_bound(decision, substituted) is False


def test_missing_routing_field_is_rejected() -> None:
    """(§11 fail-closed) A None routing field (under-count) is rejected."""
    decision = clean_decision(route=clean_instrument_route())
    missing = clean_instrument_route().model_copy(update={"venue_listing": None})
    assert exact_instrument_route_bound(decision, missing) is False


def test_alias_set_both_ways_missing_and_spurious() -> None:
    """(§4.7 both-ways set) A missing alias (under) and a spurious alias (over) both reject."""
    decision = clean_decision(route=clean_instrument_route())
    # under-count: a missing alias
    missing_alias = clean_instrument_route().model_copy(
        update={"routing_relevant_aliases": frozenset({"ALIAS-A"})}
    )
    assert exact_instrument_route_bound(decision, missing_alias) is False
    # over-count: a spurious alias substitution
    spurious_alias = clean_instrument_route().model_copy(
        update={
            "routing_relevant_aliases": frozenset({"ALIAS-A", "ALIAS-B", "ALIAS-C"})
        }
    )
    assert exact_instrument_route_bound(decision, spurious_alias) is False


def test_none_decision_or_candidate_is_rejected() -> None:
    """(∅) A None decision or candidate proves nothing."""
    route = clean_instrument_route()
    assert exact_instrument_route_bound(None, route) is False
    assert exact_instrument_route_bound(clean_decision(route=route), None) is False
