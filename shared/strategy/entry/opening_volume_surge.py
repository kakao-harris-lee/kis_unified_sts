"""Opening Volume Surge entry strategy (stocks).

Trigger idea:
  - In the first N minutes (default 30) after market open,
    if today's cumulative volume >= previous day's total volume,
    treat as a strong attention/liquidity event.

Notes:
  - We use "capital inflow proxy" as trade value/turnover trends in the
    after-close watchlist, but this entry is purely intraday volume-based.
  - "Execution rate" isn't directly available in our current quote schema;
    we approximate strength using price position within day's range and % change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class OpeningVolumeSurgeConfig(ConfigMixin):
    only_first_minutes: int = 30
    market_open_hour: int = 9
    market_open_minute: int = 0

    # Price-strength filters (to avoid catching dump volume).
    min_change_pct: float = 1.0
    require_above_open: bool = True
    min_range_position: float = 0.7  # (close-low)/(high-low)

    # Risk hint for sizing (used by RiskBasedSizer via signal.metadata)
    stop_loss_pct: float = 5.0  # percent


class OpeningVolumeSurgeEntry(EntrySignalGenerator[OpeningVolumeSurgeConfig]):
    CONFIG_CLASS = OpeningVolumeSurgeConfig

    def _validate_config(self):
        if self.config.only_first_minutes <= 0:
            raise ValueError("only_first_minutes must be > 0")
        if not (0 <= self.config.market_open_hour <= 23):
            raise ValueError("market_open_hour must be 0..23")
        if not (0 <= self.config.market_open_minute <= 59):
            raise ValueError("market_open_minute must be 0..59")
        if not (0.0 <= self.config.min_range_position <= 1.0):
            raise ValueError("min_range_position must be 0..1")

    @property
    def name(self) -> str:
        return "opening_volume_surge"

    @property
    def required_indicators(self) -> list[str]:
        return []

    async def generate(self, context: EntryContext) -> Optional[Signal]:
        data = context.market_data or {}

        code = str(data.get("code", "") or "")
        name = str(data.get("name", "") or code)
        if not code:
            return None

        now: datetime = context.timestamp
        open_dt = datetime.combine(now.date(), time(self.config.market_open_hour, self.config.market_open_minute))
        minutes_since_open = (now - open_dt).total_seconds() / 60.0

        if minutes_since_open < 0:
            return None
        if minutes_since_open > float(self.config.only_first_minutes):
            return None

        volume = int(data.get("volume", 0) or 0)
        prev_day_volume = int(data.get("prev_day_volume", 0) or 0)
        if prev_day_volume <= 0:
            # Baseline isn't available -> can't apply this strategy safely.
            return None

        # Core trigger: today 30m cumulative >= yesterday total.
        if volume < prev_day_volume:
            return None

        close = float(data.get("close", 0) or 0.0)
        o = float(data.get("open", 0) or 0.0)
        high = float(data.get("high", 0) or 0.0)
        low = float(data.get("low", 0) or 0.0)
        change = float(data.get("change", 0) or 0.0)  # ratio (e.g. 0.02 = 2%)
        change_pct = change * 100.0

        if close <= 0 or o <= 0:
            return None

        if self.config.require_above_open and close < o:
            return None

        if change_pct < self.config.min_change_pct:
            return None

        range_pos = 0.5
        if high > low and close > 0:
            range_pos = (close - low) / (high - low)
        if range_pos < self.config.min_range_position:
            return None

        vol_ratio = volume / prev_day_volume if prev_day_volume > 0 else 1.0
        confidence = min(1.0, max(0.5, vol_ratio / 2.0))

        logger.info(
            f"Opening volume surge ENTRY: {code} "
            f"vol={volume:,} prev={prev_day_volume:,} ({vol_ratio:.2f}x) "
            f"chg={change_pct:+.2f}% rangePos={range_pos:.2f}"
        )

        return Signal(
            code=code,
            name=name,
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=context.timestamp,
            strategy=self.name,  # will be overwritten to TradingStrategy.name by StrategyManager
            confidence=confidence,
            metadata={
                "signal_direction": "long",
                "stop_loss_pct": float(self.config.stop_loss_pct),
                "prev_day_volume": prev_day_volume,
                "current_volume": volume,
                "volume_ratio_vs_prev_day": float(vol_ratio),
                "minutes_since_open": float(minutes_since_open),
                "range_position": float(range_pos),
                "change_pct": float(change_pct),
            },
        )

