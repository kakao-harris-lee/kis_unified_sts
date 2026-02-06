"""RL 전용 피처 엔지니어링

기존 FeatureCalculator (10개)를 확장하여 RL용 25개 피처 생성.

기존 10개: returns, ma_ratio_{5,10,20}, rsi, bb_position,
           volume_ratio, volatility, hl_range, candle_body
추가 15개: macd, macd_signal, macd_hist,
           sma_ratio_60, sma_ratio_120,
           ema_ratio_5, ema_ratio_10, ema_ratio_20,
           bb_upper_dist, bb_lower_dist, bb_width,
           atr, stoch_k, stoch_d, price_change_5
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from domains.futures.prediction.features import FEATURE_COLUMNS, FeatureCalculator

logger = logging.getLogger(__name__)

# RL 전용 추가 피처 컬럼
RL_EXTRA_COLUMNS = [
    "macd",
    "macd_signal",
    "macd_hist",
    "sma_ratio_60",
    "sma_ratio_120",
    "ema_ratio_5",
    "ema_ratio_10",
    "ema_ratio_20",
    "bb_upper_dist",
    "bb_lower_dist",
    "bb_width",
    "atr",
    "stoch_k",
    "stoch_d",
    "price_change_5",
]

# 전체 RL 피처 컬럼 (기존 10 + 추가 15 = 25)
RL_FEATURE_COLUMNS = FEATURE_COLUMNS + RL_EXTRA_COLUMNS


class RLFeatureCalculator(FeatureCalculator):
    """RL용 확장 피처 계산기 (25개)

    기존 FeatureCalculator를 상속하여 10개 피처에 15개 추가.
    모든 파라미터는 config에서 로드.

    Usage:
        calc = RLFeatureCalculator()
        df = calc.calculate(ohlcv_df)
        features = calc.extract_rl_features(df)
    """

    def __init__(
        self,
        rsi_period: int = 14,
        bb_period: int = 20,
        bb_std: float = 2.0,
        volatility_period: int = 20,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        atr_period: int = 14,
        stoch_period: int = 14,
        stoch_smooth: int = 3,
    ):
        super().__init__(
            rsi_period=rsi_period,
            bb_period=bb_period,
            bb_std=bb_std,
            volatility_period=volatility_period,
        )
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal_period = macd_signal
        self.atr_period = atr_period
        self.stoch_period = stoch_period
        self.stoch_smooth = stoch_smooth

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """기존 10개 + 추가 15개 피처 계산

        Args:
            df: OHLCV DataFrame (datetime, open, high, low, close, volume)

        Returns:
            25개 피처가 추가된 DataFrame
        """
        # 기존 10개 피처 계산
        df = super().calculate(df)

        # === MACD (3개) ===
        ema_fast = df["close"].ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=self.macd_slow, adjust=False).mean()
        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = (
            df["macd"].ewm(span=self.macd_signal_period, adjust=False).mean()
        )
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # === SMA 비율 (2개) ===
        for window in [60, 120]:
            sma = df["close"].rolling(window=window).mean()
            df[f"sma_ratio_{window}"] = df["close"] / (sma + 1e-10)

        # === EMA 비율 (3개) ===
        for window in [5, 10, 20]:
            ema = df["close"].ewm(span=window, adjust=False).mean()
            df[f"ema_ratio_{window}"] = df["close"] / (ema + 1e-10)

        # === 볼린저 밴드 확장 (3개) ===
        bb_mid = df["close"].rolling(window=self.bb_period).mean()
        bb_std = df["close"].rolling(window=self.bb_period).std()
        bb_upper = bb_mid + self.bb_std * bb_std
        bb_lower = bb_mid - self.bb_std * bb_std

        # 상단/하단 거리 (정규화)
        df["bb_upper_dist"] = (bb_upper - df["close"]) / (df["close"] + 1e-10)
        df["bb_lower_dist"] = (df["close"] - bb_lower) / (df["close"] + 1e-10)
        df["bb_width"] = (bb_upper - bb_lower) / (bb_mid + 1e-10)

        # === ATR (1개) ===
        df["atr"] = self._calc_atr(df, self.atr_period)

        # === Stochastic (2개) ===
        df["stoch_k"], df["stoch_d"] = self._calc_stochastic(
            df, self.stoch_period, self.stoch_smooth
        )

        # === 가격 변화율 5분 (1개) ===
        df["price_change_5"] = df["close"].pct_change(periods=5)

        return df

    def _calc_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """ATR (Average True Range) 계산"""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        # 가격 대비 정규화
        return atr / (close + 1e-10)

    def _calc_stochastic(
        self, df: pd.DataFrame, period: int, smooth: int
    ) -> tuple[pd.Series, pd.Series]:
        """Stochastic Oscillator 계산"""
        low_min = df["low"].rolling(window=period).min()
        high_max = df["high"].rolling(window=period).max()

        stoch_k = 100 * (df["close"] - low_min) / (high_max - low_min + 1e-10)
        stoch_d = stoch_k.rolling(window=smooth).mean()

        return stoch_k, stoch_d

    def extract_rl_features(self, df: pd.DataFrame) -> np.ndarray:
        """RL용 25개 피처 배열 추출

        Args:
            df: calculate()로 피처가 계산된 DataFrame

        Returns:
            (n_rows, 25) 배열
        """
        df_clean = df[RL_FEATURE_COLUMNS].dropna()
        return df_clean.values

    def get_feature_names(self) -> list[str]:
        """피처 이름 목록 반환"""
        return RL_FEATURE_COLUMNS.copy()
