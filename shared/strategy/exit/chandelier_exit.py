"""Chandelier Exit Strategy.

일봉 기반 Chandelier Exit 청산 전략:
- Highest High(lookback) - ATR(period) × multiplier 기반 트레일링 스탑
- Hard stop loss (-7% 기본)
- Max hold days (60일 기본)

Exit Priority:
    1. Hard stop → 즉시 청산
    2. Max hold days → 보유 기간 초과
    3. Chandelier trailing stop → close < chandelier_stop
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator, MarketStateProtocol

logger = logging.getLogger(__name__)


def _holding_days_since(entry_time: datetime, now: datetime) -> int:
    """Return holding days without failing on mixed timezone awareness."""
    if entry_time.tzinfo is None and now.tzinfo is not None:
        entry_time = entry_time.replace(tzinfo=now.tzinfo)
    elif entry_time.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=entry_time.tzinfo)
    return max(0, (now - entry_time).days)


@dataclass
class ChandelierExitConfig(ConfigMixin):
    """Chandelier Exit 청산 전략 설정."""

    # ATR
    atr_period: int = 22
    atr_multiplier: float = 3.0

    # Lookback for highest high
    lookback_period: int = 22

    # Hard stop loss (negative ratio, e.g., -0.07 = -7%)
    hard_stop_pct: float = -0.07

    # Fixed take-profit (positive ratio, e.g., 0.10 = +10%). 0 disables.
    take_profit_pct: float = 0.0

    # Max hold days
    max_hold_days: int = 60

    # Confidence
    default_exit_confidence: float = 0.85

    # Use the position's post-entry high for trailing stops. The rolling
    # lookback high can predate a pullback entry and cause immediate loss exits.
    use_position_high_since_entry: bool = True


class ChandelierExit(ExitSignalGenerator[ChandelierExitConfig]):
    """Chandelier Exit 청산 전략.

    chandelier_stop = max(high[-lookback:]) - ATR(period) × multiplier

    Exit Priority:
        1. Hard stop (entry_price × (1 + hard_stop_pct))
        2. Max hold days exceeded
        3. Chandelier trailing stop

    이 전략은 일봉 전용이며, indicators dict에 사전 계산된
    ATR, highest_high 값이 포함되어 있다고 가정합니다.
    """

    CONFIG_CLASS = ChandelierExitConfig

    def __init__(self, config: ChandelierExitConfig):
        super().__init__(config)

    def _validate_config(self):
        assert self.config.atr_period > 0, "atr_period must be positive"
        assert self.config.atr_multiplier > 0, "atr_multiplier must be positive"
        assert self.config.lookback_period > 0, "lookback_period must be positive"
        assert (
            -1.0 < self.config.hard_stop_pct < 0.0
        ), "hard_stop_pct must be between -1.0 and 0.0"
        assert (
            0.0 <= self.config.take_profit_pct < 10.0
        ), "take_profit_pct must be in [0.0, 10.0)"
        assert self.config.max_hold_days > 0, "max_hold_days must be positive"
        assert (
            0 < self.config.default_exit_confidence <= 1.0
        ), "default_exit_confidence must be in (0, 1]"

    @property
    def name(self) -> str:
        return "chandelier_exit"

    async def should_exit(self, context: ExitContext) -> tuple[bool, ExitSignal | None]:
        """Check whether position should be exited."""
        position = context.position
        data = context.market_data or {}
        indicators = context.indicators or {}

        close = float(data.get("close", 0) or 0)
        if close <= 0:
            return (False, None)

        entry_price = position.entry_price
        code = position.code
        now = context.timestamp

        def _get(key: str, default: float = 0.0) -> float:
            # Check exact key, then daily_ prefixed key (paper trading injects daily_ prefix)
            for k in (key, f"daily_{key}"):
                if k in indicators:
                    val = indicators.get(k, default)
                    return float(val) if val is not None else default
                if k in data:
                    val = data.get(k, default)
                    return float(val) if val is not None else default
            return default

        # Profit calculation (long only for this strategy)
        profit_pct = (close - entry_price) / entry_price if entry_price > 0 else 0.0

        # --- Priority 1: Hard stop ---
        if profit_pct <= self.config.hard_stop_pct:
            logger.info(
                f"ChandelierExit HARD STOP: {code} "
                f"profit={profit_pct:.2%} <= {self.config.hard_stop_pct:.2%}"
            )
            return (
                True,
                ExitSignal(
                    code=code,
                    reason=ExitReason.STOP_LOSS,
                    strategy="chandelier_exit",
                    current_price=close,
                    exit_price=close,
                    entry_price=entry_price,
                    profit_pct=profit_pct,
                    confidence=1.0,
                    priority=1,
                    timestamp=now,
                    metadata={"exit_type": "hard_stop"},
                ),
            )

        # --- Priority 2: Fixed take-profit ---
        if (
            self.config.take_profit_pct > 0
            and profit_pct >= self.config.take_profit_pct
        ):
            logger.info(
                f"ChandelierExit TAKE PROFIT: {code} "
                f"profit={profit_pct:.2%} >= {self.config.take_profit_pct:.2%}"
            )
            return (
                True,
                ExitSignal(
                    code=code,
                    reason=ExitReason.TARGET_REACHED,
                    strategy="chandelier_exit",
                    current_price=close,
                    exit_price=close,
                    entry_price=entry_price,
                    profit_pct=profit_pct,
                    confidence=self.config.default_exit_confidence,
                    priority=2,
                    timestamp=now,
                    metadata={"exit_type": "take_profit"},
                ),
            )

        # --- Priority 3: Max hold days ---
        holding_days = _get("holding_days", 0)
        # Fallback: compute from position.entry_time (paper trading)
        if (
            holding_days == 0
            and hasattr(position, "entry_time")
            and position.entry_time
        ):
            holding_days = _holding_days_since(position.entry_time, now)
        if holding_days >= self.config.max_hold_days:
            logger.info(
                f"ChandelierExit MAX HOLD: {code} "
                f"holding_days={holding_days} >= {self.config.max_hold_days}"
            )
            return (
                True,
                ExitSignal(
                    code=code,
                    reason=ExitReason.TIME_CUT,
                    strategy="chandelier_exit",
                    current_price=close,
                    exit_price=close,
                    entry_price=entry_price,
                    profit_pct=profit_pct,
                    confidence=self.config.default_exit_confidence,
                    priority=3,
                    timestamp=now,
                    metadata={"exit_type": "max_hold", "holding_days": holding_days},
                ),
            )

        # --- Priority 4: Chandelier trailing stop ---
        atr = _get("atr", 0)
        indicator_highest_high = _get("highest_high", 0)
        position_highest_high = float(getattr(position, "highest_price", 0.0) or 0.0)
        highest_high = (
            position_highest_high
            if self.config.use_position_high_since_entry and position_highest_high > 0
            else indicator_highest_high
        )

        if atr > 0 and highest_high > 0:
            chandelier_stop = highest_high - atr * self.config.atr_multiplier

            if close < chandelier_stop:
                logger.info(
                    f"ChandelierExit TRAILING: {code} "
                    f"close={close:.0f} < chandelier={chandelier_stop:.0f} "
                    f"(HH={highest_high:.0f} - ATR={atr:.0f}×{self.config.atr_multiplier})"
                )
                return (
                    True,
                    ExitSignal(
                        code=code,
                        reason=ExitReason.TRAILING_STOP,
                        strategy="chandelier_exit",
                        current_price=close,
                        exit_price=close,
                        entry_price=entry_price,
                        profit_pct=profit_pct,
                        confidence=self.config.default_exit_confidence,
                        priority=4,
                        timestamp=now,
                        metadata={
                            "exit_type": "chandelier",
                            "chandelier_stop": chandelier_stop,
                            "highest_high": highest_high,
                            "indicator_highest_high": indicator_highest_high,
                            "position_highest_high": position_highest_high,
                            "atr": atr,
                        },
                    ),
                )

        return (False, None)

    async def scan_positions(
        self,
        positions: list,
        market_data: dict[str, Any],
        market_state: MarketStateProtocol | None = None,
    ) -> list[ExitSignal]:
        """Scan multiple positions for exit signals."""
        signals = []
        now = datetime.now()
        for position in positions:
            # Extract per-symbol data from symbol-keyed market_data dict
            symbol_data = market_data.get(position.code, {})
            if isinstance(symbol_data, dict):
                per_symbol = symbol_data
            else:
                per_symbol = {"close": symbol_data} if symbol_data else {}
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
