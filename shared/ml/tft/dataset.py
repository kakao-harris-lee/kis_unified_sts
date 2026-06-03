"""TFT 데이터셋: 슬라이딩 윈도우 시퀀스 + 다중 지평 수익률 타겟

일별 피처 배열 → lookback 윈도우 슬라이딩 → (x, y) 쌍 생성.
시간 피처 3개 (hour_norm, sin_progress, cos_progress) 자동 추가.

Usage:
    dataset = TFTDataset(days_features, days_prices, lookback=60, horizons=[1,5,15])
    x, y = dataset[0]  # x: (60, 28), y: (3,)
"""

from __future__ import annotations

import logging
import math

import numpy as np
import torch
from torch.utils.data import Dataset

logger = logging.getLogger(__name__)


def compute_time_features(n_bars: int, start_hour: float = 9.0) -> np.ndarray:
    """시간 피처 계산 (3개)

    1분봉 기준: 09:00 시작, 15:45 종료 (약 405바).

    Args:
        n_bars: 해당 일의 바 수

    Returns:
        (n_bars, 3) — [hour_norm, sin_progress, cos_progress]
    """
    features = np.zeros((n_bars, 3), dtype=np.float32)
    total_minutes = 6 * 60 + 45  # 09:00 ~ 15:45 = 405분

    for i in range(n_bars):
        minute_offset = i
        hour = start_hour + minute_offset / 60.0

        # progress: 0 (장 시작) ~ 1 (장 마감)
        progress = min(minute_offset / total_minutes, 1.0)

        features[i, 0] = (hour - 9.0) / 6.75       # hour_norm: 0~1
        features[i, 1] = math.sin(2 * math.pi * progress)
        features[i, 2] = math.cos(2 * math.pi * progress)

    return features


class TFTDataset(Dataset):
    """TFT 학습용 슬라이딩 윈도우 데이터셋

    각 샘플:
      x: (lookback, 28) — 25 market features + 3 time features
      y: (n_horizons,)  — 다중 지평 수익률 타겟
    """

    def __init__(
        self,
        days_features: list[np.ndarray],
        days_prices: list[np.ndarray],
        lookback: int = 60,
        horizons: list[int] | None = None,
        mode: str = "regression",
        classification_threshold: float = 0.0,
    ):
        """
        Args:
            days_features: 일별 피처 배열 리스트, 각 (n_bars, 25)
            days_prices: 일별 가격 배열 리스트, 각 (n_bars, 4) OHLC
            lookback: 과거 참조 윈도우 크기
            horizons: 예측 지평 리스트 (분)
            mode: "regression" (수익률) | "classification" (방향 0/1)
            classification_threshold: classification 모드에서 상승 판단 임계값
        """
        if horizons is None:
            horizons = [1, 5, 15]

        self.lookback = lookback
        self.horizons = horizons
        self.max_horizon = max(horizons)
        self.mode = mode
        self.classification_threshold = classification_threshold

        # 유효한 인덱스 사전 계산
        self._x_sequences: list[np.ndarray] = []
        self._y_targets: list[np.ndarray] = []

        n_skipped = 0
        for day_feat, day_prices in zip(days_features, days_prices):
            n_bars = len(day_feat)
            if n_bars < lookback + self.max_horizon:
                n_skipped += 1
                continue

            # 시간 피처 계산 + 결합
            time_feat = compute_time_features(n_bars)
            combined = np.concatenate([day_feat, time_feat], axis=1)  # (n_bars, 28)

            # close 가격 (column index 3)
            close = day_prices[:, 3].astype(np.float64)

            # 슬라이딩 윈도우
            for t in range(lookback, n_bars - self.max_horizon):
                x = combined[t - lookback : t]  # (lookback, 28)

                targets = np.zeros(len(horizons), dtype=np.float32)
                for h_idx, h in enumerate(horizons):
                    ret = (close[t + h] - close[t]) / close[t]
                    if mode == "classification":
                        targets[h_idx] = 1.0 if ret > classification_threshold else 0.0
                    else:
                        targets[h_idx] = float(ret)

                self._x_sequences.append(x.astype(np.float32))
                self._y_targets.append(targets)

        if n_skipped > 0:
            logger.warning(
                f"Skipped {n_skipped} days (< lookback + max_horizon = "
                f"{lookback + self.max_horizon} bars)"
            )

        logger.info(
            f"TFTDataset[{mode}]: {len(self._x_sequences)} samples from "
            f"{len(days_features) - n_skipped} days, "
            f"lookback={lookback}, horizons={horizons}"
        )

    def __len__(self) -> int:
        return len(self._x_sequences)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Returns:
            x: (lookback, total_input_dim) float32
            y: (n_horizons,) float32
        """
        x = torch.from_numpy(self._x_sequences[idx])
        y = torch.from_numpy(self._y_targets[idx])
        return x, y
