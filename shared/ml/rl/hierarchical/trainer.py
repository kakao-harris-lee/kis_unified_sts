"""계층적 RL 학습 파이프라인

두 가지 학습 모드 지원:
1. Sequential (train): Low-level 먼저 학습 → High-level 학습
2. Joint (train_joint): High/Low-level 동시 학습, 교대 업데이트

Phase 1: Low-level (1분봉) — 전체 데이터로 매매 실행 모델 학습
Phase 2: High-level (15분봉) — low-level 결과 기반 리스크 예산 또는 방향성 편향 모델 학습

Usage:
    # Sequential training (risk_budget mode)
    trainer = HierarchicalTrainer(mode="risk_budget")
    models = trainer.train(train_days, train_prices)

    # Sequential training (directional mode)
    trainer = HierarchicalTrainer(mode="directional")
    models = trainer.train(train_days, train_prices)

    # Joint training (alternating updates)
    trainer = HierarchicalTrainer(mode="directional")
    models = trainer.train_joint(train_days, train_prices)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from shared.config import ConfigLoader
from shared.ml.base import get_device
from shared.ml.rl.env import RLEnvConfig
from shared.ml.rl.hierarchical.high_level_env import (
    DirectionalHighLevelConfig,
    DirectionalHighLevelEnv,
    HighLevelAction,
    HighLevelConfig,
    HighLevelDirectionalAction,
    HighLevelEnv,
)
from shared.ml.rl.hierarchical.low_level_env import LowLevelEnv
from shared.ml.rl.hierarchical.utils import downsample_1m_to_15m

logger = logging.getLogger(__name__)


class HierarchicalTrainer:
    """계층적 RL 학습기

    Training Modes:
        - Sequential (train): Low-level 완전 학습 후 High-level 학습
        - Joint (train_joint): High/Low-level 동시 학습, 교대 업데이트

    Phase 1: Low-level (1분봉 FuturesTradingEnv)
        - 전체 데이터로 MaskablePPO 학습
        - 결과: 일별 15분 구간 PnL 기록

    Phase 2: High-level (15분봉)
        - Phase 1 low-level 결과를 보상으로 사용
        - 15분마다 risk_budget 또는 directional_bias 결정 모델 학습

    High-level Modes:
        - "risk_budget": High-level이 리스크 예산 결정 (AGGRESSIVE/NEUTRAL/DEFENSIVE)
        - "directional": High-level이 방향성 편향 결정 (LONG_BIAS/SHORT_BIAS/FLAT)
    """

    def __init__(self, config_path: str = "ml/rl_mppo.yaml", mode: str = "risk_budget"):
        """
        Args:
            config_path: 설정 파일 경로
            mode: "risk_budget" 또는 "directional"
        """
        if mode not in ("risk_budget", "directional"):
            raise ValueError(
                f"Invalid mode '{mode}'. Must be 'risk_budget' or 'directional'."
            )

        self.config = ConfigLoader.load(config_path)
        self.config_path = config_path
        self.mode = mode
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
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import DummyVecEnv

        hl_cfg = self.config.get("hierarchical", {})

        # 모드에 따라 환경 설정 및 클래스 선택
        if self.mode == "directional":
            hl_config = DirectionalHighLevelConfig(
                initial_balance=self.env_config.initial_balance,
            )
            env_class = DirectionalHighLevelEnv
            logger.info("Using DirectionalHighLevelEnv for high-level training")
        else:  # risk_budget
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
            env_class = HighLevelEnv
            logger.info("Using HighLevelEnv (risk_budget) for high-level training")

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
            class _RotatingHighEnv(env_class):
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

        model = PPO(
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

    def train_joint(
        self,
        train_days: list[np.ndarray],
        train_prices: list[np.ndarray],
        eval_days: list[np.ndarray] | None = None,
        eval_prices: list[np.ndarray] | None = None,
    ) -> dict[str, Any]:
        """Joint training (alternating high/low-level updates)

        High-level과 low-level 모델을 동시에 학습. High-level은 15분마다 결정,
        low-level은 매 분마다 실행. 두 모델의 업데이트를 교대로 수행.

        Returns:
            {"low_level": model, "high_level": model}
        """
        from sb3_contrib import MaskablePPO
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import DummyVecEnv

        logger.info("=== Joint Training: High-level + Low-level ===")

        hl_cfg = self.config.get("hierarchical", {})
        mppo_cfg = self.config.get("mppo", {})

        # Joint training 설정
        total_timesteps = hl_cfg.get("joint_timesteps", 1_000_000)
        update_ratio = hl_cfg.get("joint_update_ratio", 15)  # low업데이트 N회당 high업데이트 1회
        n_steps_low = mppo_cfg.get("n_steps", 2048)
        n_steps_high = hl_cfg.get("high_level", {}).get("n_steps", 128)

        logger.info(f"Joint training config: timesteps={total_timesteps}, update_ratio={update_ratio}")

        # Low-level 모델 생성
        logger.info("Creating low-level model (MaskablePPO)...")
        low_model = self._create_low_level_model(train_days, train_prices, mppo_cfg)

        # High-level 모델 생성 (초기 segment results는 랜덤 low-level로 수집)
        logger.info("Collecting initial segment results for high-level...")
        initial_segment_results = self._collect_segment_results(
            low_model, train_days, train_prices
        )

        logger.info("Creating high-level model (PPO)...")
        high_model = self._create_high_level_model(
            train_days, initial_segment_results, hl_cfg
        )

        # Joint training loop
        timesteps_elapsed = 0
        low_update_count = 0
        iteration = 0

        while timesteps_elapsed < total_timesteps:
            iteration += 1

            # Low-level 학습 (n_steps만큼 경험 수집 + 업데이트)
            logger.info(f"[Iter {iteration}] Low-level learning...")
            low_model.learn(total_timesteps=n_steps_low, reset_num_timesteps=False, progress_bar=False)
            timesteps_elapsed += n_steps_low
            low_update_count += 1

            # update_ratio마다 high-level 업데이트
            if low_update_count >= update_ratio:
                logger.info(f"[Iter {iteration}] High-level learning (after {low_update_count} low updates)...")

                # 현재 low-level로 segment results 재수집
                current_segment_results = self._collect_segment_results(
                    low_model, train_days, train_prices
                )

                # High-level 환경에 새 results 주입
                high_model.env.envs[0].update_low_level_results(current_segment_results)

                # High-level 학습
                high_model.learn(total_timesteps=n_steps_high, reset_num_timesteps=False, progress_bar=False)

                low_update_count = 0

            if iteration % 10 == 0:
                logger.info(f"Joint training progress: {timesteps_elapsed}/{total_timesteps} timesteps")

        # 최종 저장
        low_model.save(str(self.save_dir / "low_level_joint"))
        high_model.save(str(self.save_dir / "high_level_joint"))
        logger.info(f"Joint trained models saved: {self.save_dir}")

        return {"low_level": low_model, "high_level": high_model}

    def _create_low_level_model(
        self,
        train_days: list[np.ndarray],
        train_prices: list[np.ndarray],
        mppo_cfg: dict,
    ) -> Any:
        """Low-level MaskablePPO 모델 생성"""
        from sb3_contrib import MaskablePPO
        from stable_baselines3.common.vec_env import DummyVecEnv

        # Day rotation 환경
        day_idx = [0]

        def make_fn():
            class _RotatingLowEnv(LowLevelEnv):
                def reset(self, **kwargs):
                    idx = day_idx[0] % len(train_days)
                    self.day_data = train_days[idx]
                    self.prices = train_prices[idx]
                    day_idx[0] += 1
                    return super().reset(**kwargs)

            return _RotatingLowEnv(
                day_data=train_days[0],
                config=self.env_config,
                prices=train_prices[0],
            )

        vec_env = DummyVecEnv([make_fn])

        model = MaskablePPO(
            "MlpPolicy",
            vec_env,
            learning_rate=mppo_cfg.get("learning_rate", 0.0003),
            gamma=mppo_cfg.get("gamma", 0.99),
            n_steps=mppo_cfg.get("n_steps", 2048),
            batch_size=mppo_cfg.get("batch_size", 64),
            n_epochs=mppo_cfg.get("n_epochs", 10),
            ent_coef=mppo_cfg.get("ent_coef", 0.01),
            tensorboard_log=str(self.save_dir / "tb_low_joint"),
            device=self.device,
            verbose=0,
        )

        return model

    def _create_high_level_model(
        self,
        train_days: list[np.ndarray],
        all_segment_results: list[list[dict[str, float]]],
        hl_cfg: dict,
    ) -> Any:
        """High-level PPO 모델 생성"""
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import DummyVecEnv

        # 모드에 따라 환경 설정
        if self.mode == "directional":
            hl_config = DirectionalHighLevelConfig(
                initial_balance=self.env_config.initial_balance,
            )
            env_class = DirectionalHighLevelEnv
        else:  # risk_budget
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
            env_class = HighLevelEnv

        # 15분봉 피처 생성
        train_15m_days = []
        train_results_days = []

        for i, day_data in enumerate(train_days):
            features_15m = self._downsample_to_15m(day_data)
            if i < len(all_segment_results):
                train_15m_days.append(features_15m)
                train_results_days.append(all_segment_results[i])

        if not train_15m_days:
            raise ValueError("No valid 15m data for high-level training")

        # Day rotation 환경
        day_idx = [0]
        results_holder = [train_results_days]  # Mutable holder

        def make_fn():
            class _RotatingHighEnv(env_class):
                def reset(self, **kwargs):
                    idx = day_idx[0] % len(train_15m_days)
                    self.day_data = train_15m_days[idx]
                    self.low_level_results = results_holder[0][idx]
                    day_idx[0] += 1
                    return super().reset(**kwargs)

                def update_low_level_results(self, new_results):
                    """Joint training에서 low-level 결과 업데이트용"""
                    results_holder[0] = new_results

            return _RotatingHighEnv(
                day_data_15m=train_15m_days[0],
                config=hl_config,
                low_level_results=train_results_days[0],
            )

        vec_env = DummyVecEnv([make_fn])

        hl_algo = hl_cfg.get("high_level", {})
        model = PPO(
            "MlpPolicy",
            vec_env,
            learning_rate=hl_algo.get("learning_rate", 0.0003),
            gamma=hl_algo.get("gamma", 0.99),
            n_steps=hl_algo.get("n_steps", 128),
            batch_size=hl_algo.get("batch_size", 32),
            n_epochs=hl_algo.get("n_epochs", 10),
            ent_coef=hl_algo.get("ent_coef", 0.05),
            tensorboard_log=str(self.save_dir / "tb_high_joint"),
            device=self.device,
            verbose=0,
        )

        return model

    def _downsample_to_15m(self, day_data_1m: np.ndarray) -> np.ndarray:
        """1분봉 -> 15분봉 다운샘플 (구간 평균)

        Args:
            day_data_1m: (n_bars, 25) 1분봉 정규화 피처

        Returns:
            (n_bars_15m, 25) 15분봉 피처
        """
        return downsample_1m_to_15m(day_data_1m, self.bars_per_step)
