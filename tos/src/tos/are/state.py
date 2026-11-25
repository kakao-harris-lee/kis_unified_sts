"""are temporal / lifecycle predicates — concurrency, currentness, non-revival (§6.3/§6.4/§6.6)."""

from __future__ import annotations

from tos.are.records import AggregateRiskDecision
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "non_cyclic_binding",
    "concurrent_not_reservation",
    "decision_generation_monotone",
    "currentness_invalidation",
    "non_revival_holds",
    "economic_effect_persists",
]

_FORWARD_ONLY_FORBIDDEN_FIELDS: frozenset[str] = frozenset(
    {
        "bound_reservation_revision",
        "bound_reservation_digest",
        "bound_generation",
        "reservation_id",
    }
)


def non_cyclic_binding(decision: AggregateRiskDecision) -> bool:
    """Whether the decision is forward-only and binds no future commitment (§6.3 / §4.6 / §16)."""
    return _FORWARD_ONLY_FORBIDDEN_FIELDS.isdisjoint(type(decision).model_fields)


def concurrent_not_reservation(
    *,
    headroom_observed: bool | None,
    rcl_serialization_committed: bool | None,
) -> bool:
    """Whether an exclusive commitment exists (only RCL serialization creates one) (§6.3 / §18)."""
    del headroom_observed
    return rcl_serialization_committed is True


def decision_generation_monotone(earlier: OrderingEvent, later: OrderingEvent) -> bool:
    """Whether ``earlier`` strictly precedes ``later`` in append-only order (§3.2 / §5.2)."""
    return compare_order(earlier, later) is Ordering.BEFORE


def currentness_invalidation(
    *,
    material_change_present: bool | None,
    cache_ttl_or_heartbeat_only: bool | None,
) -> bool:
    """Whether an unconsumed decision must be invalidated (§6.4 / §17)."""
    if material_change_present is not False:
        return True
    return cache_ttl_or_heartbeat_only is True


def non_revival_holds() -> bool:
    """Whether nothing revives a prior decision / grant / authority / live scope (§6.6 / §21)."""
    return True


def economic_effect_persists(*, terminal_release_proven: bool | None) -> bool:
    """Whether the committed economic effect persists (§6.6 / §20 / ARE-INV-011 line 193)."""
    return terminal_release_proven is not True
