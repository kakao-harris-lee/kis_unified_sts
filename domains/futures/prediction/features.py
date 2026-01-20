"""Feature Calculator

선물 CNN-LSTM 모델용 피처 계산.

10개 피처:
    - returns: 1-bar 가격 변화율
    - ma_ratio_5, ma_ratio_10, ma_ratio_20: 이동평균 대비 비율
    - rsi: RSI(14)
    - bb_position: 볼린저 밴드 내 위치 (0-1)
    - volume_ratio: 거래량 / MA(20)
    - volatility: 수익률 롤링 표준편차
    - hl_range: (고가-저가) / 종가
    - candle_body: (종가-시가) / (고가-저가)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 모델 입력 피처 컬럼 (순서 중요!)
FEATURE_COLUMNS = [
    "returns",
    "ma_ratio_5",
    "ma_ratio_10",
    "ma_ratio_20",
    "rsi",
    "bb_position",
    "volume_ratio",
    "volatility",
    "hl_range",
    "candle_body",
]


class FeatureCalculator:
    """피처 계산기

    OHLCV 데이터로부터 기술적 지표 계산.

    Usage:
        calc = FeatureCalculator()
        df = calc.calculate(ohlcv_df)
    """

    def __init__(
        self,
        rsi_period: int = 14,
        bb_period: int = 20,
        bb_std: float = 2.0,
        volatility_period: int = 20,
    ):
        """
        Args:
            rsi_period: RSI 기간
            bb_period: 볼린저 밴드 기간
            bb_std: 볼린저 밴드 표준편차 배수
            volatility_period: 변동성 계산 기간
        """
        self.rsi_period = rsi_period
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.volatility_period = volatility_period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """피처 계산

        Args:
            df: OHLCV DataFrame (datetime, open, high, low, close, volume)

        Returns:
            피처가 추가된 DataFrame
        """
        df = df.copy()
        df = df.sort_values("datetime").reset_index(drop=True)

        # 1. 가격 변화율
        df["returns"] = df["close"].pct_change()

        # 2. 이동평균 비율
        for window in [5, 10, 20]:
            ma = df["close"].rolling(window=window).mean()
            df[f"ma_ratio_{window}"] = df["close"] / ma

        # 3. RSI
        df["rsi"] = self._calc_rsi(df["close"], self.rsi_period)

        # 4. 볼린저 밴드 위치
        bb_mid = df["close"].rolling(window=self.bb_period).mean()
        bb_std = df["close"].rolling(window=self.bb_period).std()
        bb_upper = bb_mid + self.bb_std * bb_std
        bb_lower = bb_mid - self.bb_std * bb_std
        df["bb_position"] = (df["close"] - bb_lower) / (bb_upper - bb_lower + 1e-10)

        # 5. 거래량 비율
        volume_ma = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / (volume_ma + 1)

        # 6. 변동성
        df["volatility"] = df["returns"].rolling(window=self.volatility_period).std()

        # 7. 고가-저가 범위
        df["hl_range"] = (df["high"] - df["low"]) / df["close"]

        # 8. 캔들 바디
        df["candle_body"] = (df["close"] - df["open"]) / (
            df["high"] - df["low"] + 1e-10
        )

        return df

    def _calc_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-10)
        return 100 - (100 / (1 + rs))

    def extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """피처 배열 추출

        Args:
            df: 피처가 계산된 DataFrame

        Returns:
            (n_rows, n_features) 배열
        """
        # NaN 제거
        df_clean = df[FEATURE_COLUMNS].dropna()
        return df_clean.values

    def prepare_sequence(
        self, features: list[dict[str, Any]], seq_len: int = 60
    ) -> np.ndarray | None:
        """피처 리스트를 시퀀스로 변환

        Args:
            features: 피처 딕셔너리 리스트
            seq_len: 시퀀스 길이

        Returns:
            (seq_len, n_features) 배열 또는 None
        """
        # 기술적 지표가 포함된 피처만 필터링
        valid_features = [f for f in features if "returns" in f]

        if len(valid_features) < seq_len:
            logger.debug(
                f"Insufficient features: {len(valid_features)} < {seq_len}"
            )
            return None

        # 최근 seq_len개만 사용
        recent = valid_features[-seq_len:]

        # numpy 배열로 변환
        sequence = []
        for f in recent:
            row = []
            for col in FEATURE_COLUMNS:
                val = f.get(col, 0)
                row.append(float(val) if val is not None else 0.0)
            sequence.append(row)

        return np.array(sequence)
