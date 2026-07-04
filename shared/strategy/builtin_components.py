"""Builtin strategy component registration tables."""

from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger("shared.strategy.registry")

BuiltinComponentTable = tuple[tuple[str, tuple[tuple[str, str], ...], str], ...]

_BUILTIN_ENTRY_COMPONENTS: BuiltinComponentTable = (
    (
        "shared.strategy.entry.stochrsi_trend",
        (("stochrsi_trend", "StochRSITrendEntry"),),
        "StochRSITrendEntry",
    ),
    (
        "shared.strategy.entry.mean_reversion",
        (("mean_reversion", "MeanReversionEntry"),),
        "MeanReversionEntry",
    ),
    (
        "shared.strategy.entry.breakout",
        (("breakout", "BreakoutEntry"),),
        "BreakoutEntry",
    ),
    (
        "shared.strategy.entry.opening_volume_surge",
        (("opening_volume_surge", "OpeningVolumeSurgeEntry"),),
        "OpeningVolumeSurgeEntry",
    ),
    (
        "shared.strategy.entry.volume_accumulation",
        (("volume_accumulation", "VolumeAccumulationBreakoutEntry"),),
        "VolumeAccumulationBreakoutEntry",
    ),
    (
        "shared.strategy.entry.trix_golden",
        (("trix_golden", "TrixGoldenEntry"),),
        "TrixGoldenEntry",
    ),
    (
        "shared.strategy.entry.williams_r",
        (("williams_r", "WilliamsREntry"),),
        "WilliamsREntry",
    ),
    (
        "shared.strategy.entry.macd_ema_crossover",
        (("macd_ema_crossover", "MACDEMACrossoverEntry"),),
        "MACDEMACrossoverEntry",
    ),
    (
        "shared.strategy.entry.builder_strategy",
        (("builder_v1", "BuilderStrategyEntry"),),
        "BuilderStrategyEntry",
    ),
    (
        "shared.strategy.entry.technical_consensus",
        (("technical_consensus", "TechnicalConsensusEntry"),),
        "TechnicalConsensusEntry",
    ),
    (
        "shared.strategy.entry.llm_directed_indicator",
        (("llm_directed_indicator", "LLMDirectedIndicatorEntry"),),
        "LLMDirectedIndicatorEntry",
    ),
    (
        "shared.strategy.entry.trend_pullback",
        (("trend_pullback", "TrendPullbackEntry"),),
        "TrendPullbackEntry",
    ),
    (
        "shared.strategy.entry.momentum_breakout",
        (("momentum_breakout", "MomentumBreakoutEntry"),),
        "MomentumBreakoutEntry",
    ),
    (
        "shared.strategy.entry.trend_continuation_vwap",
        (("trend_continuation_vwap", "TrendContinuationVWAPEntry"),),
        "TrendContinuationVWAPEntry",
    ),
    (
        "shared.strategy.entry.daily_pullback",
        (("daily_pullback", "DailyPullbackEntry"),),
        "DailyPullbackEntry",
    ),
    (
        "shared.strategy.entry.pattern_pullback",
        (("pattern_pullback", "PatternPullbackEntry"),),
        "PatternPullbackEntry",
    ),
    (
        "shared.strategy.entry.setup_adapters",
        (
            ("setup_a_gap_reversion", "SetupAEntryAdapter"),
            ("setup_c_event_reaction", "SetupCEntryAdapter"),
            ("setup_d_vwap_reversion", "SetupDEntryAdapter"),
        ),
        "Setup adapters (SetupAEntryAdapter, SetupCEntryAdapter, SetupDEntryAdapter)",
    ),
    (
        "shared.strategy.entry.vr_composite",
        (("vr_composite", "VRCompositeEntry"),),
        "VRCompositeEntry",
    ),
)

_BUILTIN_EXIT_COMPONENTS: BuiltinComponentTable = (
    (
        "shared.strategy.exit.three_stage",
        (("three_stage", "ThreeStageExit"),),
        "ThreeStageExit",
    ),
    (
        "shared.strategy.exit.momentum_decay",
        (("momentum_decay", "MomentumDecayExit"),),
        "MomentumDecayExit",
    ),
    (
        "shared.strategy.exit.builder_strategy_exit",
        (("builder_v1_exit", "BuilderStrategyExit"),),
        "BuilderStrategyExit",
    ),
    (
        "shared.strategy.exit.trix_golden_exit",
        (("trix_golden_exit", "TrixGoldenExit"),),
        "TrixGoldenExit",
    ),
    (
        "shared.strategy.exit.williams_r_exit",
        (("williams_r_exit", "WilliamsRExit"),),
        "WilliamsRExit",
    ),
    (
        "shared.strategy.exit.llm_directed_indicator_exit",
        (("llm_directed_indicator_exit", "LLMDirectedIndicatorExit"),),
        "LLMDirectedIndicatorExit",
    ),
    (
        "shared.strategy.exit.mean_reversion_exit",
        (("mean_reversion_exit", "MeanReversionExit"),),
        "MeanReversionExit",
    ),
    (
        "shared.strategy.exit.atr_dynamic",
        (("atr_dynamic", "ATRDynamicExit"),),
        "ATRDynamicExit",
    ),
    (
        "shared.strategy.exit.setup_target_exit",
        (("setup_target_exit", "SetupTargetExit"),),
        "SetupTargetExit",
    ),
    (
        "shared.strategy.exit.track_a_exit",
        (("track_a_exit", "TrackAExit"),),
        "TrackAExit",
    ),
    (
        "shared.strategy.exit.chandelier_exit",
        (("chandelier_exit", "ChandelierExit"),),
        "ChandelierExit",
    ),
    (
        "shared.strategy.exit.technical_consensus_exit",
        (("technical_consensus_exit", "TechnicalConsensusExit"),),
        "TechnicalConsensusExit",
    ),
    (
        "shared.strategy.exit.vr_composite_exit",
        (("vr_composite_exit", "VRCompositeExit"),),
        "VRCompositeExit",
    ),
)

_BUILTIN_SIZER_COMPONENTS: BuiltinComponentTable = (
    (
        "shared.strategy.position.sizers",
        (("fixed_fractional_futures", "FixedFractionalFuturesSizer"),),
        "FixedFractionalFuturesSizer",
    ),
    (
        "shared.strategy.position",
        (
            ("fixed", "FixedSizer"),
            ("risk_based", "RiskBasedSizer"),
        ),
        "Position sizers",
    ),
    (
        "shared.strategy.position.llm_adaptive_sizer",
        (("llm_adaptive", "LLMAdaptiveSizer"),),
        "LLMAdaptiveSizer",
    ),
)


def _register_builtin_table(registry: type[Any], table: BuiltinComponentTable) -> None:
    for module_path, registrations, debug_label in table:
        try:
            module = importlib.import_module(module_path)
        except ImportError:
            logger.debug("%s not available", debug_label)
            continue

        try:
            component_classes = [
                (name, getattr(module, class_name))
                for name, class_name in registrations
            ]
        except AttributeError:
            logger.debug("%s not available", debug_label)
            continue

        for name, component_class in component_classes:
            registry.register_class(name, component_class)


def register_builtin_components() -> None:
    """Register builtin strategy components."""
    from shared.strategy.registry import EntryRegistry, ExitRegistry, SizerRegistry

    _register_builtin_table(EntryRegistry, _BUILTIN_ENTRY_COMPONENTS)
    _register_builtin_table(ExitRegistry, _BUILTIN_EXIT_COMPONENTS)
    _register_builtin_table(SizerRegistry, _BUILTIN_SIZER_COMPONENTS)

    logger.info(
        f"Registered components - "
        f"Entry: {EntryRegistry.list_all()}, "
        f"Exit: {ExitRegistry.list_all()}, "
        f"Sizer: {SizerRegistry.list_all()}"
    )
