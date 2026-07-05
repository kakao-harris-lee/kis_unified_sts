"""Adapters bridging runtime bar/candle types to the engine's OHLCVWindow.

Kept in its own module (not ``spec.py``) so the engine core stays free of any
runtime-type coupling. The bridge is structural — a :class:`OHLCVBar` Protocol —
so it accepts the runtime ``Candle`` (and any equivalent bar) **without importing
it**, keeping ``shared`` independent of ``services`` (no layering violation).
"""

from __future__ import annotations

from collections.abc import Sequence
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
