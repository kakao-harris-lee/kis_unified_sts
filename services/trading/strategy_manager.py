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
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from shared.exceptions import ConfigurationError, TradingSystemError
from shared.models.position import Position
from shared.models.signal import ExitSignal, Signal
from shared.strategy.base import (
    EntryContext,
    ExitContext,
    MarketStateProtocol,
    TradingStrategy,
)
from shared.strategy.decision_cadence import DecisionCadenceGate
from shared.strategy.filters import CostFilter, CostFilterConfig
from shared.strategy.registry import (
    StrategyFactory,
    register_builtin_components,
)

if TYPE_CHECKING:
    from shared.llm.market_context import MarketContext

# Local import to avoid circular dependencies
from services.trading.llm_context_provider import LLMContextProvider

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

    # Cost filter
    cost_filter_enabled: bool = True
    min_atr_cost_ratio: float = 1.5
    commission_rate: float = 0.003
    slippage_bps: float = 1.5

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

        if not isinstance(self.cost_filter_enabled, bool):
            raise TypeError(
                f"cost_filter_enabled must be bool, got {type(self.cost_filter_enabled)}"
            )

        if self.min_atr_cost_ratio <= 0.0:
            raise ValueError(
                f"min_atr_cost_ratio must be positive, got {self.min_atr_cost_ratio}"
            )

        if not (0.0 <= self.commission_rate <= 0.1):
            raise ValueError(
                f"commission_rate must be between 0.0 and 0.1, got {self.commission_rate}"
            )

        if not (0.0 <= self.slippage_bps <= 100.0):
            raise ValueError(
                f"slippage_bps must be between 0.0 and 100.0, got {self.slippage_bps}"
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
        cost_filter_enabled = data.get("cost_filter_enabled", True)
        min_atr_cost_ratio = data.get("min_atr_cost_ratio", 1.5)
        commission_rate = data.get("commission_rate", 0.003)
        slippage_bps = data.get("slippage_bps", 1.5)

        # Type validation
        if not isinstance(min_confidence, (int, float)):
            raise TypeError(
                f"min_confidence must be numeric, got {type(min_confidence)}"
            )
        if not isinstance(dedupe_window, (int, float)):
            raise TypeError(
                f"dedupe_window_seconds must be numeric, got {type(dedupe_window)}"
            )
        if not isinstance(min_atr_cost_ratio, (int, float)):
            raise TypeError(
                f"min_atr_cost_ratio must be numeric, got {type(min_atr_cost_ratio)}"
            )
        if not isinstance(commission_rate, (int, float)):
            raise TypeError(
                f"commission_rate must be numeric, got {type(commission_rate)}"
            )
        if not isinstance(slippage_bps, (int, float)):
            raise TypeError(f"slippage_bps must be numeric, got {type(slippage_bps)}")

        return cls(
            min_confidence=float(min_confidence),
            dedupe_by_symbol=bool(dedupe_by_symbol),
            dedupe_scope=str(dedupe_scope),
            dedupe_window_seconds=float(dedupe_window),
            parallel_entries=bool(parallel_entries),
            parallel_exits=bool(parallel_exits),
            cost_filter_enabled=bool(cost_filter_enabled),
            min_atr_cost_ratio=float(min_atr_cost_ratio),
            commission_rate=float(commission_rate),
            slippage_bps=float(slippage_bps),
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
        indicator_engine: Any | None = None,
    ):
        """
        Args:
            asset_class: Asset class ("stock" or "futures")
            strategy_names: Specific strategies to load (None = all enabled)
            config: Manager configuration
            indicator_engine: Optional indicator engine exposing
                ``mtf_total_appended(symbol, timeframe)`` for the
                decision-cadence gate (futures 15m strategies).
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

        # Initialize cost filter
        if self.config.cost_filter_enabled:
            cost_filter_config = CostFilterConfig(
                min_atr_cost_ratio=self.config.min_atr_cost_ratio,
                commission_rate=self.config.commission_rate,
                slippage_bps=self.config.slippage_bps,
            )
            self.cost_filter = CostFilter(cost_filter_config)
        else:
            self.cost_filter = None

        # LLM context provider for market analysis
        self._llm_context_provider = LLMContextProvider(asset_class=asset_class)

        # Throttle for cycle summary logging (every 60s)
        self._last_cycle_log_time: float = 0.0

        # Decision-cadence gates. DRY: ONE DecisionCadenceGate *class*
        # (shared/strategy/decision_cadence.py), reused for both the backtest
        # adapter and here. Parity goal: a timeframe_minutes=N strategy must
        # decide entry ONCE and exit ONCE per CLOSED N-min bar (same as the
        # probe / backtest adapter).
        #
        # Why TWO gate instances per strategy (entry vs exit) and NOT one
        # shared instance: in the backtest adapter the engine is sequential
        # (check_exit then on_bar, one decision per bar) so a single gate
        # works. In LIVE the orchestrator drives entry and exit as INDEPENDENT
        # async loops on separate intervals (services/trading/pipeline.py
        # _run_stage_loop per PipelineStage) that each poll continuously. With
        # a SINGLE shared watermark, whichever loop fires first after a 15m
        # bar closes advances the watermark and STARVES the other loop for
        # that whole window — erratic entry/exit alternation, the OPPOSITE of
        # parity. Independent per-side watermarks give true parity: entry
        # decides exactly once and exit decides exactly once per closed bar.
        # The reviewer's stated drift bug (exit firing a bar late when
        # _check_exits_safe raises) is fixed by advancing the watermark in a
        # `finally` (mark before the strategy call so an exception never skips
        # it; never advances on a non-decision bar; never twice).
        self._indicator_engine: Any | None = indicator_engine
        self._cadence_gates: dict[str, DecisionCadenceGate] = {}
        self._exit_cadence_gates: dict[str, DecisionCadenceGate] = {}
        self._rebuild_cadence_gates()

        logger.info(
            f"StrategyManager initialized: {len(self.strategies)} strategies "
            f"for {asset_class}, cost_filter={'enabled' if self.cost_filter else 'disabled'}"
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
                except (ConfigurationError, ValueError, TypeError, KeyError) as e:
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
            except (ConfigurationError, ValueError, TypeError, KeyError) as e:
                logger.error(f"Failed to load strategies: {e}")

    def _rebuild_cadence_gates(self) -> None:
        """Build per-strategy entry & exit DecisionCadenceGates.

        Same DecisionCadenceGate class (DRY) for both; separate instances per
        side because live entry/exit are independent async loops — see the
        rationale block in __init__. Reads
        ``strategy.entry.config.timeframe_minutes`` (default 0 → no-op).
        Call after strategies are loaded or added.
        """
        self._cadence_gates = {}
        self._exit_cadence_gates = {}
        for name, strategy in self.strategies.items():
            tf = int(
                getattr(
                    getattr(strategy.entry, "config", None),
                    "timeframe_minutes",
                    0,
                )
                or 0
            )
            self._cadence_gates[name] = DecisionCadenceGate(tf)
            self._exit_cadence_gates[name] = DecisionCadenceGate(tf)

    def set_indicator_engine(self, engine: Any) -> None:
        """Inject the indicator engine for decision-cadence gating.

        Called by the orchestrator after the engine is initialized so the
        manager can consult ``engine.mtf_total_appended`` per-symbol to gate
        N-min strategy decisions to closed-bar boundaries.
        """
        self._indicator_engine = engine

    def _gate_for(self, strategy_name: str, for_exit: bool) -> DecisionCadenceGate | None:
        """Return the entry or exit DecisionCadenceGate for a strategy."""
        gates = self._exit_cadence_gates if for_exit else self._cadence_gates
        return gates.get(strategy_name)

    def _gate_allows(
        self, strategy_name: str, symbol: str, for_exit: bool = False
    ) -> bool:
        """Return True if the cadence gate allows a decision for strategy/symbol.

        Entry and exit each have their OWN gate instance (same class, DRY) so
        that — with the live orchestrator's INDEPENDENT entry/exit loops — each
        side decides EXACTLY ONCE per closed N-min bar (true parity with the
        probe), instead of one side starving the other under a shared
        watermark. Pure predicate: it does NOT advance the watermark; callers
        must call _gate_mark_decided EXACTLY ONCE per (strategy,symbol,side)
        per decision bar in a ``finally`` (so an exception in the strategy
        never skips the advance and never causes a one-bar drift).

        If no indicator engine is set, always returns True (gate disabled →
        backward-compatible no-op for timeframe_minutes <= 1 and stock).
        Extracted helper, unit-tested by test_decision_cadence.py.
        """
        engine = self._indicator_engine
        if engine is None:
            return True
        gate = self._gate_for(strategy_name, for_exit)
        if gate is None or not gate.enabled:
            return True
        return gate.should_decide(engine, symbol)

    def _gate_mark_decided(
        self, strategy_name: str, symbol: str, for_exit: bool = False
    ) -> None:
        """Advance the entry/exit cadence watermark for strategy/symbol.

        Must be called EXACTLY ONCE per (strategy,symbol,side) per decision bar,
        in a ``finally`` block, so the watermark advances even if the strategy
        raised (fixing the reviewer's one-bar drift bug) — and only when it WAS
        a decision bar (callers guard with _gate_allows first). ``mark_decided``
        itself is a no-op when the gate is disabled.
        """
        engine = self._indicator_engine
        if engine is None:
            return
        gate = self._gate_for(strategy_name, for_exit)
        if gate is not None:
            gate.mark_decided(engine, symbol)

    def add_strategy(self, strategy: TradingStrategy):
        """Add a strategy manually"""
        self.strategies[strategy.name] = strategy
        self._rebuild_cadence_gates()
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

        # Fetch LLM market context and inject into EntryContext
        market_context = self._llm_context_provider.get_context()
        context.market_context = market_context

        if market_context:
            logger.debug(
                f"LLM market context injected: regime={market_context.regime}, "
                f"risk_score={market_context.risk_score:.2f}"
            )
        else:
            logger.debug(
                "No LLM market context available - strategies will proceed without it"
            )

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
        signals = self._filter_by_cost(signals, context)
        signals = self._dedupe_signals(signals)

        if signals:
            logger.info(
                f"Entry signals: {len(signals)} from {len(self.strategies)} strategies"
            )

        # Throttled cycle summary (every 60s) — helps diagnose silent periods
        now_mono = time.monotonic()
        if now_mono - self._last_cycle_log_time >= 60.0:
            strategy_names = ", ".join(self.strategies.keys())
            logger.info(f"Signal cycle: {len(signals)} signals from [{strategy_names}]")
            self._last_cycle_log_time = now_mono

        return signals

    async def _check_entry_safe(
        self,
        strategy: TradingStrategy,
        context: EntryContext,
    ) -> Signal | None:
        """Check entry with exception handling"""
        # Decision-cadence gate (ENTRY side): skip if no new closed N-min bar
        # since this side last decided. If it IS a decision bar, advance the
        # ENTRY watermark EXACTLY ONCE in a `finally` so it advances even if
        # strategy.check_entry raises (no one-bar drift) and exactly once per
        # decision bar (never on a non-decision bar — guarded by _gate_allows).
        market_data = getattr(context, "market_data", {}) or {}
        symbol = str(market_data.get("code", "") if isinstance(market_data, dict) else "")
        if not self._gate_allows(strategy.name, symbol):
            return None
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
        except TradingSystemError as e:
            logger.error(f"Entry check failed for {strategy.name}: {e}", exc_info=True)
            return None
        finally:
            self._gate_mark_decided(strategy.name, symbol)

    async def check_exits(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: MarketStateProtocol | None = None,
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

        # Fetch LLM market context and inject into ExitContext
        market_context = self._llm_context_provider.get_context()

        if market_context:
            logger.debug(
                f"LLM market context injected for exits: regime={market_context.regime}, "
                f"risk_score={market_context.risk_score:.2f}"
            )
        else:
            logger.debug(
                "No LLM market context available for exits - strategies will proceed without it"
            )

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
                    market_context,
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
                    strategy,
                    strategy_positions,
                    market_data,
                    market_state,
                    market_context,
                )
                signals.extend(result)

        # Sort by priority (lower = higher priority)
        signals.sort(key=lambda s: s.priority)

        if signals:
            logger.info(f"Exit signals: {len(signals)} for {len(positions)} positions")

        return signals

    async def _check_exits_safe(
        self,
        strategy: TradingStrategy,
        strategy_positions: list[Position],
        market_data: dict[str, Any],
        market_state: MarketStateProtocol | None,
        market_context: MarketContext | None,
    ) -> list[ExitSignal]:
        """Check exits with exception handling.

        Args:
            strategy: Trading strategy to check
            strategy_positions: Pre-filtered positions for this strategy
            market_data: Current market data
            market_state: Market regime
            market_context: LLM-derived market analysis context

        Returns:
            List of exit signals
        """
        # Positions are already filtered by caller
        if not strategy_positions:
            return []

        # Decision-cadence gate (EXIT side, independent watermark from entry):
        # keep only positions whose symbol has seen a new closed N-min bar for
        # the EXIT side (no-op when timeframe_minutes <= 1). The EXIT watermark
        # for each gated symbol is advanced EXACTLY ONCE in a `finally` so it
        # advances even if strategy.check_exit/scan_positions raises (fixes the
        # one-bar drift bug) and only on a decision bar (guarded by
        # _gate_allows). Independent per-side watermarks give true parity:
        # entry decides once and exit decides once per closed bar even though
        # the orchestrator drives them as separate async loops.
        gated_positions = [
            p for p in strategy_positions
            if self._gate_allows(strategy.name, p.code, for_exit=True)
        ]
        if not gated_positions:
            return []

        try:
            # Use scan_positions if available
            if hasattr(strategy.exit, "scan_positions"):
                return await strategy.exit.scan_positions(
                    positions=gated_positions,
                    market_data=market_data,
                    market_state=market_state,
                )

            # Fallback: check each position individually
            signals = []
            for position in gated_positions:
                context = ExitContext(
                    position=position,
                    market_data=market_data,
                    market_state=market_state,
                    market_context=market_context,
                    timestamp=datetime.now(),
                )
                should_exit, signal = await strategy.check_exit(context)
                if should_exit and signal:
                    signals.append(signal)

            return signals

        except TradingSystemError as e:
            logger.error(f"Exit check failed for {strategy.name}: {e}", exc_info=True)
            return []
        finally:
            # EXACTLY ONCE per gated (strategy,symbol) this decision bar, even
            # on exception (never on a non-decision bar — those were filtered
            # out of gated_positions above).
            for p in gated_positions:
                self._gate_mark_decided(strategy.name, p.code, for_exit=True)

    def _filter_signals(self, signals: list[Signal]) -> list[Signal]:
        """Filter signals by confidence threshold"""
        return [s for s in signals if s.confidence >= self.config.min_confidence]

    def _filter_by_cost(
        self, signals: list[Signal], context: EntryContext
    ) -> list[Signal]:
        """Filter signals by cost-aware edge threshold.

        Args:
            signals: Signals to filter
            context: Entry context with market data and indicators

        Returns:
            Filtered signals that pass cost filter
        """
        if not self.cost_filter:
            return signals

        filtered = []
        for signal in signals:
            # EntryContext market_data/indicators may be either:
            # 1) symbol-scoped flat payloads (orchestrator hot path), or
            # 2) symbol-keyed nested dicts (some tests/backtests).
            indicators = self._resolve_symbol_payload(context.indicators, signal.code)
            market_data = self._resolve_symbol_payload(context.market_data, signal.code)
            indicators = self._with_cost_atr_alias(indicators, market_data)
            price = market_data.get("close") or market_data.get("price", 0.0)

            # Check cost filter
            passed, reason = self.cost_filter.check_signal(signal, indicators, price)

            if passed:
                filtered.append(signal)
            else:
                logger.info(f"Cost filter rejected {signal.code}: {reason}")

        return filtered

    @staticmethod
    def _resolve_symbol_payload(payload: dict[str, Any], symbol: str) -> dict[str, Any]:
        """Resolve symbol-specific nested payloads while preserving flat contexts."""
        candidate = payload.get(symbol)
        if isinstance(candidate, dict):
            return candidate
        return payload

    @staticmethod
    def _with_cost_atr_alias(
        indicators: dict[str, Any], market_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Expose daily ATR under ``atr`` for the generic cost filter.

        Daily stock strategies publish precomputed indicators as ``daily_*``.
        Their entry logic handles those aliases, but the shared cost filter
        intentionally consumes the generic ``atr`` key. Add a local alias for
        the cost check without mutating the original EntryContext payload.
        """

        def positive_float(value: Any) -> float | None:
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                return None
            return parsed if parsed > 0 else None

        if positive_float(indicators.get("atr")) is not None:
            return indicators

        for payload in (indicators, market_data):
            atr = positive_float(payload.get("daily_atr"))
            if atr is not None:
                with_alias = dict(indicators)
                with_alias["atr"] = atr
                return with_alias

        return indicators

    def _dedupe_signals(self, signals: list[Signal]) -> list[Signal]:
        """Deduplicate signals by symbol"""
        if not self.config.dedupe_by_symbol:
            return signals

        # tz-aware UTC. _recent_signals values are stored from this `now`
        # below, so subsequent comparisons stay consistent within this dict.
        now = datetime.now(UTC)
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
        stats = {
            "asset_class": self.asset_class,
            "strategy_count": len(self.strategies),
            "strategies": list(self.strategies.keys()),
            "required_indicators": self.required_indicators,
            "recent_signals_cached": len(self._recent_signals),
        }

        # Add cost filter stats if enabled
        if self.cost_filter:
            stats["cost_filter"] = self.cost_filter.get_stats()

        return stats
