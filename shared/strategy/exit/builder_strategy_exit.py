"""Builder-strategy exit (no-code Strategy Builder runtime adapter).

Pairs with ``shared.strategy.entry.builder_strategy.BuilderStrategyEntry``.
Reads the same ``BuilderState`` and evaluates the exit-condition group
plus the risk toggles (stop_loss / take_profit / trailing_stop) every cycle.

The trailing stop keeps a per-position high-water-mark (peak price since
entry). It arms only once the position has shown a profit (HWM above the
entry price) so it never doubles as a second stop-loss; once armed it
exits when price retraces ``trailing_stop_pct`` below the peak. Builder
drafts are long-only (stock), so the peak is the running max price.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.indicators.engine import default_engine, window_from_records
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator, MarketStateProtocol
from shared.strategy.market_time import to_kst
from shared.strategy_builder.evaluator import StrategyBuilderEvaluator
from shared.strategy_builder.futures_safety import FuturesSafety, load_futures_safety
from shared.strategy_builder.indicator_context import build_indicator_context
from shared.strategy_builder.schema import BuilderState, SymbolSeries

logger = logging.getLogger(__name__)


@dataclass
class BuilderStrategyExitConfig(ConfigMixin):
    """Config for builder_v1_exit."""

    builder_state: dict[str, Any] = field(default_factory=dict)
    # Risk toggles (mirror BuilderState.risk.* — kept separate so the
    # operator can override defaults at deploy time without re-saving the
    # builder draft).
    stop_loss_pct: float = 5.0  # 0 disables; positive percent (5.0 = 5%)
    take_profit_pct: float = 0.0  # 0 disables
    trailing_stop_pct: float = 0.0  # 0 disables; retrace from peak that exits
    # Confidence threshold for emitting condition-based exit. Mirrors entry.
    min_confidence: float = 0.5


class BuilderStrategyExit(ExitSignalGenerator[BuilderStrategyExitConfig]):
    """Exit handler for builder_v1 entries."""

    CONFIG_CLASS = BuilderStrategyExitConfig

    def __init__(self, config: BuilderStrategyExitConfig):
        super().__init__(config)
        self._evaluator = StrategyBuilderEvaluator()
        self._engine = default_engine()
        self._state: BuilderState | None = None
        # Per-position peak price since entry, for the trailing stop. Keyed by
        # position id (falls back to code). Persists across cycles because the
        # exit instance is long-lived; cleared whenever a position exits.
        self._hwm: dict[str, float] = {}
        self._parse_state()
        self._is_futures = (
            self._state is not None and self._state.asset_class == "futures"
        )
        self._safety: FuturesSafety | None = (
            load_futures_safety() if self._is_futures else None
        )

    def _validate_config(self) -> None:
        assert self.config.stop_loss_pct >= 0
        assert self.config.take_profit_pct >= 0
        assert self.config.trailing_stop_pct >= 0
        assert 0.0 <= self.config.min_confidence <= 1.0

    def _parse_state(self) -> None:
        if not self.config.builder_state:
            logger.warning(
                "builder_v1_exit has empty builder_state; will only use SL/TP"
            )
            return
        try:
            self._state = BuilderState.model_validate(self.config.builder_state)
        except Exception as exc:
            logger.error("builder_v1_exit failed to parse builder_state: %s", exc)
            self._state = None
            return

    @property
    def name(self) -> str:
        if self._state is not None:
            return f"builder_v1_exit::{self._state.metadata.id}"
        return "builder_v1_exit"

    async def should_exit(self, context: ExitContext) -> tuple[bool, ExitSignal | None]:
        position = context.position
        market_data = context.market_data or {}
        current_price = float(
            market_data.get("close")
            or market_data.get("current_price")
            or position.current_price
            or 0
        )
        if current_price <= 0:
            return False, None

        entry_price = float(position.entry_price or 0)
        if entry_price <= 0:
            return False, None
        pnl_pct = (current_price - entry_price) / entry_price * 100.0

        pos_key = str(getattr(position, "id", "") or position.code)
        # Seed the peak from the position's persisted high-water-mark so the
        # trailing stop survives a process restart (Redis restores
        # highest_price); falls back to entry_price for a fresh position.
        hwm_seed = float(getattr(position, "highest_price", None) or entry_price)
        # Track the running peak price every cycle so the trailing stop
        # measures retrace from the high, not just the latest tick.
        if self.config.trailing_stop_pct > 0:
            self._hwm[pos_key] = max(self._hwm.get(pos_key, hwm_seed), current_price)

        # Futures auto-enforced safety (cannot be disabled by the user).
        if self._is_futures and self._safety is not None:
            # EOD time close (KST) — highest priority.
            now_kst = to_kst(context.timestamp)
            if now_kst.time() >= self._safety.eod_close_time:
                self._hwm.pop(pos_key, None)
                return True, self._make_signal(
                    position=position,
                    current_price=current_price,
                    entry_price=entry_price,
                    pnl_pct=pnl_pct,
                    reason=ExitReason.EOD_CLOSE,
                    confidence=1.0,
                    note="futures_eod_close",
                )
            # Hard-stop cap: take the tighter of the user's stop and the cap;
            # the cap also applies when the user disabled their stop (<= 0).
            cap = self._safety.hard_stop_pct
            user_stop = self.config.stop_loss_pct
            effective_stop = cap if user_stop <= 0 else min(user_stop, cap)
            if pnl_pct <= -effective_stop:
                self._hwm.pop(pos_key, None)
                note = (
                    "futures_hard_stop"
                    if effective_stop == cap
                    else "stop_loss_within_cap"
                )
                return True, self._make_signal(
                    position=position,
                    current_price=current_price,
                    entry_price=entry_price,
                    pnl_pct=pnl_pct,
                    reason=ExitReason.STOP_LOSS,
                    confidence=1.0,
                    note=note,
                )

        # 1) Hard stop loss
        if self.config.stop_loss_pct > 0 and pnl_pct <= -self.config.stop_loss_pct:
            self._hwm.pop(pos_key, None)
            return True, self._make_signal(
                position=position,
                current_price=current_price,
                entry_price=entry_price,
                pnl_pct=pnl_pct,
                reason=ExitReason.STOP_LOSS,
                confidence=1.0,
                note="stop_loss",
            )

        # 2) Take profit
        if self.config.take_profit_pct > 0 and pnl_pct >= self.config.take_profit_pct:
            self._hwm.pop(pos_key, None)
            return True, self._make_signal(
                position=position,
                current_price=current_price,
                entry_price=entry_price,
                pnl_pct=pnl_pct,
                reason=ExitReason.TARGET_REACHED,
                confidence=1.0,
                note="take_profit",
            )

        # 3) Trailing stop — only after the position has shown a profit
        #    (peak above entry), so it never fires as a second stop-loss.
        if self.config.trailing_stop_pct > 0:
            peak = self._hwm.get(pos_key, hwm_seed)
            if peak > entry_price:
                stop_price = peak * (1.0 - self.config.trailing_stop_pct / 100.0)
                if current_price <= stop_price:
                    self._hwm.pop(pos_key, None)
                    return True, self._make_signal(
                        position=position,
                        current_price=current_price,
                        entry_price=entry_price,
                        pnl_pct=pnl_pct,
                        reason=ExitReason.TRAILING_STOP,
                        confidence=1.0,
                        note="trailing_stop",
                    )

        # 4) Builder exit conditions
        if self._state is None or not self._state.exit.conditions:
            return False, None

        series = self._build_series(
            position.code,
            getattr(position, "name", "") or "",
            context.indicators or {},
        )
        evaluation = self._evaluator.evaluate_group(
            self._state.exit.conditions,
            self._state.exit.logic,
            series,
        )
        if not evaluation.passed or evaluation.score < self.config.min_confidence:
            return False, None

        self._hwm.pop(pos_key, None)
        return True, self._make_signal(
            position=position,
            current_price=current_price,
            entry_price=entry_price,
            pnl_pct=pnl_pct,
            reason=ExitReason.STRATEGY_EXIT,
            confidence=evaluation.score,
            note="builder_conditions",
        )

    async def scan_positions(
        self,
        positions: list[Any],
        market_data: dict[str, Any],
        market_state: MarketStateProtocol | None = None,
    ) -> list[ExitSignal]:
        """Iterate positions; builder_v1_exit defers indicator data to caller."""
        signals: list[ExitSignal] = []
        for position in positions:
            ctx = ExitContext(
                position=position,
                market_data=market_data.get(position.code, {}),
                indicators=market_data.get(f"{position.code}.indicators", {}) or {},
                timestamp=datetime.now(UTC),
                market_state=market_state,
            )
            should_exit, signal = await self.should_exit(ctx)
            if should_exit and signal is not None:
                signals.append(signal)
        return signals

    def _make_signal(
        self,
        *,
        position: Any,
        current_price: float,
        entry_price: float,
        pnl_pct: float,
        reason: ExitReason,
        confidence: float,
        note: str,
    ) -> ExitSignal:
        quantity = int(getattr(position, "quantity", 0))
        profit_amount = (current_price - entry_price) * max(quantity, 0)
        return ExitSignal(
            code=position.code,
            name=getattr(position, "name", "") or "",
            position_id=getattr(position, "id", "") or "",
            reason=reason,
            strategy=self.name,
            current_price=current_price,
            exit_price=current_price,
            entry_price=entry_price,
            profit_amount=profit_amount,
            profit_pct=pnl_pct / 100.0,
            confidence=confidence,
            metadata={
                "note": note,
                "builder_state_id": self._state.metadata.id if self._state else "",
            },
        )

    def _build_series(
        self,
        code: str,
        name: str,
        indicators: dict[str, Any],
    ) -> SymbolSeries:
        """Compute the declarative Indicator Context over the OHLCV history.

        The paired builder_v1 entry declares ``required_indicators == ["ohlcv"]``,
        so the resolver's exit payload carries ``indicators["ohlcv"]``. All
        indicator math is delegated to the TA-Lib engine; absent history yields
        an empty series (condition exits fail safe — SL/TP/trailing still apply).
        """
        if self._state is None:
            return SymbolSeries(symbol=code, name=name or None)
        rows = indicators.get("ohlcv")
        if not isinstance(rows, list) or not rows:
            return SymbolSeries(symbol=code, name=name or None)
        window = window_from_records(rows)
        context = build_indicator_context(self._state, window, self._engine)
        return context.to_symbol_series(code, name or None)
