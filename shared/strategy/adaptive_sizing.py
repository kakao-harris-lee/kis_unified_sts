"""Adaptive position sizing based on strategy win rate from Redis trade history.

Adjusts per-trade investment amount (fixed_amount) by a multiplier derived from
recent strategy performance.  Slot counts (max_positions) are not changed.

Usage::

    from shared.strategy.adaptive_sizing import AdaptiveSizingManager

    mgr = AdaptiveSizingManager(config_dict, asset_class="stock")
    mgr.refresh()                           # read Redis trades
    mult = mgr.get_multiplier("trend_pullback")  # e.g. 1.3
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Default tiers: (min_win_rate, max_win_rate, multiplier)
DEFAULT_TIERS: list[tuple[float, float, float]] = [
    (0.0, 0.30, 0.5),
    (0.30, 0.45, 0.75),
    (0.45, 0.55, 1.0),
    (0.55, 0.65, 1.3),
    (0.65, 1.0, 1.8),
]


@dataclass
class AdaptiveSizingConfig:
    """Configuration for adaptive position sizing."""

    enabled: bool = True
    min_trades: int = 5
    lookback_trades: int = 30
    max_multiplier: float = 2.0
    min_multiplier: float = 0.5
    tiers: list[tuple[float, float, float]] = field(default_factory=lambda: list(DEFAULT_TIERS))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdaptiveSizingConfig:
        raw_tiers = data.get("tiers", DEFAULT_TIERS)
        tiers = [tuple(t) for t in raw_tiers]  # type: ignore[arg-type]
        return cls(
            enabled=data.get("enabled", True),
            min_trades=int(data.get("min_trades", 5)),
            lookback_trades=int(data.get("lookback_trades", 30)),
            max_multiplier=float(data.get("max_multiplier", 2.0)),
            min_multiplier=float(data.get("min_multiplier", 0.5)),
            tiers=tiers,  # type: ignore[arg-type]
        )


def _lookup_multiplier(win_rate: float, tiers: list[tuple[float, float, float]]) -> float:
    """Find the multiplier for a given win rate from tier ranges."""
    for low, high, mult in tiers:
        if low <= win_rate < high:
            return mult
    # Edge case: win_rate == 1.0 (100%)
    if tiers and win_rate >= tiers[-1][0]:
        return tiers[-1][2]
    return 1.0


class AdaptiveSizingManager:
    """Manages per-strategy investment amount multipliers based on Redis trade history."""

    def __init__(self, config: AdaptiveSizingConfig, asset_class: str):
        self._config = config
        self._asset = asset_class
        self._multipliers: dict[str, float] = {}
        self._win_rates: dict[str, float] = {}
        self._trade_counts: dict[str, int] = {}

    @property
    def multipliers(self) -> dict[str, float]:
        return dict(self._multipliers)

    def refresh(self) -> None:
        """Read trades from Redis and recompute per-strategy multipliers."""
        if not self._config.enabled:
            return

        try:
            from shared.streaming.trading_state import TradingStateReader

            reader = TradingStateReader(self._asset)
            trades = reader.get_trades(start=0, count=500)
        except Exception as e:
            logger.warning(f"Adaptive sizing: failed to read trades: {e}")
            return

        if not trades:
            return

        # Group trades by strategy (trades are most-recent-first)
        by_strategy: dict[str, list[dict]] = defaultdict(list)
        for t in trades:
            strategy = t.get("strategy", "")
            if strategy:
                by_strategy[strategy].append(t)

        parts: list[str] = []
        for name, strades in by_strategy.items():
            recent = strades[: self._config.lookback_trades]
            count = len(recent)
            self._trade_counts[name] = count

            if count < self._config.min_trades:
                self._multipliers[name] = 1.0
                self._win_rates[name] = 0.0
                parts.append(f"{name}=1.0x ({count} trades < min {self._config.min_trades})")
                continue

            wins = sum(1 for t in recent if float(t.get("pnl", 0)) > 0)
            win_rate = wins / count
            self._win_rates[name] = win_rate

            raw_mult = _lookup_multiplier(win_rate, self._config.tiers)
            clamped = max(self._config.min_multiplier, min(self._config.max_multiplier, raw_mult))
            self._multipliers[name] = clamped

            parts.append(f"{name}={clamped}x (WR {win_rate:.1%}, {count} trades)")

        if parts:
            logger.info(f"Adaptive sizing: {', '.join(parts)}")

    def get_multiplier(self, strategy_name: str) -> float:
        """Return the multiplier for a strategy. Defaults to 1.0 if unknown."""
        if not self._config.enabled:
            return 1.0
        return self._multipliers.get(strategy_name, 1.0)

    def get_stats(self) -> dict[str, dict[str, float]]:
        """Return current stats for monitoring/logging."""
        result: dict[str, dict[str, float]] = {}
        for name in set(self._multipliers) | set(self._win_rates):
            result[name] = {
                "multiplier": self._multipliers.get(name, 1.0),
                "win_rate": self._win_rates.get(name, 0.0),
                "trade_count": self._trade_counts.get(name, 0),
            }
        return result
