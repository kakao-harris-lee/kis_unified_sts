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


def build_market_context(
    *,
    now: datetime,
    symbol: str,
    current_price: float,
    prev_close: float,
    today_open: float,
    atr_14: float,
    last_15min_high: float,
    last_15min_low: float,
    vwap: float | None = None,
    atr_90th_percentile: float | None = None,
    current_spread_ticks: float | None = None,
    macro_overnight: object | None = None,
    scheduled_events: list[ScheduledEvent] | None = None,
) -> MarketContext:
    """Assemble a MarketContext with the canonical default policy (F-4).

    Setup A and Setup C read NONE of ``vwap`` / ``atr_90th_percentile`` /
    ``current_spread_ticks`` (locked by the F-4 invariance test). They are
    assembled here with shared defaults so the decoupled (decision_engine) and
    orchestrator (setup_adapters) builders stay consistent: vwap→current_price,
    atr_90th→atr_14*1.5, spread→1.0. ``current_spread_ticks`` is uncomputable
    from the OHLCV-only tick stream, so the decoupled path always defaults it.
    """
    return MarketContext(
        now=now,
        symbol=symbol,
        current_price=current_price,
        prev_close=prev_close,
        today_open=today_open,
        vwap=vwap if vwap is not None else current_price,
        atr_14=atr_14,
        atr_90th_percentile=(
            atr_90th_percentile if atr_90th_percentile is not None else atr_14 * 1.5
        ),
        last_15min_high=last_15min_high,
        last_15min_low=last_15min_low,
        current_spread_ticks=(
            current_spread_ticks if current_spread_ticks is not None else 1.0
        ),
        macro_overnight=macro_overnight,
        scheduled_events=list(scheduled_events) if scheduled_events else [],
    )
