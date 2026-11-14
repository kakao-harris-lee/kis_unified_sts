"""Predicate-only §6.1 — credential-route authority disjointness (design #22; EGRESS-EV-001)."""

from __future__ import annotations

from tos.egress import credential_route_authority_disjoint

from ._egress_strategies import clean_inventory_entry


def test_disjoint_when_outside_principals_lack_both() -> None:
    """(§6.1) Disjoint when no outside principal holds both usable credential and route."""
    inventory = [
        clean_inventory_entry(
            principal="inside-1",
            usable_credential=True,
            broker_route=True,
            inside_boundary=True,
        ),
        clean_inventory_entry(
            principal="outside-cred-only",
            usable_credential=True,
            broker_route=False,
            inside_boundary=False,
        ),
    ]
    assert credential_route_authority_disjoint(inventory) is True


def test_outside_principal_with_both_is_not_disjoint() -> None:
    """(§6.1 / EGRESS-INV-002) An outside principal with credential AND route is a bypass ⇒ False."""
    inventory = [
        clean_inventory_entry(
            principal="outside-both",
            usable_credential=True,
            broker_route=True,
            inside_boundary=False,
        ),
    ]
    assert credential_route_authority_disjoint(inventory) is False


def test_unknown_flags_treated_as_potentially_usable() -> None:
    """(§6.1 / §4.6) A None credential / route flag is UNKNOWN ⇒ conservatively potentially-usable."""
    inventory = [
        clean_inventory_entry(
            principal="outside-unknown",
            usable_credential=None,
            broker_route=None,
            inside_boundary=False,
        ),
    ]
    assert credential_route_authority_disjoint(inventory) is False


def test_unknown_boundary_treated_as_outside() -> None:
    """(§6.1 / §4.6) A None inside_boundary is UNKNOWN ⇒ treated as outside (conservative)."""
    inventory = [
        clean_inventory_entry(
            principal="unknown-boundary",
            usable_credential=True,
            broker_route=True,
            inside_boundary=None,
        ),
    ]
    assert credential_route_authority_disjoint(inventory) is False


def test_outside_with_credential_but_explicit_no_route_is_disjoint() -> None:
    """(§6.1 both-ways) An outside principal with credential but an explicit False route is disjoint."""
    inventory = [
        clean_inventory_entry(
            principal="outside-no-route",
            usable_credential=True,
            broker_route=False,
            inside_boundary=False,
        ),
    ]
    assert credential_route_authority_disjoint(inventory) is True


def test_empty_inventory_is_denial() -> None:
    """(§6.1 / §4.7) An ∅ inventory ⇒ False (disjointness unproven — completeness is unproven)."""
    assert credential_route_authority_disjoint([]) is False
