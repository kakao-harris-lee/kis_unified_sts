"""Regime detection models."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict


class RegimeState(str, Enum):
    """Market regime states."""
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    UNKNOWN = "UNKNOWN"


@dataclass
class RegimeSignal:
    """Regime detection signal."""
    state: RegimeState
    confidence: float
    timestamp: datetime
    indicators: Optional[Dict] = None

    @property
    def is_confident(self) -> bool:
        """Check if signal has high confidence."""
        return self.confidence >= 0.7


@dataclass
class RegimeConfig:
    """Configuration for regime detection."""
    lookback_period: int = 20
    sma_fast: int = 10
    sma_slow: int = 50
    volatility_window: int = 20
    trend_threshold: float = 0.02  # 2% threshold for trend
    confidence_threshold: float = 0.7
    # Volatility adjustment parameters (previously hardcoded)
    high_volatility_threshold: float = 0.03  # 3% volatility = high
    volatility_confidence_adjustment: float = 0.8  # Reduce confidence by 20%
