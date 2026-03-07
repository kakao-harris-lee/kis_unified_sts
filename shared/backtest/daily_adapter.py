"""DailyBacktestAdapter — bridges daily TradingStrategy → StrategyProtocol.

일봉 전략을 BacktestEngine에 연결하기 위한 어댑터.
1분봉 어댑터(BacktestStrategyAdapter)와 달리 StreamingIndicatorEngine을 사용하지 않고,
pandas rolling으로 SMA/RSI/ATR을 사전 계산하여 on_bar()에서 조회합니다.

Usage:
    adapted = DailyBacktestAdapter(trading_strategy, strategy_config)
    engine = BacktestEngine(adapted, config)
    result = engine.run(daily_df)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from shared.backtest.engine import ExitReason, SignalType
from shared.backtest.metadata import load_backtest_metadata, resolve_symbol_metadata
from shared.models.position import Position as ModelPosition, PositionSide
from shared.strategy.base import EntryContext, ExitContext, TradingStrategy

logger = logging.getLogger(__name__)


class DailyBacktestAdapter:
    """Wraps daily TradingStrategy to implement StrategyProtocol for BacktestEngine.

    Pre-computes all indicators (SMA, RSI, ATR, Highest High) from the daily DataFrame
    before the backtest loop starts, then looks them up per bar.
    """

    def __init__(self, strategy: TradingStrategy, strategy_config: dict):
        self.name = strategy.name
        self._strategy = strategy
        self._loop = asyncio.new_event_loop()
        self._backtest_metadata = load_backtest_metadata(strategy_config)

        entry_params = (
            strategy_config.get("strategy", {})
            .get("entry", {})
            .get("params", {})
        )
        exit_params = (
            strategy_config.get("strategy", {})
            .get("exit", {})
            .get("params", {})
        )

        # Entry indicator periods
        self._sma_long = entry_params.get("sma_long_period", 200)
        self._sma_short = entry_params.get("sma_short_period", 20)
        self._sma_mid = entry_params.get("sma_mid_period", 60)
        self._rsi_period = entry_params.get("rsi_period", 5)
        self._mid_trend_lookback = entry_params.get("mid_trend_lookback", 5)

        # Exit indicator periods
        self._atr_period = exit_params.get("atr_period", 22)
        self._lookback_period = exit_params.get("lookback_period", 22)

        # Pre-computed indicators: index → dict of indicators
        self._precomputed: list[dict[str, float]] = []
        self._bar_index: int = 0

        # Raw daily series for strategies that compute their own indicators (e.g. VR composite)
        self._raw_closes: list[float] = []
        self._raw_volumes: list[int] = []
        self._series_window: int = entry_params.get("vr_period", 0) + entry_params.get("ma_long", 0) + 10
        if self._series_window < 80:
            self._series_window = 80

        # Warmup indicator key: strategy-dependent
        # daily_pullback needs sma_200; vr_composite computes its own indicators
        self._warmup_key = "sma_200" if self._sma_long >= 100 else None
        self._warmup_bars = max(
            self._sma_long,
            entry_params.get("vr_period", 20) + entry_params.get("ma_long", 60),
        )

        # Position state (synced from BacktestEngine)
        self._current_position: dict[str, Any] | None = None
        self._entry_bar_index: int | None = None

    def _context_metadata(self, code: str, market_state: str = "UNKNOWN") -> dict[str, Any]:
        """Build metadata payload aligned with live orchestrator context."""
        return {
            "market_state": market_state,
            "regime": market_state,
            "is_backtest": True,
            "symbol_metadata": resolve_symbol_metadata(self._backtest_metadata, code),
            "daily_watchlist": self._backtest_metadata.get("daily_watchlist", {}),
            "dip_candidates": self._backtest_metadata.get("dip_candidates", {}),
            "accumulation_candidates": self._backtest_metadata.get(
                "accumulation_candidates", {}
            ),
        }

    def prescan_data(self, data: pd.DataFrame) -> None:
        """Pre-compute all indicators for the entire daily DataFrame.

        Computes SMA(200), SMA(20), SMA(60), RSI(5), ATR(22), Highest High(22).
        """
        df = data.copy()

        # SMA
        df["sma_200"] = df["close"].rolling(window=self._sma_long, min_periods=self._sma_long).mean()
        df["sma_20"] = df["close"].rolling(window=self._sma_short, min_periods=self._sma_short).mean()
        df["sma_60"] = df["close"].rolling(window=self._sma_mid, min_periods=self._sma_mid).mean()
        df["sma_60_prev"] = df["sma_60"].shift(self._mid_trend_lookback)

        # RSI
        df["rsi_5"] = self._compute_rsi(df["close"], self._rsi_period)

        # ATR (True Range based)
        high = df["high"]
        low = df["low"]
        prev_close = df["close"].shift(1)
        tr = pd.concat([
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=self._atr_period, min_periods=self._atr_period).mean()

        # Highest High (lookback)
        df["highest_high"] = df["high"].rolling(window=self._lookback_period, min_periods=1).max()

        # Store as list of dicts for O(1) lookup
        indicator_cols = ["sma_200", "sma_20", "sma_60", "sma_60_prev", "rsi_5", "atr", "highest_high"]
        self._precomputed = df[indicator_cols].to_dict("records")
        self._bar_index = 0

        # Store raw series for strategies that need rolling windows (VR composite)
        self._raw_closes = df["close"].astype(float).tolist()
        self._raw_volumes = df["volume"].astype(int).tolist()

        warmup = self._warmup_bars
        valid_count = sum(1 for r in self._precomputed if not np.isnan(r.get("sma_200", float("nan"))))
        logger.info(
            f"DailyBacktestAdapter: pre-computed {len(self._precomputed)} bars, "
            f"{valid_count} valid (warmup={warmup})"
        )

    @staticmethod
    def _compute_rsi(series: pd.Series, period: int) -> pd.Series:
        """Compute RSI using exponential moving average (Wilder's method)."""
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, float("nan"))
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def set_position(self, position: dict[str, Any] | None) -> None:
        """BacktestEngine → adapter position sync."""
        prev = self._current_position
        self._current_position = position
        if position is not None and prev is None:
            # New position opened — record entry bar
            self._entry_bar_index = self._bar_index

    def check_exit(self, bar: dict[str, Any]) -> tuple[bool, ExitReason | None]:
        """Check exit strategy for current position."""
        if not self._current_position:
            return (False, None)

        code = str(bar.get("code", "BACKTEST") or "BACKTEST")
        timestamp = bar.get("datetime", datetime.now())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        symbol_meta = resolve_symbol_metadata(self._backtest_metadata, code)
        if symbol_meta:
            bar.update(symbol_meta)

        # Get pre-computed indicators
        indicators: dict[str, Any] = {}
        idx = max(0, self._bar_index - 1)  # Exit sees same bar's indicators
        if idx < len(self._precomputed):
            indicators = {k: v for k, v in self._precomputed[idx].items() if not np.isnan(v)}

        # Include rolling daily series for exit (VR composite exit needs them)
        bar_end = idx + 1
        bar_start = max(0, bar_end - self._series_window)
        if bar_end <= len(self._raw_closes):
            indicators["daily_closes"] = self._raw_closes[bar_start:bar_end]
            indicators["daily_volumes"] = self._raw_volumes[bar_start:bar_end]

        # Calculate holding days
        if self._entry_bar_index is not None:
            holding_days = self._bar_index - self._entry_bar_index
        else:
            holding_days = 0
        indicators["holding_days"] = holding_days

        # Build Position model
        pos = self._current_position
        entry_time = pos.get("entry_time", timestamp)
        if isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time)
        entry_price = float(pos["entry_price"])
        highest_price = float(pos.get("highest_price", entry_price) or entry_price)
        lowest_price = float(pos.get("lowest_price", entry_price) or entry_price)
        position = ModelPosition(
            id=f"bt_{code}",
            code=code,
            name=code,
            strategy=self.name,
            side=PositionSide.LONG if pos["side"] == "BUY" else PositionSide.SHORT,
            entry_price=entry_price,
            quantity=pos["quantity"],
            entry_time=entry_time,
            current_price=float(bar.get("close", 0) or 0),
            highest_price=highest_price,
            lowest_price=lowest_price,
        )

        context = ExitContext(
            position=position,
            market_data=bar,
            indicators=indicators,
            timestamp=timestamp,
            metadata=self._context_metadata(code),
        )

        try:
            should_exit, exit_signal = self._loop.run_until_complete(
                self._strategy.check_exit(context)
            )
        except Exception:
            logger.debug("Exit strategy error", exc_info=True)
            return (False, None)

        if should_exit and exit_signal:
            reason_value = exit_signal.reason.value
            try:
                return (True, ExitReason(reason_value))
            except ValueError:
                return (True, ExitReason.STRATEGY_EXIT)

        return (False, None)

    def on_bar(self, bar: dict[str, Any]) -> SignalType:
        """Convert a daily bar dict into a BUY/SELL/HOLD signal."""
        code = str(bar.get("code", "BACKTEST") or "BACKTEST")

        timestamp = bar.get("datetime", datetime.now())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        symbol_meta = resolve_symbol_metadata(self._backtest_metadata, code)
        if symbol_meta:
            bar.update(symbol_meta)

        # Get pre-computed indicators for this bar
        indicators: dict[str, Any] = {}
        if self._bar_index < len(self._precomputed):
            indicators = {
                k: v for k, v in self._precomputed[self._bar_index].items()
                if not np.isnan(v)
            }

        # Include rolling daily series (for VR composite and similar strategies)
        bar_end = self._bar_index + 1
        bar_start = max(0, bar_end - self._series_window)
        if bar_end <= len(self._raw_closes):
            indicators["daily_closes"] = self._raw_closes[bar_start:bar_end]
            indicators["daily_volumes"] = self._raw_volumes[bar_start:bar_end]

        self._bar_index += 1

        # Skip if warmup not complete
        if self._warmup_key and self._warmup_key not in indicators:
            return SignalType.HOLD
        if not self._warmup_key and self._bar_index < self._warmup_bars:
            return SignalType.HOLD

        context = EntryContext(
            market_data=bar,
            indicators=indicators,
            current_positions=[],
            timestamp=timestamp,
            metadata=self._context_metadata(code),
        )

        try:
            signal = self._loop.run_until_complete(
                self._strategy.check_entry(context)
            )
        except Exception:
            logger.debug("Entry generator error", exc_info=True)
            return SignalType.HOLD

        if signal is None:
            return SignalType.HOLD

        direction = signal.metadata.get("signal_direction", "long")
        if direction == "long":
            return SignalType.BUY
        elif direction == "short":
            return SignalType.SELL

        return SignalType.HOLD


def load_stock_daily_from_clickhouse(
    code: str,
    start_date=None,
    end_date=None,
) -> pd.DataFrame:
    """Load stock daily data from ClickHouse market.daily_candles.

    Returns DataFrame with columns: code, datetime, open, high, low, close, volume
    Compatible with BacktestEngine (uses 'datetime' column name).
    """
    import os

    import clickhouse_connect

    from shared.config.tls import get_clickhouse_tls_params

    tls_params = get_clickhouse_tls_params()

    client = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        **tls_params,
    )

    # Build parameterized query to prevent SQL injection
    conditions = ["code = {code:String}"]
    parameters = {"code": code}

    if start_date:
        conditions.append("date >= {start:Date}")
        parameters["start"] = start_date
    if end_date:
        conditions.append("date <= {end:Date}")
        parameters["end"] = end_date

    where = " AND ".join(conditions)
    query = f"""
        SELECT code, date, open, high, low, close, volume
        FROM market.daily_candles
        WHERE {where}
        ORDER BY date ASC
    """

    result = client.query(query, parameters=parameters)
    if not result.result_rows:
        raise ValueError(f"No daily data found for {code}")

    df = pd.DataFrame(
        result.result_rows,
        columns=["code", "datetime", "open", "high", "low", "close", "volume"],
    )

    # Convert date to datetime for BacktestEngine compatibility
    df["datetime"] = pd.to_datetime(df["datetime"])

    logger.info(f"Loaded {len(df)} daily bars for {code}")
    return df
