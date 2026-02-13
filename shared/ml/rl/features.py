"""RL 전용 피처 엔지니어링

기본 10개 피처 + RL 확장 15개 = 25개 기술적 피처 생성.
+ 시장 레짐 피처 3개 (KOSPI200 일간 지수에서 계산).

기본 10개: returns, ma_ratio_{5,10,20}, rsi, bb_position,
           volume_ratio, volatility, hl_range, candle_body
추가 15개: macd, macd_signal, macd_hist,
           sma_ratio_60, sma_ratio_120,
           ema_ratio_5, ema_ratio_10, ema_ratio_20,
           bb_upper_dist, bb_lower_dist, bb_width,
           atr, stoch_k, stoch_d, price_change_5
레짐 3개: regime_trend, regime_momentum, regime_volatility
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 기본 모델 입력 피처 컬럼 (순서 중요!)
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
    """기본 피처 계산기 (10개)

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

        df["returns"] = df["close"].pct_change()

        for window in [5, 10, 20]:
            ma = df["close"].rolling(window=window).mean()
            df[f"ma_ratio_{window}"] = df["close"] / ma

        df["rsi"] = self._calc_rsi(df["close"], self.rsi_period)

        bb_mid = df["close"].rolling(window=self.bb_period).mean()
        bb_std = df["close"].rolling(window=self.bb_period).std()
        bb_upper = bb_mid + self.bb_std * bb_std
        bb_lower = bb_mid - self.bb_std * bb_std
        df["bb_position"] = (df["close"] - bb_lower) / (bb_upper - bb_lower + 1e-10)

        volume_ma = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / (volume_ma + 1)

        df["volatility"] = df["returns"].rolling(window=self.volatility_period).std()
        df["hl_range"] = (df["high"] - df["low"]) / df["close"]
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
        """피처 배열 추출"""
        df_clean = df[FEATURE_COLUMNS].dropna()
        return df_clean.values

    def prepare_sequence(
        self, features: list[dict[str, Any]], seq_len: int = 60
    ) -> np.ndarray | None:
        """피처 리스트를 시퀀스로 변환"""
        valid_features = [f for f in features if "returns" in f]

        if len(valid_features) < seq_len:
            return None

        recent = valid_features[-seq_len:]
        sequence = []
        for f in recent:
            row = []
            for col in FEATURE_COLUMNS:
                val = f.get(col, 0)
                row.append(float(val) if val is not None else 0.0)
            sequence.append(row)

        return np.array(sequence)


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

# 시장 레짐 피처 (KOSPI200 일간 지수에서 계산)
REGIME_FEATURE_COLUMNS = ["regime_trend", "regime_momentum", "regime_volatility"]

# 레짐 포함 전체 피처 (25 + 3 = 28)
RL_FEATURE_COLUMNS_WITH_REGIME = RL_FEATURE_COLUMNS + REGIME_FEATURE_COLUMNS


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
        # 부모 FeatureCalculator.calculate()는 bb_position만 저장하고
        # bb_mid/bb_upper/bb_lower는 로컬 변수로 소멸 → 재계산 불가피
        bb_mid = df["close"].rolling(window=self.bb_period).mean()
        bb_std_val = df["close"].rolling(window=self.bb_period).std()
        bb_upper = bb_mid + self.bb_std * bb_std_val
        bb_lower = bb_mid - self.bb_std * bb_std_val

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


def load_daily_regime_features() -> pd.DataFrame:
    """ClickHouse에서 KOSPI200 일간 지수 로드 → 레짐 피처 계산

    레짐 피처 3개:
        - regime_trend: SMA(20)/SMA(60) - 1.0 (양수=bull, 음수=bear)
        - regime_momentum: 20일 수익률
        - regime_volatility: 20일 수익률 표준편차

    Returns:
        DataFrame[date, regime_trend, regime_momentum, regime_volatility]
    """
    import os

    from clickhouse_driver import Client

    client = Client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_NATIVE_PORT", "9000")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
    )
    rows = client.execute(
        "SELECT date, close FROM kospi.kospi200_index_daily ORDER BY date"
    )
    df = pd.DataFrame(rows, columns=["date", "close"])

    close = df["close"].astype(float)
    sma20 = close.rolling(20).mean()
    sma60 = close.rolling(60).mean()
    df["regime_trend"] = sma20 / (sma60 + 1e-10) - 1.0
    df["regime_momentum"] = close.pct_change(20)
    df["regime_volatility"] = close.pct_change().rolling(20).std()

    logger.info(
        f"Regime features loaded: {len(df)} rows, "
        f"date range {df['date'].min()} ~ {df['date'].max()}"
    )

    return df[["date"] + REGIME_FEATURE_COLUMNS].dropna()
