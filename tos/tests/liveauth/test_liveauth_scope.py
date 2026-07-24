"""Subset scope coverage — vacuous-True closure both ways (§5.3; REARM-AC-009).

``scope_covers`` is True only when the requested scope is a non-empty subset of a
non-empty authorization scope in every dimension. An empty authorization scope covers
nothing, an empty request is not a valid action, a narrow authorization does not cover a
wider request, and a None / unrepresentable-wildcard dimension fails closed. The non-empty
requirements close the ``∅ ⊆ ∅`` vacuous-True fail-open. [REARM-EV-009]
"""

from __future__ import annotations

import pytest
from tos.liveauth import LiveAuthorizationScope, scope_covers
from tos.liveauth.predicates import _SCOPE_DIMENSIONS

from ._liveauth_strategies import full_scope, wide_scope


def test_subset_is_covered() -> None:
    """(guard fires True) A narrow request is covered by a wider authorization."""
    assert scope_covers(wide_scope(), full_scope()) is True


def test_equal_scope_is_covered() -> None:
    """An exactly-equal request is covered (⊆ is reflexive on non-empty sets)."""
    assert scope_covers(full_scope(), full_scope()) is True


def test_narrow_authorization_does_not_cover_wider_request() -> None:
    """(canary) A narrow authorization does not cover a wider request (⊄ => False)."""
    assert scope_covers(full_scope(), wide_scope()) is False


def test_none_scope_either_side_is_false() -> None:
    """(canary) A None scope on either side fails closed."""
    assert scope_covers(None, full_scope()) is False
    assert scope_covers(full_scope(), None) is False


@pytest.mark.parametrize("dim", _SCOPE_DIMENSIONS)
def test_empty_authorization_dimension_covers_nothing(dim: str) -> None:
    """(canary, vacuous-True closure) An empty authorization dimension covers nothing."""
    auth = full_scope(**{dim: frozenset()})
    assert scope_covers(auth, full_scope()) is False


@pytest.mark.parametrize("dim", _SCOPE_DIMENSIONS)
def test_empty_requested_dimension_is_not_valid(dim: str) -> None:
    """(canary, vacuous-True closure) An empty requested dimension is not a valid action."""
    requested = full_scope(**{dim: frozenset()})
    assert scope_covers(wide_scope(), requested) is False


@pytest.mark.parametrize("dim", _SCOPE_DIMENSIONS)
def test_none_dimension_either_side_is_false(dim: str) -> None:
    """(canary, wildcard/None) A None (unrepresentable-wildcard) dimension fails closed."""
    assert scope_covers(full_scope(**{dim: None}), full_scope()) is False
    assert scope_covers(wide_scope(), full_scope(**{dim: None})) is False


def test_both_empty_scopes_is_false() -> None:
    """(canary, the core vacuous-True case) ∅ authorization vs ∅ request is False."""
    empty = LiveAuthorizationScope(
        accounts=frozenset(),
        strategies=frozenset(),
        instrument_classes=frozenset(),
        venues=frozenset(),
        sessions=frozenset(),
        order_types=frozenset(),
        action_classes=frozenset(),
    )
    assert scope_covers(empty, empty) is False


def test_default_scope_is_not_covered() -> None:
    """A default (all-None) scope covers nothing and is not a valid request."""
    default = LiveAuthorizationScope()
    assert scope_covers(default, full_scope()) is False
    assert scope_covers(wide_scope(), default) is False


@pytest.mark.parametrize("dim", _SCOPE_DIMENSIONS)
def test_out_of_authorization_element_in_one_dimension_fails(dim: str) -> None:
    """(canary) A requested element outside the authorization in any one dimension fails."""
    requested = full_scope(**{dim: frozenset({"NOT-IN-AUTH"})})
    assert scope_covers(full_scope(), requested) is False


def test_seven_dimensions_present() -> None:
    """The coverage predicate ranges over exactly the seven §2.5 dimensions."""
    assert len(_SCOPE_DIMENSIONS) == 7
