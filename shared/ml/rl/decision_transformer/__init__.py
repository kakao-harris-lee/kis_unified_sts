"""Decision Transformer for KOSPI200 futures trading.

GPT architecture for (returns-to-go, state, action) sequence modeling.
Trained on MPPO expert rollouts for offline RL.
"""

from shared.ml.rl.decision_transformer.dataset import (
    TrajectoryCollector,
    TrajectoryDataset,
)
from shared.ml.rl.decision_transformer.model import DTAgent, DTConfig
from shared.ml.rl.decision_transformer.trainer import DTTrainer

__all__ = [
    "DTAgent",
    "DTConfig",
    "DTTrainer",
    "TrajectoryCollector",
    "TrajectoryDataset",
]
