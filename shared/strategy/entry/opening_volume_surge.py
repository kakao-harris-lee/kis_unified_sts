"""Opening Volume Surge entry strategy (stocks).

Trigger idea:
  - Volume gate supports cumulative baseline (vs previous day) and/or
    intraday burst gate (RVOL) via config.
  - Optional early-session window can be enabled via only_first_minutes.

Notes:
  - We use "capital inflow proxy" as trade value/turnover trends in the
    after-close watchlist, but this entry is purely intraday volume-based.
  - "Execution rate" isn't directly available in our current quote schema;
    we approximate strength using price position within day's range and % change.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime, time

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.entry.gates import MarketSessionWindow, is_in_entry_session
from shared.strategy.market_time import to_kst

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


@dataclass
class OpeningVolumeSurgeConfig(ConfigMixin):
    # 0 disables upper time-window gate (allow all intraday session).
    only_first_minutes: int = 0
    market_open_hour: int = 9
    market_open_minute: int = 0

    # Volume trigger
    volume_multiplier: float = 1.0
    # cumulative | rvol | either | both
    volume_gate_mode: str = "cumulative"
    min_rvol: float = 0.0

    # Price-strength filters (to avoid catching dump volume).
    min_change_pct: float = 1.0
    require_above_open: bool = True
    min_range_position: float = 0.7  # (close-low)/(high-low)
    min_day_range_pct: float = 0.5  # (high-low)/open * 100

    # Change input handling
    change_input_unit: str = "ratio"  # "ratio" | "percent" | "auto"
    change_auto_threshold_pct: float = 1.0  # used only if change_input_unit == "auto"

    # Intraday momentum filters
    min_return_1m_pct: float = 0.0
    rvol_spike_threshold: float = 0.0
    spike_lookback_minutes: int = 0
    min_spike_hits: int = 0

    # Optional cutoff (if hour < 0, disabled)
    entry_cutoff_hour: int = -1
    entry_cutoff_minute: int = 0

    # Composite score filter (disable with negative value)
    min_signal_score: float = -1.0
    score_weight_vol_ratio: float = 0.45
    score_weight_rvol: float = 0.35
    score_weight_change_pct: float = 0.15
    score_weight_range_pos: float = 0.05

    # Risk hint for sizing (used by RiskBasedSizer via signal.metadata)
    stop_loss_pct: float = 5.0  # percent


class OpeningVolumeSurgeEntry(EntrySignalGenerator[OpeningVolumeSurgeConfig]):
    CONFIG_CLASS = OpeningVolumeSurgeConfig

    def __init__(self, config: OpeningVolumeSurgeConfig):
        self._last_minute_close: dict[str, tuple[int, float]] = {}
        self._spike_windows: dict[str, deque[tuple[int, int]]] = {}
        super().__init__(config)

    def _validate_config(self):
        if self.config.only_first_minutes < 0:
            raise ValueError("only_first_minutes must be >= 0")
        if not (0 <= self.config.market_open_hour <= 23):
            raise ValueError("market_open_hour must be 0..23")
        if not (0 <= self.config.market_open_minute <= 59):
            raise ValueError("market_open_minute must be 0..59")
        if not (0.0 <= self.config.min_range_position <= 1.0):
            raise ValueError("min_range_position must be 0..1")
        if self.config.volume_multiplier <= 0:
            raise ValueError("volume_multiplier must be > 0")
        mode = str(self.config.volume_gate_mode).lower()
        if mode not in ("cumulative", "rvol", "either", "both"):
            raise ValueError(
                "volume_gate_mode must be cumulative|rvol|either|both"
            )
        if self.config.min_rvol < 0:
            raise ValueError("min_rvol must be >= 0")
        if self.config.min_day_range_pct < 0:
            raise ValueError("min_day_range_pct must be >= 0")
        if self.config.change_input_unit not in ("ratio", "percent", "auto"):
            raise ValueError("change_input_unit must be ratio|percent|auto")
        if self.config.change_auto_threshold_pct < 0:
            raise ValueError("change_auto_threshold_pct must be >= 0")
        if self.config.min_return_1m_pct < 0:
            raise ValueError("min_return_1m_pct must be >= 0")
        if self.config.rvol_spike_threshold < 0:
            raise ValueError("rvol_spike_threshold must be >= 0")
        if self.config.spike_lookback_minutes < 0:
            raise ValueError("spike_lookback_minutes must be >= 0")
        if self.config.min_spike_hits < 0:
            raise ValueError("min_spike_hits must be >= 0")
        if self.config.entry_cutoff_hour != -1 and not (0 <= self.config.entry_cutoff_hour <= 23):
            raise ValueError("entry_cutoff_hour must be -1 or 0..23")
        if not (0 <= self.config.entry_cutoff_minute <= 59):
            raise ValueError("entry_cutoff_minute must be 0..59")
        if self.config.min_signal_score < -1:
            raise ValueError("min_signal_score must be >= -1")
        if self.config.score_weight_vol_ratio < 0:
            raise ValueError("score_weight_vol_ratio must be >= 0")
        if self.config.score_weight_rvol < 0:
            raise ValueError("score_weight_rvol must be >= 0")
        if self.config.score_weight_change_pct < 0:
            raise ValueError("score_weight_change_pct must be >= 0")
        if self.config.score_weight_range_pos < 0:
            raise ValueError("score_weight_range_pos must be >= 0")

    @property
    def name(self) -> str:
        return "opening_volume_surge"

    @property
    def required_indicators(self) -> list[str]:
        return []

    async def generate(self, context: EntryContext) -> Signal | None:
        data = context.market_data or {}

        code = str(data.get("code", "") or "")
        name = str(data.get("name", "") or code)
        if not code:
            return None

        now: datetime = context.timestamp
        window = MarketSessionWindow(
            market_open_hour=self.config.market_open_hour,
            market_open_minute=self.config.market_open_minute,
            market_close_hour=23,
            market_close_minute=59,
            skip_market_open_minutes=0,
            skip_market_close_minutes=0,
        )
        if not is_in_entry_session(now, window):
            return None

        now = to_kst(now)

        open_dt = datetime.combine(
            now.date(),
            time(self.config.market_open_hour, self.config.market_open_minute),
            tzinfo=KST,
        )
        minutes_since_open = (now - open_dt).total_seconds() / 60.0

        if (
            self.config.only_first_minutes > 0
            and minutes_since_open > float(self.config.only_first_minutes)
        ):
            return None
        if self.config.entry_cutoff_hour >= 0:
            cutoff_dt = datetime.combine(
                now.date(),
                time(self.config.entry_cutoff_hour, self.config.entry_cutoff_minute),
                tzinfo=KST,
            )
            if now > cutoff_dt:
                return None

        volume = int(data.get("volume", 0) or 0)
        prev_day_volume = int(data.get("prev_day_volume", 0) or 0)
        rvol = float(data.get("rvol", 0.0) or 0.0)
        mode = str(self.config.volume_gate_mode).lower()

        required_volume = 0.0
        pass_cumulative = False
        if prev_day_volume > 0:
            # Core baseline trigger: today cumulative >= yesterday total * multiplier.
            required_volume = prev_day_volume * self.config.volume_multiplier
            pass_cumulative = volume >= required_volume
        elif mode in ("cumulative", "both"):
            # Baseline-required mode without metadata -> can't evaluate safely.
            logger.warning(
                "Opening volume surge skipped: missing prev_day_volume (%s)",
                code,
            )
            return None
        pass_rvol = self.config.min_rvol > 0 and rvol >= self.config.min_rvol

        volume_gate_pass = False
        if mode == "cumulative":
            volume_gate_pass = pass_cumulative
        elif mode == "rvol":
            volume_gate_pass = pass_rvol
        elif mode == "either":
            volume_gate_pass = pass_cumulative or pass_rvol
        elif mode == "both":
            volume_gate_pass = pass_cumulative and pass_rvol

        if not volume_gate_pass:
            return None

        close = float(data.get("close", 0) or 0.0)
        o = float(data.get("open", 0) or 0.0)
        high = float(data.get("high", 0) or 0.0)
        low = float(data.get("low", 0) or 0.0)
        raw_change_pct = data.get("change_pct")
        if raw_change_pct is None:
            raw_change_pct = data.get("change_percent")
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

        minute_key = int(now.timestamp() // 60)
        ret_1m_pct = 0.0
        prev_minute_close = self._last_minute_close.get(code)
        if prev_minute_close is not None:
            prev_minute_key, prev_close = prev_minute_close
            if minute_key > prev_minute_key and prev_close > 0:
                ret_1m_pct = (close / prev_close - 1.0) * 100.0

        spike_hits_window = 0
        if (
            self.config.rvol_spike_threshold > 0
            and self.config.spike_lookback_minutes > 0
            and self.config.min_spike_hits > 0
        ):
            dq = self._spike_windows.get(code)
            if dq is None:
                dq = deque()
                self._spike_windows[code] = dq

            if not dq or dq[-1][0] != minute_key:
                hit = 1 if rvol >= self.config.rvol_spike_threshold else 0
                dq.append((minute_key, hit))

            min_allowed = minute_key - self.config.spike_lookback_minutes + 1
            while dq and dq[0][0] < min_allowed:
                dq.popleft()

            spike_hits_window = sum(v for _, v in dq)
            if spike_hits_window < self.config.min_spike_hits:
                self._last_minute_close[code] = (minute_key, close)
                return None

        if self.config.min_return_1m_pct > 0 and ret_1m_pct < self.config.min_return_1m_pct:
            self._last_minute_close[code] = (minute_key, close)
            return None

        vol_ratio = volume / prev_day_volume if prev_day_volume > 0 else 0.0
        signal_score = (
            self.config.score_weight_vol_ratio * math.log1p(max(vol_ratio, 0.0))
            + self.config.score_weight_rvol * math.log1p(max(rvol, 0.0))
            + self.config.score_weight_change_pct * max(change_pct, 0.0)
            + self.config.score_weight_range_pos * max(range_pos, 0.0)
        )
        if self.config.min_signal_score >= 0 and signal_score < self.config.min_signal_score:
            self._last_minute_close[code] = (minute_key, close)
            return None

        confidence = min(1.0, max(0.5, vol_ratio / 2.0))
        self._last_minute_close[code] = (minute_key, close)

        logger.info(
            f"Opening volume surge ENTRY: {code} "
            f"vol={volume:,} req={int(required_volume):,} ({vol_ratio:.2f}x) "
            f"mode={mode} rvol={rvol:.2f} "
            f"ret1m={ret_1m_pct:+.3f}% spikes={spike_hits_window} score={signal_score:.3f} "
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
                "volume_gate_mode": mode,
                "volume_gate_pass_cumulative": bool(pass_cumulative),
                "volume_gate_pass_rvol": bool(pass_rvol),
                "rvol": float(rvol),
                "ret_1m_pct": float(ret_1m_pct),
                "spike_hits_window": int(spike_hits_window),
                "signal_score": float(signal_score),
                "minutes_since_open": float(minutes_since_open),
                "range_position": float(range_pos),
                "day_range_pct": float(day_range_pct),
                "change_pct": float(change_pct),
            },
        )
