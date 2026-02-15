"""TFT 모델: Temporal Fusion Transformer for return prediction

Custom PyTorch 구현:
  VariableSelectionNetwork → LSTM Encoder → MultiHeadAttention → GRN → FC

출력: 다중 시간 지평 수익률 예측 [ret_1m, ret_5m, ret_15m]

Usage:
    config = TFTConfig.from_yaml("ml/tft.yaml")
    model = TFTModel(config)
    out = model(x)  # (batch, lookback, 28) → (batch, 3)
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn

from shared.config import ConfigLoader

logger = logging.getLogger(__name__)


@dataclass
class TFTConfig:
    """TFT 하이퍼파라미터

    config/ml/tft.yaml의 tft 섹션에서 로드.
    """

    n_features: int = 25
    n_time_features: int = 3
    total_input_dim: int = 28

    hidden_size: int = 64
    lstm_layers: int = 2
    n_heads: int = 4
    dropout: float = 0.1
    grn_hidden: int = 32

    lookback: int = 60
    horizons: list[int] = field(default_factory=lambda: [1, 5, 15])

    mode: str = "regression"  # "regression" | "classification"
    label_smoothing: float = 0.05
    classification_threshold: float = 0.0

    @classmethod
    def from_yaml(cls, config_path: str = "ml/tft.yaml") -> TFTConfig:
        """YAML 설정에서 로드"""
        config = ConfigLoader.load(config_path)
        tft_cfg = config.get("tft", {})
        horizons = tft_cfg.get("horizons", [1, 5, 15])
        return cls(
            n_features=tft_cfg.get("n_features", 25),
            n_time_features=tft_cfg.get("n_time_features", 3),
            total_input_dim=tft_cfg.get("total_input_dim", 28),
            hidden_size=tft_cfg.get("hidden_size", 64),
            lstm_layers=tft_cfg.get("lstm_layers", 2),
            n_heads=tft_cfg.get("n_heads", 4),
            dropout=tft_cfg.get("dropout", 0.1),
            grn_hidden=tft_cfg.get("grn_hidden", 32),
            lookback=tft_cfg.get("lookback", 60),
            horizons=horizons,
            mode=tft_cfg.get("mode", "regression"),
            label_smoothing=tft_cfg.get("label_smoothing", 0.05),
            classification_threshold=tft_cfg.get("classification_threshold", 0.0),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> TFTConfig:
        """JSON 파일에서 로드"""
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_features": self.n_features,
            "n_time_features": self.n_time_features,
            "total_input_dim": self.total_input_dim,
            "hidden_size": self.hidden_size,
            "lstm_layers": self.lstm_layers,
            "n_heads": self.n_heads,
            "dropout": self.dropout,
            "grn_hidden": self.grn_hidden,
            "lookback": self.lookback,
            "horizons": self.horizons,
            "mode": self.mode,
            "label_smoothing": self.label_smoothing,
            "classification_threshold": self.classification_threshold,
        }


class GatedResidualNetwork(nn.Module):
    """Gated Residual Network (GRN)

    FC → ELU → FC → Dropout → GLU gate + skip connection + LayerNorm.
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        output_size: int,
        dropout: float = 0.1,
        context_size: int | None = None,
    ):
        super().__init__()
        self.input_size = input_size
        self.output_size = output_size

        self.fc1 = nn.Linear(input_size, hidden_size)
        self.elu = nn.ELU()
        self.fc2 = nn.Linear(hidden_size, output_size * 2)  # GLU doubles
        self.dropout = nn.Dropout(dropout)

        if context_size is not None:
            self.context_proj = nn.Linear(context_size, hidden_size, bias=False)
        else:
            self.context_proj = None

        # Skip connection projection if dims differ
        if input_size != output_size:
            self.skip_proj = nn.Linear(input_size, output_size)
        else:
            self.skip_proj = None

        self.layer_norm = nn.LayerNorm(output_size)

    def forward(
        self, x: torch.Tensor, context: torch.Tensor | None = None
    ) -> torch.Tensor:
        """
        Args:
            x: (..., input_size)
            context: optional (..., context_size)

        Returns:
            (..., output_size)
        """
        residual = x if self.skip_proj is None else self.skip_proj(x)

        hidden = self.fc1(x)
        if self.context_proj is not None and context is not None:
            hidden = hidden + self.context_proj(context)
        hidden = self.elu(hidden)
        hidden = self.fc2(hidden)
        hidden = self.dropout(hidden)

        # GLU gating
        value, gate = hidden.chunk(2, dim=-1)
        gated = value * torch.sigmoid(gate)

        return self.layer_norm(gated + residual)


class VariableSelectionNetwork(nn.Module):
    """Variable Selection Network (VSN)

    피처별 GRN → softmax 가중치 → 가중합.
    각 피처에 독립적 GRN을 적용하여 중요도를 학습.
    """

    def __init__(
        self,
        n_vars: int,
        hidden_size: int,
        grn_hidden: int,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.n_vars = n_vars
        self.hidden_size = hidden_size

        # 각 변수를 hidden_size로 프로젝션
        self.var_projections = nn.ModuleList(
            [nn.Linear(1, hidden_size) for _ in range(n_vars)]
        )

        # 각 변수별 GRN
        self.var_grns = nn.ModuleList(
            [
                GatedResidualNetwork(hidden_size, grn_hidden, hidden_size, dropout)
                for _ in range(n_vars)
            ]
        )

        # 가중치 생성 GRN (flatten input → n_vars weights)
        self.weight_grn = GatedResidualNetwork(
            n_vars * hidden_size, grn_hidden, n_vars, dropout
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: (batch, seq_len, n_vars)

        Returns:
            (selected: (batch, seq_len, hidden_size),
             weights: (batch, seq_len, n_vars))
        """
        batch, seq_len, _ = x.shape

        # 각 변수를 독립적으로 프로젝션 + GRN
        var_outputs = []
        for i in range(self.n_vars):
            # (batch, seq_len, 1) → (batch, seq_len, hidden_size)
            proj = self.var_projections[i](x[..., i : i + 1])
            processed = self.var_grns[i](proj)
            var_outputs.append(processed)

        # Stack: (batch, seq_len, n_vars, hidden_size)
        var_stack = torch.stack(var_outputs, dim=2)

        # Flatten for weight computation
        flat = var_stack.reshape(batch, seq_len, -1)  # (batch, seq, n_vars*hidden)
        weights = torch.softmax(self.weight_grn(flat), dim=-1)  # (batch, seq, n_vars)

        # Weighted sum
        # weights: (batch, seq, n_vars, 1) * var_stack: (batch, seq, n_vars, hidden)
        selected = (weights.unsqueeze(-1) * var_stack).sum(dim=2)

        return selected, weights


class TFTModel(nn.Module):
    """Temporal Fusion Transformer

    Input: (batch, lookback, total_input_dim)
      → VSN (피처 중요도)
      → LSTM Encoder (시계열 패턴)
      → MultiHeadAttention (자기주의)
      → GRN (비선형 변환)
      → FC Output (수익률 예측)
    Output: (batch, n_horizons)
    """

    def __init__(self, config: TFTConfig):
        super().__init__()
        self.config = config
        n_horizons = len(config.horizons)

        # Variable Selection Network
        self.vsn = VariableSelectionNetwork(
            n_vars=config.total_input_dim,
            hidden_size=config.hidden_size,
            grn_hidden=config.grn_hidden,
            dropout=config.dropout,
        )

        # LSTM Encoder
        self.lstm = nn.LSTM(
            input_size=config.hidden_size,
            hidden_size=config.hidden_size,
            num_layers=config.lstm_layers,
            batch_first=True,
            dropout=config.dropout if config.lstm_layers > 1 else 0.0,
        )

        # Post-LSTM gate + skip
        self.post_lstm_gate = nn.Linear(config.hidden_size, config.hidden_size * 2)
        self.post_lstm_norm = nn.LayerNorm(config.hidden_size)

        # Multi-Head Attention
        self.attention = nn.MultiheadAttention(
            embed_dim=config.hidden_size,
            num_heads=config.n_heads,
            dropout=config.dropout,
            batch_first=True,
        )

        # Post-attention GRN
        self.post_attn_grn = GatedResidualNetwork(
            config.hidden_size, config.grn_hidden, config.hidden_size, config.dropout
        )

        # Output head — regression: n_horizons, classification: n_horizons logits
        self.output_fc = nn.Linear(config.hidden_size, n_horizons)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, lookback, total_input_dim)

        Returns:
            (batch, n_horizons) 수익률 예측
        """
        # 1. Variable Selection
        selected, _ = self.vsn(x)  # (batch, lookback, hidden)

        # 2. LSTM Encoder
        lstm_out, _ = self.lstm(selected)  # (batch, lookback, hidden)

        # Post-LSTM gating + residual
        gate_input = self.post_lstm_gate(lstm_out)
        value, gate = gate_input.chunk(2, dim=-1)
        gated = value * torch.sigmoid(gate)
        lstm_out = self.post_lstm_norm(gated + selected)

        # 3. Multi-Head Self-Attention
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)

        # 4. Post-attention GRN + residual
        enriched = self.post_attn_grn(attn_out + lstm_out)

        # 5. Output: 마지막 timestep만 사용
        last_hidden = enriched[:, -1, :]  # (batch, hidden)
        predictions = self.output_fc(last_hidden)  # (batch, n_horizons)

        return predictions

    @torch.no_grad()
    def predict_direction_probs(
        self, x: torch.Tensor | np.ndarray,
    ) -> np.ndarray:
        """방향 확률 예측 (classification 모드 전용)

        Args:
            x: (lookback, total_input_dim) or (batch, lookback, total_input_dim)

        Returns:
            (n_horizons,) or (batch, n_horizons) — 각 horizon의 상승 확률 [0, 1]
        """
        self.eval()
        squeezed = False

        if isinstance(x, np.ndarray):
            x = torch.from_numpy(x.astype(np.float32))

        if x.dim() == 2:
            x = x.unsqueeze(0)
            squeezed = True

        device = next(self.parameters()).device
        x = x.to(device)

        logits = self.forward(x)  # (batch, n_horizons)
        probs = torch.sigmoid(logits).cpu().numpy()

        if squeezed:
            return probs[0]  # (n_horizons,)
        return probs

    def get_attention_weights(self, x: torch.Tensor) -> torch.Tensor:
        """주의 가중치 반환 (해석용)"""
        selected, _ = self.vsn(x)
        lstm_out, _ = self.lstm(selected)
        gate_input = self.post_lstm_gate(lstm_out)
        value, gate = gate_input.chunk(2, dim=-1)
        gated = value * torch.sigmoid(gate)
        lstm_out = self.post_lstm_norm(gated + selected)
        _, attn_weights = self.attention(
            lstm_out, lstm_out, lstm_out, need_weights=True
        )
        return attn_weights

    def get_variable_importance(self, x: torch.Tensor) -> torch.Tensor:
        """VSN 피처 중요도 반환 (해석용)"""
        _, weights = self.vsn(x)
        return weights.mean(dim=(0, 1))  # (n_vars,)

    def save(self, save_dir: str | Path) -> None:
        """모델 + 설정 저장"""
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        torch.save(self.state_dict(), save_dir / "model.pt")
        with open(save_dir / "config.json", "w") as f:
            json.dump(self.config.to_dict(), f, indent=2)

        logger.info(f"TFTModel saved: {save_dir}")

    @classmethod
    def load(
        cls, model_dir: str | Path, device: str = "cpu"
    ) -> TFTModel:
        """저장된 모델 로드"""
        model_dir = Path(model_dir)
        config = TFTConfig.from_json(model_dir / "config.json")

        model = cls(config)
        state_dict = torch.load(
            model_dir / "model.pt", map_location=device, weights_only=True
        )
        model.load_state_dict(state_dict)
        model.to(device)
        model.eval()

        logger.info(f"TFTModel loaded: {model_dir}")
        return model
