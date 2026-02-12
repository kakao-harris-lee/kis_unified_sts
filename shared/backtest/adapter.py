"""BacktestStrategyAdapter — bridges TradingStrategy → StrategyProtocol.

TradingStrategy (from the registry/factory) uses async check_entry(EntryContext)
returning Signal, while BacktestEngine expects sync on_bar(bar) → SignalType.
This adapter handles the conversion:

    1. Feeds each bar into StreamingIndicatorEngine to compute BB/RSI
    2. Builds EntryContext from bar + computed indicators
    3. Runs the async entry generator synchronously
    4. Maps Signal.metadata["signal_direction"] → SignalType.BUY / SELL / HOLD
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from services.trading.indicator_engine import StreamingIndicatorEngine
from shared.backtest.engine import SignalType
from shared.strategy.base import EntryContext, TradingStrategy

logger = logging.getLogger(__name__)


class BacktestStrategyAdapter:
    """Wraps TradingStrategy to implement StrategyProtocol for BacktestEngine."""

    def __init__(self, strategy: TradingStrategy, strategy_config: dict):
        self.name = strategy.name
        self._strategy = strategy

        entry_params = (
            strategy_config.get("strategy", {})
            .get("entry", {})
            .get("params", {})
        )
        bb_period = entry_params.get("bb_period", 20)
        bb_std = entry_params.get("bb_std", 2.0)
        rsi_period = entry_params.get("rsi_period", 14)

        self._indicator_engine = StreamingIndicatorEngine(
            bb_period=bb_period,
            bb_std=bb_std,
            rsi_period=rsi_period,
        )
        self._loop = asyncio.new_event_loop()

    def on_bar(self, bar: dict[str, Any]) -> SignalType:
        """Convert a bar dict into a BUY/SELL/HOLD signal."""
        code = str(bar.get("code", "BACKTEST") or "BACKTEST")

        # Feed bar as a completed candle
        self._indicator_engine.seed_candles(code, [bar])

        # Need warmup before generating signals
        if not self._indicator_engine.is_warm(code):
            return SignalType.HOLD

        indicators = self._indicator_engine.get_indicators(code)

        # Derive market_state from MFI so MeanReversionEntry's market_state_filter works
        mfi = indicators.get("mfi")
        if mfi is not None:
            if mfi >= 43:
                market_state = "SIDEWAYS_FLAT"
            elif mfi >= 41:
                market_state = "SIDEWAYS_DOWN"
            else:
                market_state = "BEAR"
        else:
            market_state = "SIDEWAYS_FLAT"

        timestamp = bar.get("datetime", datetime.now())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        context = EntryContext(
            market_data=bar,
            indicators=indicators,
            current_positions=[],
            timestamp=timestamp,
            metadata={"market_state": market_state},
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
