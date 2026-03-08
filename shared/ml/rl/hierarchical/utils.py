"""계층적 RL 공유 유틸리티

evaluator.py와 trainer.py에서 공통으로 사용하는 헬퍼 함수.
"""

from __future__ import annotations

import numpy as np


def downsample_1m_to_15m(
    day_data_1m: np.ndarray, bars_per_step: int = 15
) -> np.ndarray:
    """1분봉 -> 15분봉 다운샘플 (구간 평균)

    Args:
        day_data_1m: (n_bars, n_features) 1분봉 정규화 피처
        bars_per_step: 1 high-level step 당 1분봉 수 (기본 15)

    Returns:
        (n_bars_15m, n_features) 15분봉 피처
    """
    n_bars = len(day_data_1m)
    features_15m = []

    for start in range(0, n_bars, bars_per_step):
        end = min(start + bars_per_step, n_bars)
        segment = day_data_1m[start:end]
        features_15m.append(segment.mean(axis=0))

    return np.array(features_15m, dtype=np.float32)
