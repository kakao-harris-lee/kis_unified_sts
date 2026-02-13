"""HMM 기반 시장 레짐 감지기

GaussianHMM 3상태 모델로 시장 레짐을 자동 감지.
입력: returns, volatility, volume_ratio (3차원 관측)
출력: BULL(0), BEAR(1), SIDEWAYS(2) 중 하나

Usage:
    detector = HMMRegimeDetector()
    detector.fit(train_features)
    state = detector.predict(current_features)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import hashlib

import joblib
import numpy as np
import pandas as pd

from shared.config import ConfigLoader

logger = logging.getLogger(__name__)


@dataclass
class HMMConfig:
    """HMM 레짐 감지 설정"""

    n_states: int = 3
    covariance_type: str = "full"
    n_iter: int = 100
    random_state: int = 42
    # 관측 피처 (RL 피처 배열에서의 인덱스)
    feature_names: list[str] = field(
        default_factory=lambda: ["returns", "volatility", "volume_ratio"]
    )
    # 레짐 라벨링 기준 (학습 후 자동 매핑)
    bull_threshold: float = 0.0     # returns 평균 > 0 → BULL 후보
    volatility_threshold: float = 0.01  # volatility > threshold → SIDEWAYS (높은 변동성)


class HMMRegimeState:
    """HMM 레짐 상태 상수"""

    BULL = 0
    BEAR = 1
    SIDEWAYS = 2
    NAMES = {0: "BULL", 1: "BEAR", 2: "SIDEWAYS"}


class HMMRegimeDetector:
    """GaussianHMM 3상태 레짐 감지기

    학습:
        1. train_features (returns, volatility, volume_ratio) 입력
        2. GaussianHMM 3상태 학습
        3. 각 상태의 평균 returns로 BULL/BEAR/SIDEWAYS 자동 매핑

    추론:
        - 최근 N개 관측의 은닉 상태 디코딩 → 현재 레짐 반환
    """

    def __init__(self, config: HMMConfig | None = None):
        self.config = config or HMMConfig()
        self._model: Any = None
        self._state_map: dict[int, int] = {}  # hmm_state → regime_state

    @classmethod
    def from_yaml(cls, config_path: str = "ml/rl_multi_agent.yaml") -> HMMRegimeDetector:
        """YAML config에서 생성"""
        data = ConfigLoader.load(config_path)
        hmm_cfg = data.get("hmm", {})
        return cls(config=HMMConfig(
            n_states=hmm_cfg.get("n_states", 3),
            covariance_type=hmm_cfg.get("covariance_type", "full"),
            n_iter=hmm_cfg.get("n_iter", 100),
            random_state=hmm_cfg.get("random_state", 42),
            feature_names=hmm_cfg.get(
                "feature_names", ["returns", "volatility", "volume_ratio"]
            ),
        ))

    def fit(self, features: np.ndarray) -> HMMRegimeDetector:
        """HMM 학습

        Args:
            features: (n_samples, 3) 배열 [returns, volatility, volume_ratio]

        Returns:
            self (chaining)
        """
        from hmmlearn.hmm import GaussianHMM

        cfg = self.config
        self._model = GaussianHMM(
            n_components=cfg.n_states,
            covariance_type=cfg.covariance_type,
            n_iter=cfg.n_iter,
            random_state=cfg.random_state,
        )

        self._model.fit(features)
        logger.info(
            f"HMM fitted: {cfg.n_states} states, "
            f"converged={self._model.monitor_.converged}"
        )

        # 상태 자동 매핑: 평균 returns 기준
        self._auto_map_states(features)

        return self

    def fit_from_dataframe(self, df: pd.DataFrame) -> HMMRegimeDetector:
        """DataFrame에서 직접 학습

        Args:
            df: OHLCV 피처가 계산된 DataFrame
                (returns, volatility, volume_ratio 컬럼 필요)
        """
        features = df[self.config.feature_names].dropna().values
        return self.fit(features)

    def _auto_map_states(self, features: np.ndarray) -> None:
        """HMM 상태를 BULL/BEAR/SIDEWAYS로 자동 매핑

        기준: 각 상태의 평균 returns
        - 가장 높은 returns → BULL
        - 가장 낮은 returns → BEAR
        - 나머지 → SIDEWAYS

        Raises:
            ValueError: n_states != 3 (BULL/BEAR/SIDEWAYS 매핑은 3상태 전용)
        """
        if self.config.n_states != 3:
            raise ValueError(
                f"Auto state mapping requires exactly 3 states, "
                f"got n_states={self.config.n_states}"
            )
        states = self._model.predict(features)
        mean_returns = {}
        for s in range(self.config.n_states):
            mask = states == s
            if mask.any():
                mean_returns[s] = features[mask, 0].mean()  # returns = col 0
            else:
                mean_returns[s] = 0.0

        sorted_states = sorted(mean_returns, key=lambda k: mean_returns[k])

        self._state_map = {
            sorted_states[-1]: HMMRegimeState.BULL,      # 최고 수익
            sorted_states[0]: HMMRegimeState.BEAR,       # 최저 수익
            sorted_states[1]: HMMRegimeState.SIDEWAYS,   # 중간
        }

        for hmm_s, regime_s in self._state_map.items():
            name = HMMRegimeState.NAMES[regime_s]
            logger.info(
                f"HMM state {hmm_s} → {name} "
                f"(mean_return={mean_returns[hmm_s]:.6f})"
            )

    def predict(self, features: np.ndarray) -> int:
        """현재 레짐 예측

        Args:
            features: (n_samples, 3) 최근 관측 시퀀스

        Returns:
            HMMRegimeState (0=BULL, 1=BEAR, 2=SIDEWAYS)
        """
        if self._model is None:
            return HMMRegimeState.SIDEWAYS

        if features.ndim == 1:
            features = features.reshape(1, -1)

        hidden_states = self._model.predict(features)
        current_hmm_state = hidden_states[-1]  # 마지막 시점
        return self._state_map.get(current_hmm_state, HMMRegimeState.SIDEWAYS)

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        """레짐 확률 분포 예측

        Returns:
            (3,) 배열 [P(BULL), P(BEAR), P(SIDEWAYS)]
        """
        if self._model is None:
            return np.array([0.33, 0.33, 0.34])

        if features.ndim == 1:
            features = features.reshape(1, -1)

        posteriors = self._model.predict_proba(features)
        last_posterior = posteriors[-1]  # (n_states,)

        # HMM 상태 → 레짐 상태로 재배치
        regime_probs = np.zeros(3)
        for hmm_s, regime_s in self._state_map.items():
            regime_probs[regime_s] = last_posterior[hmm_s]

        return regime_probs

    def get_state_distribution(self, features: np.ndarray) -> dict[str, float]:
        """전체 시퀀스의 레짐 분포

        Returns:
            {"BULL": 0.4, "BEAR": 0.3, "SIDEWAYS": 0.3}
        """
        if self._model is None:
            return {name: 1.0 / 3 for name in HMMRegimeState.NAMES.values()}

        states = self._model.predict(features)
        dist = {}
        for hmm_s, regime_s in self._state_map.items():
            name = HMMRegimeState.NAMES[regime_s]
            dist[name] = float(np.mean(states == hmm_s))

        return dist

    def save(self, path: str | Path) -> None:
        """모델 저장 (해시 파일 동반 생성)"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"model": self._model, "state_map": self._state_map, "config": self.config},
            path,
        )
        # 무결성 해시 저장
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(path.suffix + ".sha256").write_text(file_hash)
        logger.info(f"HMM model saved: {path} (sha256={file_hash[:16]}...)")

    def load(self, path: str | Path) -> HMMRegimeDetector:
        """모델 로드 (해시 검증)"""
        path = Path(path)
        hash_path = path.with_suffix(path.suffix + ".sha256")
        if hash_path.exists():
            expected = hash_path.read_text().strip()
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(
                    f"Model integrity check failed: {path} "
                    f"(expected={expected[:16]}..., actual={actual[:16]}...)"
                )
        else:
            logger.warning(f"No hash file for {path} — skipping integrity check")

        data = joblib.load(path)
        self._model = data["model"]
        self._state_map = data["state_map"]
        self.config = data.get("config", self.config)
        logger.info(f"HMM model loaded: {path}")
        return self

    @property
    def is_fitted(self) -> bool:
        return self._model is not None
