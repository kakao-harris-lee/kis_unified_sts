"""RL 모듈

KOSPI200 선물 강화학습 기반 자동매매.
Gymnasium 환경, Maskable PPO / SAC / Decision Transformer.
"""

from shared.ml.rl.env import Action, FuturesTradingEnv, PositionSide, RLEnvConfig, mask_fn
from shared.ml.rl.features import RLFeatureCalculator, RL_FEATURE_COLUMNS
from shared.ml.rl.wrappers import ContinuousActionWrapper

try:  # Optional runtime dependency (Crypto/websocket stack)
    from shared.ml.rl.paper_trader import RLPaperTrader, run_paper_trader
except Exception:  # pragma: no cover
    RLPaperTrader = None  # type: ignore
    run_paper_trader = None  # type: ignore

try:  # Optional: transformers for Decision Transformer
    from shared.ml.rl.decision_transformer import DTAgent, DTConfig, DTTrainer
except ImportError:  # pragma: no cover
    DTAgent = None  # type: ignore
    DTConfig = None  # type: ignore
    DTTrainer = None  # type: ignore

__all__ = [
    "Action",
    "ContinuousActionWrapper",
    "DTAgent",
    "DTConfig",
    "DTTrainer",
    "FuturesTradingEnv",
    "PositionSide",
    "RLEnvConfig",
    "RLFeatureCalculator",
    "RLPaperTrader",
    "RL_FEATURE_COLUMNS",
    "mask_fn",
    "run_paper_trader",
]
