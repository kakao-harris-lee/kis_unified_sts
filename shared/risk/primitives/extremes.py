"""Favorable-extreme primitives (P4-a).

Single source for the ``_get_extreme_since_entry`` static method copy-pasted
across 5 exit generators (``atr_dynamic``, ``mean_reversion_exit``,
``momentum_decay``, ``three_stage``, ``williams_r_exit``).

Scope note:
    The extreme source is the ``Position`` model's own price tracking
    (``highest_price`` / ``lowest_price``, maintained by
    ``Position.update_price``). Two exit generators —
    ``builder_strategy_exit`` and ``trix_golden_exit`` — keep their extremes in
    private per-position dicts instead of the ``Position`` attributes; those
    sites are intentionally NOT covered by this primitive.

Pure and stateless; consumers are rewired in P4-b, not here.
"""

from __future__ import annotations

from shared.models.position import Position, PositionSide

__all__ = ["extreme_since_entry"]


def extreme_since_entry(position: Position, current_price: float) -> float:
    """Most favorable price since entry (high for LONG, low for SHORT).

    LONG returns ``max(highest_price or entry_price, current_price)``;
    SHORT returns ``min(lowest_price if finite else entry_price,
    current_price)``. ``current_price`` is always folded in as the latest data
    point, so a stale ``Position`` extreme can never lag behind the price the
    caller is evaluating. Unset extremes (``highest_price == 0.0`` /
    ``lowest_price == inf``) fall back to ``entry_price``, matching the legacy
    copies bit-for-bit.

    Args:
        position: Open position (uses ``side``, ``entry_price``,
            ``highest_price``, ``lowest_price``).
        current_price: Latest traded/mark price.

    Returns:
        The favorable extreme price since entry.
    """
    if position.side == PositionSide.SHORT:
        return min(
            (
                position.lowest_price
                if position.lowest_price < float("inf")
                else position.entry_price
            ),
            current_price,
        )
    return max(position.highest_price or position.entry_price, current_price)
