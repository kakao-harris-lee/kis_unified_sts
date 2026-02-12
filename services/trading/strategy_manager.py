"""Strategy Manager

Manages multiple trading strategies for the orchestrator.

Loads strategies from config, executes entry/exit checks across all strategies,
and aggregates signals.

Usage:
    manager = StrategyManager(asset_class="stock")

    # Or load specific strategies
    manager = StrategyManager(
        asset_class="stock",
        strategy_names=["bb_reversion", "mean_reversion"],
    )

    # Check entries across all strategies
    signals = await manager.check_entries(context)

    # Check exits for positions
    exit_signals = await manager.check_exits(positions, market_data)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from shared.models.position import Position
from shared.models.signal import ExitSignal, Signal
from shared.strategy.base import EntryContext, ExitContext, TradingStrategy
from shared.strategy.registry import (
    StrategyFactory,
    register_builtin_components,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# Validation constants
MIN_CONFIDENCE = 0.0
MAX_CONFIDENCE = 1.0
MIN_DEDUPE_WINDOW = 0.0
MAX_DEDUPE_WINDOW = 3600.0  # 1 hour max
DEDUPE_SCOPES = {"symbol", "strategy", "direction"}


@dataclass
class StrategyManagerConfig:
    """Strategy manager configuration"""

    # Signal filtering
    min_confidence: float = 0.3

    # Deduplication
    dedupe_by_symbol: bool = True
    dedupe_scope: str = "direction"
    dedupe_window_seconds: float = 60.0

    # Parallel execution
    parallel_entries: bool = True
    parallel_exits: bool = True

    def __post_init__(self):
        """Validate configuration values."""
        self._validate()

    def _validate(self):
        """Validate all configuration parameters."""
        if not (MIN_CONFIDENCE <= self.min_confidence <= MAX_CONFIDENCE):
            raise ValueError(
                f"min_confidence must be between {MIN_CONFIDENCE} "
                f"and {MAX_CONFIDENCE}, got {self.min_confidence}"
            )

        if not (MIN_DEDUPE_WINDOW <= self.dedupe_window_seconds <= MAX_DEDUPE_WINDOW):
            raise ValueError(
                f"dedupe_window_seconds must be between {MIN_DEDUPE_WINDOW} "
                f"and {MAX_DEDUPE_WINDOW}, got {self.dedupe_window_seconds}"
            )
        if self.dedupe_scope not in DEDUPE_SCOPES:
            raise ValueError(
                f"dedupe_scope must be one of {sorted(DEDUPE_SCOPES)}, got {self.dedupe_scope}"
            )

        if not isinstance(self.dedupe_by_symbol, bool):
            raise TypeError(
                f"dedupe_by_symbol must be bool, got {type(self.dedupe_by_symbol)}"
            )

        if not isinstance(self.parallel_entries, bool):
            raise TypeError(
                f"parallel_entries must be bool, got {type(self.parallel_entries)}"
            )

        if not isinstance(self.parallel_exits, bool):
            raise TypeError(
                f"parallel_exits must be bool, got {type(self.parallel_exits)}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StrategyManagerConfig:
        """Create config from dict with validation.

        Args:
            data: Configuration dictionary

        Returns:
            Validated StrategyManagerConfig

        Raises:
            ValueError: If validation fails
            TypeError: If type validation fails
        """
        min_confidence = data.get("min_confidence", 0.3)
        dedupe_by_symbol = data.get("dedupe_by_symbol", True)
        dedupe_window = data.get("dedupe_window_seconds", 60.0)
        dedupe_scope = data.get("dedupe_scope", "direction")
        parallel_entries = data.get("parallel_entries", True)
        parallel_exits = data.get("parallel_exits", True)

        # Type validation
        if not isinstance(min_confidence, (int, float)):
            raise TypeError(
                f"min_confidence must be numeric, got {type(min_confidence)}"
            )
        if not isinstance(dedupe_window, (int, float)):
            raise TypeError(
                f"dedupe_window_seconds must be numeric, got {type(dedupe_window)}"
            )

        return cls(
            min_confidence=float(min_confidence),
            dedupe_by_symbol=bool(dedupe_by_symbol),
            dedupe_scope=str(dedupe_scope),
            dedupe_window_seconds=float(dedupe_window),
            parallel_entries=bool(parallel_entries),
            parallel_exits=bool(parallel_exits),
        )


class StrategyManager:
    """Multi-strategy manager

    Loads and manages multiple trading strategies.
    Executes entry/exit checks and aggregates results.

    Usage:
        # Load all enabled strategies for asset class
        manager = StrategyManager(asset_class="stock")

        # Load specific strategies
        manager = StrategyManager(
            asset_class="stock",
            strategy_names=["bb_reversion"],
        )

        # Check entries
        context = EntryContext(market_data=data, ...)
        signals = await manager.check_entries(context)

        # Check exits
        exit_signals = await manager.check_exits(
            positions=tracker.positions,
            market_data=data,
            market_state=regime,
        )
    """

    def __init__(
        self,
        asset_class: str = "stock",
        strategy_names: list[str] | None = None,
        config: StrategyManagerConfig | None = None,
    ):
        """
        Args:
            asset_class: Asset class ("stock" or "futures")
            strategy_names: Specific strategies to load (None = all enabled)
            config: Manager configuration
        """
        self.asset_class = asset_class
        self.config = config or StrategyManagerConfig()

        # Register built-in components first
        register_builtin_components()

        # Load strategies
        self.strategies: dict[str, TradingStrategy] = {}
        self._load_strategies(strategy_names)

        # Signal deduplication cache
        self._recent_signals: dict[str, datetime] = {}

        logger.info(
            f"StrategyManager initialized: {len(self.strategies)} strategies "
            f"for {asset_class}"
        )

    def _load_strategies(self, strategy_names: list[str] | None):
        """Load strategies from config files"""
        if strategy_names:
            # Load specific strategies
            for name in strategy_names:
                try:
                    strategy = StrategyFactory.create_from_file(self.asset_class, name)
                    self.strategies[strategy.name] = strategy
                    logger.info(f"Loaded strategy: {strategy.name}")
                except Exception as e:
                    logger.error(f"Failed to load strategy '{name}': {e}")
        else:
            # Load all enabled strategies
            try:
                strategies = StrategyFactory.create_all(
                    asset_class=self.asset_class,
                    enabled_only=True,
                )
                for strategy in strategies:
                    self.strategies[strategy.name] = strategy
                    logger.info(f"Loaded strategy: {strategy.name}")
            except Exception as e:
                logger.error(f"Failed to load strategies: {e}")

    def add_strategy(self, strategy: TradingStrategy):
        """Add a strategy manually"""
        self.strategies[strategy.name] = strategy
        logger.info(f"Added strategy: {strategy.name}")

    def remove_strategy(self, name: str):
        """Remove a strategy"""
        if name in self.strategies:
            del self.strategies[name]
            logger.info(f"Removed strategy: {name}")

    @property
    def strategy_names(self) -> list[str]:
        """Get list of loaded strategy names"""
        return list(self.strategies.keys())

    @property
    def required_indicators(self) -> list[str]:
        """Get all required indicators across strategies"""
        indicators = set()
        for strategy in self.strategies.values():
            indicators.update(strategy.required_indicators)
        return list(indicators)

    async def check_entries(self, context: EntryContext) -> list[Signal]:
        """Check entry signals across all strategies

        Args:
            context: Entry context with market data and indicators

        Returns:
            List of aggregated entry signals (deduplicated)
        """
        if not self.strategies:
            return []

        signals = []

        if self.config.parallel_entries:
            # Run all strategies in parallel
            tasks = [
                self._check_entry_safe(strategy, context)
                for strategy in self.strategies.values()
            ]
            results = await asyncio.gather(*tasks)

            for result in results:
                if result:
                    signals.append(result)
        else:
            # Run sequentially
            for strategy in self.strategies.values():
                signal = await self._check_entry_safe(strategy, context)
                if signal:
                    signals.append(signal)

        # Filter and deduplicate
        signals = self._filter_signals(signals)
        signals = self._dedupe_signals(signals)

        if signals:
            logger.info(
                f"Entry signals: {len(signals)} from {len(self.strategies)} strategies"
            )

        return signals

    async def _check_entry_safe(
        self,
        strategy: TradingStrategy,
        context: EntryContext,
    ) -> Signal | None:
        """Check entry with exception handling"""
        try:
            signal = await strategy.check_entry(context)
            if signal is None:
                return None

            # Ensure exit routing works: positions are grouped by TradingStrategy.name.
            # Preserve the original entry component name in metadata for debugging.
            if signal.strategy and signal.strategy != strategy.name:
                signal.metadata.setdefault("entry_component", signal.strategy)
            signal.strategy = strategy.name
            return signal
        except Exception as e:
            logger.error(f"Entry check failed for {strategy.name}: {e}", exc_info=True)
            return None

    async def check_exits(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: Any | None = None,
    ) -> list[ExitSignal]:
        """Check exit signals for positions

        Pre-groups positions by strategy to avoid redundant filtering in
        parallel execution.

        Args:
            positions: List of open positions
            market_data: Current market data
            market_state: Market regime (BULL/BEAR/SIDEWAYS)

        Returns:
            List of exit signals
        """
        if not positions or not self.strategies:
            return []

        # Pre-group positions by strategy (O(n) instead of O(n*m))
        positions_by_strategy: dict[str, list[Position]] = {}
        for position in positions:
            strategy_name = position.strategy
            if strategy_name not in positions_by_strategy:
                positions_by_strategy[strategy_name] = []
            positions_by_strategy[strategy_name].append(position)

        signals: list[ExitSignal] = []

        if self.config.parallel_exits:
            # Run all strategies in parallel with pre-grouped positions
            tasks = [
                self._check_exits_safe(
                    strategy,
                    positions_by_strategy.get(strategy.name, []),
                    market_data,
                    market_state,
                )
                for strategy in self.strategies.values()
            ]
            results = await asyncio.gather(*tasks)

            for result in results:
                signals.extend(result)
        else:
            # Run sequentially with pre-grouped positions
            for strategy in self.strategies.values():
                strategy_positions = positions_by_strategy.get(strategy.name, [])
                result = await self._check_exits_safe(
                    strategy, strategy_positions, market_data, market_state
                )
                signals.extend(result)

        # Sort by priority (lower = higher priority)
        signals.sort(key=lambda s: s.priority)

        if signals:
            logger.info(
                f"Exit signals: {len(signals)} for {len(positions)} positions"
            )

        return signals

    async def _check_exits_safe(
        self,
        strategy: TradingStrategy,
        strategy_positions: list[Position],
        market_data: dict[str, Any],
        market_state: Any | None,
    ) -> list[ExitSignal]:
        """Check exits with exception handling.

        Args:
            strategy: Trading strategy to check
            strategy_positions: Pre-filtered positions for this strategy
            market_data: Current market data
            market_state: Market regime

        Returns:
            List of exit signals
        """
        try:
            # Positions are already filtered by caller
            if not strategy_positions:
                return []

            # Use scan_positions if available
            if hasattr(strategy.exit, "scan_positions"):
                return await strategy.exit.scan_positions(
                    positions=strategy_positions,
                    market_data=market_data,
                    market_state=market_state,
                )

            # Fallback: check each position individually
            signals = []
            for position in strategy_positions:
                context = ExitContext(
                    position=position,
                    market_data=market_data,
                    market_state=market_state,
                    timestamp=datetime.now(),
                )
                should_exit, signal = await strategy.check_exit(context)
                if should_exit and signal:
                    signals.append(signal)

            return signals

        except Exception as e:
            logger.error(f"Exit check failed for {strategy.name}: {e}", exc_info=True)
            return []

    def _filter_signals(self, signals: list[Signal]) -> list[Signal]:
        """Filter signals by confidence threshold"""
        return [s for s in signals if s.confidence >= self.config.min_confidence]

    def _dedupe_signals(self, signals: list[Signal]) -> list[Signal]:
        """Deduplicate signals by symbol"""
        if not self.config.dedupe_by_symbol:
            return signals

        now = datetime.now()
        result = []

        for signal in signals:
            key = self._dedupe_key(signal)

            # Check recent signals
            last_time = self._recent_signals.get(key)
            if last_time:
                elapsed = (now - last_time).total_seconds()
                if elapsed < self.config.dedupe_window_seconds:
                    logger.debug(f"Deduped signal for {signal.code} (recent)")
                    continue

            # Keep signal
            result.append(signal)
            self._recent_signals[key] = now

        # Clean old entries
        cutoff = now
        self._recent_signals = {
            k: v
            for k, v in self._recent_signals.items()
            if (cutoff - v).total_seconds() < self.config.dedupe_window_seconds * 2
        }

        return result

    def _dedupe_key(self, signal: Signal) -> str:
        """Build dedupe key according to configured scope."""
        scope = self.config.dedupe_scope
        if scope == "symbol":
            return signal.code
        if scope == "strategy":
            return f"{signal.code}:{signal.strategy}"

        metadata = getattr(signal, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            metadata = {}
        direction = metadata.get("signal_direction") or metadata.get("direction")
        if not direction:
            # Missing direction should not over-dedupe distinct signals.
            ts = getattr(signal, "timestamp", None)
            if isinstance(ts, datetime):
                return f"{signal.code}:{signal.strategy}:ts:{ts.isoformat()}"
            return f"{signal.code}:{signal.strategy}:id:{id(signal)}"
        direction = str(direction)
        return f"{signal.code}:{signal.strategy}:{direction}"

    def get_strategy_info(self) -> list[dict[str, Any]]:
        """Get information about loaded strategies"""
        return [
            {
                "name": strategy.name,
                "entry": strategy.entry.name,
                "exit": strategy.exit.name,
                "required_indicators": strategy.required_indicators,
            }
            for strategy in self.strategies.values()
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get manager statistics"""
        return {
            "asset_class": self.asset_class,
            "strategy_count": len(self.strategies),
            "strategies": list(self.strategies.keys()),
            "required_indicators": self.required_indicators,
            "recent_signals_cached": len(self._recent_signals),
        }
