"""Ensemble filter for combining DL predictions with technical filters."""
import logging
import time
from typing import List, Optional, Tuple

from .config import EnsembleConfig
from .models import FilterResult, EnsembleSignal, HorizonResult
from .calibrator import ProbabilityCalibrator
from ..trend.models import TechnicalData

logger = logging.getLogger(__name__)


class EnsembleFilter:
    """Ensemble filter combining DL predictions with technical indicators.

    The filter evaluates:
    1. DL model probability (calibrated)
    2. MA alignment (short vs long)
    3. Ichimoku cloud alignment
    4. Volume confirmation
    5. Multi-horizon consensus (optional)
    """

    def __init__(self, config: EnsembleConfig):
        self.config = config
        self.calibrator = ProbabilityCalibrator(config)

        # Statistics
        self._stats = {
            "total_checks": 0,
            "long_signals": 0,
            "short_signals": 0,
            "rejected_ma": 0,
            "rejected_ichimoku": 0,
            "rejected_confidence": 0,
        }

    def check_long(
        self,
        dl_probability: float,
        technical_data: TechnicalData,
        volume_ratio: float = 1.0,
        timestamp: Optional[float] = None
    ) -> FilterResult:
        """Check long entry conditions.

        Args:
            dl_probability: Raw DL model probability for long
            technical_data: Current technical indicators
            volume_ratio: Current volume vs average
            timestamp: Optional timestamp

        Returns:
            FilterResult with alignment status
        """
        self._stats["total_checks"] += 1
        timestamp = timestamp or time.time()

        # Update calibrator
        self.calibrator.update(dl_probability)

        # Calibrate probability
        calibrated = self.calibrator.calibrate(dl_probability)

        # Check MA alignment (short > long for bullish)
        ma_aligned = technical_data.ma_short > technical_data.ma_long

        # Check Ichimoku alignment (price above cloud, tenkan > kijun)
        cloud_top = max(technical_data.ichimoku_senkou_a, technical_data.ichimoku_senkou_b)
        ichimoku_aligned = (
            technical_data.close > cloud_top and
            technical_data.ichimoku_tenkan > technical_data.ichimoku_kijun
        )

        # Volume confirmation
        volume_confirmed = volume_ratio >= 1.0

        # Calculate confidence
        confidence = self._calculate_confidence(
            calibrated, ma_aligned, ichimoku_aligned, volume_confirmed
        )

        if not ma_aligned:
            self._stats["rejected_ma"] += 1
        if not ichimoku_aligned:
            self._stats["rejected_ichimoku"] += 1

        return FilterResult(
            timestamp=timestamp,
            direction="LONG",
            confidence=confidence,
            dl_probability=dl_probability,
            ma_aligned=ma_aligned,
            ichimoku_aligned=ichimoku_aligned,
            volume_confirmed=volume_confirmed,
        )

    def check_short(
        self,
        dl_probability: float,
        technical_data: TechnicalData,
        volume_ratio: float = 1.0,
        timestamp: Optional[float] = None
    ) -> FilterResult:
        """Check short entry conditions.

        Args:
            dl_probability: Raw DL model probability for short
            technical_data: Current technical indicators
            volume_ratio: Current volume vs average
            timestamp: Optional timestamp

        Returns:
            FilterResult with alignment status
        """
        self._stats["total_checks"] += 1
        timestamp = timestamp or time.time()

        # Update calibrator
        self.calibrator.update(dl_probability)

        # Calibrate probability
        calibrated = self.calibrator.calibrate(dl_probability)

        # Check MA alignment (short < long for bearish)
        ma_aligned = technical_data.ma_short < technical_data.ma_long

        # Check Ichimoku alignment (price below cloud, tenkan < kijun)
        cloud_bottom = min(technical_data.ichimoku_senkou_a, technical_data.ichimoku_senkou_b)
        ichimoku_aligned = (
            technical_data.close < cloud_bottom and
            technical_data.ichimoku_tenkan < technical_data.ichimoku_kijun
        )

        # Volume confirmation
        volume_confirmed = volume_ratio >= 1.0

        # Calculate confidence
        confidence = self._calculate_confidence(
            calibrated, ma_aligned, ichimoku_aligned, volume_confirmed
        )

        if not ma_aligned:
            self._stats["rejected_ma"] += 1
        if not ichimoku_aligned:
            self._stats["rejected_ichimoku"] += 1

        return FilterResult(
            timestamp=timestamp,
            direction="SHORT",
            confidence=confidence,
            dl_probability=dl_probability,
            ma_aligned=ma_aligned,
            ichimoku_aligned=ichimoku_aligned,
            volume_confirmed=volume_confirmed,
        )

    def _calculate_confidence(
        self,
        dl_calibrated: float,
        ma_aligned: bool,
        ichimoku_aligned: bool,
        volume_confirmed: bool
    ) -> float:
        """Calculate weighted confidence score."""
        c = self.config

        # Base confidence from DL
        confidence = dl_calibrated * c.dl_weight

        # Add MA contribution
        if ma_aligned:
            confidence += c.ma_weight

        # Add Ichimoku contribution
        if ichimoku_aligned:
            confidence += c.ichimoku_weight

        # Volume bonus (small)
        if volume_confirmed:
            confidence += 0.05

        return min(confidence, 1.0)

    def check_multi_horizon(
        self,
        horizon_results: List[HorizonResult],
        direction: str
    ) -> Tuple[bool, float]:
        """Check multi-horizon confirmation.

        Args:
            horizon_results: Results from multiple prediction horizons
            direction: Expected direction ("LONG" or "SHORT")

        Returns:
            (confirmed, avg_confidence)
        """
        confirmed_count = 0
        total_prob = 0.0

        for result in horizon_results:
            if result.confirmed and result.direction == direction:
                confirmed_count += 1
                total_prob += result.probability

        confirmed = confirmed_count >= self.config.min_horizons_confirmed

        avg_confidence = total_prob / len(horizon_results) if horizon_results else 0.0

        return confirmed, avg_confidence

    def generate_signal(
        self,
        direction: str,
        dl_probability: float,
        technical_data: TechnicalData,
        current_price: float,
        volume_ratio: float = 1.0,
        timestamp: Optional[float] = None
    ) -> Optional[EnsembleSignal]:
        """Generate trading signal with stop/target levels.

        Args:
            direction: "LONG" or "SHORT"
            dl_probability: DL model probability
            technical_data: Technical indicator data
            current_price: Current market price
            volume_ratio: Volume ratio

        Returns:
            EnsembleSignal if valid, None otherwise
        """
        timestamp = timestamp or time.time()

        # Check entry conditions
        if direction == "LONG":
            filter_result = self.check_long(dl_probability, technical_data, volume_ratio, timestamp)
        else:
            filter_result = self.check_short(dl_probability, technical_data, volume_ratio, timestamp)

        # Calculate stop and target
        atr = technical_data.atr
        if direction == "LONG":
            stop_loss = current_price - (atr * self.config.atr_stop_multiplier)
            take_profit = current_price + (atr * self.config.atr_target_multiplier)
        else:
            stop_loss = current_price + (atr * self.config.atr_stop_multiplier)
            take_profit = current_price - (atr * self.config.atr_target_multiplier)

        # Track signal generation
        if direction == "LONG":
            self._stats["long_signals"] += 1
        else:
            self._stats["short_signals"] += 1

        return EnsembleSignal(
            timestamp=timestamp,
            direction=direction,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=self.config.default_position_size,
            filter_result=filter_result,
        )

    def get_stats(self) -> dict:
        """Return filter statistics."""
        return self._stats.copy()
