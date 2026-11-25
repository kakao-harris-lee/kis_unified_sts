"""Adapters bridging runtime bar/candle types to the engine's OHLCVWindow.

Kept in its own module (not ``spec.py``) so the engine core stays free of any
runtime-type coupling. The bridge is structural — a :class:`OHLCVBar` Protocol —
so it accepts the runtime ``Candle`` (and any equivalent bar) **without importing
it**, keeping ``shared`` independent of ``services`` (no layering violation).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from shared.indicators.engine.spec import OHLCVWindow


@runtime_checkable
class OHLCVBar(Protocol):
    """Structural type for a single OHLCV bar (e.g. the runtime ``Candle``)."""

    open: float
    high: float
    low: float
    close: float
    volume: float


def window_from_bars(bars: Sequence[OHLCVBar]) -> OHLCVWindow:
    """Build an :class:`OHLCVWindow` from an ordered sequence of OHLCV bars."""
    return OHLCVWindow.from_sequences(
        open=[bar.open for bar in bars],
        high=[bar.high for bar in bars],
        low=[bar.low for bar in bars],
        close=[bar.close for bar in bars],
        volume=[bar.volume for bar in bars],
    )


def window_from_records(rows: Sequence[Mapping[str, float]]) -> OHLCVWindow:
    """Build an :class:`OHLCVWindow` from ``{open,high,low,close,volume}`` dicts.

    Matches the shape returned by the runtime's ``get_recent_candles`` /
    ``context.indicators["ohlcv"]``.
    """
    return OHLCVWindow.from_sequences(
        open=[float(row["open"]) for row in rows],
        high=[float(row["high"]) for row in rows],
        low=[float(row["low"]) for row in rows],
        close=[float(row["close"]) for row in rows],
        volume=[float(row["volume"]) for row in rows],
    )
