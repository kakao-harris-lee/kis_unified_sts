"""청산 전략 모듈

다양한 청산 전략 구현체.

Available Strategies:
    - ThreeStageExit: 3-Stage Dynamic Exit (SURVIVAL→BREAKEVEN→MAXIMIZE)
    - MomentumDecayExit: 모멘텀 소진 기반 스윙 청산
"""

from shared.strategy.exit.three_stage import (
    ThreeStageExit,
    ThreeStageExitConfig,
)
from shared.strategy.exit.momentum_decay import (
    MomentumDecayExit,
    MomentumDecayConfig,
)

__all__ = [
    # Three Stage Exit
    "ThreeStageExit",
    "ThreeStageExitConfig",
    # Momentum Decay Exit
    "MomentumDecayExit",
    "MomentumDecayConfig",
]
