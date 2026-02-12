"""딥러닝 모델 정의

TradingLSTM, TradingCNNLSTM 모델 클래스.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# PyTorch optional import
try:
    import torch
    import torch.nn as nn

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None


if TORCH_AVAILABLE:

    class TradingLSTM(nn.Module):
        """LSTM 기반 가격 방향 예측 모델 (Attention 포함)

        Architecture:
            Input: (batch, seq_len, features)
            LSTM: 시계열 의존성 학습
            Attention: 중요 시점 가중치
            FC: 분류 헤드
            Output: (batch, num_classes) - [Hold, Up, Down]
        """

        def __init__(
            self,
            input_dim: int = 10,
            hidden_dim: int = 64,
            num_layers: int = 2,
            num_classes: int = 3,
            dropout: float = 0.2,
        ):
            super().__init__()

            self.lstm = nn.LSTM(
                input_dim,
                hidden_dim,
                num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0,
                bidirectional=False,
            )

            self.attention = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.Tanh(),
                nn.Linear(hidden_dim // 2, 1),
                nn.Softmax(dim=1),
            )

            self.fc = nn.Sequential(
                nn.Linear(hidden_dim, 32),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(32, num_classes),
            )

        def forward(self, x):
            # x: (batch, seq_len, features)
            lstm_out, _ = self.lstm(x)  # (batch, seq_len, hidden)

            # Attention
            attn_weights = self.attention(lstm_out)  # (batch, seq_len, 1)
            context = torch.sum(attn_weights * lstm_out, dim=1)  # (batch, hidden)

            # Classification
            logits = self.fc(context)
            return logits

    class TradingCNNLSTM(nn.Module):
        """CNN-LSTM 기반 가격 방향 예측 모델

        Architecture:
            Input: (batch, seq_len, features)
            CNN: 로컬 시계열 패턴 추출 (모멘텀, 단기 트렌드)
            LSTM: 장기 의존성 학습
            Attention: 중요 시점 가중치
            FC: 분류 헤드
            Output: (batch, num_classes) - [Hold, Up, Down]

        Hyperparameters:
            input_dim: 10 features
            hidden_dim: 64
            num_layers: 2
            cnn_channels: (32, 64)
            kernel_size: 3
            seq_len: 60 (1-minute bars)
        """

        def __init__(
            self,
            input_dim: int = 10,
            hidden_dim: int = 64,
            num_layers: int = 2,
            num_classes: int = 3,
            dropout: float = 0.2,
            cnn_channels: tuple[int, ...] = (32, 64),
            kernel_size: int = 3,
        ):
            super().__init__()

            self.input_dim = input_dim
            self.cnn_channels = cnn_channels
            self.kernel_size = kernel_size

            # CNN Block: 로컬 패턴 추출
            self.cnn = nn.Sequential(
                nn.Conv1d(
                    input_dim, cnn_channels[0], kernel_size=kernel_size, padding=1
                ),
                nn.BatchNorm1d(cnn_channels[0]),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Conv1d(
                    cnn_channels[0], cnn_channels[1], kernel_size=kernel_size, padding=1
                ),
                nn.BatchNorm1d(cnn_channels[1]),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.MaxPool1d(kernel_size=2, stride=2),
            )

            # LSTM
            self.lstm = nn.LSTM(
                cnn_channels[1],
                hidden_dim,
                num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0,
                bidirectional=False,
            )

            # Attention
            self.attention = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.Tanh(),
                nn.Linear(hidden_dim // 2, 1),
                nn.Softmax(dim=1),
            )

            # Classification head
            self.fc = nn.Sequential(
                nn.Linear(hidden_dim, 32),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(32, num_classes),
            )

        def forward(self, x):
            # x: (batch, seq_len, features)
            x = x.transpose(1, 2)  # (batch, features, seq_len)
            x = self.cnn(x)  # (batch, cnn_channels[1], seq_len // 2)
            x = x.transpose(1, 2)  # (batch, seq_len // 2, cnn_channels[1])

            lstm_out, _ = self.lstm(x)

            attn_weights = self.attention(lstm_out)
            context = torch.sum(attn_weights * lstm_out, dim=1)

            logits = self.fc(context)
            return logits

else:
    def _raise_torch_required() -> None:
        raise ImportError("PyTorch is required. Install with: pip install torch>=2.0")

    # Dummy classes when PyTorch not available
    class TradingLSTM:
        """Placeholder when PyTorch not available"""

        def __init__(self, *_args, **_kwargs):
            _raise_torch_required()

    class TradingCNNLSTM:
        """Placeholder when PyTorch not available"""

        def __init__(self, *_args, **_kwargs):
            _raise_torch_required()
