"""Trading 서비스 모듈

Trading Orchestrator 및 파이프라인 관리.

Usage:
    from services.trading import TradingOrchestrator, TradingConfig

    orchestrator = TradingOrchestrator(config)
    await orchestrator.start()
"""

from services.trading.data_provider import (
    DataProviderConfig,
    MarketDataProvider,
)
from services.trading.orchestrator import (
    TradingConfig,
    TradingOrchestrator,
    TradingState,
)
from services.trading.pipeline import (
    CircuitBreaker,
    PipelineStage,
    TradingPipeline,
)
from services.trading.position_tracker import (
    PositionTracker,
    PositionTrackerConfig,
)
from services.trading.strategy_manager import (
    StrategyManager,
    StrategyManagerConfig,
)

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
