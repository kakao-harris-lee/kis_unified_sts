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
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo
from typing import Optional

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


@dataclass
class OpeningVolumeSurgeConfig(ConfigMixin):
    only_first_minutes: int = 30
    market_open_hour: int = 9
    market_open_minute: int = 0

    # Volume trigger
    volume_multiplier: float = 1.0

    # Price-strength filters (to avoid catching dump volume).
    min_change_pct: float = 1.0
    require_above_open: bool = True
    min_range_position: float = 0.7  # (close-low)/(high-low)
    min_day_range_pct: float = 0.5  # (high-low)/open * 100

    # Change input handling
    change_input_unit: str = "ratio"  # "ratio" | "percent" | "auto"
    change_auto_threshold_pct: float = 1.0  # used only if change_input_unit == "auto"

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
        if self.config.volume_multiplier <= 0:
            raise ValueError("volume_multiplier must be > 0")
        if self.config.min_day_range_pct < 0:
            raise ValueError("min_day_range_pct must be >= 0")
        if self.config.change_input_unit not in ("ratio", "percent", "auto"):
            raise ValueError("change_input_unit must be ratio|percent|auto")
        if self.config.change_auto_threshold_pct < 0:
            raise ValueError("change_auto_threshold_pct must be >= 0")

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
        if now.tzinfo is None:
            now = now.replace(tzinfo=KST)
        else:
            now = now.astimezone(KST)

        open_dt = datetime.combine(
            now.date(),
            time(self.config.market_open_hour, self.config.market_open_minute),
            tzinfo=KST,
        )
        minutes_since_open = (now - open_dt).total_seconds() / 60.0

        if minutes_since_open < 0:
            return None
        if minutes_since_open > float(self.config.only_first_minutes):
            return None

        volume = int(data.get("volume", 0) or 0)
        prev_day_volume = int(data.get("prev_day_volume", 0) or 0)
        if prev_day_volume <= 0:
            # Baseline isn't available -> can't apply this strategy safely.
            logger.warning(
                "Opening volume surge skipped: missing prev_day_volume (%s)",
                code,
            )
            return None

        # Core trigger: today cumulative >= yesterday total * multiplier.
        required_volume = prev_day_volume * self.config.volume_multiplier
        if volume < required_volume:
            return None

        close = float(data.get("close", 0) or 0.0)
        o = float(data.get("open", 0) or 0.0)
        high = float(data.get("high", 0) or 0.0)
        low = float(data.get("low", 0) or 0.0)
        raw_change_pct = data.get("change_pct") or data.get("change_percent")
        if raw_change_pct is not None:
            change_pct = float(raw_change_pct)
        else:
            change = float(data.get("change", 0) or 0.0)
            unit = self.config.change_input_unit.lower()
            if unit == "percent":
                change_pct = change
            elif unit == "ratio":
                change_pct = change * 100.0
            else:
                threshold = float(self.config.change_auto_threshold_pct)
                change_pct = change if abs(change) >= threshold else change * 100.0

        if close <= 0 or o <= 0:
            return None

        if self.config.require_above_open and close < o:
            return None

        if change_pct < self.config.min_change_pct:
            return None

        day_range_pct = 0.0
        if o > 0:
            day_range_pct = (high - low) / o * 100.0
        if day_range_pct < self.config.min_day_range_pct:
            return None

        if high <= low:
            return None

        range_pos = 0.5
        if close > 0:
            safe_close = min(max(close, low), high)
            range_pos = (safe_close - low) / (high - low)
        if range_pos < self.config.min_range_position:
            return None

        vol_ratio = volume / prev_day_volume if prev_day_volume > 0 else 1.0
        confidence = min(1.0, max(0.5, vol_ratio / 2.0))

        logger.info(
            f"Opening volume surge ENTRY: {code} "
            f"vol={volume:,} req={int(required_volume):,} ({vol_ratio:.2f}x) "
            f"chg={change_pct:+.2f}% rangePos={range_pos:.2f} "
            f"dayRange={day_range_pct:.2f}%"
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
                "required_volume": float(required_volume),
                "minutes_since_open": float(minutes_since_open),
                "range_position": float(range_pos),
                "day_range_pct": float(day_range_pct),
                "change_pct": float(change_pct),
            },
        )
