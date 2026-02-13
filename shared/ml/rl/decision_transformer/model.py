"""Decision Transformer 모델 및 에이전트

HuggingFace DecisionTransformerModel 기반.
action_tanh=False → discrete logits → action masking → argmax/sample.

Usage:
    agent = DTAgent.load("models/futures/rl/dt_final")
    agent.reset(target_return=5_000_000)
    action, probs = agent.predict(obs, action_masks, reward=prev_reward)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch

from shared.config import ConfigLoader

logger = logging.getLogger(__name__)


@dataclass
class DTConfig:
    """Decision Transformer 설정

    config/ml/rl_dt.yaml의 dt 섹션에서 로드.
    """

    state_dim: int = 31
    act_dim: int = 5
    hidden_size: int = 128
    n_layer: int = 3
    n_head: int = 4
    max_ep_len: int = 405
    action_tanh: bool = False
    context_length: int = 20
    resid_pdrop: float = 0.1

    @classmethod
    def from_yaml(cls, config_path: str = "ml/rl_dt.yaml") -> DTConfig:
        """YAML 설정에서 로드"""
        config = ConfigLoader.load(config_path)
        dt_cfg = config.get("dt", {})
        return cls(
            state_dim=dt_cfg.get("state_dim", 31),
            act_dim=dt_cfg.get("act_dim", 5),
            hidden_size=dt_cfg.get("hidden_size", 128),
            n_layer=dt_cfg.get("n_layer", 3),
            n_head=dt_cfg.get("n_head", 4),
            max_ep_len=dt_cfg.get("max_ep_len", 405),
            action_tanh=dt_cfg.get("action_tanh", False),
            context_length=dt_cfg.get("context_length", 20),
            resid_pdrop=dt_cfg.get("resid_pdrop", 0.1),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> DTConfig:
        """JSON 파일에서 로드"""
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_dim": self.state_dim,
            "act_dim": self.act_dim,
            "hidden_size": self.hidden_size,
            "n_layer": self.n_layer,
            "n_head": self.n_head,
            "max_ep_len": self.max_ep_len,
            "action_tanh": self.action_tanh,
            "context_length": self.context_length,
            "resid_pdrop": self.resid_pdrop,
        }


@dataclass
class _ContextBuffer:
    """Sliding window context buffer for autoregressive inference."""

    K: int
    state_dim: int
    act_dim: int

    states: list[np.ndarray] = field(default_factory=list)
    actions: list[int] = field(default_factory=list)
    rewards: list[float] = field(default_factory=list)
    returns_to_go: list[float] = field(default_factory=list)
    timesteps: list[int] = field(default_factory=list)

    def reset(self, target_return: float) -> None:
        self.states.clear()
        self.actions.clear()
        self.rewards.clear()
        self.returns_to_go.clear()
        self.timesteps.clear()
        self._initial_rtg = target_return

    def append(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        timestep: int,
    ) -> None:
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)

        # RTG 계산: 첫 스텝이면 initial, 아니면 이전 RTG - 이전 reward
        if len(self.returns_to_go) == 0:
            self.returns_to_go.append(self._initial_rtg)
        else:
            new_rtg = self.returns_to_go[-1] - reward
            self.returns_to_go.append(new_rtg)

        self.timesteps.append(timestep)

    @property
    def length(self) -> int:
        return len(self.states)


class DTAgent:
    """Decision Transformer 추론 에이전트

    Sliding window context를 유지하며 autoregressive 추론.
    action_tanh=False → logits → masking → softmax → argmax.
    """

    def __init__(
        self,
        config: DTConfig,
        model: Any | None = None,
        device: str = "cpu",
    ):
        self.config = config
        self.device = torch.device(device)

        if model is not None:
            self.model = model
        else:
            self.model = self._build_model()

        self.model.to(self.device)
        self.model.eval()

        self._buf = _ContextBuffer(
            K=config.context_length,
            state_dim=config.state_dim,
            act_dim=config.act_dim,
        )
        self._timestep = 0

    def _build_model(self) -> Any:
        """HuggingFace DecisionTransformerModel 생성"""
        from transformers import DecisionTransformerConfig, DecisionTransformerModel

        hf_config = DecisionTransformerConfig(
            state_dim=self.config.state_dim,
            act_dim=self.config.act_dim,
            hidden_size=self.config.hidden_size,
            n_layer=self.config.n_layer,
            n_head=self.config.n_head,
            max_ep_len=self.config.max_ep_len,
            action_tanh=self.config.action_tanh,
            resid_pdrop=self.config.resid_pdrop,
            attn_pdrop=self.config.resid_pdrop,
            max_length=self.config.context_length,
        )
        return DecisionTransformerModel(hf_config)

    def reset(self, target_return: float | None = None) -> None:
        """에피소드 시작 시 context buffer 초기화

        Args:
            target_return: 목표 returns-to-go. None이면 config default.
        """
        if target_return is None:
            target_return = 5_000_000.0
        self._buf.reset(target_return)
        self._timestep = 0

    def predict(
        self,
        state: np.ndarray,
        action_masks: np.ndarray | None = None,
        reward: float = 0.0,
        deterministic: bool = True,
    ) -> tuple[int, np.ndarray]:
        """단일 스텝 추론

        Args:
            state: 현재 관측 (state_dim,)
            action_masks: 유효 행동 마스크 (act_dim,) bool
            reward: 이전 스텝 보상 (RTG 업데이트용)
            deterministic: True면 argmax, False면 sample

        Returns:
            (action_int, action_probs)
        """
        K = self.config.K if hasattr(self.config, "K") else self.config.context_length

        # 이전 행동의 reward로 buffer에 추가
        # 첫 스텝에서는 dummy action=0 추가
        if self._buf.length == 0:
            self._buf.append(state, 0, 0.0, self._timestep)
        else:
            # 이전 스텝의 reward 업데이트 + 새 state 추가
            self._buf.append(state, 0, reward, self._timestep)

        # Context window 준비 (최근 K 스텝)
        seq_len = min(self._buf.length, K)
        start = max(0, self._buf.length - K)

        states_np = np.array(self._buf.states[start:start + seq_len], dtype=np.float32)
        actions_np = np.zeros((seq_len, self.config.act_dim), dtype=np.float32)
        for i, a in enumerate(self._buf.actions[start:start + seq_len]):
            actions_np[i, a] = 1.0  # one-hot
        rewards_np = np.array(
            self._buf.rewards[start:start + seq_len], dtype=np.float32
        ).reshape(-1, 1)
        rtg_np = np.array(
            self._buf.returns_to_go[start:start + seq_len], dtype=np.float32
        ).reshape(-1, 1)
        timesteps_np = np.array(
            self._buf.timesteps[start:start + seq_len], dtype=np.int64
        )

        # Left-pad if seq_len < K
        pad_len = K - seq_len
        if pad_len > 0:
            states_np = np.concatenate(
                [np.zeros((pad_len, self.config.state_dim), dtype=np.float32), states_np]
            )
            actions_np = np.concatenate(
                [np.zeros((pad_len, self.config.act_dim), dtype=np.float32), actions_np]
            )
            rewards_np = np.concatenate(
                [np.zeros((pad_len, 1), dtype=np.float32), rewards_np]
            )
            rtg_np = np.concatenate(
                [np.zeros((pad_len, 1), dtype=np.float32), rtg_np]
            )
            timesteps_np = np.concatenate(
                [np.zeros(pad_len, dtype=np.int64), timesteps_np]
            )

        # Attention mask: 0 for padded, 1 for real
        attention_mask = np.zeros(K, dtype=np.float32)
        attention_mask[pad_len:] = 1.0

        # To tensors (batch_size=1)
        with torch.no_grad():
            states_t = torch.tensor(states_np, dtype=torch.float32).unsqueeze(0).to(self.device)
            actions_t = torch.tensor(actions_np, dtype=torch.float32).unsqueeze(0).to(self.device)
            rewards_t = torch.tensor(rewards_np, dtype=torch.float32).unsqueeze(0).to(self.device)
            rtg_t = torch.tensor(rtg_np, dtype=torch.float32).unsqueeze(0).to(self.device)
            timesteps_t = torch.tensor(timesteps_np, dtype=torch.long).unsqueeze(0).to(self.device)
            attn_mask_t = torch.tensor(attention_mask, dtype=torch.float32).unsqueeze(0).to(self.device)

            output = self.model(
                states=states_t,
                actions=actions_t,
                rewards=rewards_t,
                returns_to_go=rtg_t,
                timesteps=timesteps_t,
                attention_mask=attn_mask_t,
            )

            # action_preds shape: (1, K, act_dim)
            # 마지막 실제 위치의 예측 사용
            logits = output.action_preds[0, -1, :]  # (act_dim,)

            # Action masking
            if action_masks is not None:
                mask_tensor = torch.tensor(action_masks, dtype=torch.bool).to(self.device)
                logits[~mask_tensor] = float("-inf")

            # Softmax → action
            probs = torch.softmax(logits, dim=-1)
            probs_np = probs.cpu().numpy()

            if deterministic:
                action_int = int(torch.argmax(probs).item())
            else:
                action_int = int(torch.multinomial(probs, 1).item())

        # 선택한 action을 buffer의 마지막 항목에 반영
        self._buf.actions[-1] = action_int
        self._timestep += 1

        return action_int, probs_np

    def save(self, save_dir: str | Path) -> None:
        """모델 + 설정 저장

        Args:
            save_dir: 저장 디렉토리
        """
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        # 모델 state dict
        torch.save(self.model.state_dict(), save_dir / "model.pt")

        # 설정
        with open(save_dir / "config.json", "w") as f:
            json.dump(self.config.to_dict(), f, indent=2)

        logger.info(f"DTAgent saved: {save_dir}")

    @classmethod
    def load(
        cls,
        model_dir: str | Path,
        device: str = "cpu",
        scaler: Any = None,
    ) -> DTAgent:
        """저장된 모델 로드

        Args:
            model_dir: 모델 디렉토리 (model.pt + config.json)
            device: 디바이스
            scaler: MinMaxScaler (paper trading용)
        """
        model_dir = Path(model_dir)
        config = DTConfig.from_json(model_dir / "config.json")

        agent = cls(config=config, device=device)
        state_dict = torch.load(
            model_dir / "model.pt", map_location=device, weights_only=True,
        )
        agent.model.load_state_dict(state_dict)
        agent.model.eval()

        logger.info(f"DTAgent loaded: {model_dir}")
        return agent
