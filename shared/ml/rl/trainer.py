"""RL 모델 학습 파이프라인

MLflow로 학습 과정 추적. 모든 하이퍼파라미터는 config에서 로드.
지원 알고리즘: MaskablePPO (메인), SAC (off-policy), DQN, A2C, PPO (비교군)

Usage:
    trainer = RLTrainer()
    model = trainer.train("mppo")
    trainer.train("sac")     # SAC (연속 행동 공간)
    trainer.train_all()       # 전체 비교 학습
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from shared.config import ConfigLoader
from shared.ml.base import get_device
from shared.ml.rl.env import FuturesTradingEnv, RLEnvConfig, mask_fn

logger = logging.getLogger(__name__)

# 알고리즘별 라이브러리 lazy import용
ALGO_REGISTRY: dict[str, str] = {
    "mppo": "sb3_contrib.MaskablePPO",
    "sac": "stable_baselines3.SAC",
    "dqn": "stable_baselines3.DQN",
    "a2c": "stable_baselines3.A2C",
    "ppo": "stable_baselines3.PPO",
    "dt": "shared.ml.rl.decision_transformer.DTTrainer",
}

# 연속 행동 공간 알고리즘 (ActionMasker 대신 ContinuousActionWrapper 사용)
CONTINUOUS_ACTION_ALGOS = {"sac"}

# SB3 외 자체 학습 루프 알고리즘
NON_SB3_ALGOS = {"dt"}


class RLTrainer:
    """RL 학습 파이프라인

    모든 하이퍼파라미터는 YAML 설정에서 로드.
    학습 과정은 MLflow + TensorBoard로 추적.
    """

    def __init__(self, config_path: str = "ml/rl_mppo.yaml"):
        self.config = ConfigLoader.load(config_path)
        self.env_config = RLEnvConfig.from_yaml(config_path)
        self.device = get_device(self.config.get("mppo", {}).get("device", "auto"))
        self.save_dir = Path(
            self.config.get("training", {}).get("save_dir", "./models/futures/rl/")
        )
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.tb_log = self.config.get("training", {}).get(
            "tensorboard_log", "./results/rl/tensorboard/"
        )

    def train(
        self,
        algo: str = "mppo",
        train_days: list[np.ndarray] | None = None,
        train_prices: list[np.ndarray] | None = None,
        eval_days: list[np.ndarray] | None = None,
        eval_prices: list[np.ndarray] | None = None,
        slippage: float | None = None,
    ) -> Any:
        """단일 알고리즘 학습

        Args:
            algo: 알고리즘 이름 (mppo, sac, dqn, a2c, ppo)
            train_days: 학습 데이터 (일별 피처 배열 리스트)
            train_prices: 학습 가격 데이터 (일별 OHLC 배열 리스트)
            eval_days: 평가 데이터
            eval_prices: 평가 가격 데이터
            slippage: 슬리피지 오버라이드 (None이면 config 기본값)

        Returns:
            학습된 모델
        """
        if algo not in ALGO_REGISTRY:
            raise ValueError(f"Unknown algo: {algo}. Supported: {list(ALGO_REGISTRY.keys())}")

        # DT uses its own training pipeline
        if algo in NON_SB3_ALGOS:
            return self._train_dt(
                train_days=train_days,
                train_prices=train_prices,
                eval_days=eval_days,
                eval_prices=eval_prices,
            )

        algo_config = self.config.get(algo, {})
        total_timesteps = algo_config.get("total_timesteps", 5_000_000)

        logger.info(f"Training {algo.upper()} | timesteps={total_timesteps} | device={self.device}")

        # 환경 설정
        env_config = self.env_config
        if slippage is not None:
            env_config.slippage = slippage

        # 학습 환경 생성 (SAC는 연속 행동 공간)
        is_continuous = algo in CONTINUOUS_ACTION_ALGOS
        env = self._make_env(train_days, train_prices, env_config, continuous=is_continuous)

        # 모델 생성
        model = self._create_model(algo, env, algo_config)

        # 콜백 설정
        callbacks = self._build_callbacks(
            algo, eval_days, eval_prices, env_config, continuous=is_continuous
        )

        # MLflow 추적
        mlflow_params = {
            "algo": algo,
            "device": self.device,
            "slippage": env_config.slippage,
            **{f"{algo}_{k}": v for k, v in algo_config.items() if not isinstance(v, dict)},
        }
        self._log_mlflow_start(algo, mlflow_params)

        try:
            # 학습
            model.learn(
                total_timesteps=total_timesteps,
                callback=callbacks,
                progress_bar=True,
            )

            # 저장
            save_path = self.save_dir / f"{algo}_final"
            model.save(str(save_path))
            logger.info(f"Model saved: {save_path}")
        finally:
            self._log_mlflow_end(algo)

        return model

    def train_all(
        self,
        train_days: list[np.ndarray] | None = None,
        train_prices: list[np.ndarray] | None = None,
        eval_days: list[np.ndarray] | None = None,
        eval_prices: list[np.ndarray] | None = None,
    ) -> dict[str, Any]:
        """전체 알고리즘 비교 학습

        Returns:
            algo_name → trained model 딕셔너리
        """
        models = {}
        for algo in ALGO_REGISTRY:
            try:
                models[algo] = self.train(
                    algo=algo,
                    train_days=train_days,
                    train_prices=train_prices,
                    eval_days=eval_days,
                    eval_prices=eval_prices,
                )
            except Exception as e:
                logger.error(f"Failed to train {algo}: {e}")
        return models

    def _make_env(
        self,
        days: list[np.ndarray] | None,
        prices: list[np.ndarray] | None,
        config: RLEnvConfig,
        continuous: bool = False,
    ) -> Any:
        """학습용 환경 생성

        DummyVecEnv로 래핑. 에피소드마다 다른 일자 데이터 사용.

        Args:
            days: 일별 피처 배열 리스트
            prices: 일별 OHLC 배열 리스트
            config: 환경 설정
            continuous: True면 연속 행동 공간 (SAC용)
        """
        from stable_baselines3.common.vec_env import DummyVecEnv

        if days is None or len(days) == 0:
            raise ValueError("train_days must be provided with at least one day of data")

        day_prices = prices if prices is not None else [None] * len(days)

        class _DayRotatingEnv(FuturesTradingEnv):
            """에피소드마다 다른 일자 데이터를 순회하는 래퍼"""

            def __init__(self, all_days, all_prices, cfg):
                self._all_days = all_days
                self._all_prices = all_prices
                self._day_idx = 0
                super().__init__(
                    day_data=all_days[0],
                    config=cfg,
                    prices=all_prices[0] if all_prices[0] is not None else None,
                )

            def reset(self, **kwargs):
                self._day_idx = (self._day_idx + 1) % len(self._all_days)
                self.day_data = self._all_days[self._day_idx]
                if self._all_prices[self._day_idx] is not None:
                    self.prices = self._all_prices[self._day_idx]
                return super().reset(**kwargs)

        if continuous:
            from shared.ml.rl.wrappers import ContinuousActionWrapper

            cont_cfg = self.config.get("continuous_action", {})
            entry_thresh = cont_cfg.get("entry_threshold", 0.3)
            exit_thresh = cont_cfg.get("exit_threshold", 0.1)

            def make_fn():
                base_env = _DayRotatingEnv(days, day_prices, config)
                return ContinuousActionWrapper(
                    base_env,
                    entry_threshold=entry_thresh,
                    exit_threshold=exit_thresh,
                )
        else:
            from sb3_contrib.common.wrappers import ActionMasker

            def make_fn():
                base_env = _DayRotatingEnv(days, day_prices, config)
                return ActionMasker(base_env, mask_fn)

        return DummyVecEnv([make_fn])

    def _create_model(self, algo: str, env: Any, algo_config: dict) -> Any:
        """알고리즘별 모델 생성"""
        if algo == "mppo":
            from sb3_contrib import MaskablePPO

            policy_kwargs = algo_config.get("policy_kwargs", {})
            return MaskablePPO(
                "MlpPolicy",
                env,
                learning_rate=algo_config.get("learning_rate", 0.0001),
                gamma=algo_config.get("gamma", 0.99),
                gae_lambda=algo_config.get("gae_lambda", 0.95),
                clip_range=algo_config.get("clip_range", 0.2),
                ent_coef=algo_config.get("ent_coef", 0.01),
                vf_coef=algo_config.get("vf_coef", 0.5),
                max_grad_norm=algo_config.get("max_grad_norm", 0.5),
                n_steps=algo_config.get("n_steps", 2048),
                batch_size=algo_config.get("batch_size", 64),
                n_epochs=algo_config.get("n_epochs", 10),
                policy_kwargs=policy_kwargs if policy_kwargs else None,
                tensorboard_log=self.tb_log,
                device=self.device,
                verbose=1,
            )

        elif algo == "sac":
            from stable_baselines3 import SAC

            policy_kwargs = algo_config.get("policy_kwargs", {})
            # SAC의 ent_coef는 문자열 "auto" 가능
            ent_coef = algo_config.get("ent_coef", "auto")

            return SAC(
                "MlpPolicy",
                env,
                learning_rate=algo_config.get("learning_rate", 0.0003),
                gamma=algo_config.get("gamma", 0.99),
                buffer_size=algo_config.get("buffer_size", 100_000),
                learning_starts=algo_config.get("learning_starts", 5_000),
                batch_size=algo_config.get("batch_size", 256),
                tau=algo_config.get("tau", 0.005),
                ent_coef=ent_coef,
                target_entropy=algo_config.get("target_entropy", "auto"),
                train_freq=algo_config.get("train_freq", 1),
                gradient_steps=algo_config.get("gradient_steps", 1),
                policy_kwargs=policy_kwargs if policy_kwargs else None,
                tensorboard_log=self.tb_log,
                device=self.device,
                verbose=1,
            )

        elif algo == "dqn":
            from stable_baselines3 import DQN

            return DQN(
                "MlpPolicy",
                env,
                learning_rate=algo_config.get("learning_rate", 0.0001),
                gamma=algo_config.get("gamma", 0.99),
                buffer_size=algo_config.get("buffer_size", 100_000),
                learning_starts=algo_config.get("learning_starts", 10_000),
                batch_size=algo_config.get("batch_size", 64),
                target_update_interval=algo_config.get("target_update_interval", 1000),
                exploration_fraction=algo_config.get("exploration_fraction", 0.1),
                exploration_final_eps=algo_config.get("exploration_final_eps", 0.05),
                tensorboard_log=self.tb_log,
                device=self.device,
                verbose=1,
            )

        elif algo == "a2c":
            from stable_baselines3 import A2C

            return A2C(
                "MlpPolicy",
                env,
                learning_rate=algo_config.get("learning_rate", 0.0007),
                gamma=algo_config.get("gamma", 0.99),
                gae_lambda=algo_config.get("gae_lambda", 0.95),
                ent_coef=algo_config.get("ent_coef", 0.01),
                vf_coef=algo_config.get("vf_coef", 0.5),
                n_steps=algo_config.get("n_steps", 5),
                tensorboard_log=self.tb_log,
                device=self.device,
                verbose=1,
            )

        elif algo == "ppo":
            from stable_baselines3 import PPO

            return PPO(
                "MlpPolicy",
                env,
                learning_rate=algo_config.get("learning_rate", 0.0001),
                gamma=algo_config.get("gamma", 0.99),
                gae_lambda=algo_config.get("gae_lambda", 0.95),
                clip_range=algo_config.get("clip_range", 0.2),
                ent_coef=algo_config.get("ent_coef", 0.01),
                vf_coef=algo_config.get("vf_coef", 0.5),
                n_steps=algo_config.get("n_steps", 2048),
                batch_size=algo_config.get("batch_size", 64),
                n_epochs=algo_config.get("n_epochs", 10),
                tensorboard_log=self.tb_log,
                device=self.device,
                verbose=1,
            )

        raise ValueError(f"Unknown algo: {algo}")

    def _build_callbacks(
        self,
        algo: str,
        eval_days: list[np.ndarray] | None,
        eval_prices: list[np.ndarray] | None,
        env_config: RLEnvConfig,
        continuous: bool = False,
    ) -> list:
        """학습 콜백 구성"""
        from stable_baselines3.common.callbacks import (
            CheckpointCallback,
            EvalCallback,
        )

        callbacks = []
        training_cfg = self.config.get("training", {})

        # 체크포인트 콜백
        checkpoint_freq = training_cfg.get("checkpoint_freq", 50_000)
        callbacks.append(
            CheckpointCallback(
                save_freq=checkpoint_freq,
                save_path=str(self.save_dir / algo),
                name_prefix=algo,
            )
        )

        # 평가 콜백 (eval 데이터가 있는 경우)
        if eval_days is not None and len(eval_days) > 0:
            eval_env = self._make_env(
                eval_days, eval_prices, env_config, continuous=continuous
            )
            eval_freq = training_cfg.get("eval_freq", 10_000)

            if algo == "mppo":
                # MaskablePPO용 EvalCallback (action masking 지원)
                try:
                    from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback

                    callbacks.append(
                        MaskableEvalCallback(
                            eval_env,
                            best_model_save_path=str(self.save_dir / f"{algo}_best"),
                            log_path=str(self.save_dir / f"{algo}_eval"),
                            eval_freq=eval_freq,
                            deterministic=True,
                        )
                    )
                except ImportError:
                    # MaskableEvalCallback 미지원 버전 — 일반 EvalCallback 사용
                    callbacks.append(
                        EvalCallback(
                            eval_env,
                            best_model_save_path=str(self.save_dir / f"{algo}_best"),
                            log_path=str(self.save_dir / f"{algo}_eval"),
                            eval_freq=eval_freq,
                            deterministic=True,
                        )
                    )
            else:
                callbacks.append(
                    EvalCallback(
                        eval_env,
                        best_model_save_path=str(self.save_dir / f"{algo}_best"),
                        log_path=str(self.save_dir / f"{algo}_eval"),
                        eval_freq=eval_freq,
                        deterministic=True,
                    )
                )

        return callbacks

    def _log_mlflow_start(self, algo: str, params: dict) -> None:
        """MLflow 실험 시작 로깅"""
        try:
            import mlflow

            mlflow.set_experiment(f"rl_{algo}")
            mlflow.start_run(run_name=f"{algo}_training")
            mlflow.log_params(params)
            logger.info(f"MLflow experiment started: rl_{algo}")
        except ImportError:
            logger.debug("MLflow not available, skipping tracking")
        except Exception as e:
            logger.warning(f"MLflow logging failed: {e}")

    def _train_dt(
        self,
        train_days: list[np.ndarray] | None = None,
        train_prices: list[np.ndarray] | None = None,
        eval_days: list[np.ndarray] | None = None,
        eval_prices: list[np.ndarray] | None = None,
    ) -> Any:
        """Decision Transformer 학습 (자체 PyTorch 루프)

        궤적 캐시가 있으면 로드, 없으면 MPPO expert rollout으로 생성.
        """
        from shared.ml.rl.decision_transformer.dataset import TrajectoryCollector
        from shared.ml.rl.decision_transformer.trainer import DTTrainer

        config = ConfigLoader.load("ml/rl_dt.yaml")
        traj_cfg = config.get("trajectory", {})
        traj_path = Path(traj_cfg.get("save_path", "models/futures/rl/dt_trajectories.pt"))

        # 궤적 로드 또는 생성
        if traj_path.exists():
            logger.info(f"Loading cached trajectories: {traj_path}")
            all_trajs = TrajectoryCollector.load(traj_path)
        else:
            if train_days is None or train_prices is None:
                raise ValueError("train_days/train_prices required for trajectory collection")

            logger.info("Collecting expert trajectories...")
            collector = TrajectoryCollector(config_path="ml/rl_dt.yaml")
            all_trajs = collector.collect(train_days, train_prices)
            collector.save(all_trajs, traj_path)

        # Train/eval 분할 (궤적 레벨)
        data_cfg = config.get("data", {})
        train_ratio = float(data_cfg.get("train_ratio", 0.8))
        split_idx = int(len(all_trajs) * train_ratio)
        train_trajs = all_trajs[:split_idx]
        eval_trajs = all_trajs[split_idx:] if split_idx < len(all_trajs) else None

        # DTTrainer로 학습
        dt_trainer = DTTrainer(config_path="ml/rl_dt.yaml")
        agent = dt_trainer.train(
            train_trajs=train_trajs,
            eval_trajs=eval_trajs,
            eval_days=eval_days,
            eval_prices=eval_prices,
        )

        return agent

    def _log_mlflow_end(self, _algo: str) -> None:
        """MLflow 실험 종료 로깅"""
        try:
            import mlflow

            mlflow.end_run()
        except (ImportError, Exception):
            pass
