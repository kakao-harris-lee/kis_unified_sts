"""Tick math utilities for futures execution.

Phase 4 Task 4 — extracted from spec §3.3 so passive maker / fill logger /
slippage-aware reporters share one source of truth instead of inlining
``/ 0.05`` constants.

Public API kept underscored to mirror the spec snippet — these are
package-private helpers consumed by ``shared/execution/passive_maker.py``
and ``shared/execution/fill_logger.py``.
"""

from __future__ import annotations


def _round_to_tick(price: float, tick_size: float) -> float:
    """Round ``price`` to nearest ``tick_size`` increment, float-safe.

    Double round absorbs IEEE-754 representation drift that would otherwise
    produce e.g. 331.20000000000005 from a clean 331.20 input.
    """
    if tick_size <= 0:
        raise ValueError(f"tick_size must be positive, got {tick_size}")
    return round(round(price / tick_size) * tick_size, 4)


def _compute_slippage_ticks(
    *,
    requested: float,
    filled: float,
    direction: str,
    tick_size: float,
) -> float:
    """Slippage in ticks signed against the trader.

    Long pays — ``filled > requested`` → +slip (worse for trader).
    Short receives — ``filled < requested`` → +slip.
    """
    if tick_size <= 0:
        raise ValueError(f"tick_size must be positive, got {tick_size}")
    if direction not in ("long", "short"):
        raise ValueError(f"direction must be long|short, got {direction!r}")
    raw = (filled - requested) / tick_size
    return raw if direction == "long" else -raw
