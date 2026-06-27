"""청산 전략 모듈

다양한 청산 전략 구현체.

Available Strategies:
    - ThreeStageExit: 3-Stage Dynamic Exit (SURVIVAL→BREAKEVEN→MAXIMIZE)
    - MomentumDecayExit: 모멘텀 소진 기반 스윙 청산
    - TechnicalConsensusExit: RSI/Williams %R/MACD 합의 기반 스윙 청산
"""

from shared.strategy.exit.momentum_decay import (
    MomentumDecayConfig,
    MomentumDecayExit,
)
from shared.strategy.exit.technical_consensus_exit import (
    TechnicalConsensusExit,
    TechnicalConsensusExitConfig,
)
from shared.strategy.exit.three_stage import (
    ThreeStageExit,
    ThreeStageExitConfig,
)
from shared.strategy.exit.trix_golden_exit import (
    TrixGoldenExit,
    TrixGoldenExitConfig,
)

__all__ = [
    # Three Stage Exit
    "ThreeStageExit",
    "ThreeStageExitConfig",
    # Momentum Decay Exit
    "MomentumDecayExit",
    "MomentumDecayConfig",
    # TRIX Golden Exit
    "TrixGoldenExit",
    "TrixGoldenExitConfig",
    # Technical Consensus Exit
    "TechnicalConsensusExit",
    "TechnicalConsensusExitConfig",
]
