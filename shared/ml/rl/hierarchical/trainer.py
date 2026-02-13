"""계층적 RL 2단계 학습 파이프라인

Phase 1: Low-level (1분봉) — 전체 데이터로 매매 실행 모델 학습
Phase 2: High-level (15분봉) — low-level 결과 기반 리스크 예산 모델 학습

Usage:
    trainer = HierarchicalTrainer()
    models = trainer.train(train_days, train_prices)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from shared.config import ConfigLoader
from shared.ml.base import get_device
from shared.ml.rl.env import RLEnvConfig
from shared.ml.rl.hierarchical.high_level_env import HighLevelAction, HighLevelConfig, HighLevelEnv
from shared.ml.rl.hierarchical.low_level_env import LowLevelEnv

logger = logging.getLogger(__name__)


class HierarchicalTrainer:
    """계층적 RL 2단계 학습기

    Phase 1: Low-level (1분봉 FuturesTradingEnv)
        - 전체 데이터로 MaskablePPO 학습
        - 결과: 일별 15분 구간 PnL 기록

    Phase 2: High-level (15분봉)
        - Phase 1 low-level 결과를 보상으로 사용
        - 15분마다 risk_budget 결정 모델 학습
    """

    def __init__(self, config_path: str = "ml/rl_mppo.yaml"):
        self.config = ConfigLoader.load(config_path)
        self.config_path = config_path
        self.env_config = RLEnvConfig.from_yaml(config_path)
        self.device = get_device(self.config.get("mppo", {}).get("device", "auto"))

        self.save_dir = Path(
            self.config.get("training", {}).get("save_dir", "./models/futures/rl/")
        ) / "hierarchical"
        self.save_dir.mkdir(parents=True, exist_ok=True)

        hl_cfg = self.config.get("hierarchical", {})
        self.bars_per_step = hl_cfg.get("bars_per_step", 15)

    def train(
        self,
        train_days: list[np.ndarray],
        train_prices: list[np.ndarray],
        eval_days: list[np.ndarray] | None = None,
        eval_prices: list[np.ndarray] | None = None,
    ) -> dict[str, Any]:
        """2단계 학습

        Returns:
            {"low_level": model, "high_level": model}
        """
        # Phase 1: Low-level 학습
        logger.info("=== Phase 1: Low-level (1-min) training ===")
        low_model = self._train_low_level(
            train_days, train_prices, eval_days, eval_prices
        )

        # Phase 1.5: Low-level 결과 수집 (15분 구간별)
        logger.info("Collecting low-level segment results...")
        all_segment_results = self._collect_segment_results(
            low_model, train_days, train_prices
        )

        # Phase 2: High-level 학습
        logger.info("=== Phase 2: High-level (15-min) training ===")
        high_model = self._train_high_level(
            train_days, all_segment_results
        )

        # 저장
        low_model.save(str(self.save_dir / "low_level_final"))
        high_model.save(str(self.save_dir / "high_level_final"))
        logger.info(f"Hierarchical models saved: {self.save_dir}")

        return {"low_level": low_model, "high_level": high_model}

    def _train_low_level(
        self,
        train_days: list[np.ndarray],
        train_prices: list[np.ndarray],
        eval_days: list[np.ndarray] | None,
        eval_prices: list[np.ndarray] | None,
    ) -> Any:
        """Phase 1: Low-level 모델 학습 (기존 RLTrainer 활용)"""
        from shared.ml.rl.trainer import RLTrainer

        trainer = RLTrainer(config_path=self.config_path)
        return trainer.train(
            algo="mppo",
            train_days=train_days,
            train_prices=train_prices,
            eval_days=eval_days,
            eval_prices=eval_prices,
        )

    def _collect_segment_results(
        self,
        low_model: Any,
        days: list[np.ndarray],
        prices: list[np.ndarray],
    ) -> list[list[dict[str, float]]]:
        """Low-level 모델로 각 일자 실행 → 15분 구간별 결과 수집

        Returns:
            day별 [segment_result, ...] 리스트
        """
        all_results = []

        for day_data, day_prices in zip(days, prices):
            env = LowLevelEnv(
                day_data=day_data,
                config=self.env_config,
                prices=day_prices,
            )
            obs, _ = env.reset()

            terminated = False
            while not terminated:
                masks = env.action_masks()
                try:
                    action, _ = low_model.predict(
                        obs, deterministic=True, action_masks=masks
                    )
                except TypeError:
                    action, _ = low_model.predict(obs, deterministic=True)
                obs, _, terminated, _, _ = env.step(int(action))

            # 15분 구간별 결과 수집
            n_bars = len(day_data)
            segment_results = []
            for start in range(0, n_bars, self.bars_per_step):
                end = min(start + self.bars_per_step, n_bars)
                result = env.get_15min_segment_results(start, end)
                segment_results.append(result)

            all_results.append(segment_results)

        return all_results

    def _train_high_level(
        self,
        train_days: list[np.ndarray],
        all_segment_results: list[list[dict[str, float]]],
    ) -> Any:
        """Phase 2: High-level 모델 학습"""
        from sb3_contrib import MaskablePPO
        from stable_baselines3.common.vec_env import DummyVecEnv

        hl_cfg = self.config.get("hierarchical", {})
        risk_budgets_raw = hl_cfg.get("risk_budgets", {})
        risk_budgets = {
            HighLevelAction.AGGRESSIVE: risk_budgets_raw.get("aggressive", 1.0),
            HighLevelAction.NEUTRAL: risk_budgets_raw.get("neutral", 0.5),
            HighLevelAction.DEFENSIVE: risk_budgets_raw.get("defensive", 0.0),
        }
        hl_config = HighLevelConfig(
            initial_balance=self.env_config.initial_balance,
            risk_budgets=risk_budgets,
        )

        # 15분봉 피처 생성 (1분봉을 15분 평균으로 축소)
        train_15m_days = []
        train_results_days = []

        for i, day_data in enumerate(train_days):
            features_15m = self._downsample_to_15m(day_data)
            if i < len(all_segment_results):
                train_15m_days.append(features_15m)
                train_results_days.append(all_segment_results[i])

        if not train_15m_days:
            raise ValueError("No valid 15m data for high-level training")

        # DayRotating 환경
        day_idx = [0]

        def make_fn():
            class _RotatingHighEnv(HighLevelEnv):
                def reset(self, **kwargs):
                    idx = day_idx[0] % len(train_15m_days)
                    self.day_data = train_15m_days[idx]
                    self.low_level_results = train_results_days[idx]
                    day_idx[0] += 1
                    return super().reset(**kwargs)

            return _RotatingHighEnv(
                day_data_15m=train_15m_days[0],
                config=hl_config,
                low_level_results=train_results_days[0],
            )

        vec_env = DummyVecEnv([make_fn])

        # High-level 하이퍼파라미터 (YAML config에서 로드)
        hl_algo = hl_cfg.get("high_level", {})
        hl_timesteps = hl_cfg.get("high_level_timesteps", 500_000)

        model = MaskablePPO(
            "MlpPolicy",
            vec_env,
            learning_rate=hl_algo.get("learning_rate", 0.0003),
            gamma=hl_algo.get("gamma", 0.99),
            n_steps=hl_algo.get("n_steps", 128),
            batch_size=hl_algo.get("batch_size", 32),
            n_epochs=hl_algo.get("n_epochs", 10),
            ent_coef=hl_algo.get("ent_coef", 0.05),
            tensorboard_log=str(self.save_dir / "tb_high"),
            device=self.device,
            verbose=1,
        )

        model.learn(total_timesteps=hl_timesteps, progress_bar=True)
        return model

    def _downsample_to_15m(self, day_data_1m: np.ndarray) -> np.ndarray:
        """1분봉 → 15분봉 다운샘플 (구간 평균)

        Args:
            day_data_1m: (n_bars, 25) 1분봉 정규화 피처

        Returns:
            (n_bars_15m, 25) 15분봉 피처
        """
        n_bars = len(day_data_1m)
        features_15m = []

        for start in range(0, n_bars, self.bars_per_step):
            end = min(start + self.bars_per_step, n_bars)
            segment = day_data_1m[start:end]
            features_15m.append(segment.mean(axis=0))

        return np.array(features_15m, dtype=np.float32)
