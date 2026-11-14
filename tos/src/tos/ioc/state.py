"""ioc temporal / lifecycle predicates — non-revival, economic continuity, generation fence (§6.6/§5.7)."""

from __future__ import annotations

from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "recovery_revives_nothing",
    "economic_effect_outlives",
    "construction_generation_fences",
]


def recovery_revives_nothing() -> bool:
    """Whether nothing revives a prior proof / capability / command permission / live scope (§6.6 / §21)."""
    return True


def economic_effect_outlives(*, terminal_release_proven: bool | None) -> bool:
    """Whether the committed economic effect outlives artifact expiry (§6.6 / §18 / IOC-INV-012)."""
    return terminal_release_proven is not True


def construction_generation_fences(older: OrderingEvent, newer: OrderingEvent) -> bool:
    """Whether a newer restrictive Construction Generation fences an older one (§5.7 / §3.2)."""
    return compare_order(older, newer) is Ordering.BEFORE
