"""Indicator engine using Polars vector operations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from shared.strategy.entry.v35_optimized import V35Config

logger = logging.getLogger(__name__)


def _require_polars():
    try:
        import polars as pl  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("polars is required for core.indicator_engine") from e
    return pl


def _ewm_mean(expr: Any, *, span: int):
    try:
        return expr.ewm_mean(span=span, adjust=False)
    except TypeError:
        return expr.ewm_mean(span=span)


@dataclass(frozen=True)
class IndicatorEngineConfig:
    """Indicator engine configuration."""

    max_eval_rows: int = 800


class IndicatorEngine:
    """Compute indicator columns for strategy evaluation."""

    def __init__(
        self,
        v35_config: V35Config | None = None,
        config: IndicatorEngineConfig | None = None,
    ):
        self.v35 = v35_config or V35Config()
        self.config = config or IndicatorEngineConfig()

    def add_v35_indicators(self, df: Any):
        """Return DataFrame enriched with BB/RSI/MACD columns.

        Returns None if not enough rows.
        """
        pl = _require_polars()

        if df is None:
            return None

        # Bound rows for predictable cost
        df_eval = df.tail(self.config.max_eval_rows) if hasattr(df, "tail") else df

        min_rows = max(self.v35.bb_period, self.v35.rsi_period, self.v35.macd_slow) + 5
        if df_eval.height < min_rows:
            return None

        close = pl.col("close")

        # Bollinger Bands
        bb_mid = close.rolling_mean(window_size=int(self.v35.bb_period))
        bb_std = close.rolling_std(window_size=int(self.v35.bb_period))
        bb_lower = (bb_mid - float(self.v35.bb_std) * bb_std).alias("bb_lower")
        bb_upper = (bb_mid + float(self.v35.bb_std) * bb_std).alias("bb_upper")

        # RSI (rolling mean variant)
        delta = close.diff()
        gain = pl.when(delta > 0).then(delta).otherwise(0.0)
        loss = pl.when(delta < 0).then(-delta).otherwise(0.0)
        avg_gain = gain.rolling_mean(window_size=int(self.v35.rsi_period))
        avg_loss = loss.rolling_mean(window_size=int(self.v35.rsi_period))
        rs = avg_gain / avg_loss
        rsi = (
            pl.when(avg_loss == 0)
            .then(100.0)
            .otherwise(100.0 - (100.0 / (1.0 + rs)))
            .alias("rsi")
        )

        # MACD (EMA-based)
        ema_fast = _ewm_mean(close, span=int(self.v35.macd_fast))
        ema_slow = _ewm_mean(close, span=int(self.v35.macd_slow))
        macd_expr = ema_fast - ema_slow
        signal_expr = _ewm_mean(macd_expr, span=int(self.v35.macd_signal))
        hist_expr = macd_expr - signal_expr

        return df_eval.with_columns(
            [
                bb_lower,
                bb_upper,
                rsi,
                macd_expr.alias("macd"),
                signal_expr.alias("macd_signal"),
                hist_expr.alias("macd_hist"),
            ]
        )

