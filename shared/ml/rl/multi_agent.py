"""레짐 인식 멀티 에이전트 RL

HMM으로 감지된 레짐별 특화 에이전트를 라우팅.
BULL/BEAR/SIDEWAYS 각각에 별도 모델을 학습하고,
추론 시 현재 레짐에 맞는 모델을 선택.

Usage:
    agent = RegimeAwareAgent.from_yaml("ml/rl_multi_agent.yaml")
    agent.train(train_days, train_prices)
    action = agent.predict(obs, masks, regime_features)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from shared.config import ConfigLoader
from shared.ml.rl.env import RLEnvConfig
from shared.regime.hmm_detector import HMMConfig, HMMRegimeDetector, HMMRegimeState

logger = logging.getLogger(__name__)


class RegimeAwareAgent:
    """레짐별 특화 에이전트 라우터

    구조:
        HMM Detector → 현재 레짐 판정
        → regime_models[regime] → 해당 레짐 모델로 추론

    학습:
        1. 전체 데이터로 HMM 학습
        2. 데이터를 레짐별로 분할
        3. 각 레짐별 RL 모델 학습

    추론:
        1. HMM으로 현재 레짐 예측
        2. 해당 레짐 모델로 행동 결정
        3. 확신 낮으면 fallback 모델 사용
    """

    def __init__(
        self,
        config_path: str = "ml/rl_multi_agent.yaml",
        hmm_detector: HMMRegimeDetector | None = None,
    ):
        self.config = ConfigLoader.load(config_path)
        self.config_path = config_path
        self.env_config = RLEnvConfig.from_yaml(config_path)

        self.hmm = hmm_detector or HMMRegimeDetector.from_yaml(config_path)
        self.regime_models: dict[int, Any] = {}  # regime_state → trained model
        self.fallback_model: Any = None  # 전체 데이터로 학습된 기본 모델

        ma_cfg = self.config.get("multi_agent", {})
        self.confidence_threshold = ma_cfg.get("confidence_threshold", 0.5)
        self.min_days_per_regime = ma_cfg.get("min_days_per_regime", 5)

        self._save_dir = Path(
            self.config.get("training", {}).get("save_dir", "./models/futures/rl/")
        ) / "multi_agent"
        self._save_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_yaml(cls, config_path: str = "ml/rl_multi_agent.yaml") -> RegimeAwareAgent:
        return cls(config_path=config_path)

    def train(
        self,
        train_days: list[np.ndarray],
        train_prices: list[np.ndarray],
        eval_days: list[np.ndarray] | None = None,
        eval_prices: list[np.ndarray] | None = None,
        regime_features: np.ndarray | None = None,
    ) -> dict[str, Any]:
        """레짐별 모델 학습

        Args:
            train_days: 학습 데이터 (일별 피처 배열)
            train_prices: 학습 가격 데이터
            eval_days: 평가 데이터
            eval_prices: 평가 가격 데이터
            regime_features: HMM 입력용 피처 (n_days, 3)
                             None이면 각 일자의 평균 returns/volatility/volume_ratio로 자동 생성

        Returns:
            학습 결과 요약
        """
        from shared.ml.rl.trainer import RLTrainer

        # 1. 레짐 피처 생성 (없으면 자동)
        if regime_features is None:
            regime_features = self._extract_regime_features(train_days)

        # 2. HMM 학습
        self.hmm.fit(regime_features)

        # 3. 일별 레짐 라벨링
        day_labels = []
        for i in range(len(train_days)):
            feat = regime_features[i].reshape(1, -1)
            regime = self.hmm.predict(feat)
            day_labels.append(regime)

        # 레짐별 분포 로깅
        label_counts = {}
        for r in [HMMRegimeState.BULL, HMMRegimeState.BEAR, HMMRegimeState.SIDEWAYS]:
            count = sum(1 for l in day_labels if l == r)
            label_counts[HMMRegimeState.NAMES[r]] = count
        logger.info(f"Regime distribution: {label_counts}")

        # 4. Fallback 모델 학습 (전체 데이터)
        trainer = RLTrainer(config_path=self.config_path)
        algo = self.config.get("multi_agent", {}).get("algo", "mppo")

        logger.info("Training fallback model (all data)...")
        self.fallback_model = trainer.train(
            algo=algo,
            train_days=train_days,
            train_prices=train_prices,
            eval_days=eval_days,
            eval_prices=eval_prices,
        )

        # 5. 레짐별 모델 학습
        results = {"fallback": "trained"}
        for regime in [HMMRegimeState.BULL, HMMRegimeState.BEAR, HMMRegimeState.SIDEWAYS]:
            regime_name = HMMRegimeState.NAMES[regime]
            indices = [i for i, l in enumerate(day_labels) if l == regime]

            if len(indices) < self.min_days_per_regime:
                logger.warning(
                    f"Regime {regime_name}: only {len(indices)} days "
                    f"(< {self.min_days_per_regime}). Using fallback."
                )
                self.regime_models[regime] = self.fallback_model
                results[regime_name] = "fallback"
                continue

            regime_days = [train_days[i] for i in indices]
            regime_prices = [train_prices[i] for i in indices]

            logger.info(
                f"Training {regime_name} model ({len(regime_days)} days)..."
            )
            model = trainer.train(
                algo=algo,
                train_days=regime_days,
                train_prices=regime_prices,
                eval_days=eval_days,
                eval_prices=eval_prices,
            )
            self.regime_models[regime] = model
            results[regime_name] = f"trained ({len(regime_days)} days)"

        # 6. 모델 저장
        self._save_models()

        logger.info(f"Multi-agent training complete: {results}")
        return results

    def predict(
        self,
        obs: np.ndarray,
        action_masks: np.ndarray | None = None,
        regime_features: np.ndarray | None = None,
        deterministic: bool = True,
    ) -> tuple[int, int]:
        """레짐 인식 행동 결정

        Args:
            obs: 관측 벡터 (31차원)
            action_masks: 유효 행동 마스크
            regime_features: 최근 HMM 피처 시퀀스 (n, 3). None이면 fallback 사용.
            deterministic: 결정적 행동

        Returns:
            (action, regime_state) 튜플
        """
        # 레짐 판정
        if regime_features is not None and self.hmm.is_fitted:
            regime = self.hmm.predict(regime_features)
            regime_probs = self.hmm.predict_proba(regime_features)
            confidence = float(regime_probs.max())
        else:
            regime = HMMRegimeState.SIDEWAYS
            confidence = 0.0

        # 모델 선택
        if confidence >= self.confidence_threshold and regime in self.regime_models:
            model = self.regime_models[regime]
        else:
            model = self.fallback_model

        if model is None:
            from shared.ml.rl.env import Action
            return Action.HOLD, regime

        # 추론
        try:
            action, _ = model.predict(
                obs, deterministic=deterministic, action_masks=action_masks
            )
        except TypeError:
            action, _ = model.predict(obs, deterministic=deterministic)

        return int(action), regime

    def _extract_regime_features(
        self, days: list[np.ndarray]
    ) -> np.ndarray:
        """일별 피처 배열에서 HMM 입력 피처 추출

        각 일자의 전체 바에서 평균값 사용:
        - returns (col 0), volatility (col 7), volume_ratio (col 6)
        """
        features = []
        for day_data in days:
            avg_returns = np.mean(day_data[:, 0])       # returns
            avg_volatility = np.mean(day_data[:, 7])    # volatility
            avg_volume_ratio = np.mean(day_data[:, 6])  # volume_ratio
            features.append([avg_returns, avg_volatility, avg_volume_ratio])
        return np.array(features)

    def _save_models(self) -> None:
        """모델 저장"""
        # HMM 저장
        self.hmm.save(self._save_dir / "hmm_detector.joblib")

        # Fallback 모델
        if self.fallback_model:
            self.fallback_model.save(str(self._save_dir / "fallback"))

        # 레짐별 모델
        for regime, model in self.regime_models.items():
            if model is not self.fallback_model:
                name = HMMRegimeState.NAMES[regime].lower()
                model.save(str(self._save_dir / name))

        logger.info(f"Multi-agent models saved: {self._save_dir}")

    def _get_model_class(self) -> type:
        """config의 algo 설정에 따른 모델 클래스 반환"""
        algo = self.config.get("multi_agent", {}).get("algo", "mppo")
        if algo == "mppo":
            from sb3_contrib import MaskablePPO
            return MaskablePPO
        elif algo == "sac":
            from stable_baselines3 import SAC
            return SAC
        elif algo == "dqn":
            from stable_baselines3 import DQN
            return DQN
        elif algo == "a2c":
            from stable_baselines3 import A2C
            return A2C
        elif algo == "ppo":
            from stable_baselines3 import PPO
            return PPO
        else:
            from sb3_contrib import MaskablePPO
            logger.warning(f"Unknown algo '{algo}', falling back to MaskablePPO")
            return MaskablePPO

    def load_models(self) -> RegimeAwareAgent:
        """저장된 모델 로드"""
        model_cls = self._get_model_class()

        # HMM
        hmm_path = self._save_dir / "hmm_detector.joblib"
        if hmm_path.exists():
            self.hmm.load(hmm_path)

        # Fallback
        fallback_path = self._save_dir / "fallback.zip"
        if fallback_path.exists():
            self.fallback_model = model_cls.load(str(fallback_path))

        # 레짐별
        for regime in [HMMRegimeState.BULL, HMMRegimeState.BEAR, HMMRegimeState.SIDEWAYS]:
            name = HMMRegimeState.NAMES[regime].lower()
            model_path = self._save_dir / f"{name}.zip"
            if model_path.exists():
                self.regime_models[regime] = model_cls.load(str(model_path))
            elif self.fallback_model:
                self.regime_models[regime] = self.fallback_model

        logger.info(f"Multi-agent models loaded: {self._save_dir}")
        return self
