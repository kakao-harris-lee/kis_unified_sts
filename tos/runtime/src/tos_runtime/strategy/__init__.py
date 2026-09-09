"""``tos_runtime.strategy`` — loads Authored Strategy YAML files and admits
them through the kernel's own typed admission gate (TOS Phase 3 슬라이스 D-R,
``docs/plans/2026-09-09-tos-phase3-event-core-plan.md`` §1.2).

See :mod:`tos_runtime.strategy.loader` for the loader contract. The
composition-root hookup (building a :class:`~tos.engine.StrategyRegistry`
from the loaded set, and the ``registry``-injection-vs-file both-present
refusal) is plan §1.2 ``[D-R-2]``, gated on ``[A-R-done]`` landing first —
not yet wired here.
"""

from __future__ import annotations

from tos_runtime.strategy.loader import (
    AdmitFn,
    LoadedStrategies,
    LoadedStrategy,
    ParseFn,
    StrategyLoadError,
    load_strategies,
)

__all__ = [
    "AdmitFn",
    "LoadedStrategies",
    "LoadedStrategy",
    "ParseFn",
    "StrategyLoadError",
    "load_strategies",
]
