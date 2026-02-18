"""Strategy engine operating on StateManager Polars frames.

Implements V35 entry logic (BB lower band + RSI oversold + MACD hist positive)
using Polars vector operations.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from shared.models.signal import Signal, SignalType
from core.indicator_engine import IndicatorEngine, _IndicatorDefaults

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StrategyEngineConfig:
    """Runtime knobs for strategy evaluation."""

    max_eval_rows: int = int(os.environ.get("ENGINE_MAX_EVAL_ROWS", "800"))


class StrategyEngine:
    """Evaluates V35OptimizedEntry conditions on OHLCV frames."""

    def __init__(
        self,
        *,
        v35_config: _IndicatorDefaults | None = None,
        config: StrategyEngineConfig | None = None,
        indicator_engine: IndicatorEngine | None = None,
    ):
        self.config = config or StrategyEngineConfig()
        self.v35 = v35_config or _IndicatorDefaults()
        self.indicators = indicator_engine or IndicatorEngine(self.v35)

    def evaluate_frames(self, frames: dict[str, Any]) -> list[Signal]:
        """Evaluate all frames and return entry signals."""
        signals: list[Signal] = []
        for code, df in frames.items():
            try:
                s = self.evaluate_frame(code, df)
                if s is not None:
                    signals.append(s)
            except Exception as e:
                logger.debug(f"Strategy evaluation failed ({code}): {e}")
        return signals

    def evaluate_frame(self, code: str, df: Any) -> Signal | None:
        """Evaluate a single symbol frame.

        Expects OHLCV columns: datetime, close (optionally: code, name).
        """
        if df is None:
            return None

        enriched = self.indicators.add_v35_indicators(df)
        if enriched is None:
            return None

        last = enriched.tail(1).select(
            [
                "datetime",
                "close",
                "bb_lower",
                "rsi",
                "macd_hist",
            ]
        )
        row = last.to_dicts()[0]

        close_v = float(row.get("close") or 0.0)
        bb_lower_v = float(row.get("bb_lower") or 0.0)
        rsi_v = float(row.get("rsi") or 50.0)
        macd_hist_v = float(row.get("macd_hist") or 0.0)

        if not (close_v < bb_lower_v and rsi_v < float(self.v35.rsi_oversold) and macd_hist_v > 0):
            return None

        confidence = self._calculate_confidence(rsi_v, macd_hist_v)
        ts = row.get("datetime")
        if isinstance(ts, datetime):
            when = ts
        else:
            when = datetime.now()

        return Signal(
            code=code,
            signal_type=SignalType.ENTRY,
            strategy="v35_optimized_polars",
            price=close_v,
            confidence=confidence,
            timestamp=when,
            metadata={
                "bb_lower": bb_lower_v,
                "rsi": rsi_v,
                "macd_hist": macd_hist_v,
            },
        )

    def _calculate_confidence(self, rsi: float, macd_hist: float) -> float:
        if self.v35.rsi_oversold <= 0:
            rsi_score = 0.5
        else:
            rsi_score = min(
                1.0, max(0.0, (float(self.v35.rsi_oversold) - rsi) / float(self.v35.rsi_oversold))
            )

        if macd_hist <= 0:
            macd_score = 0.0
        else:
            macd_score = min(
                1.0,
                max(0.0, macd_hist / float(self.v35.macd_normalization_factor)),
            )

        return (rsi_score + macd_score) / 2.0
