"""청산 전략 모듈

다양한 청산 전략 구현체.

Available Strategies:
    - E1: ThreeStageExit (3-Stage Dynamic Exit)
    - E2: ATRTrailingExit (ATR-based Dynamic Trailing)
    - E3: TimeDecayExit (Time-based Exit)
    - E4: MarketRegimeExit (Market State-based Exit)
"""

from shared.strategy.exit.three_stage import (
    ThreeStageExit,
    ThreeStageExitConfig,
)
from shared.strategy.exit.atr_trailing import (
    ATRTrailingExit,
    ATRTrailingConfig,
)
from shared.strategy.exit.time_decay import (
    TimeDecayExit,
    TimeDecayConfig,
)
from shared.strategy.exit.market_regime import (
    MarketRegimeExit,
    MarketRegimeConfig,
)
from shared.strategy.exit.momentum_decay import (
    MomentumDecayExit,
    MomentumDecayConfig,
)

__all__ = [
    # E1: Three Stage Exit
    "ThreeStageExit",
    "ThreeStageExitConfig",
    # E2: ATR Trailing Exit
    "ATRTrailingExit",
    "ATRTrailingConfig",
    # E3: Time Decay Exit
    "TimeDecayExit",
    "TimeDecayConfig",
    # E4: Market Regime Exit
    "MarketRegimeExit",
    "MarketRegimeConfig",
    # E5: Momentum Decay Exit
    "MomentumDecayExit",
    "MomentumDecayConfig",
]
