"""Core market-data and strategy execution components.

This package contains the stock "real-time" pipeline building blocks:
- `core.state_manager`: subscribes to `market:ticks` + `system:universe`,
  warms up from ClickHouse, and maintains per-symbol Polars DataFrames.
- `core.strategy_engine`: evaluates strategy logic (e.g., V35) using Polars
  vector operations.
"""

from core.data_engine import DataEngine, DataEngineConfig
from core.indicator_engine import IndicatorEngine, IndicatorEngineConfig
from core.state_manager import StateManager, StateManagerConfig
from core.strategy_engine import StrategyEngine, StrategyEngineConfig

__all__ = [
    "DataEngine",
    "DataEngineConfig",
    "IndicatorEngine",
    "IndicatorEngineConfig",
    "StateManager",
    "StateManagerConfig",
    "StrategyEngine",
    "StrategyEngineConfig",
]
