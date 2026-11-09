"""Builtin strategy component registration tables."""

from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger("shared.strategy.registry")

BuiltinComponentTable = tuple[tuple[str, tuple[tuple[str, str], ...], str], ...]

#: Entry components are EMPTY since the legacy-removal step L6: every
#: ``shared.strategy.entry.*`` module was outside the surviving import closure
#: and was deleted (docs/plans/2026-11-07-legacy-removal-plan.md §3). The table
#: and its loader stay because ``register_builtin_components`` is still the one
#: place a component is wired, and ``EntryRegistry`` is still read by
#: ``StrategyFactory``; L7 measures whether that whole path can go.
_BUILTIN_ENTRY_COMPONENTS: BuiltinComponentTable = ()

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
        "shared.strategy.exit.trix_golden_exit",
        (("trix_golden_exit", "TrixGoldenExit"),),
        "TrixGoldenExit",
    ),
    (
        "shared.strategy.exit.setup_target_exit",
        (("setup_target_exit", "SetupTargetExit"),),
        "SetupTargetExit",
    ),
    (
        "shared.strategy.exit.technical_consensus_exit",
        (("technical_consensus_exit", "TechnicalConsensusExit"),),
        "TechnicalConsensusExit",
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
