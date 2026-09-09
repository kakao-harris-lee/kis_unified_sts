"""``tos_runtime.strategy`` — loads Authored Strategy YAML files, admits
them through the kernel's own typed admission gate, and resolves the ONE
composition-root strategy source (TOS Phase 3 슬라이스 D-R,
``docs/plans/2026-09-09-tos-phase3-event-core-plan.md`` §1.2).

See :mod:`tos_runtime.strategy.loader` for the file-loading contract,
:mod:`tos_runtime.strategy.bindings` for the per-strategy config bindings
surface (``[D-R-3]``, finding #9 disposition), and
:mod:`tos_runtime.strategy.resolve` for the composition-root hookup
(building a :class:`~tos.engine.StrategyRegistry` from the loaded set, the
``registry``-injection-vs-file both-present refusal, the positive bindings
resolution, and the ``STRATEGY_REFUSED`` evidence-before-halt discipline).
"""

from __future__ import annotations

from tos_runtime.strategy.bindings import (
    STRATEGY_BINDINGS_FILE_NAME,
    LoadedStrategyBindings,
    OneStrategyBindings,
    StrategyBindingsLoadError,
    load_strategy_bindings,
)
from tos_runtime.strategy.loader import (
    AdmitFn,
    LoadedStrategies,
    LoadedStrategy,
    ParseFn,
    StrategyLoadError,
    load_strategies,
)
from tos_runtime.strategy.resolve import (
    STRATEGIES_DIRNAME,
    STRATEGY_REFUSED_EVIDENCE_KIND,
    STRATEGY_SOURCE_ABSENT_EVIDENCE_KIND,
    ResolvedStrategyRegistry,
    StrategyRegistryResolutionRefused,
    resolve_strategy_registry,
)

__all__ = [
    "STRATEGIES_DIRNAME",
    "STRATEGY_BINDINGS_FILE_NAME",
    "STRATEGY_REFUSED_EVIDENCE_KIND",
    "STRATEGY_SOURCE_ABSENT_EVIDENCE_KIND",
    "AdmitFn",
    "LoadedStrategies",
    "LoadedStrategy",
    "LoadedStrategyBindings",
    "OneStrategyBindings",
    "ParseFn",
    "ResolvedStrategyRegistry",
    "StrategyBindingsLoadError",
    "StrategyLoadError",
    "StrategyRegistryResolutionRefused",
    "load_strategies",
    "load_strategy_bindings",
    "resolve_strategy_registry",
]
