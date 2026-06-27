"""Volume Accumulation Breakout Entry Strategy.

Entry strategy for stocks showing volume accumulation patterns:
- Identifies consolidation breakouts with volume confirmation
- Requires stock to be in pre-screened accumulation candidate list
- Combines price breakout, volume surge, and VWAP position
- Uses accumulation score from overnight scan for confidence scoring

Entry Signal Generation:
1. Prerequisites: Stock must be in accumulation candidate list
2. Price: Breaks above N-day high (consolidation breakout)
3. Volume: RVOL > threshold with positive acceleration
4. Position: Price above VWAP
5. Timing: Respects market open/close buffer zones
"""
import logging
from dataclasses import dataclass
from datetime import datetime, time

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.market_time import to_kst

logger = logging.getLogger(__name__)


@dataclass
class VolumeAccumulationConfig(ConfigMixin):
    """Volume Accumulation Breakout strategy configuration."""

    # Breakout detection
    breakout_period: int = 5  # N-day high for breakout
    breakout_buffer_pct: float = 0.3  # Must exceed high by 0.3%

    # Volume confirmation
    rvol_threshold: float = 2.0  # Minimum RVOL for entry
    require_volume_acceleration: bool = True

    # VWAP
    require_above_vwap: bool = True

    # Accumulation candidate filter
    min_accumulation_score: int = 60  # From overnight scan

    # Time filters
    skip_market_open_minutes: int = 15
    skip_market_close_minutes: int = 30
    market_open_hour: int = 9
    market_open_minute: int = 0
    market_close_hour: int = 15
    market_close_minute: int = 30

    # Position limits
    max_positions: int = 5
    stop_loss_pct: float = 3.0  # For position sizer hint

    # Cooldown
    signal_cooldown_seconds: int = 600


class VolumeAccumulationBreakoutEntry(EntrySignalGenerator[VolumeAccumulationConfig]):
    """Volume Accumulation Breakout entry strategy.

    Entry conditions (ALL must be true):
    1. Stock in accumulation candidate list (from overnight scan)
    2. Price breaks above N-day high with buffer
    3. Volume surge: current RVOL > threshold
    4. Volume acceleration: positive velocity AND acceleration
    5. Price above VWAP
    6. Time: after market open buffer, before close buffer

    Confidence scoring:
    - Accumulation score (from overnight): 0-40%
    - Volume surge magnitude: 0-30%
    - Breakout strength: 0-20%
    - VWAP position: 0-10%
    """

    CONFIG_CLASS = VolumeAccumulationConfig

    def __init__(self, config: VolumeAccumulationConfig):
        super().__init__(config)
        self._last_signal_times: dict[str, datetime] = {}

    def _validate_config(self):
        """Validate configuration parameters."""
        assert self.config.breakout_period > 0, "breakout_period must be positive"
        assert self.config.breakout_buffer_pct >= 0, "breakout_buffer_pct must be non-negative"
        assert self.config.rvol_threshold > 0, "rvol_threshold must be positive"
        assert 0 <= self.config.min_accumulation_score <= 100, "min_accumulation_score must be 0-100"
        assert self.config.signal_cooldown_seconds >= 0, "signal_cooldown_seconds must be non-negative"

    @property
    def name(self) -> str:
        return "volume_accumulation"

    @property
    def required_indicators(self) -> list[str]:
        """Required indicators for this strategy."""
        period = self.config.breakout_period
        indicators = ["close", f"high_{period}", "volume", "vwap", "rvol"]
        if self.config.require_volume_acceleration:
            indicators.extend(["volume_velocity", "volume_acceleration"])
        return indicators

    async def generate(self, context: EntryContext) -> Signal | None:
        """Generate entry signal based on volume accumulation breakout conditions."""
        data = context.market_data
        code = data.get("code", "")
        name = data.get("name", "")

        # Check if stock is in accumulation candidate list
        accumulation_candidates = context.metadata.get("accumulation_candidates", {})
        if code not in accumulation_candidates:
            return None

        accumulation_score = accumulation_candidates[code]
        if accumulation_score < self.config.min_accumulation_score:
            logger.debug(
                f"{code}: Accumulation score {accumulation_score} below threshold "
                f"{self.config.min_accumulation_score}"
            )
            return None

        # Check signal cooldown
        if not self._check_cooldown(code, context.timestamp):
            return None

        # Check time filters
        if not self._check_time_filter(context.timestamp):
            return None

        # Extract required data
        close = data.get("close", 0.0)
        period = self.config.breakout_period
        high_n = data.get(f"high_{period}", 0.0)
        rvol = data.get("rvol", 1.0)
        vwap = data.get("vwap", 0.0)

        # Validate data
        if close <= 0 or high_n <= 0:
            logger.debug(f"{code}: Invalid price data (close={close}, high_{period}={high_n})")
            return None

        # Check breakout condition
        breakout_threshold = high_n * (1 + self.config.breakout_buffer_pct / 100)
        if close <= breakout_threshold:
            return None

        # Check RVOL
        if rvol < self.config.rvol_threshold:
            logger.debug(f"{code}: RVOL {rvol:.2f} below threshold {self.config.rvol_threshold}")
            return None

        # Check volume acceleration if required
        if self.config.require_volume_acceleration:
            volume_velocity = data.get("volume_velocity", 0.0)
            volume_acceleration = data.get("volume_acceleration", 0.0)
            if volume_velocity <= 0 or volume_acceleration <= 0:
                logger.debug(
                    f"{code}: Insufficient volume acceleration "
                    f"(velocity={volume_velocity:.2f}, accel={volume_acceleration:.2f})"
                )
                return None

        # Check VWAP position if required
        if self.config.require_above_vwap and (vwap <= 0 or close <= vwap):
            logger.debug(f"{code}: Price {close} not above VWAP {vwap}")
            return None

        # Calculate confidence
        confidence = self._calculate_confidence(
            close=close,
            high_n=high_n,
            rvol=rvol,
            vwap=vwap,
            accumulation_score=accumulation_score,
        )

        # Update cooldown tracker
        self._last_signal_times[code] = context.timestamp

        # Calculate breakout percentage for logging
        breakout_pct = ((close - high_n) / high_n) * 100

        logger.info(
            f"Volume Accumulation LONG signal: {code} ({name}) "
            f"close={close:.2f}, high_{period}={high_n:.2f}, "
            f"breakout={breakout_pct:.2f}%, rvol={rvol:.2f}, "
            f"vwap={vwap:.2f}, accum_score={accumulation_score}, "
            f"confidence={confidence:.2%}"
        )

        return Signal(
            code=code,
            name=name,
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=context.timestamp,
            strategy="volume_accumulation",
            confidence=confidence,
            metadata={
                "signal_direction": "long",
                "stop_loss_pct": float(self.config.stop_loss_pct),
                "accumulation_score": accumulation_score,
                "rvol": rvol,
                "breakout_pct": breakout_pct,
                "vwap": vwap,
                "high_n": high_n,
            },
        )

    def _check_cooldown(self, code: str, timestamp: datetime) -> bool:
        """Check if signal cooldown period has elapsed."""
        if code not in self._last_signal_times:
            return True

        last_signal_time = self._last_signal_times[code]
        elapsed_seconds = (timestamp - last_signal_time).total_seconds()

        if elapsed_seconds < self.config.signal_cooldown_seconds:
            logger.debug(
                f"{code}: Signal cooldown active "
                f"({elapsed_seconds:.0f}s / {self.config.signal_cooldown_seconds}s)"
            )
            return False

        return True

    def _check_time_filter(self, timestamp: datetime) -> bool:
        """Check if current time is within allowed trading window."""
        # Market hour filters use KST; timestamp is UTC-aware (PR #159).
        ts_kst = to_kst(timestamp)
        current_time = ts_kst.time()

        # Calculate market open time (with buffer)
        open_hour = self.config.market_open_hour
        open_minute = self.config.market_open_minute + self.config.skip_market_open_minutes
        if open_minute >= 60:
            open_hour += open_minute // 60
            open_minute = open_minute % 60
        market_open = time(hour=open_hour, minute=open_minute)

        # Calculate market close time (with buffer)
        close_hour = self.config.market_close_hour
        close_minute = self.config.market_close_minute - self.config.skip_market_close_minutes
        if close_minute < 0:
            close_hour -= 1
            close_minute += 60

        market_close = time(hour=close_hour, minute=close_minute)

        if current_time < market_open:
            logger.debug(f"Before market open buffer: {current_time} < {market_open}")
            return False

        if current_time > market_close:
            logger.debug(f"After market close buffer: {current_time} > {market_close}")
            return False

        return True

    def _calculate_confidence(
        self,
        close: float,
        high_n: float,
        rvol: float,
        vwap: float,
        accumulation_score: int,
    ) -> float:
        """Calculate signal confidence 0-1.

        Confidence components:
        - Accumulation score (from overnight): 0-40% (normalized from 0-100 range)
        - Volume surge magnitude: 0-30% (based on RVOL)
        - Breakout strength: 0-20% (based on distance above high_n)
        - VWAP position: 0-10% (based on distance above VWAP)
        """
        # Accumulation score component (0-40%)
        # Normalize score from 0-100 to 0-0.4
        accum_component = (accumulation_score / 100) * 0.4

        # Volume surge component (0-30%)
        # Scale RVOL: 2.0 -> 0%, 4.0 -> 15%, 6.0+ -> 30%
        rvol_normalized = (rvol - self.config.rvol_threshold) / 4.0
        volume_component = min(0.3, max(0.0, rvol_normalized * 0.3))

        # Breakout strength component (0-20%)
        # Percentage above high_n
        breakout_pct = (close - high_n) / high_n
        # Scale: 0.3% -> 0%, 1% -> 10%, 2%+ -> 20%
        breakout_normalized = (breakout_pct - (self.config.breakout_buffer_pct / 100)) / 0.02
        breakout_component = min(0.2, max(0.0, breakout_normalized * 0.2))

        # VWAP position component (0-10%)
        # Distance above VWAP
        if vwap > 0:
            vwap_pct = (close - vwap) / vwap
            # Scale: 0% -> 0%, 0.5% -> 5%, 1%+ -> 10%
            vwap_normalized = vwap_pct / 0.01
            vwap_component = min(0.1, max(0.0, vwap_normalized * 0.1))
        else:
            vwap_component = 0.0

        confidence = accum_component + volume_component + breakout_component + vwap_component

        # Ensure confidence is in valid range [0, 1]
        return max(0.0, min(1.0, confidence))
