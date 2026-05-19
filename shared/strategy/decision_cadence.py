"""Decision-cadence gate: throttle a strategy's entry/exit decisions to
its configured higher-timeframe bar boundary.

A strategy fed 1-minute bars but configured `timeframe_minutes = N`
must DECIDE only when a new *closed* N-min bar has appeared since it
last decided (the engine still consumes every 1m bar to build the N-min
candle). This makes the registered backtest path and the live path
behave like the N-min strategy validated by the robust gate
(decision-cadence parity), instead of deciding every 1m with N-min
indicators. Look-ahead-safe: callers evaluate AFTER the N-min bucket
closes, using closed-bars-only indicators (`get_indicators_tf`).

`timeframe_minutes <= 1` → no-op (always decide), so 1-minute strategies
(stock `bb_reversion`, all other `mean_reversion` users) are unchanged.
"""

from __future__ import annotations

from typing import Any


class DecisionCadenceGate:
    def __init__(self, timeframe_minutes: int = 0) -> None:
        self._tf = int(timeframe_minutes or 0)
        self._decided_at: dict[str, int] = {}

    @property
    def enabled(self) -> bool:
        return self._tf > 1

    def should_decide(self, engine: Any, symbol: str) -> bool:
        if not self.enabled:
            return True
        try:
            closed = int(engine.mtf_total_appended(symbol, self._tf))
        except Exception:  # noqa: BLE001
            # engine not ready during warmup / hot trading path → safe HOLD;
            # this gate sits in the live orchestrator loop and must NEVER raise
            # (do not narrow/remove this broad swallow).
            return False
        return closed > self._decided_at.get(symbol, 0)

    def mark_decided(self, engine: Any, symbol: str) -> None:
        if not self.enabled:
            return
        try:  # noqa: SIM105
            self._decided_at[symbol] = int(
                engine.mtf_total_appended(symbol, self._tf)
            )
        except Exception:  # noqa: BLE001
            # engine not ready / hot trading path → skip watermark advance;
            # this gate sits in the live orchestrator loop and must NEVER raise
            # (do not narrow/remove this broad swallow).
            pass
