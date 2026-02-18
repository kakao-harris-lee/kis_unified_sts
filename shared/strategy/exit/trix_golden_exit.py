"""TRIX Golden Signal Exit Strategy.

5분봉 TRIX 지표 기반 청산 전략. 분할청산(50%/100%) 지원.

Exit Triggers (Priority Order):
    1. Bearish Divergence: 즉시 전량 청산 (최우선)
    2. Stop Loss: 진입가 대비 -N% 또는 스윙 저점 이탈
    3. Partial Exit (50%): TRIX peak-out 또는 RSI 과매수 이탈
    4. Full Exit (100%):
       - TRIX Dead Cross (TRIX < Signal)
       - TRIX 0선 하향 돌파
       - 잔여 수량 전량 청산

Usage:
    config = TrixGoldenExitConfig(stop_loss_pct=-0.03, partial_exit_ratio=0.5)
    strategy = TrixGoldenExit(config)
    should_exit, signal = await strategy.should_exit(context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

import pandas as pd

from shared.config.mixins import ConfigMixin
from shared.indicators.momentum import DivergenceDetector
from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator
from shared.strategy.market_data import (
    get_price_from_snapshot,
    get_symbol_snapshot,
)

logger = logging.getLogger(__name__)


@dataclass
class TrixGoldenExitConfig(ConfigMixin):
    """TRIX Golden Signal Exit 설정.

    Attributes:
        stop_loss_pct: Hard stop loss (negative pct, e.g., -0.03 = -3%).
        partial_exit_ratio: Ratio for 1st partial exit (default: 0.5 = 50%).
        trix_n: TRIX EMA period (match entry config).
        trix_signal: TRIX signal line period.
        rsi_overbought: RSI level triggering partial exit (default: 70).
        divergence_lookback: Bars to check for divergence (default: 20).
        use_swing_low_stop: Use swing low for dynamic stop loss (default: True).
        swing_lookback: Bars to find swing low (default: 10).
        timeframe_minutes: Candle timeframe (default: 5).
        eod_close_enabled: Force close at end of day (default: True).
        eod_close_hour: EOD close hour (default: 15).
        eod_close_minute: EOD close minute (default: 15).
    """

    # Stop loss
    stop_loss_pct: float = -0.03  # -3%

    # Partial exit
    partial_exit_ratio: float = 0.5

    # Indicator params (should match entry)
    trix_n: int = 12
    trix_signal: int = 9
    rsi_overbought: float = 70.0

    # Divergence
    divergence_lookback: int = 20

    # Swing low stop
    use_swing_low_stop: bool = True
    swing_lookback: int = 10

    # Timeframe
    timeframe_minutes: int = 5

    # EOD
    eod_close_enabled: bool = True
    eod_close_hour: int = 15
    eod_close_minute: int = 15

    def validate(self) -> None:
        """Validate configuration."""
        if self.stop_loss_pct >= 0:
            raise ValueError("stop_loss_pct must be negative")
        if not 0 < self.partial_exit_ratio < 1:
            raise ValueError("partial_exit_ratio must be between 0 and 1 exclusive")
        if self.divergence_lookback < 5:
            raise ValueError("divergence_lookback must be at least 5")
        if self.swing_lookback < 3:
            raise ValueError("swing_lookback must be at least 3")


class TrixGoldenExit(ExitSignalGenerator[TrixGoldenExitConfig]):
    """TRIX Golden Signal Exit Strategy.

    Implements indicator-based exit with partial exit support:
    - 1st exit (50%): On TRIX peak-out or RSI overbought exit
    - 2nd exit (100%): On TRIX dead cross, 0-line cross, or divergence
    """

    NAME = "TRIX_GOLDEN_EXIT"
    VERSION = "1.0"
    CONFIG_CLASS = TrixGoldenExitConfig

    def __init__(self, config: TrixGoldenExitConfig):
        super().__init__(config)

        # Track partial exits per position
        self._partial_exited: dict[str, bool] = {}
        # Track TRIX peak for peak-out detection
        self._trix_peak: dict[str, float] = {}
        # Track RSI was overbought for exit-on-leave
        self._rsi_was_overbought: dict[str, bool] = {}

        self._divergence_detector = DivergenceDetector(
            lookback=config.divergence_lookback
        )

        logger.info(
            f"{self.name} ({self.version}) initialized: "
            f"stop_loss={config.stop_loss_pct:.1%}, "
            f"partial_ratio={config.partial_exit_ratio:.0%}, "
            f"rsi_overbought={config.rsi_overbought}"
        )

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def version(self) -> str:
        return self.VERSION

    def _validate_config(self) -> None:
        """Validate configuration."""
        self.config.validate()

    # -------------------------------------------------------------------------
    # Main Interface
    # -------------------------------------------------------------------------

    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, ExitSignal | None]:
        """Check if position should exit."""
        signal = self._check_position(
            position=context.position,
            market_data=context.market_data,
            market_state=context.market_state,
            now=context.timestamp,
        )
        return (signal is not None, signal)

    async def scan_positions(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: Any | None = None,
    ) -> list[ExitSignal]:
        """Scan multiple positions for exit signals."""
        if not positions:
            return []

        signals: list[ExitSignal] = []
        now = datetime.now()

        for position in positions:
            signal = self._check_position(
                position=position,
                market_data=market_data,
                market_state=market_state,
                now=now,
            )
            if signal:
                signals.append(signal)

        if signals:
            logger.info(
                f"[{self.name}] {len(signals)}/{len(positions)} positions "
                f"triggered exit signals"
            )

        return signals

    def update_state(self, context: ExitContext) -> None:
        """Update tracking state for position (TRIX peak, RSI overbought)."""
        position = context.position
        momentum = self._get_momentum_data(context.market_data, position.code)
        if not momentum:
            return

        df = momentum.get("df")
        if df is None or len(df) < 2:
            return

        pid = position.id
        trix_val = float(df["trix"].iloc[-1])

        # Track TRIX peak
        current_peak = self._trix_peak.get(pid, float("-inf"))
        if trix_val > current_peak:
            self._trix_peak[pid] = trix_val

        # Track RSI overbought state
        if "rsi" in df.columns:
            rsi_val = float(df["rsi"].iloc[-1])
            if rsi_val >= self.config.rsi_overbought:
                self._rsi_was_overbought[pid] = True

    # -------------------------------------------------------------------------
    # Position Check Logic
    # -------------------------------------------------------------------------

    def _check_position(
        self,
        position: Position,
        market_data: dict[str, Any],
        market_state: Any | None,  # noqa: ARG002
        now: datetime,
    ) -> ExitSignal | None:
        """Check individual position for exit conditions.

        Priority:
            1. Bearish Divergence → full exit (highest priority)
            2. Hard Stop Loss → full exit
            3. Swing Low Stop → full exit
            4. EOD Close → full exit
            5. Partial Exit (50%) → TRIX peak-out or RSI overbought exit
            6. Full Exit → TRIX dead cross or 0-line cross
        """
        # Get current price
        snapshot = get_symbol_snapshot(market_data, position.code)
        current_price = get_price_from_snapshot(snapshot)
        if current_price is None or current_price <= 0:
            return None

        # Update position price tracking
        position.update_price(current_price)

        # Profit calculation (side-aware)
        profit_pct = self._calc_profit_pct(position, current_price)
        profit_amount = self._calc_profit_amount(position, current_price)
        high_since_entry = max(position.highest_price, current_price)
        holding_minutes = int(position.get_hold_duration())

        # Get momentum indicators
        momentum = self._get_momentum_data(market_data, position.code)
        df = momentum.get("df") if momentum else None

        # 1. Bearish Divergence (highest priority — 명세: "조건식과 관계없이 즉시 청산")
        if (
            df is not None
            and len(df) >= self.config.divergence_lookback
            and self._divergence_detector.detect_bearish(df["close"], df["trix"])
        ):
                logger.warning(
                    f"[{self.name}] BEARISH DIVERGENCE detected for {position.code}! "
                    f"Immediate full exit."
                )
                return self._create_exit_signal(
                    position=position,
                    current_price=current_price,
                    profit_pct=profit_pct,
                    profit_amount=profit_amount,
                    reason=ExitReason.INDICATOR_EXIT,
                    priority=1,
                    high_since_entry=high_since_entry,
                    holding_minutes=holding_minutes,
                    quantity=position.quantity,  # Full exit
                    metadata={"trigger": "bearish_divergence"},
                )

        # 2. Hard Stop Loss
        if profit_pct <= self.config.stop_loss_pct:
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.STOP_LOSS,
                priority=1,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
                quantity=position.quantity,  # Full exit
                metadata={"trigger": "hard_stop"},
            )

        # 3. Swing Low Stop
        if self.config.use_swing_low_stop and df is not None:
            swing_low = self._find_swing_low(df, self.config.swing_lookback)
            if swing_low is not None and current_price < swing_low:
                return self._create_exit_signal(
                    position=position,
                    current_price=current_price,
                    profit_pct=profit_pct,
                    profit_amount=profit_amount,
                    reason=ExitReason.STOP_LOSS,
                    priority=1,
                    high_since_entry=high_since_entry,
                    holding_minutes=holding_minutes,
                    quantity=position.quantity,  # Full exit
                    metadata={"trigger": "swing_low_stop", "swing_low": swing_low},
                )

        # 4. EOD Close
        if self.config.eod_close_enabled:
            eod_time = time(self.config.eod_close_hour, self.config.eod_close_minute)
            if now.time() >= eod_time:
                return self._create_exit_signal(
                    position=position,
                    current_price=current_price,
                    profit_pct=profit_pct,
                    profit_amount=profit_amount,
                    reason=ExitReason.EOD_CLOSE,
                    priority=2,
                    high_since_entry=high_since_entry,
                    holding_minutes=holding_minutes,
                    quantity=position.quantity,  # Full exit
                    metadata={"trigger": "eod_close"},
                )

        # Need momentum data for indicator-based exits below
        if df is None or len(df) < 2:
            return None

        pid = position.id

        # 5. Partial Exit (50%) — TRIX peak-out or RSI overbought exit
        if not self._partial_exited.get(pid, False):
            partial_signal = self._check_partial_exit(
                position,
                df,
                current_price,
                profit_pct,
                profit_amount,
                high_since_entry,
                holding_minutes,
            )
            if partial_signal:
                self._partial_exited[pid] = True
                return partial_signal

        # 6. Full Exit — TRIX Dead Cross or 0-line cross
        full_signal = self._check_full_exit(
            position,
            df,
            current_price,
            profit_pct,
            profit_amount,
            high_since_entry,
            holding_minutes,
        )
        if full_signal:
            return full_signal

        # Update tracking state
        self._update_tracking(pid, df)

        return None

    def _check_partial_exit(
        self,
        position: Position,
        df: pd.DataFrame,
        current_price: float,
        profit_pct: float,
        profit_amount: float,
        high_since_entry: float,
        holding_minutes: int,
    ) -> ExitSignal | None:
        """Check for partial (50%) exit conditions.

        Triggers:
            - TRIX peak-out: TRIX formed a peak and is declining
            - RSI overbought exit: Was overbought, now leaving
        """
        pid = position.id
        partial_qty = max(1, int(position.quantity * self.config.partial_exit_ratio))

        # Only partial exit in profit
        if profit_pct <= 0:
            return None

        # TRIX peak-out: TRIX was rising, now declining
        trix_current = float(df["trix"].iloc[-1])
        trix_prev = float(df["trix"].iloc[-2])
        trix_peak = self._trix_peak.get(pid, float("-inf"))

        if trix_peak > trix_current and trix_current < trix_prev and trix_prev > 0:
            logger.info(
                f"[{self.name}] TRIX peak-out for {position.code}: "
                f"peak={trix_peak:.4f}, current={trix_current:.4f}"
            )
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.TRAILING_STOP,
                priority=3,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
                quantity=partial_qty,
                metadata={"trigger": "trix_peak_out", "partial": True},
            )

        # RSI overbought exit: was above threshold, now below
        if "rsi" in df.columns and self._rsi_was_overbought.get(pid, False):
            rsi_current = float(df["rsi"].iloc[-1])
            if rsi_current < self.config.rsi_overbought:
                logger.info(
                    f"[{self.name}] RSI overbought exit for {position.code}: "
                    f"rsi={rsi_current:.1f} (was overbought)"
                )
                return self._create_exit_signal(
                    position=position,
                    current_price=current_price,
                    profit_pct=profit_pct,
                    profit_amount=profit_amount,
                    reason=ExitReason.INDICATOR_EXIT,
                    priority=3,
                    high_since_entry=high_since_entry,
                    holding_minutes=holding_minutes,
                    quantity=partial_qty,
                    metadata={"trigger": "rsi_overbought_exit", "partial": True},
                )

        return None

    def _check_full_exit(
        self,
        position: Position,
        df: pd.DataFrame,
        current_price: float,
        profit_pct: float,
        profit_amount: float,
        high_since_entry: float,
        holding_minutes: int,
    ) -> ExitSignal | None:
        """Check for full exit conditions.

        Triggers:
            - TRIX Dead Cross: TRIX < Signal (was >= previously)
            - TRIX 0-line cross: TRIX < 0 (was >= 0 previously)
        """
        trix_current = float(df["trix"].iloc[-1])
        trix_signal_current = float(df["trix_signal"].iloc[-1])
        trix_prev = float(df["trix"].iloc[-2])
        trix_signal_prev = float(df["trix_signal"].iloc[-2])

        # TRIX Dead Cross
        if trix_current < trix_signal_current and trix_prev >= trix_signal_prev:
            logger.info(
                f"[{self.name}] TRIX dead cross for {position.code}: "
                f"trix={trix_current:.4f}, signal={trix_signal_current:.4f}"
            )
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.INDICATOR_EXIT,
                priority=2,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
                quantity=position.quantity,  # Remaining full exit
                metadata={"trigger": "trix_dead_cross"},
            )

        # TRIX 0-line downward cross
        if trix_current < 0 and trix_prev >= 0:
            logger.info(
                f"[{self.name}] TRIX 0-line break for {position.code}: "
                f"trix={trix_current:.4f}"
            )
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.INDICATOR_EXIT,
                priority=2,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
                quantity=position.quantity,  # Remaining full exit
                metadata={"trigger": "trix_zero_cross"},
            )

        return None

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _update_tracking(self, pid: str, df: pd.DataFrame) -> None:
        """Update TRIX peak and RSI tracking."""
        trix_val = float(df["trix"].iloc[-1])
        current_peak = self._trix_peak.get(pid, float("-inf"))
        if trix_val > current_peak:
            self._trix_peak[pid] = trix_val

        if "rsi" in df.columns:
            rsi_val = float(df["rsi"].iloc[-1])
            if rsi_val >= self.config.rsi_overbought:
                self._rsi_was_overbought[pid] = True

    @staticmethod
    def _get_momentum_data(market_data: dict[str, Any], code: str) -> dict[str, Any]:
        """Extract momentum_5m data from market_data."""
        snapshot = get_symbol_snapshot(market_data, code)
        momentum = snapshot.get("momentum_5m")
        if isinstance(momentum, dict):
            return momentum
        return {}

    @staticmethod
    def _find_swing_low(df: pd.DataFrame, lookback: int) -> float | None:
        """Find the swing low (lowest low) over the last N bars before the signal bar.

        Returns the lowest low price in the lookback window, or None if
        insufficient data.
        """
        if len(df) < lookback + 1:
            return None
        # Swing low is the min low of the bars before current
        lows = df["low"].iloc[-(lookback + 1) : -1]
        if lows.empty:
            return None
        return float(lows.min())

    @staticmethod
    def _calc_profit_pct(position: Position, current_price: float) -> float:
        """Side-aware profit percentage."""
        if position.entry_price <= 0:
            return 0.0
        if position.side == PositionSide.SHORT:
            return (position.entry_price - current_price) / position.entry_price
        return (current_price - position.entry_price) / position.entry_price

    @staticmethod
    def _calc_profit_amount(position: Position, current_price: float) -> float:
        """Side-aware profit amount."""
        if position.side == PositionSide.SHORT:
            return (position.entry_price - current_price) * position.quantity
        return (current_price - position.entry_price) * position.quantity

    def _create_exit_signal(
        self,
        *,
        position: Position,
        current_price: float,
        profit_pct: float,
        profit_amount: float,
        reason: ExitReason,
        priority: int,
        high_since_entry: float,
        holding_minutes: int,
        quantity: int,
        metadata: dict[str, Any] | None = None,
    ) -> ExitSignal:
        """Create standardized ExitSignal."""
        return ExitSignal(
            code=position.code,
            name=position.name,
            position_id=position.id,
            reason=reason,
            strategy=self.name,
            current_price=current_price,
            exit_price=current_price,
            entry_price=position.entry_price,
            profit_amount=profit_amount,
            profit_pct=profit_pct,
            confidence=0.8,
            priority=priority,
            timestamp=datetime.now(),
            stage=position.state.value if position.state else "",
            high_since_entry=high_since_entry,
            holding_minutes=holding_minutes,
            quantity=quantity,
            metadata=metadata or {},
        )

    def cleanup_position(self, position_id: str) -> None:
        """Clean up tracking state for a fully closed position."""
        self._partial_exited.pop(position_id, None)
        self._trix_peak.pop(position_id, None)
        self._rsi_was_overbought.pop(position_id, None)
