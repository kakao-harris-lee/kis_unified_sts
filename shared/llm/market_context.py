"""
MarketContext dataclass for LLM market analysis integration.

This module provides a structured representation of market conditions derived
from LLM analysis, including regime classification, sentiment, and risk scores.
MarketContext is published to Redis and consumed by trading strategies to
adjust entry/exit signals and position sizing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from shared.llm.data_classes import MarketSignal, RiskMode


@dataclass
class MarketContext:
    """Market context derived from LLM analysis.

    This dataclass encapsulates market regime, sentiment, and risk metrics
    that strategies can use to adjust their behavior. All fields have defaults
    to support partial initialization and graceful degradation.

    Attributes:
        regime: Market regime classification (e.g., 'BULL_STRONG', 'BEAR',
                'SIDEWAYS', 'NEUTRAL'). Free-form string to accommodate various
                LLM-generated regime types.
        overall_signal: Directional market signal (STRONG_BULLISH to STRONG_BEARISH).
        risk_mode: Risk appetite indicator (RISK_ON, NEUTRAL, RISK_OFF).
        risk_score: Aggregated risk score from 0 (low risk) to 100 (high risk).
                    Strategies can scale position sizes inversely with this score.
        confidence: LLM analysis confidence from 0.0 (no confidence) to 1.0
                    (maximum confidence). Strategies can boost/reduce signals
                    based on this value.
        sector_rotation: Dict mapping sector names to flow signals
                         (e.g., {'Technology': 'INFLOW', 'Energy': 'OUTFLOW'}).
        generated_at: Timestamp when this context was generated.
        metadata: Optional additional metadata from LLM analysis.
    """

    regime: str = "NEUTRAL"
    overall_signal: MarketSignal = MarketSignal.NEUTRAL
    risk_mode: RiskMode = RiskMode.NEUTRAL
    risk_score: float = 50.0  # 0-100 scale
    confidence: float = 0.5  # 0.0-1.0 scale
    sector_rotation: dict[str, str] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, str] | None = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dictionary for Redis storage.

        Converts enums to their string values and datetime to ISO format
        for JSON-compatible serialization.

        Returns:
            Dictionary representation suitable for Redis/JSON storage.
        """
        return {
            "regime": self.regime,
            "overall_signal": self.overall_signal.value,
            "risk_mode": self.risk_mode.value,
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            "sector_rotation": self.sector_rotation,
            "generated_at": self.generated_at.isoformat(),
            "metadata": self.metadata or {},
        }

    @classmethod
    def from_dict(cls, data: dict) -> MarketContext:
        """Deserialize from dictionary (Redis/JSON source).

        Reconstructs enums from string values and parses ISO datetime.
        Handles missing fields gracefully by using class defaults.

        Args:
            data: Dictionary representation from Redis or other source.

        Returns:
            MarketContext instance.

        Raises:
            ValueError: If enum values are invalid.
        """
        # Parse enums from string values
        overall_signal = MarketSignal.NEUTRAL
        if "overall_signal" in data:
            signal_value = data["overall_signal"]
            for signal in MarketSignal:
                if signal.value == signal_value:
                    overall_signal = signal
                    break

        risk_mode = RiskMode.NEUTRAL
        if "risk_mode" in data:
            mode_value = data["risk_mode"]
            for mode in RiskMode:
                if mode.value == mode_value:
                    risk_mode = mode
                    break

        # Parse datetime
        generated_at = datetime.now()
        if "generated_at" in data:
            try:
                generated_at = datetime.fromisoformat(data["generated_at"])
            except (ValueError, TypeError):
                pass  # Use default if parsing fails

        return cls(
            regime=data.get("regime", "NEUTRAL"),
            overall_signal=overall_signal,
            risk_mode=risk_mode,
            risk_score=float(data.get("risk_score", 50.0)),
            confidence=float(data.get("confidence", 0.5)),
            sector_rotation=data.get("sector_rotation", {}),
            generated_at=generated_at,
            metadata=data.get("metadata", {}),
        )

    def is_bullish(self) -> bool:
        """Check if overall market signal is bullish.

        Returns:
            True if overall_signal is BULLISH or STRONG_BULLISH.
        """
        return self.overall_signal in (MarketSignal.BULLISH, MarketSignal.STRONG_BULLISH)

    def is_bearish(self) -> bool:
        """Check if overall market signal is bearish.

        Returns:
            True if overall_signal is BEARISH or STRONG_BEARISH.
        """
        return self.overall_signal in (MarketSignal.BEARISH, MarketSignal.STRONG_BEARISH)

    def is_high_risk(self, threshold: float = 70.0) -> bool:
        """Check if risk score exceeds a threshold.

        Args:
            threshold: Risk score threshold (default 70.0).

        Returns:
            True if risk_score >= threshold.
        """
        return self.risk_score >= threshold

    def is_low_confidence(self, threshold: float = 0.4) -> bool:
        """Check if confidence is below a threshold.

        Args:
            threshold: Confidence threshold (default 0.4).

        Returns:
            True if confidence < threshold.
        """
        return self.confidence < threshold

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"MarketContext(regime={self.regime!r}, "
            f"signal={self.overall_signal.name}, "
            f"risk_mode={self.risk_mode.name}, "
            f"risk_score={self.risk_score:.1f}, "
            f"confidence={self.confidence:.2f})"
        )
