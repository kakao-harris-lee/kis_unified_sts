"""tos.ordering — shared causal-ordering primitive (time design §0.4b/§5 PROMOTE)."""

from __future__ import annotations

from tos.ordering._ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "Ordering",
    "OrderingEvent",
    "compare_order",
]
