"""Strategy factory for composing registered strategy components."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from shared.config import ConfigLoader
from shared.exceptions import ConfigurationError

if TYPE_CHECKING:
    from shared.strategy.base import PositionSizer, TradingStrategy

logger = logging.getLogger("shared.strategy.registry")


class StrategyFactory:
    """Create trading strategies from strategy config dictionaries and files."""

    @classmethod
    def create(cls, config: dict[str, Any]) -> TradingStrategy:
        """Create a strategy from a config dictionary."""
        from shared.strategy.base import TradingStrategy
        from shared.strategy.registry import (
            ComponentNotFoundError,
            EntryRegistry,
            ExitRegistry,
            SizerRegistry,
        )

        strategy_cfg = config.get("strategy", config)

        entry_cfg = strategy_cfg.get("entry", {})
        entry_type = entry_cfg.get("type", "default")
        entry_params = entry_cfg.get("params", {})

        if not EntryRegistry.is_registered(entry_type):
            raise ComponentNotFoundError(
                f"Entry strategy not found: '{entry_type}'. "
                f"Available: {EntryRegistry.list_all()}"
            )

        # P2-3 T7 fix: get (not pop) - entry_params may reference ConfigLoader's
        # cached dict; mutating it silently disables the gate on subsequent calls.
        gate_yaml = entry_params.get("regime_gate")
        # Filter the gate section out for the entry config (CONFIG_CLASS
        # doesn't accept it). Build a fresh dict - do NOT mutate entry_params.
        entry_params_filtered = {
            k: v for k, v in entry_params.items() if k != "regime_gate"
        }

        entry = EntryRegistry.create(entry_type, entry_params_filtered)

        # Streaming-runtime incompatibility guard: builder_v1 strategies whose
        # entry conditions use cross_above/cross_below operators can NEVER fire
        # in the streaming stock/futures daemon (no cross-cycle history series
        # and no arbitrary-period SMA keys). Raise ConfigurationError here so
        # StrategyFactory.create_all's existing warning+skip loop excludes them
        # from the active roster instead of adding a permanently-inert strategy.
        # This is the single authoritative gate; BuilderStrategyEntry._parse_state
        # still logs loudly when instantiated directly (e.g. in tests or backtest),
        # but the streaming roster path never reaches generate() for these.
        builder_state = None
        if entry_type == "builder_v1":
            builder_state = getattr(entry, "_state", None)
            if builder_state is not None:
                from shared.strategy_builder.runtime_support import (
                    streaming_support_reason,
                )

                reason = streaming_support_reason(builder_state)
                if reason is not None:
                    strategy_name = strategy_cfg.get("name", "unnamed")
                    raise ConfigurationError(
                        f"Skipping streaming-incompatible builder_v1 strategy "
                        f"'{strategy_name}': {reason}"
                    )
                # Schema-v2 gate hook: a BuilderState-declared regime gate feeds
                # the same generic _gate_cfg attachment below. The entry params'
                # regime_gate section (deploy-time override) wins when both exist.
                if (
                    gate_yaml is None
                    and builder_state.gates is not None
                    and builder_state.gates.regime_gate is not None
                ):
                    gate_yaml = builder_state.gates.regime_gate.model_dump()

        # Attach GateConfig to the adapter (P2-3 T7).  The hasattr guard
        # preserves backward-compat for entry adapters that don't support gates.
        if hasattr(entry, "_gate_cfg"):
            from shared.strategy.gates.regime_gate import regime_gate_cfg_from_yaml

            entry._gate_cfg = regime_gate_cfg_from_yaml(gate_yaml)

        exit_cfg = strategy_cfg.get("exit", {})
        exit_type = exit_cfg.get("type", "default")
        exit_params = exit_cfg.get("params", {})

        if not ExitRegistry.is_registered(exit_type):
            raise ComponentNotFoundError(
                f"Exit strategy not found: '{exit_type}'. "
                f"Available: {ExitRegistry.list_all()}"
            )

        exit = ExitRegistry.create(exit_type, exit_params)

        # Schema-v2 named exit primitive: compose the declarative builder exit
        # with the referenced registered exit component (first trigger wins).
        if builder_state is not None and builder_state.exit_primitive is not None:
            exit = cls._compose_builder_exit_primitive(
                exit, builder_state, strategy_cfg.get("name", "unnamed")
            )

        position_cfg = strategy_cfg.get("position", {})
        position_type = position_cfg.get("type", "fixed")
        position_params = position_cfg.get("params", {})

        if SizerRegistry.is_registered(position_type):
            sizer = SizerRegistry.create(position_type, position_params)
        else:
            sizer = cls._create_default_sizer(position_params)

        return TradingStrategy(
            name=strategy_cfg.get("name", "unnamed"),
            entry=entry,
            exit=exit,
            position_sizer=sizer,
        )

    @classmethod
    def _compose_builder_exit_primitive(
        cls,
        declarative_exit: Any,
        builder_state: Any,
        strategy_name: str,
    ) -> Any:
        """Compose a builder exit with its schema-declared named primitive.

        Validates ``BuilderState.exit_primitive`` against the ExitRegistry
        (the SoT for primitive names, plus catalog asset-class restrictions)
        and wraps the declarative exit + primitive in a ``FirstTriggerExit``
        (declarative risk block evaluated first).

        Args:
            declarative_exit: The exit created from the strategy YAML
                (normally ``builder_v1_exit``).
            builder_state: Parsed ``BuilderState`` with a non-None
                ``exit_primitive``.
            strategy_name: Strategy name for actionable error messages.

        Returns:
            The composed exit generator.

        Raises:
            ConfigurationError: When the primitive reference is invalid.
        """
        from shared.strategy.exit.composite import FirstTriggerExit
        from shared.strategy.registry import ExitRegistry
        from shared.strategy_builder.exit_primitives import validate_exit_primitive

        error = validate_exit_primitive(builder_state)
        if error is not None:
            raise ConfigurationError(f"builder_v1 strategy '{strategy_name}': {error}")
        ref = builder_state.exit_primitive
        primitive_exit = ExitRegistry.create(ref.primitive, dict(ref.params))
        logger.info(
            "builder_v1 strategy '%s': composing exit primitive '%s' with the "
            "declarative risk block",
            strategy_name,
            ref.primitive,
        )
        return FirstTriggerExit([declarative_exit, primitive_exit])

    @classmethod
    def _create_default_sizer(cls, params: dict[str, Any]) -> PositionSizer:
        """Create the default fixed position sizer."""
        from shared.strategy.position import FixedSizer, FixedSizerConfig

        config = FixedSizerConfig.from_dict(params)
        return FixedSizer(config)

    @classmethod
    def create_from_file(cls, asset_class: str, strategy_name: str) -> TradingStrategy:
        """Create a strategy from a strategy config file."""
        config = ConfigLoader.load_strategy(asset_class, strategy_name)
        return cls.create(config)

    @classmethod
    def create_all(
        cls, asset_class: str | None = None, enabled_only: bool = True
    ) -> list[TradingStrategy]:
        """Create all enabled strategies, warning and skipping failures."""
        configs = ConfigLoader.load_all_strategies(asset_class, enabled_only)
        strategies = []

        for config in configs:
            try:
                strategy = cls.create(config)
                strategies.append(strategy)
            except Exception as e:
                strategy_name = config.get("strategy", {}).get("name", "unknown")
                logger.warning(f"Failed to create strategy '{strategy_name}': {e}")

        return strategies
