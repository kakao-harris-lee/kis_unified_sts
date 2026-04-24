"""MarketContext + ScheduledEvent dataclasses + YAML loader."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import yaml

if TYPE_CHECKING:
    pass

KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class ScheduledEvent:
    """A macro calendar event that may influence trading decisions."""

    event_id: str
    event_type: str
    scheduled_at: datetime  # tz-aware
    impact_tier: int  # 1 = top tier, 3 = minor


@dataclass(frozen=True)
class MarketContext:
    """Aggregated market state snapshot consumed by signal generators."""

    now: datetime  # KST
    symbol: str  # e.g. "A05603" — mini front-month
    current_price: float
    prev_close: float
    today_open: float
    vwap: float
    atr_14: float
    atr_90th_percentile: float  # 60-day rolling percentile (backtest warmup)
    last_15min_high: float
    last_15min_low: float
    current_spread_ticks: float
    macro_overnight: object | None  # MacroSnapshot | None
    scheduled_events: list[ScheduledEvent]  # recent / upcoming macro events

    def market_open_time(self) -> datetime:
        """Return 09:00 KST on the same date as ``self.now``."""
        return datetime(
            self.now.year,
            self.now.month,
            self.now.day,
            9,
            0,
            tzinfo=KST,
        )

    def minutes_since_open(self) -> float:
        """Elapsed minutes since today's 09:00 KST market open."""
        return (self.now - self.market_open_time()).total_seconds() / 60

    def find_recent_event(
        self,
        window_minutes: float,
        min_tier: int,
    ) -> ScheduledEvent | None:
        """Return the most recent qualifying ScheduledEvent, or None.

        Qualifying criteria:
        - ``scheduled_at <= self.now``  (event has already occurred)
        - elapsed minutes since event ``<= window_minutes``
        - ``impact_tier <= min_tier``  (tier 1 is top; lower = higher impact)
        """
        best: ScheduledEvent | None = None
        best_elapsed: float = float("inf")

        for evt in self.scheduled_events:
            if evt.scheduled_at > self.now:
                continue
            elapsed = (self.now - evt.scheduled_at).total_seconds() / 60
            if elapsed > window_minutes:
                continue
            if evt.impact_tier > min_tier:
                continue
            if elapsed < best_elapsed:
                best = evt
                best_elapsed = elapsed

        return best


def load_scheduled_events(path: str) -> list[ScheduledEvent]:
    """Parse a ``scheduled_events.yaml`` file and return a list of ScheduledEvent.

    Each event's ``scheduled_at`` is an ISO 8601 string converted to a
    tz-aware ``datetime`` with UTC tzinfo.
    """
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw_events = data.get("events", [])
    events: list[ScheduledEvent] = []
    for item in raw_events:
        scheduled_at_str: str = item["scheduled_at"]
        # Parse ISO 8601; Python 3.11+ fromisoformat handles Z suffix
        dt = datetime.fromisoformat(scheduled_at_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        events.append(
            ScheduledEvent(
                event_id=item["event_id"],
                event_type=item["event_type"],
                scheduled_at=dt,
                impact_tier=int(item["impact_tier"]),
            )
        )
    return events
