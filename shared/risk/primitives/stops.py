"""Stateless stop / trailing-stop decision primitives (P4-a).

Pure functions covering the stop shapes that exit generators actually use
today — deliberately no more general than the existing call sites:

- Absolute price stop (direction-aware level cross):
  ``momentum_decay._stop_hit`` / ``three_stage._stop_hit`` /
  ``setup_target_exit._price_crossed(trigger="stop")``.
- Percent hard stop from entry: ``three_stage`` Stage-1
  (``profit_pct <= stop_loss_pct``).
- ATR-offset stop level: ``track_a_exit.trail_stop_price`` /
  ``chandelier_exit`` chandelier level / catastrophic backstop level.
- Percent-retrace trailing level from the favorable extreme:
  ``three_stage._calculate_trailing_stop`` / ``momentum_decay`` trailing
  (gap selection and ``position.stop_price`` clamping stay at the call site —
  they are config/state concerns, not primitive math).

Statelessness contract:
    The high-water-mark / favorable extreme is passed IN as an argument.
    Its canonical source is the ``Position`` price tracking (see
    ``shared.risk.primitives.extremes``); sites that keep extremes in private
    dicts (``builder_strategy_exit``, ``trix_golden_exit``) can still pass
    their own value.

Boundary semantics:
    Legacy ``_stop_hit`` and ``track_a_exit`` use inclusive comparison
    (``<=`` / ``>=``); ``chandelier_exit`` uses strict ``<``. ``inclusive``
    is therefore an explicit argument (default ``True`` == the majority
    convention).

No hardcoded thresholds; every multiplier/percentage is a parameter.
Consumers are rewired in P4-b, not here.
"""

from __future__ import annotations

from shared.models.position import Position, PositionSide
from shared.risk.primitives.pnl import profit_pct

__all__ = [
    "abs_stop_hit",
    "atr_stop_level",
    "pct_stop_hit",
    "pct_trailing_stop_level",
    "trailing_stop_hit",
]


def abs_stop_hit(
    side: PositionSide,
    current_price: float,
    stop_price: float,
    *,
    inclusive: bool = True,
) -> bool:
    """Direction-aware absolute price stop check.

    LONG stops fire when the price falls to/through the stop level; SHORT
    stops fire when it rises to/through it. Equivalent to the legacy
    ``_stop_hit(position, current_price, stop_price)`` copies and to
    ``setup_target_exit._price_crossed(trigger="stop")``.

    Args:
        side: Position direction.
        current_price: Latest traded/mark price.
        stop_price: Absolute stop level in price units.
        inclusive: When ``True`` (legacy ``_stop_hit`` / ``track_a`` semantics)
            touching the level fires; ``False`` requires a strict cross
            (``chandelier_exit`` semantics).

    Returns:
        ``True`` when the stop is hit.
    """
    if side == PositionSide.SHORT:
        return current_price >= stop_price if inclusive else current_price > stop_price
    return current_price <= stop_price if inclusive else current_price < stop_price


def pct_stop_hit(
    position: Position, current_price: float, stop_loss_pct: float
) -> bool:
    """Percent hard stop from entry (three_stage Stage-1 style).

    Fires when the side-aware profit ratio is at or below ``stop_loss_pct``
    (typically negative, e.g. ``-0.02`` for a 2% stop). Uses
    :func:`shared.risk.primitives.pnl.profit_pct`, so ``entry_price <= 0``
    yields a ``0.0`` profit ratio and the stop fires only if
    ``stop_loss_pct >= 0``.

    Args:
        position: Open position (uses ``side`` and ``entry_price``).
        current_price: Latest traded/mark price.
        stop_loss_pct: Loss threshold as a ratio (``-0.02`` == -2%).

    Returns:
        ``True`` when ``profit_pct(position, current_price) <= stop_loss_pct``.
    """
    return profit_pct(position, current_price) <= stop_loss_pct


def atr_stop_level(
    reference_price: float,
    atr: float,
    multiplier: float,
    side: PositionSide,
) -> float:
    """ATR-offset stop level on the adverse side of a reference price.

    LONG: ``reference - multiplier * atr``; SHORT: ``reference + multiplier *
    atr``. With ``reference_price`` == favorable extreme this is the
    ``track_a_exit.trail_stop_price`` / chandelier level; with
    ``reference_price`` == entry price it is the catastrophic-backstop level
    (``catastrophic_stop_hit`` is ``abs_stop_hit`` against this level).

    Args:
        reference_price: Anchor price (favorable extreme or entry price).
        atr: ATR in absolute price units (see
            ``shared.risk.primitives.atr_read.normalize_atr``).
        multiplier: ATR multiple for the stop distance.
        side: Position direction.

    Returns:
        Stop level in price units.
    """
    offset = multiplier * atr
    if side == PositionSide.SHORT:
        return reference_price + offset
    return reference_price - offset


def pct_trailing_stop_level(
    extreme: float, retrace_pct: float, side: PositionSide
) -> float:
    """Percent-retrace trailing stop level from the favorable extreme.

    LONG: ``extreme * (1 - |retrace_pct|)``; SHORT: ``extreme * (1 +
    |retrace_pct|)``. The ``abs()`` mirrors the legacy sites
    (``three_stage`` / ``momentum_decay``), which take ``abs()`` of the
    configured gap before applying it.

    Args:
        extreme: Favorable extreme since entry (high for LONG, low for SHORT).
        retrace_pct: Allowed retrace as a ratio (``0.01`` == 1%); sign is
            ignored.
        side: Position direction.

    Returns:
        Trailing stop level in price units.
    """
    gap = abs(retrace_pct)
    if side == PositionSide.SHORT:
        return extreme * (1 + gap)
    return extreme * (1 - gap)


def trailing_stop_hit(
    side: PositionSide,
    current_price: float,
    extreme: float,
    *,
    retrace_pct: float | None = None,
    atr: float | None = None,
    atr_multiplier: float | None = None,
    inclusive: bool = True,
) -> bool:
    """Trailing stop check in exactly one of the two forms used today.

    Pass either ``retrace_pct`` (percent-retrace form: ``three_stage`` /
    ``momentum_decay``) or both ``atr`` and ``atr_multiplier`` (ATR-offset
    form: ``track_a_exit`` / ``chandelier_exit``). The favorable extreme is a
    caller-supplied argument (stateless HWM contract).

    Args:
        side: Position direction.
        current_price: Latest traded/mark price.
        extreme: Favorable extreme since entry (high for LONG, low for SHORT).
        retrace_pct: Percent-retrace gap as a ratio; mutually exclusive with
            the ATR form.
        atr: ATR in absolute price units (ATR form).
        atr_multiplier: ATR multiple for the trail distance (ATR form).
        inclusive: Level-touch semantics; see :func:`abs_stop_hit`
            (``chandelier_exit`` uses ``False``).

    Returns:
        ``True`` when the trailing stop is hit.

    Raises:
        ValueError: If neither or both forms are supplied, or the ATR form is
            missing one of ``atr`` / ``atr_multiplier``.
    """
    atr_form = atr is not None or atr_multiplier is not None
    if retrace_pct is not None and atr_form:
        raise ValueError(
            "trailing_stop_hit: pass either retrace_pct or atr+atr_multiplier, not both"
        )
    if retrace_pct is not None:
        level = pct_trailing_stop_level(extreme, retrace_pct, side)
    elif atr is not None and atr_multiplier is not None:
        level = atr_stop_level(extreme, atr, atr_multiplier, side)
    else:
        raise ValueError(
            "trailing_stop_hit: pass retrace_pct, or both atr and atr_multiplier"
        )
    return abs_stop_hit(side, current_price, level, inclusive=inclusive)
