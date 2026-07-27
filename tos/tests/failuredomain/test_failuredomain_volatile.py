"""§4.3 ``decision_sole_sourced_from_volatile`` — injected volatile set, ∅ both ways (design #27 §6).

ADR-002-009 §8.3 line 212: "Redis or any other cache SHALL NOT be the sole source of current
permission, revocation state, Final Quantity Proof, or capacity release"; line 214: "Cache miss,
expiration, eviction, restart, or stale replica read SHALL fail closed for permissive decisions."
§8.2 line 206: "absence of a deny event is not proof of permission." §10.1 item 5 line 282: "their
absence, deletion, expiry, or recovery never establishes current permission or clears the deny
latch."

The M5 redesign made the volatile set **injected**: design #27 §4.3 removed the v1.0 hardcoded
``{cache, event_infrastructure}``, because which domains are volatile is deployment- and
broker-profile business (CLAUDE.md configuration-driven; design #27 §0.2 "수치 하드코딩 0"). This
file seals that structurally — the parameter has no default, so a caller must supply the profile's
set or explicitly say ``None``.

Regime tag: EV-L1 predicate substrate only; closes no FD-EV; the L1-decidable content is
sibling-owned per design #27 §3.5.
"""

from __future__ import annotations

import inspect
from enum import StrEnum

import pytest
from hypothesis import given
from tos.failuredomain import FailureDomainKind, decision_sole_sourced_from_volatile

from ._failuredomain_strategies import DOMAIN_SET

_CACHE = FailureDomainKind.CACHE
_EVENTS = FailureDomainKind.EVENT_INFRASTRUCTURE
_DATASTORE = FailureDomainKind.DATASTORE


# --- the three-valued verdict ------------------------------------------------


def test_unestablished_volatile_set_is_unknown() -> None:
    """(§4.3 M5) ``volatile_domains is None`` => None (UNKNOWN) — never a guess, never False."""
    assert decision_sole_sourced_from_volatile(frozenset({_DATASTORE}), None) is None
    assert decision_sole_sourced_from_volatile(frozenset(), None) is None
    assert (
        decision_sole_sourced_from_volatile(frozenset({_CACHE, _EVENTS}), None) is None
    )


def test_support_drawn_only_from_volatile_domains_is_true() -> None:
    """(§8.3) Cache-only / cache+event-only support => True => the consumer must fail closed."""
    volatile = frozenset({_CACHE, _EVENTS})
    assert decision_sole_sourced_from_volatile(frozenset({_CACHE}), volatile) is True
    assert (
        decision_sole_sourced_from_volatile(frozenset({_CACHE, _EVENTS}), volatile)
        is True
    )


def test_any_non_volatile_support_is_false() -> None:
    """(both-ways b) A decision with a non-volatile leg is not sole-sourced — legitimate pass."""
    volatile = frozenset({_CACHE, _EVENTS})
    assert (
        decision_sole_sourced_from_volatile(frozenset({_DATASTORE}), volatile) is False
    )
    assert (
        decision_sole_sourced_from_volatile(frozenset({_CACHE, _DATASTORE}), volatile)
        is False
    )


# --- ∅ both ways -------------------------------------------------------------


def test_empty_support_is_the_worst_case() -> None:
    """(∅ a) No support at all has no non-volatile basis => True (deliberate, by the subset law)."""
    assert decision_sole_sourced_from_volatile(frozenset(), frozenset({_CACHE})) is True
    assert decision_sole_sourced_from_volatile(frozenset(), frozenset()) is True


def test_positively_empty_volatile_set_does_not_block() -> None:
    """(∅ b) A profile that declares *nothing* volatile lets real support through => False."""
    assert (
        decision_sole_sourced_from_volatile(frozenset({_CACHE}), frozenset()) is False
    )
    assert (
        decision_sole_sourced_from_volatile(frozenset({_DATASTORE}), frozenset())
        is False
    )


def test_injected_empty_and_unestablished_are_distinguishable() -> None:
    """(∅ both ways, the core distinction) ``frozenset()`` (declared) != ``None`` (unestablished)."""
    support = frozenset({_CACHE})
    assert decision_sole_sourced_from_volatile(support, frozenset()) is False
    assert decision_sole_sourced_from_volatile(support, None) is None


# --- no hardcoded volatile set (M5) -----------------------------------------


def test_volatile_domains_has_no_default() -> None:
    """(M5) The volatile set must be supplied — there is no built-in {cache, event} default."""
    parameters = inspect.signature(decision_sole_sourced_from_volatile).parameters
    assert list(parameters) == ["support_domains", "volatile_domains"]
    for parameter in parameters.values():
        assert parameter.default is inspect.Parameter.empty, (
            f"{parameter.name} must be injected, never defaulted "
            "(design #27 §4.3 M5 — no hardcoded volatile set)"
        )


def test_no_taxonomy_member_is_privileged_as_volatile() -> None:
    """(M5) Every domain behaves identically — nothing is volatile except by injection."""
    for member in FailureDomainKind:
        assert (
            decision_sole_sourced_from_volatile(
                frozenset({member}), frozenset({member})
            )
            is True
        )
        assert (
            decision_sole_sourced_from_volatile(frozenset({member}), frozenset())
            is False
        )


# --- properties --------------------------------------------------------------


@given(support=DOMAIN_SET, volatile=DOMAIN_SET)
def test_property_matches_the_subset_law(
    support: frozenset[FailureDomainKind], volatile: frozenset[FailureDomainKind]
) -> None:
    """(§4.3 property) With an injected set the verdict is exactly ``support ⊆ volatile``."""
    assert decision_sole_sourced_from_volatile(support, volatile) is (
        support <= volatile
    )


@given(support=DOMAIN_SET)
def test_property_none_volatile_is_always_unknown(
    support: frozenset[FailureDomainKind],
) -> None:
    """(§4.3 property) No support shape can turn an unestablished volatile set into a bool."""
    assert decision_sole_sourced_from_volatile(support, None) is None


@given(support=DOMAIN_SET, volatile=DOMAIN_SET)
def test_property_verdict_is_only_true_false_or_none(
    support: frozenset[FailureDomainKind], volatile: frozenset[FailureDomainKind]
) -> None:
    """(polarity) The predicate is strictly three-valued — never a truthy proxy object."""
    verdict = decision_sole_sourced_from_volatile(support, volatile)
    assert verdict is True or verdict is False
    assert decision_sole_sourced_from_volatile(support, None) is None


def test_a_non_set_support_is_rejected_rather_than_coerced() -> None:
    """(no silent coercion) A list is not a set — a sloppy caller fails loudly, not permissively."""
    with pytest.raises(TypeError):
        decision_sole_sourced_from_volatile([_CACHE], frozenset({_CACHE}))  # type: ignore[arg-type]


# --- member type guard (adversarial review MAJOR-2) --------------------------


def test_a_raw_string_member_is_rejected_not_silently_matched() -> None:
    """(MAJOR-2) ``"ACCOUNT"`` hash-compares equal to the member — it must raise, not answer.

    Both operands are ``str``-backed, so ``{"ACCOUNT"} <= {FailureDomainKind.ACCOUNT}`` is
    ``True`` without the guard: a caller passing raw strings would get plausible answers while
    bypassing the closed taxonomy entirely.
    """
    with pytest.raises(TypeError):
        decision_sole_sourced_from_volatile(
            frozenset({"ACCOUNT"}),  # type: ignore[arg-type]
            frozenset({FailureDomainKind.ACCOUNT}),
        )


def test_a_mistyped_string_is_rejected_rather_than_failing_open() -> None:
    """(MAJOR-2) A typo is the dangerous case — it would silently return a fail-open ``False``.

    Without the guard ``{"CACHEE"} <= {CACHE}`` is ``False``: "this decision has non-volatile
    support", the *permissive* answer, produced entirely by a typo.
    """
    with pytest.raises(TypeError):
        decision_sole_sourced_from_volatile(
            frozenset({"CACHEE"}),  # type: ignore[arg-type]
            frozenset({_CACHE}),
        )


def test_a_foreign_axis_member_is_rejected() -> None:
    """(MAJOR-2 / §3.3) A look-alike member of another closed axis never crosses the seam."""

    class ForeignAxis(StrEnum):
        """A different package's axis that happens to share a token with the taxonomy."""

        ACCOUNT = "ACCOUNT"

    with pytest.raises(TypeError):
        decision_sole_sourced_from_volatile(
            frozenset({ForeignAxis.ACCOUNT}),  # type: ignore[arg-type]
            frozenset({FailureDomainKind.ACCOUNT}),
        )


def test_the_volatile_side_is_guarded_too() -> None:
    """(MAJOR-2) The injected volatile set is validated as strictly as the support set."""
    with pytest.raises(TypeError):
        decision_sole_sourced_from_volatile(
            frozenset({_CACHE}),
            frozenset({"CACHE"}),  # type: ignore[arg-type]
        )


def test_the_support_side_is_guarded_even_when_volatile_is_unestablished() -> None:
    """(MAJOR-2) A malformed support set raises rather than being absolved by a ``None`` volatile."""
    with pytest.raises(TypeError):
        decision_sole_sourced_from_volatile(frozenset({"CACHE"}), None)  # type: ignore[arg-type]


def test_a_mixed_set_is_rejected_on_its_one_foreign_member() -> None:
    """(MAJOR-2) One foreign member in an otherwise valid set is enough to raise."""
    with pytest.raises(TypeError):
        decision_sole_sourced_from_volatile(
            frozenset({_CACHE, "EVENT_INFRASTRUCTURE"}),  # type: ignore[arg-type]
            frozenset({_CACHE, _EVENTS}),
        )


@given(support=DOMAIN_SET, volatile=DOMAIN_SET)
def test_property_well_typed_sets_are_never_rejected(
    support: frozenset[FailureDomainKind], volatile: frozenset[FailureDomainKind]
) -> None:
    """(MAJOR-2 both-ways) The guard never fires on genuine taxonomy members."""
    assert decision_sole_sourced_from_volatile(support, volatile) is (
        support <= volatile
    )
