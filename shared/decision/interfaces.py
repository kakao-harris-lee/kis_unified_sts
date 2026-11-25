"""Thin structural contracts for decision setup inputs and generators."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from shared.decision.signal import Signal


@runtime_checkable
class MacroOvernightView(Protocol):
    """Overnight macro fields consumed by Setup A."""

    sp500_change_pct: float | None


@runtime_checkable
class ScheduledEventView(Protocol):
    """Calendar-event fields consumed by futures decision setups."""

    event_id: str
    event_type: str
    scheduled_at: datetime
    impact_tier: int


@runtime_checkable
class FuturesMarketView(Protocol):
    """Market snapshot surface consumed by Setup A/C/D."""

    now: datetime
    symbol: str
    current_price: float
    prev_close: float
    today_open: float
    vwap: float
    atr_14: float
    atr_90th_percentile: float
    last_15min_high: float
    last_15min_low: float
    current_spread_ticks: float
    macro_overnight: object | None
    scheduled_events: Sequence[ScheduledEventView]

    def minutes_since_open(self) -> float:
        """Elapsed minutes since the configured market open."""
        ...

    def find_recent_event(
        self,
        window_minutes: float,
        min_tier: int,
    ) -> ScheduledEventView | None:
        """Return the latest qualifying scheduled event, if present."""
        ...


@runtime_checkable
class SetupSignalGenerator(Protocol):
    """Decision setup contract independent of concrete MarketContext."""

    def check(self, ctx: FuturesMarketView) -> Signal | None:
        """Evaluate a market snapshot and optionally emit a signal."""
        ...


__all__ = [
    "FuturesMarketView",
    "MacroOvernightView",
    "ScheduledEventView",
    "SetupSignalGenerator",
]
