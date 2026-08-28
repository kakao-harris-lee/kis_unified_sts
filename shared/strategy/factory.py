"""Strategy factory for composing registered strategy components."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from shared.config import ConfigLoader
from shared.exceptions import ConfigurationError

if TYPE_CHECKING:
    from shared.strategy.base import PositionSizer, TradingStrategy

logger = logging.getLogger("shared.strategy.registry")


class StrategyDeliberatelyExcluded(ConfigurationError):
    """Raised when a strategy is kept out of the roster *by design*.

    This is the opt-out channel for "this config is well-formed, but it must
    not run here" - e.g. the builder_v1 streaming-compatibility guard below.
    Every other exception out of :meth:`StrategyFactory.create` means the
    strategy was configured to run and could not be built, which is an
    operator-visible misconfiguration.

    Subclasses ``ConfigurationError`` on purpose so that callers of
    :meth:`StrategyFactory.create_from_file` which already catch
    ``ConfigurationError`` keep behaving exactly as before; only
    :meth:`StrategyFactory.build_roster` inspects the narrower type.
    """


@dataclass(frozen=True)
class StrategyBuildFailure:
    """One configured strategy that is absent from the roster, and why.

    Attributes:
        name: ``strategy.name`` from the config, or ``"unnamed"``.
        asset_class: ``strategy.asset_class`` from the config, if declared.
        error_type: Class name of the exception raised during construction.
        message: The exception's message, kept verbatim so the operator sees
            the original diagnosis rather than a paraphrase.
        deliberate: ``True`` when the factory excluded the strategy on purpose
            (:class:`StrategyDeliberatelyExcluded`); ``False`` when it is a
            misconfiguration that somebody has to fix.
    """

    name: str
    asset_class: str | None
    error_type: str
    message: str
    deliberate: bool


@dataclass(frozen=True)
class RosterBuildReport:
    """The strategies that were built, and every one that was not.

    ``strategies`` alone is what the runtime trades. ``failures`` is what makes
    the absences answerable: without it, a strategy dropped for being broken and
    a strategy the operator disabled with ``enabled: false`` look identical from
    outside - both are simply not in the roster.
    """

    strategies: list[TradingStrategy]
    failures: list[StrategyBuildFailure]

    @property
    def misconfigured(self) -> list[StrategyBuildFailure]:
        """Absences that are defects: configured to run, could not be built."""
        return [f for f in self.failures if not f.deliberate]

    @property
    def deliberately_excluded(self) -> list[StrategyBuildFailure]:
        """Absences the factory chose. Not operator error, nothing to fix."""
        return [f for f in self.failures if f.deliberate]


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

        # Streaming-runtime incompatibility guard: a builder_v1 strategy whose
        # conditions use an operator the streaming stock/futures daemon cannot
        # evaluate can NEVER fire, so it is excluded rather than added to the
        # roster as a permanently-inert strategy. STREAMING_UNSUPPORTED_OPERATORS
        # is empty today (the full-series Indicator Context covers every
        # operator), so this branch is dormant - but re-introducing an
        # unsupported operator is a one-line change there, so the guard stays.
        # StrategyDeliberatelyExcluded, not a bare ConfigurationError: this is a
        # designed exclusion, and build_roster must not report it to the
        # operator as a misconfiguration to be fixed.
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
                    raise StrategyDeliberatelyExcluded(
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
        """Create all enabled strategies, tolerating individual failures.

        Thin wrapper over :meth:`build_roster` that returns only the strategies,
        for callers that build a roster and have nothing to do with the ones
        that failed. Failures are still logged loudly; use ``build_roster`` when
        the caller can act on them.

        Unlike :meth:`create_from_file`, this does NOT propagate: one broken
        strategy config must not leave a running system with an empty roster.
        """
        return cls.build_roster(asset_class, enabled_only).strategies

    @classmethod
    def build_roster(
        cls, asset_class: str | None = None, enabled_only: bool = True
    ) -> RosterBuildReport:
        """Build every configured strategy and report the ones that did not.

        Tolerating a failed strategy is deliberate - see :meth:`create_all` -
        but tolerance is not silence. Each absence is logged with its
        consequence and returned in :class:`RosterBuildReport` so the caller can
        distinguish the two reasons a strategy is missing from the roster:

        - Disabled on purpose (``enabled: false``): filtered out by
          ``ConfigLoader.load_all_strategies`` before the factory sees it, so it
          never appears as a failure. Nothing to fix.
        - Could not be built: recorded in ``failures``. Either a designed
          exclusion (:class:`StrategyDeliberatelyExcluded`) or, for every other
          exception, a misconfiguration the operator has to fix.

        Args:
            asset_class: Restrict to one asset class, or ``None`` for all.
            enabled_only: Skip configs with ``strategy.enabled: false``.

        Returns:
            The built strategies plus a classified record of every absence.
        """
        configs = ConfigLoader.load_all_strategies(asset_class, enabled_only)
        strategies: list[TradingStrategy] = []
        failures: list[StrategyBuildFailure] = []
        scope = asset_class or "all-assets"

        for config in configs:
            # Resolve identity the same way create() does, so the report names
            # the strategy exactly as the roster would have.
            strategy_cfg = config.get("strategy", config)
            name = strategy_cfg.get("name", "unnamed")
            declared_asset = strategy_cfg.get("asset_class")
            try:
                strategies.append(cls.create(config))
            except StrategyDeliberatelyExcluded as e:
                failures.append(
                    StrategyBuildFailure(
                        name=name,
                        asset_class=declared_asset,
                        error_type=type(e).__name__,
                        message=str(e),
                        deliberate=True,
                    )
                )
                logger.warning(
                    "Strategy '%s' (asset_class=%s) was excluded from the %s "
                    "roster by design - this is not a misconfiguration: %s",
                    name,
                    declared_asset,
                    scope,
                    e,
                )
            except Exception as e:  # noqa: BLE001 - classified and re-reported
                failures.append(
                    StrategyBuildFailure(
                        name=name,
                        asset_class=declared_asset,
                        error_type=type(e).__name__,
                        message=str(e),
                        deliberate=False,
                    )
                )
                logger.error(
                    "Strategy '%s' (asset_class=%s) is MISCONFIGURED and is NOT "
                    "in the %s roster: it will emit no signals and place no "
                    "orders for this entire run. It was not disabled - it was "
                    "configured to run and failed to build. %s: %s",
                    name,
                    declared_asset,
                    scope,
                    type(e).__name__,
                    e,
                )

        report = RosterBuildReport(strategies=strategies, failures=failures)
        cls._log_roster_summary(report, scope)
        return report

    @classmethod
    def _log_roster_summary(cls, report: RosterBuildReport, scope: str) -> None:
        """Log one line stating whether the roster is whole or degraded."""
        broken = report.misconfigured
        if not broken:
            logger.info(
                "%s roster: %d strategies active, %d excluded by design.",
                scope,
                len(report.strategies),
                len(report.deliberately_excluded),
            )
            return

        # No strategies at all, yet configs asked for some: the runtime is up
        # and will trade nothing. That is worse than any single bad config.
        level = logging.CRITICAL if not report.strategies else logging.ERROR
        logger.log(
            level,
            "%s roster is DEGRADED: %d strategies active, %d MISCONFIGURED and "
            "dropped (%s). Fix them, or disable them explicitly with "
            "'enabled: false' so the absence is intentional.",
            scope,
            len(report.strategies),
            len(broken),
            ", ".join(f.name for f in broken),
        )
