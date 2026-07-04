"""Trading service facade.

Public convenience imports stay available, but heavy runtime modules are loaded
only when their exported symbols are requested.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from services.trading.data_provider import DataProviderConfig, MarketDataProvider
    from services.trading.orchestrator import TradingOrchestrator
    from services.trading.pipeline import CircuitBreaker, PipelineStage, TradingPipeline
    from services.trading.position_tracker import (
        PositionTracker,
        PositionTrackerConfig,
    )
    from services.trading.runtime_config import TradingConfig
    from services.trading.session_calendar import TradingState
    from services.trading.strategy_manager import StrategyManager, StrategyManagerConfig

_EXPORT_MODULES = {
    # Orchestrator facade
    "TradingOrchestrator": "services.trading.orchestrator",
    "TradingConfig": "services.trading.runtime_config",
    "TradingState": "services.trading.session_calendar",
    # Pipeline
    "TradingPipeline": "services.trading.pipeline",
    "PipelineStage": "services.trading.pipeline",
    "CircuitBreaker": "services.trading.pipeline",
    # Components
    "MarketDataProvider": "services.trading.data_provider",
    "DataProviderConfig": "services.trading.data_provider",
    "PositionTracker": "services.trading.position_tracker",
    "PositionTrackerConfig": "services.trading.position_tracker",
    "StrategyManager": "services.trading.strategy_manager",
    "StrategyManagerConfig": "services.trading.strategy_manager",
}

_SUBMODULES = {
    "data_provider": "services.trading.data_provider",
    "execution_facade": "services.trading.execution_facade",
    "orchestrator": "services.trading.orchestrator",
    "pipeline": "services.trading.pipeline",
    "position_tracker": "services.trading.position_tracker",
    "reentry_guard": "services.trading.reentry_guard",
    "recovery": "services.trading.recovery",
    "runtime_config": "services.trading.runtime_config",
    "session_calendar": "services.trading.session_calendar",
    "strategy_manager": "services.trading.strategy_manager",
}

__all__ = [
    # Orchestrator
    "TradingOrchestrator",
    "TradingConfig",
    "TradingState",
    # Pipeline
    "TradingPipeline",
    "PipelineStage",
    "CircuitBreaker",
    # Components
    "MarketDataProvider",
    "DataProviderConfig",
    "PositionTracker",
    "PositionTrackerConfig",
    "StrategyManager",
    "StrategyManagerConfig",
]


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None and name in _SUBMODULES:
        value = import_module(_SUBMODULES[name])
        globals()[name] = value
        return value

    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(_SUBMODULES))
