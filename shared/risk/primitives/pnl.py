"""Side-aware PnL primitives (P4-a).

Single source for the side-aware profit calculations that were copy-pasted as
``_calc_profit_pct`` / ``_calc_profit_amount`` static methods across 9 exit
generators (``atr_dynamic``, ``mean_reversion_exit``, ``momentum_decay``,
``setup_target_exit``, ``technical_consensus_exit``, ``three_stage``,
``track_a_exit``, ``trix_golden_exit``, ``williams_r_exit``).

This module is pure and stateless: no I/O, no config, no hardcoded thresholds.
Consumers are NOT rewired in P4-a (behavior-0 landing); substitution happens
in P4-b.

Guard convention:
    ``entry_price <= 0`` returns ``0.0``. This matches the
    ``shared.models.position.Position.profit_rate`` property (the model's own
    semantics) and the guarded copies (``atr_dynamic``,
    ``technical_consensus_exit``, ``trix_golden_exit``). The unguarded copies
    (e.g. ``track_a_exit``) would raise ``ZeroDivisionError`` for
    ``entry_price == 0``; the guard here is the intended unification.
"""

from __future__ import annotations

from shared.models.position import Position, PositionSide

__all__ = ["profit_amount", "profit_pct"]


def profit_pct(position: Position, current_price: float) -> float:
    """Side-aware profit ratio relative to entry price.

    LONG: ``(current - entry) / entry``; SHORT: ``(entry - current) / entry``.
    The return value is a ratio (``0.05`` == +5%), matching the legacy
    ``_calc_profit_pct`` copies despite their ``pct`` naming.

    Args:
        position: Open position (uses ``side`` and ``entry_price``).
        current_price: Latest traded/mark price.

    Returns:
        Profit ratio; ``0.0`` when ``position.entry_price <= 0``
        (``Position.profit_rate`` convention).
    """
    if position.entry_price <= 0:
        return 0.0
    if position.side == PositionSide.SHORT:
        return (position.entry_price - current_price) / position.entry_price
    return (current_price - position.entry_price) / position.entry_price


def profit_amount(position: Position, current_price: float) -> float:
    """Side-aware profit amount in price units times quantity.

    LONG: ``(current - entry) * quantity``; SHORT: ``(entry - current) *
    quantity``. Identical to the 9 legacy ``_calc_profit_amount`` copies
    (no entry-price guard is needed: multiplication cannot divide by zero).

    Args:
        position: Open position (uses ``side``, ``entry_price``, ``quantity``).
        current_price: Latest traded/mark price.

    Returns:
        Signed profit amount (positive == favorable move).
    """
    if position.side == PositionSide.SHORT:
        return (position.entry_price - current_price) * position.quantity
    return (current_price - position.entry_price) * position.quantity
