"""Trend-day trailing exit (futures, long/short symmetric).

Designed for ``orb_trend_day``: cut losers fast, let the rare trend-day winner
run. Priority cascade per position:

1. Catastrophic / hard stop: ``stop_atr_mult`` * entry-ATR from entry.
2. Breakeven ratchet: once ``breakeven_activation_atr`` in favor, the stop never
   goes worse than entry.
3. ATR trailing stop: once ``trail_activation_atr`` in favor, trail by
   ``trail_atr_mult`` * ATR from the best price (high since entry for long, low for
   short). This captures the trend runner.
4. EOD flatten (KST): futures are intraday — flatten by ``eod_flatten_time``.

Futures-only intraday EOD flatten does not violate the stock no-blanket-EOD rule
(that rule is stock-specific; futures positions are day-bounded by nature).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import time
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.models.position import PositionSide
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator, MarketStateProtocol
from shared.strategy.market_time import now_kst, to_kst

logger = logging.getLogger(__name__)


@dataclass
class TrendTrailExitConfig(ConfigMixin):
    """Configuration for the trend-day trailing exit."""

    atr_period: int = 14
    stop_atr_mult: float = 1.5
    breakeven_activation_atr: float = 1.0
    trail_activation_atr: float = 1.5
    trail_atr_mult: float = 2.0

    eod_flatten_enabled: bool = True
    eod_flatten_hour: int = 15
    eod_flatten_minute: int = 15

    default_exit_confidence: float = 0.85

    def validate(self) -> None:
        assert self.stop_atr_mult > 0, "stop_atr_mult must be positive"
        assert (
            self.breakeven_activation_atr >= 0
        ), "breakeven_activation_atr must be >= 0"
        assert self.trail_activation_atr >= 0, "trail_activation_atr must be >= 0"
        assert self.trail_atr_mult > 0, "trail_atr_mult must be positive"
        assert 0 <= self.eod_flatten_hour <= 23, "eod_flatten_hour out of range"
        assert 0 <= self.eod_flatten_minute <= 59, "eod_flatten_minute out of range"
        assert (
            0 < self.default_exit_confidence <= 1.0
        ), "default_exit_confidence must be in (0, 1]"


class TrendTrailExit(ExitSignalGenerator[TrendTrailExitConfig]):
    """ATR trailing exit with breakeven ratchet and EOD flatten (long/short)."""

    CONFIG_CLASS = TrendTrailExitConfig

    def __init__(self, config: TrendTrailExitConfig):
        super().__init__(config)

    def _validate_config(self) -> None:
        self.config.validate()

    @property
    def name(self) -> str:
        return "trend_trail_exit"

    @staticmethod
    def _atr_points(
        indicators: dict[str, Any], data: dict[str, Any], close: float
    ) -> float:
        """Resolve ATR in price points from indicators/market data."""
        for src in (indicators, data):
            raw = src.get("atr")
            if raw is None:
                continue
            atr = float(raw)
            if atr > 0 and atr < 0.5 and close > 0:
                return atr * close
            if atr > 0:
                return atr
        return 0.0

    def _build_signal(
        self,
        *,
        position: Any,
        close: float,
        profit_pct: float,
        reason: ExitReason,
        priority: int,
        exit_type: str,
        extra: dict[str, Any] | None = None,
    ) -> ExitSignal:
        meta = {"exit_type": exit_type}
        if extra:
            meta.update(extra)
        return ExitSignal(
            code=position.code,
            name=getattr(position, "name", position.code),
            position_id=getattr(position, "id", ""),
            reason=reason,
            strategy=self.name,
            current_price=close,
            exit_price=close,
            entry_price=position.entry_price,
            profit_pct=profit_pct,
            confidence=self.config.default_exit_confidence,
            priority=priority,
            quantity=getattr(position, "quantity", 0),
            metadata=meta,
        )

    async def should_exit(self, context: ExitContext) -> tuple[bool, ExitSignal | None]:
        position = context.position
        data = context.market_data or {}
        indicators = context.indicators or {}

        close = float(data.get("close", 0) or 0)
        if close <= 0:
            return (False, None)

        entry_price = float(position.entry_price)
        if entry_price <= 0:
            return (False, None)

        is_long = position.side == PositionSide.LONG
        now = context.timestamp or now_kst()

        # Direction-aware profit pct.
        if is_long:
            profit_pct = (close - entry_price) / entry_price
        else:
            profit_pct = (entry_price - close) / entry_price

        # ATR in points: prefer the entry-time ATR (stable stop distance), else live.
        entry_atr = float((position.metadata or {}).get("entry_atr", 0.0) or 0.0)
        live_atr = self._atr_points(indicators, data, close)
        atr = entry_atr if entry_atr > 0 else live_atr

        # --- Priority 1: hard / catastrophic stop ---
        if atr > 0:
            stop_dist = self.config.stop_atr_mult * atr
            if is_long and close <= entry_price - stop_dist:
                return (
                    True,
                    self._build_signal(
                        position=position,
                        close=close,
                        profit_pct=profit_pct,
                        reason=ExitReason.STOP_LOSS,
                        priority=1,
                        exit_type="hard_stop",
                        extra={"atr": atr, "stop_dist": stop_dist},
                    ),
                )
            if (not is_long) and close >= entry_price + stop_dist:
                return (
                    True,
                    self._build_signal(
                        position=position,
                        close=close,
                        profit_pct=profit_pct,
                        reason=ExitReason.STOP_LOSS,
                        priority=1,
                        exit_type="hard_stop",
                        extra={"atr": atr, "stop_dist": stop_dist},
                    ),
                )

        # --- Priority 2: EOD flatten (intraday futures) ---
        if self.config.eod_flatten_enabled:
            flatten_t = time(
                self.config.eod_flatten_hour, self.config.eod_flatten_minute
            )
            if to_kst(now).time() >= flatten_t:
                return (
                    True,
                    self._build_signal(
                        position=position,
                        close=close,
                        profit_pct=profit_pct,
                        reason=ExitReason.EOD_CLOSE,
                        priority=2,
                        exit_type="eod_flatten",
                    ),
                )

        # --- Priority 3: ATR trailing stop (with breakeven ratchet) ---
        if atr > 0:
            best = self._best_price(position, close, is_long)
            in_favor = (best - entry_price) if is_long else (entry_price - best)
            breakeven_reached = in_favor >= self.config.breakeven_activation_atr * atr
            trail_reached = in_favor >= self.config.trail_activation_atr * atr

            if trail_reached:
                trail_dist = self.config.trail_atr_mult * atr
                if is_long:
                    trail_stop = best - trail_dist
                    if breakeven_reached:
                        trail_stop = max(trail_stop, entry_price)
                    if close <= trail_stop:
                        return (
                            True,
                            self._build_signal(
                                position=position,
                                close=close,
                                profit_pct=profit_pct,
                                reason=ExitReason.TRAILING_STOP,
                                priority=3,
                                exit_type="atr_trail",
                                extra={
                                    "trail_stop": trail_stop,
                                    "best": best,
                                    "atr": atr,
                                },
                            ),
                        )
                else:
                    trail_stop = best + trail_dist
                    if breakeven_reached:
                        trail_stop = min(trail_stop, entry_price)
                    if close >= trail_stop:
                        return (
                            True,
                            self._build_signal(
                                position=position,
                                close=close,
                                profit_pct=profit_pct,
                                reason=ExitReason.TRAILING_STOP,
                                priority=3,
                                exit_type="atr_trail",
                                extra={
                                    "trail_stop": trail_stop,
                                    "best": best,
                                    "atr": atr,
                                },
                            ),
                        )

        return (False, None)

    @staticmethod
    def _best_price(position: Any, close: float, is_long: bool) -> float:
        """Best favorable price since entry (high for long, low for short)."""
        if is_long:
            hi = float(getattr(position, "highest_price", 0.0) or 0.0)
            return max(hi, close) if hi > 0 else close
        lo = float(getattr(position, "lowest_price", float("inf")) or float("inf"))
        if lo == float("inf") or lo <= 0:
            return close
        return min(lo, close)

    async def scan_positions(
        self,
        positions: list,
        market_data: dict[str, Any],
        market_state: MarketStateProtocol | None = None,
    ) -> list[ExitSignal]:
        signals: list[ExitSignal] = []
        now = now_kst()
        for position in positions:
            symbol_data = market_data.get(position.code, market_data)
            per_symbol = (
                symbol_data if isinstance(symbol_data, dict) else {"close": symbol_data}
            )
            context = ExitContext(
                position=position,
                market_data=per_symbol,
                indicators=per_symbol,
                timestamp=now,
                market_state=market_state,
            )
            should_exit, signal = await self.should_exit(context)
            if should_exit and signal:
                signals.append(signal)
        return signals
