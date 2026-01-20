"""ML 기본 인터페이스

모델 로더 및 디바이스 관리.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# PyTorch optional import
try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None


def get_device(device: str = "auto") -> str:
    """디바이스 자동 선택

    Args:
        device: "auto", "cuda", "mps", "cpu"

    Returns:
        사용 가능한 디바이스 문자열
    """
    if device == "auto":
        if TORCH_AVAILABLE:
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        return "cpu"

    if device == "cuda" and TORCH_AVAILABLE and not torch.cuda.is_available():
        logger.warning("CUDA not available. Falling back to CPU.")
        return "cpu"

    return device


@dataclass
class ModelMetadata:
    """모델 메타데이터"""

    model_type: str = "lstm"  # "lstm" or "cnn-lstm"
    input_dim: int = 10
    hidden_dim: int = 64
    num_layers: int = 2
    num_classes: int = 3
    dropout: float = 0.2
    cnn_channels: tuple[int, ...] = (32, 64)
    kernel_size: int = 3
    seq_len: int = 60
    version: str = "1.0.0"
    feature_columns: list[str] | None = None

    @classmethod
    def from_json(cls, path: str | Path) -> ModelMetadata:
        """JSON 파일에서 메타데이터 로드"""
        with open(path, "r") as f:
            data = json.load(f)

        # tuple 변환
        if "cnn_channels" in data and isinstance(data["cnn_channels"], list):
            data["cnn_channels"] = tuple(data["cnn_channels"])

        return cls(**{k: v for k, v in data.items() if hasattr(cls, k) or k in cls.__dataclass_fields__})

    def to_json(self, path: str | Path) -> None:
        """JSON 파일로 저장"""
        data = {
            "model_type": self.model_type,
            "input_dim": self.input_dim,
            "hidden_dim": self.hidden_dim,
            "num_layers": self.num_layers,
            "num_classes": self.num_classes,
            "dropout": self.dropout,
            "cnn_channels": list(self.cnn_channels),
            "kernel_size": self.kernel_size,
            "seq_len": self.seq_len,
            "version": self.version,
            "feature_columns": self.feature_columns,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


@dataclass
class ScalerParams:
    """StandardScaler 파라미터"""

    mean: list[float]
    scale: list[float]

    @classmethod
    def from_json(cls, path: str | Path) -> ScalerParams:
        """JSON 파일에서 로드"""
        with open(path, "r") as f:
            data = json.load(f)
        return cls(mean=data["mean"], scale=data["scale"])

    def to_json(self, path: str | Path) -> None:
        """JSON 파일로 저장"""
        with open(path, "w") as f:
            json.dump({"mean": self.mean, "scale": self.scale}, f, indent=2)

    def transform(self, X: np.ndarray) -> np.ndarray:
        """표준화 적용"""
        mean = np.array(self.mean)
        scale = np.array(self.scale)
        return (X - mean) / scale


class ModelLoader:
    """모델 로더

    PyTorch 모델 로드 및 추론.

    Usage:
        loader = ModelLoader("models/futures/trading_lstm.pth")
        loader.load()
        probs = loader.predict(sequence)  # (seq_len, features) -> (3,)
    """

    def __init__(
        self,
        model_path: str | Path,
        device: str = "auto",
    ):
        """
        Args:
            model_path: 모델 가중치 파일 경로 (.pth)
            device: 디바이스 ("auto", "cuda", "mps", "cpu")
        """
        self.model_path = Path(model_path)
        self.device = get_device(device)
        self.model = None
        self.metadata: Optional[ModelMetadata] = None
        self.scaler: Optional[ScalerParams] = None

    def load(self) -> None:
        """모델 로드"""
        if not TORCH_AVAILABLE:
            logger.warning("PyTorch not available. Using mock predictions.")
            return

        # 메타데이터 로드
        meta_path = self.model_path.with_suffix(".json")
        if meta_path.exists():
            self.metadata = ModelMetadata.from_json(meta_path)
            logger.info(
                f"Model metadata loaded: type={self.metadata.model_type}, "
                f"input_dim={self.metadata.input_dim}"
            )
        else:
            self.metadata = ModelMetadata()
            logger.warning(f"Model metadata not found: {meta_path}, using defaults")

        # 스케일러 로드
        scaler_path = self.model_path.parent / "scaler.json"
        if scaler_path.exists():
            self.scaler = ScalerParams.from_json(scaler_path)
            logger.info("Scaler parameters loaded")

        # 모델 아키텍처 생성
        from shared.ml.models import TradingCNNLSTM, TradingLSTM

        if self.metadata.model_type == "cnn-lstm":
            self.model = TradingCNNLSTM(
                input_dim=self.metadata.input_dim,
                hidden_dim=self.metadata.hidden_dim,
                num_layers=self.metadata.num_layers,
                num_classes=self.metadata.num_classes,
                dropout=self.metadata.dropout,
                cnn_channels=self.metadata.cnn_channels,
                kernel_size=self.metadata.kernel_size,
            )
            logger.info("Using CNN-LSTM model")
        else:
            self.model = TradingLSTM(
                input_dim=self.metadata.input_dim,
                hidden_dim=self.metadata.hidden_dim,
                num_layers=self.metadata.num_layers,
                num_classes=self.metadata.num_classes,
                dropout=self.metadata.dropout,
            )
            logger.info("Using LSTM model")

        # 가중치 로드
        if self.model_path.exists():
            state_dict = torch.load(
                self.model_path, map_location=self.device, weights_only=True
            )
            self.model.load_state_dict(state_dict)
            logger.info(f"Model weights loaded from {self.model_path}")
        else:
            logger.warning(
                f"Model file not found: {self.model_path}. Using random weights."
            )

        self.model.to(self.device)
        self.model.eval()
        logger.info(f"Model ready on {self.device}")

    def predict(self, sequence: np.ndarray) -> Optional[np.ndarray]:
        """추론 실행

        Args:
            sequence: (seq_len, features) 입력 시퀀스

        Returns:
            (3,) 확률 배열 [hold, up, down] 또는 None
        """
        if not TORCH_AVAILABLE or self.model is None:
            # Mock prediction
            return np.array([0.33, 0.34, 0.33])

        try:
            # 스케일러 적용
            if self.scaler is not None:
                sequence = self.scaler.transform(sequence)

            with torch.no_grad():
                x = torch.tensor(sequence, dtype=torch.float32)
                x = x.unsqueeze(0).to(self.device)  # (1, seq_len, features)

                output = self.model(x)
                probs = torch.softmax(output, dim=1).cpu().numpy()[0]

                return probs

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return None

    @property
    def is_loaded(self) -> bool:
        """모델 로드 여부"""
        return self.model is not None or not TORCH_AVAILABLE
