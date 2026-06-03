"""궤적 수집 및 Dataset

MPPO expert rollout으로 궤적 생성 → DT 학습용 Dataset.

Usage:
    collector = TrajectoryCollector()
    trajs = collector.collect(train_days, train_prices)
    collector.save(trajs, "dt_trajectories.pt")

    dataset = TrajectoryDataset(trajs, K=20, act_dim=5)
    loader = DataLoader(dataset, batch_size=64, shuffle=True)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import Dataset

from shared.config import ConfigLoader
from shared.ml.rl.env import FuturesTradingEnv, RLEnvConfig

logger = logging.getLogger(__name__)


class TrajectoryCollector:
    """MPPO expert rollout으로 궤적 수집

    FuturesTradingEnv에서 MPPO 모델로 rollout하여
    (states, actions, rewards, returns_to_go, timesteps) 궤적 수집.
    """

    def __init__(self, config_path: str = "ml/rl_dt.yaml"):
        self.config = ConfigLoader.load(config_path)
        self.env_config = RLEnvConfig.from_yaml(config_path)

        # expert 모델 경로
        traj_cfg = self.config.get("trajectory", {})
        training_cfg = self.config.get("training", {})
        save_dir = Path(training_cfg.get("save_dir", "./models/futures/rl/"))
        expert_name = traj_cfg.get("expert_model", "mppo_final")

        self._expert_path = save_dir / expert_name / "best_model.zip"
        if not self._expert_path.exists():
            # fallback: direct zip file
            alt = save_dir / f"{expert_name}.zip"
            if alt.exists():
                self._expert_path = alt

    def collect(
        self,
        days: list[np.ndarray],
        prices: list[np.ndarray],
    ) -> list[dict[str, np.ndarray]]:
        """MPPO expert rollout으로 궤적 수집

        Args:
            days: 일별 피처 배열 리스트
            prices: 일별 OHLC 배열 리스트

        Returns:
            궤적 리스트. 각 dict는:
                states: (T, state_dim) float32
                actions: (T,) int64
                rewards: (T,) float32
                returns_to_go: (T,) float32
                timesteps: (T,) int64
        """
        from sb3_contrib import MaskablePPO

        if not self._expert_path.exists():
            raise FileNotFoundError(f"Expert model not found: {self._expert_path}")

        model = MaskablePPO.load(str(self._expert_path))
        logger.info(f"Loaded expert: {self._expert_path}")

        trajectories = []
        for idx, (day_data, day_prices) in enumerate(zip(days, prices)):
            env = FuturesTradingEnv(
                day_data=day_data, config=self.env_config, prices=day_prices,
            )
            obs, _ = env.reset()

            states_list = []
            actions_list = []
            rewards_list = []

            terminated = False
            while not terminated:
                masks = env.action_masks()
                action, _ = model.predict(
                    obs, deterministic=True, action_masks=masks,
                )
                action_int = int(action)

                states_list.append(obs.copy())
                actions_list.append(action_int)

                obs, reward, terminated, _, _ = env.step(action_int)
                rewards_list.append(float(reward))

            if len(states_list) == 0:
                continue

            states = np.array(states_list, dtype=np.float32)
            actions = np.array(actions_list, dtype=np.int64)
            rewards = np.array(rewards_list, dtype=np.float32)

            # Returns-to-go: 역방향 누적합
            rtg = np.zeros_like(rewards)
            rtg[-1] = rewards[-1]
            for t in range(len(rewards) - 2, -1, -1):
                rtg[t] = rewards[t] + rtg[t + 1]

            timesteps = np.arange(len(states), dtype=np.int64)

            trajectories.append({
                "states": states,
                "actions": actions,
                "rewards": rewards,
                "returns_to_go": rtg,
                "timesteps": timesteps,
            })

            if (idx + 1) % 10 == 0:
                logger.info(f"Collected {idx + 1}/{len(days)} trajectories")

        logger.info(
            f"Trajectory collection complete: {len(trajectories)} episodes, "
            f"total {sum(len(t['states']) for t in trajectories)} steps"
        )
        return trajectories

    @staticmethod
    def save(trajectories: list[dict[str, np.ndarray]], path: str | Path) -> None:
        """궤적 저장"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # numpy → torch tensor로 변환하여 저장
        torch_trajs = []
        for traj in trajectories:
            torch_trajs.append({
                k: torch.from_numpy(v) for k, v in traj.items()
            })

        torch.save(torch_trajs, path)
        logger.info(f"Saved {len(trajectories)} trajectories to {path}")

    @staticmethod
    def load(path: str | Path) -> list[dict[str, Any]]:
        """궤적 로드"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Trajectory file not found: {path}")

        trajs = torch.load(path, weights_only=True)
        # tensor → numpy 변환
        result = []
        for traj in trajs:
            result.append({
                k: v.numpy() if isinstance(v, torch.Tensor) else v
                for k, v in traj.items()
            })

        logger.info(f"Loaded {len(result)} trajectories from {path}")
        return result


class TrajectoryDataset(Dataset):
    """DT 학습용 Dataset

    궤적에서 random context window(K)를 샘플링.
    """

    def __init__(
        self,
        trajectories: list[dict[str, np.ndarray]],
        context_length: int = 20,
        act_dim: int = 5,
    ):
        """
        Args:
            trajectories: TrajectoryCollector 출력
            context_length: context window 크기 (K)
            act_dim: 행동 차원 (one-hot 인코딩용)
        """
        self.K = context_length
        self.act_dim = act_dim

        # (trajectory_idx, start_timestep) 쌍 목록
        self._indices: list[tuple[int, int]] = []
        self._trajectories = trajectories

        for traj_idx, traj in enumerate(trajectories):
            T = len(traj["states"])
            # 각 궤적에서 가능한 모든 시작점
            for start in range(max(1, T - context_length + 1)):
                self._indices.append((traj_idx, start))

    def __len__(self) -> int:
        return len(self._indices)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        """context window 샘플

        Returns:
            states: (K, state_dim) float32
            actions: (K, act_dim) float32 one-hot
            rewards: (K, 1) float32
            returns_to_go: (K, 1) float32
            timesteps: (K,) long
            attention_mask: (K,) float32
            target_actions: (K,) long — 분류 loss 타겟
        """
        traj_idx, start = self._indices[idx]
        traj = self._trajectories[traj_idx]

        T = len(traj["states"])
        end = min(start + self.K, T)
        seq_len = end - start

        state_dim = traj["states"].shape[1]

        # 실제 데이터 슬라이스
        states = traj["states"][start:end].astype(np.float32)
        actions_raw = traj["actions"][start:end]
        rewards = traj["rewards"][start:end].astype(np.float32).reshape(-1, 1)
        rtg = traj["returns_to_go"][start:end].astype(np.float32).reshape(-1, 1)
        timesteps = traj["timesteps"][start:end].astype(np.int64)

        # One-hot 인코딩
        actions_onehot = np.zeros((seq_len, self.act_dim), dtype=np.float32)
        for i, a in enumerate(actions_raw):
            actions_onehot[i, a] = 1.0

        # Left-pad if seq_len < K
        pad_len = self.K - seq_len
        if pad_len > 0:
            states = np.concatenate(
                [np.zeros((pad_len, state_dim), dtype=np.float32), states]
            )
            actions_onehot = np.concatenate(
                [np.zeros((pad_len, self.act_dim), dtype=np.float32), actions_onehot]
            )
            rewards = np.concatenate(
                [np.zeros((pad_len, 1), dtype=np.float32), rewards]
            )
            rtg = np.concatenate(
                [np.zeros((pad_len, 1), dtype=np.float32), rtg]
            )
            timesteps = np.concatenate(
                [np.zeros(pad_len, dtype=np.int64), timesteps]
            )
            actions_raw = np.concatenate(
                [np.zeros(pad_len, dtype=np.int64), actions_raw]
            )

        attention_mask = np.zeros(self.K, dtype=np.float32)
        attention_mask[pad_len:] = 1.0

        return {
            "states": torch.tensor(states, dtype=torch.float32),
            "actions": torch.tensor(actions_onehot, dtype=torch.float32),
            "rewards": torch.tensor(rewards, dtype=torch.float32),
            "returns_to_go": torch.tensor(rtg, dtype=torch.float32),
            "timesteps": torch.tensor(timesteps, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.float32),
            "target_actions": torch.tensor(actions_raw, dtype=torch.long),
        }
