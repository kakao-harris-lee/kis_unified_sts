"""백테스트 모듈

통합 백테스트 엔진, MLflow 트래킹, 결과 분석.

Usage:
    from shared.backtest import BacktestEngine, BacktestConfig, BacktestResult
    from shared.backtest import MLflowTracker

    engine = BacktestEngine(strategy, config)
    result = engine.run(data)

    # MLflow 추적
    with MLflowTracker("experiment") as tracker:
        tracker.log_result(result, strategy_config)
"""

from shared.backtest.adapter import BacktestStrategyAdapter
from shared.backtest.config import (
    BacktestConfig,
    CostConfig,
    RiskConfig,
)
from shared.backtest.engine import BacktestEngine
from shared.backtest.mlflow_tracker import (
    MLflowTracker,
    track_backtest,
)
from shared.backtest.optimizer import (
    ParamSpec,
    StrategyOptimizer,
    quick_optimize,
)
from shared.backtest.result import (
    BacktestResult,
    BacktestTrade,
)

# NOTE: VectorbtRunner (shared.backtest.vbt_runner) 는 여기서 re-export 하지
# 않는다 — 모듈 자체는 vectorbt 를 lazy import 하지만, opt-in 백엔드라는
# 의도를 import 경로(`from shared.backtest.vbt_runner import VectorbtRunner`)
# 로도 드러낸다. `import shared.backtest` 는 vectorbt 없이 항상 동작해야
# 한다 (tests/unit/backtest/test_vbt_runner.py::TestImportIsolation 이 고정).

__all__ = [
    # Result
    "BacktestResult",
    "BacktestTrade",
    # Config
    "BacktestConfig",
    "CostConfig",
    "RiskConfig",
    # Engine
    "BacktestEngine",
    # Adapter
    "BacktestStrategyAdapter",
    # MLflow
    "MLflowTracker",
    "track_backtest",
    # Optimizer
    "StrategyOptimizer",
    "ParamSpec",
    "quick_optimize",
]
