"""RL 모듈

KOSPI200 선물 강화학습 기반 자동매매.
Gymnasium 환경, Maskable PPO / SAC 학습, 평가 파이프라인, Paper Trading.
"""

from shared.ml.rl.env import Action, FuturesTradingEnv, PositionSide, RLEnvConfig, mask_fn
from shared.ml.rl.features import RLFeatureCalculator, RL_FEATURE_COLUMNS
from shared.ml.rl.wrappers import ContinuousActionWrapper

try:  # Optional runtime dependency (Crypto/websocket stack)
    from shared.ml.rl.paper_trader import RLPaperTrader, run_paper_trader
except Exception:  # pragma: no cover
    RLPaperTrader = None  # type: ignore
    run_paper_trader = None  # type: ignore

__all__ = [
    "Action",
    "ContinuousActionWrapper",
    "FuturesTradingEnv",
    "PositionSide",
    "RLEnvConfig",
    "RLFeatureCalculator",
    "RLPaperTrader",
    "RL_FEATURE_COLUMNS",
    "mask_fn",
    "run_paper_trader",
]
