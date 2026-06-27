"""Adaptive regime detector with multi-metric classification.

Combines MFI, ADX, volatility (ATR ratio), and trend (SMA crossover)
to classify market into enhanced regime states.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import numpy as np
import pandas as pd

from shared.utils.math import safe_divide

from .models import RegimeSignal

logger = logging.getLogger(__name__)


class AdaptiveRegimeState(StrEnum):
    """Enhanced market regime states with multi-metric classification."""

    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"
    VOLATILE_SIDEWAYS = "VOLATILE_SIDEWAYS"
    CALM_SIDEWAYS = "CALM_SIDEWAYS"
    MEAN_REVERTING = "MEAN_REVERTING"
    UNKNOWN = "UNKNOWN"


@dataclass
class AdaptiveRegimeConfig:
    """Configuration for adaptive regime detection.

    Thresholds for multi-metric classification combining:
    - MFI (Money Flow Index): momentum/volume indicator
    - ADX (Average Directional Index): trend strength
    - Volatility (ATR ratio): market volatility
    - Trend (SMA crossover): price trend direction
    """

    # MFI thresholds
    mfi_bull_threshold: float = 60.0  # MFI > 60 = strong buying pressure
    mfi_bear_threshold: float = 40.0  # MFI < 40 = strong selling pressure
    mfi_period: int = 14

    # ADX thresholds (trend strength)
    adx_strong_trend: float = 25.0  # ADX > 25 = strong trend
    adx_weak_trend: float = 20.0    # ADX < 20 = weak/no trend
    adx_period: int = 14

    # Volatility thresholds (ATR ratio)
    atr_period: int = 14
    atr_high_volatility: float = 0.025  # ATR/price > 2.5% = high volatility
    atr_low_volatility: float = 0.015   # ATR/price < 1.5% = low volatility

    # Trend thresholds (SMA crossover)
    sma_fast: int = 10
    sma_slow: int = 50
    trend_threshold: float = 0.01  # 1% SMA difference = trending

    # Confidence calculation
    confidence_threshold: float = 0.7  # Minimum confidence for signal
    min_bars: int = 50  # Minimum bars required for detection

    @classmethod
    def from_yaml_dict(cls, regime_cfg_dict: dict) -> "AdaptiveRegimeConfig":
        """Create config from parsed regime_adaptive.yaml dict.

        Handles the nested YAML structure:
            detector.thresholds.{mfi,adx,volatility,trend}
            detector.lookback.{mfi_period,adx_period,...}
            detector.confidence.{min_confidence}

        Args:
            regime_cfg_dict: Full dict loaded from ml/regime_adaptive.yaml

        Returns:
            AdaptiveRegimeConfig with values from YAML (or defaults)
        """
        detector_cfg = regime_cfg_dict.get("detector", {})
        thresholds = detector_cfg.get("thresholds", {})
        lookback = detector_cfg.get("lookback", {})
        confidence = detector_cfg.get("confidence", {})

        return cls(
            mfi_bull_threshold=thresholds.get("mfi", {}).get("neutral_upper", 60.0),
            mfi_bear_threshold=thresholds.get("mfi", {}).get("neutral_lower", 40.0),
            mfi_period=lookback.get("mfi_period", 14),
            adx_strong_trend=thresholds.get("adx", {}).get("strong_trend", 25.0),
            adx_weak_trend=thresholds.get("adx", {}).get("weak_trend", 20.0),
            adx_period=lookback.get("adx_period", 14),
            atr_period=lookback.get("atr_period", 14),
            atr_high_volatility=thresholds.get("volatility", {}).get("high", 0.025),
            atr_low_volatility=thresholds.get("volatility", {}).get("low", 0.015),
            sma_fast=lookback.get("sma_short", 10),
            sma_slow=lookback.get("sma_long", 50),
            trend_threshold=thresholds.get("trend", {}).get("bullish_threshold", 0.01),
            confidence_threshold=confidence.get("min_confidence", 0.7),
            min_bars=lookback.get("min_bars", 50),
        )


class AdaptiveRegimeDetector:
    """Detect market regime using multi-metric classification.

    Combines:
    1. MFI (Money Flow Index) - momentum + volume
    2. ADX (Average Directional Index) - trend strength
    3. ATR ratio - volatility measurement
    4. SMA crossover - trend direction

    Confidence is based on metric agreement:
    - High confidence (>0.8): All metrics agree
    - Medium confidence (0.6-0.8): Majority agreement
    - Low confidence (<0.6): Mixed signals

    Usage:
        detector = AdaptiveRegimeDetector()
        signal = detector.detect(df)
        if signal.is_confident:
            print(f"Regime: {signal.state} (confidence: {signal.confidence})")
    """

    def __init__(self, config: AdaptiveRegimeConfig | None = None):
        """Initialize detector.

        Args:
            config: Adaptive regime configuration. Uses defaults if None.
        """
        self.config = config or AdaptiveRegimeConfig()
        self._last_signal: RegimeSignal | None = None

    def detect(self, df: pd.DataFrame) -> RegimeSignal:
        """Detect current market regime.

        Args:
            df: DataFrame with OHLCV columns (open, high, low, close, volume)
                Must have at least config.min_bars rows

        Returns:
            RegimeSignal with detected state, confidence, and indicators
        """
        # Validate input
        if len(df) < self.config.min_bars:
            return self._unknown_signal(
                reason=f"Insufficient data: {len(df)} < {self.config.min_bars}"
            )

        required_cols = ["close", "high", "low", "volume"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return self._unknown_signal(
                reason=f"Missing columns: {missing_cols}"
            )

        # Calculate all indicators
        try:
            indicators = self._calculate_indicators(df)
        except Exception as e:
            logger.error(f"Indicator calculation failed: {e}")
            return self._unknown_signal(reason=f"Calculation error: {e}")

        # Classify regime based on multi-metric analysis
        state, confidence = self._classify_regime(indicators)

        signal = RegimeSignal(
            state=state,
            confidence=confidence,
            timestamp=datetime.now(),
            indicators=indicators,
            confidence_threshold=self.config.confidence_threshold,
        )

        self._last_signal = signal
        return signal

    def _calculate_indicators(self, df: pd.DataFrame) -> dict:
        """Calculate all indicators for regime detection.

        Args:
            df: OHLCV DataFrame

        Returns:
            dict with indicator values
        """
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values

        # 1. MFI (Money Flow Index)
        mfi = self._calc_mfi(df, period=self.config.mfi_period)

        # 2. ADX (Average Directional Index)
        adx = self._calc_adx(high, low, close, period=self.config.adx_period)

        # 3. ATR ratio (volatility)
        atr = self._calc_atr(high, low, close, period=self.config.atr_period)
        atr_ratio = safe_divide(atr, close[-1], default=0.0)

        # 4. SMA trend
        sma_fast = pd.Series(close).rolling(self.config.sma_fast).mean().iloc[-1]
        sma_slow = pd.Series(close).rolling(self.config.sma_slow).mean().iloc[-1]
        trend_pct = safe_divide(sma_fast - sma_slow, sma_slow, default=0.0)

        return {
            "mfi": mfi,
            "adx": adx,
            "atr": atr,
            "atr_ratio": atr_ratio,
            "sma_fast": sma_fast,
            "sma_slow": sma_slow,
            "trend_pct": trend_pct,
            "close": close[-1],
        }

    def _classify_regime(self, indicators: dict) -> tuple[AdaptiveRegimeState, float]:
        """Classify regime based on multi-metric analysis.

        Args:
            indicators: Dictionary of calculated indicators

        Returns:
            Tuple of (regime_state, confidence_score)
        """
        mfi = indicators["mfi"]
        adx = indicators["adx"]
        atr_ratio = indicators["atr_ratio"]
        trend_pct = indicators["trend_pct"]

        # Metric votes and confidence tracking
        votes = {
            "trending_bull": 0,
            "trending_bear": 0,
            "volatile_sideways": 0,
            "calm_sideways": 0,
            "mean_reverting": 0,
        }

        total_confidence = 0.0
        metric_count = 0

        # 1. MFI analysis (momentum + volume)
        if mfi > self.config.mfi_bull_threshold:
            votes["trending_bull"] += 1
            total_confidence += min(1.0, (mfi - 50) / 50)  # Scale 50-100 to 0-1
            metric_count += 1
        elif mfi < self.config.mfi_bear_threshold:
            votes["trending_bear"] += 1
            total_confidence += min(1.0, (50 - mfi) / 50)  # Scale 0-50 to 1-0
            metric_count += 1
        else:
            # Mean reverting or sideways
            votes["mean_reverting"] += 0.5
            votes["calm_sideways"] += 0.5
            total_confidence += 0.5
            metric_count += 1

        # 2. ADX analysis (trend strength)
        if adx > self.config.adx_strong_trend:
            # Strong trend - reinforce trending votes
            if trend_pct > self.config.trend_threshold:
                votes["trending_bull"] += 1
            elif trend_pct < -self.config.trend_threshold:
                votes["trending_bear"] += 1
            total_confidence += min(1.0, adx / 50)  # Scale ADX to confidence
            metric_count += 1
        elif adx < self.config.adx_weak_trend:
            # Weak trend - sideways or mean reverting
            votes["calm_sideways"] += 1
            votes["mean_reverting"] += 0.5
            total_confidence += 0.6
            metric_count += 1
        else:
            # Moderate trend
            total_confidence += 0.7
            metric_count += 1

        # 3. Volatility analysis (ATR ratio)
        if atr_ratio > self.config.atr_high_volatility:
            votes["volatile_sideways"] += 1
            total_confidence += 0.8  # High volatility = more certain signal
            metric_count += 1
        elif atr_ratio < self.config.atr_low_volatility:
            votes["calm_sideways"] += 1
            votes["mean_reverting"] += 0.5  # Low vol often precedes mean reversion
            total_confidence += 0.9  # Low volatility = very stable
            metric_count += 1
        else:
            # Normal volatility
            total_confidence += 0.7
            metric_count += 1

        # 4. Trend analysis (SMA crossover)
        if abs(trend_pct) > self.config.trend_threshold:
            if trend_pct > 0:
                votes["trending_bull"] += 1
            else:
                votes["trending_bear"] += 1
            total_confidence += min(1.0, abs(trend_pct) * 50)  # Scale to confidence
            metric_count += 1
        else:
            # Flat trend - mean reverting
            votes["mean_reverting"] += 1
            votes["calm_sideways"] += 0.5
            total_confidence += 0.8
            metric_count += 1

        # Determine winning regime
        max_votes = max(votes.values())
        winners = [k for k, v in votes.items() if v == max_votes]

        # If tie, use volatility as tiebreaker
        if len(winners) > 1:
            if atr_ratio > self.config.atr_high_volatility:
                regime_key = "volatile_sideways"
            elif atr_ratio < self.config.atr_low_volatility:
                regime_key = "calm_sideways"
            else:
                regime_key = winners[0]  # Default to first winner
        else:
            regime_key = winners[0]

        # Map to enum
        regime_map = {
            "trending_bull": AdaptiveRegimeState.TRENDING_BULL,
            "trending_bear": AdaptiveRegimeState.TRENDING_BEAR,
            "volatile_sideways": AdaptiveRegimeState.VOLATILE_SIDEWAYS,
            "calm_sideways": AdaptiveRegimeState.CALM_SIDEWAYS,
            "mean_reverting": AdaptiveRegimeState.MEAN_REVERTING,
        }

        state = regime_map[regime_key]

        # Calculate final confidence based on vote agreement
        vote_ratio = max_votes / sum(votes.values()) if sum(votes.values()) > 0 else 0
        avg_confidence = total_confidence / metric_count if metric_count > 0 else 0

        # Confidence = weighted average of vote agreement and metric confidence
        confidence = 0.6 * vote_ratio + 0.4 * avg_confidence
        confidence = min(1.0, max(0.0, confidence))  # Clamp to [0, 1]

        return state, confidence

    def _calc_mfi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Money Flow Index.

        Args:
            df: OHLCV DataFrame
            period: MFI period

        Returns:
            MFI value (0-100)
        """
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        money_flow = typical_price * df["volume"]

        # Positive and negative money flow
        positive_flow = []
        negative_flow = []

        for i in range(1, len(df)):
            if typical_price.iloc[i] > typical_price.iloc[i-1]:
                positive_flow.append(money_flow.iloc[i])
                negative_flow.append(0)
            elif typical_price.iloc[i] < typical_price.iloc[i-1]:
                positive_flow.append(0)
                negative_flow.append(money_flow.iloc[i])
            else:
                positive_flow.append(0)
                negative_flow.append(0)

        if len(positive_flow) < period:
            return 50.0  # Neutral

        # Calculate MFI
        positive_mf = sum(positive_flow[-period:])
        negative_mf = sum(negative_flow[-period:])

        if negative_mf == 0:
            return 100.0

        money_ratio = positive_mf / negative_mf
        mfi = 100 - (100 / (1 + money_ratio))

        return float(mfi)

    def _calc_adx(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> float:
        """Calculate Average Directional Index.

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ADX period

        Returns:
            ADX value (0-100)
        """
        if len(high) < period + 1:
            return 0.0

        # Calculate directional movement
        plus_dm = np.maximum(high[1:] - high[:-1], 0)
        minus_dm = np.maximum(low[:-1] - low[1:], 0)

        # True range
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))

        # Smooth indicators
        atr = pd.Series(tr).rolling(period).mean().iloc[-1]

        if atr == 0:
            return 0.0

        plus_di = 100 * pd.Series(plus_dm).rolling(period).mean().iloc[-1] / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(period).mean().iloc[-1] / atr

        # ADX calculation
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) != 0 else 0

        return float(dx)

    def _calc_atr(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> float:
        """Calculate Average True Range.

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period

        Returns:
            ATR value
        """
        if len(high) < 2:
            return 0.0

        # True range components
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])

        # Maximum of the three
        tr = np.maximum(tr1, np.maximum(tr2, tr3))

        # Average over period
        if len(tr) < period:
            return float(np.mean(tr))

        atr = pd.Series(tr).rolling(period).mean().iloc[-1]
        return float(atr) if pd.notna(atr) else 0.0

    def _unknown_signal(self, reason: str = "") -> RegimeSignal:
        """Create UNKNOWN regime signal.

        Args:
            reason: Reason for unknown state

        Returns:
            RegimeSignal with UNKNOWN state and 0.0 confidence
        """
        if reason:
            logger.debug(f"Regime detection returned UNKNOWN: {reason}")

        return RegimeSignal(
            state=AdaptiveRegimeState.UNKNOWN,
            confidence=0.0,
            timestamp=datetime.now(),
            indicators={"reason": reason},
            confidence_threshold=self.config.confidence_threshold,
        )

    @property
    def last_signal(self) -> RegimeSignal | None:
        """Get last detected signal."""
        return self._last_signal
