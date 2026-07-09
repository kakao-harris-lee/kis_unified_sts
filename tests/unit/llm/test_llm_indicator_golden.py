"""Golden pins: shared/llm hand-rolled indicator math (P1-b4).

Pins the exact numeric behavior of the LLM analyzers' inline RSI / MACD /
Bollinger / MA / momentum math BEFORE/AFTER delegation to
``shared.indicators.series``
(``docs/plans/2026-07-08-new-architecture-refactoring-plan.md`` §3, P1-b item 4):

* ``analyzers.StockTechnicalAnalyzer``   — SMA-RSI, MACD (``adjust=False``),
  Bollinger position, rolling MA
* ``analyzers.FuturesTechnicalAnalyzer`` — rolling MAs, SMA-RSI, MACD hist
  (legacy pandas-default ``adjust=True`` EWM)
* ``analyzers.StockBacktester``          — MA-crossover / RSI-reversal series
* ``market_analyzers.IndexAnalyzer._analyze_index``          — SMA-RSI + MAs
* ``market_analyzers.TechnicalAnalyzerForFutures.analyze``   — MAs, SMA-RSI,
  MACD hist (``adjust=True``)
* ``stock_screening.calc_momentum_metrics``                  — multi-horizon ROC

``_orig_*`` below are verbatim copies of the pre-refactor expressions.
Assertions are EXACT (``==``): the delegation must be bit-identical.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

import shared.llm.market_analyzers as market_analyzers_mod
from shared.llm.analyzers import FuturesTechnicalAnalyzer, StockBacktester, StockTechnicalAnalyzer
from shared.llm.market_analyzers import IndexAnalyzer, TechnicalAnalyzerForFutures
from shared.llm.stock_screening import calc_momentum_metrics

# ---------------------------------------------------------------------------
# Verbatim pre-refactor expressions (the golden reference)
# ---------------------------------------------------------------------------


def _orig_rsi_last(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0


def _orig_rsi_series(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _orig_macd_adjust_false(prices: pd.Series) -> tuple[float, float, float]:
    ema12 = prices.ewm(span=12, adjust=False).mean()
    ema26 = prices.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return (
        macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else 0,
        signal.iloc[-1] if not pd.isna(signal.iloc[-1]) else 0,
        hist.iloc[-1] if not pd.isna(hist.iloc[-1]) else 0,
    )


def _orig_macd_hist_adjust_true(close: pd.Series) -> float:
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    return float((macd - signal).iloc[-1])


def _orig_bollinger_position(prices: pd.Series, period: int = 20) -> float:
    ma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = ma + 2 * std
    lower = ma - 2 * std
    current = prices.iloc[-1]
    upper_val = upper.iloc[-1]
    lower_val = lower.iloc[-1]
    if pd.isna(upper_val) or pd.isna(lower_val) or upper_val == lower_val:
        return 0.5
    position = (current - lower_val) / (upper_val - lower_val)
    return max(0, min(1, position))


def _orig_ma_last(prices: pd.Series, period: int) -> float:
    ma = prices.rolling(window=period).mean()
    return ma.iloc[-1] if not pd.isna(ma.iloc[-1]) else prices.iloc[-1]


# ---------------------------------------------------------------------------
# Seeded inputs
# ---------------------------------------------------------------------------


def _prices(seed: int, n: int, flat: bool = False) -> pd.Series:
    if flat:
        return pd.Series([50_000.0] * n)
    rng = np.random.default_rng(seed)
    return pd.Series(50_000.0 + np.cumsum(rng.normal(0.0, 300.0, n)))


def _kr_ohlcv(seed: int, n: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 50_000.0 + np.cumsum(rng.normal(0.0, 300.0, n))
    spread = np.abs(rng.normal(0.0, 150.0, n))
    return pd.DataFrame(
        {
            "시가": close - rng.normal(0.0, 100.0, n),
            "고가": close + spread,
            "저가": close - spread,
            "종가": close,
            "거래량": rng.integers(100_000, 5_000_000, n).astype(float),
        }
    )


class TestStockTechnicalAnalyzerGolden:
    def test_rsi_bit_identical(self):
        for seed in range(15):
            for n in (5, 14, 15, 40, 120):
                prices = _prices(seed + 10, n)
                assert StockTechnicalAnalyzer.calculate_rsi(prices) == _orig_rsi_last(
                    prices
                )
        flat = _prices(0, 30, flat=True)  # 0/0 -> NaN -> 50.0 sentinel
        assert StockTechnicalAnalyzer.calculate_rsi(flat) == _orig_rsi_last(flat)

    def test_macd_bit_identical(self):
        for seed in range(15):
            for n in (1, 5, 40, 120):
                prices = _prices(seed + 30, n)
                assert StockTechnicalAnalyzer.calculate_macd(
                    prices
                ) == _orig_macd_adjust_false(prices)

    def test_bollinger_bit_identical(self):
        for seed in range(15):
            for n in (5, 19, 20, 21, 60):
                prices = _prices(seed + 50, n)
                assert StockTechnicalAnalyzer.calculate_bollinger(
                    prices
                ) == _orig_bollinger_position(prices)
        flat = _prices(0, 30, flat=True)  # upper == lower -> 0.5 sentinel
        assert StockTechnicalAnalyzer.calculate_bollinger(flat) == 0.5

    def test_ma_bit_identical(self):
        for seed in range(15):
            for n, period in ((3, 5), (5, 5), (40, 20), (80, 60)):
                prices = _prices(seed + 70, n)
                assert StockTechnicalAnalyzer.calculate_ma(
                    prices, period
                ) == _orig_ma_last(prices, period)

    def test_analyze_consumer_path(self):
        analyzer = StockTechnicalAnalyzer()
        df = _kr_ohlcv(seed=99, n=120)
        result = analyzer.analyze(df)
        prices = df["종가"]
        assert result.rsi == round(_orig_rsi_last(prices), 2)
        macd, signal, hist = _orig_macd_adjust_false(prices)
        assert result.macd == round(macd, 2)
        assert result.macd_signal == round(signal, 2)
        assert result.macd_hist == round(hist, 2)
        assert result.bb_position == round(_orig_bollinger_position(prices), 2)
        assert result.ma5 == round(_orig_ma_last(prices, 5), 0)
        assert result.ma20 == round(_orig_ma_last(prices, 20), 0)
        assert result.ma60 == round(_orig_ma_last(prices, 60), 0)


class TestFuturesTechnicalAnalyzerGolden:
    def _frame(self, seed: int, n: int) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        close = 350.0 + np.cumsum(rng.normal(0.0, 1.5, n))
        spread = np.abs(rng.normal(0.0, 0.8, n))
        return pd.DataFrame(
            {
                "open": close - rng.normal(0.0, 0.4, n),
                "high": close + spread,
                "low": close - spread,
                "close": close,
            }
        )

    def test_moving_averages_bit_identical(self):
        for seed in range(10):
            for n in (2, 10, 30, 61, 120):
                df = self._frame(seed + 200, n)
                index_price = float(df["close"].iloc[-1])
                got = FuturesTechnicalAnalyzer._compute_moving_averages(
                    df, index_price
                )
                ma5 = df["close"].rolling(5).mean().iloc[-1]
                ma20 = df["close"].rolling(20).mean().iloc[-1]
                ma60 = df["close"].rolling(60).mean().iloc[-1]
                want = (
                    float(ma5) if not pd.isna(ma5) else index_price,
                    float(ma20) if not pd.isna(ma20) else index_price,
                    float(ma60) if not pd.isna(ma60) else index_price,
                )
                assert got == want

    def test_rsi_bit_identical(self):
        for seed in range(10):
            for n in (5, 15, 40, 120):
                df = self._frame(seed + 300, n)
                want = _orig_rsi_series(df["close"], 14).iloc[-1]
                want = 50.0 if pd.isna(want) else float(want)
                assert FuturesTechnicalAnalyzer._compute_rsi(df) == want

    def test_macd_hist_bit_identical(self):
        for seed in range(10):
            for n in (2, 30, 120):
                df = self._frame(seed + 400, n)
                assert FuturesTechnicalAnalyzer._compute_macd_hist(
                    df
                ) == _orig_macd_hist_adjust_true(df["close"])


class TestStockBacktesterGolden:
    def _orig_backtest_ma_crossover(self, df, short=5, long=20):
        bt = StockBacktester()
        df = df.copy()
        df["ma_short"] = df["종가"].rolling(short).mean()
        df["ma_long"] = df["종가"].rolling(long).mean()
        trades = []
        position = 0
        entry_price = 0
        for i in range(long, len(df)):
            prev = df.iloc[i - 1]
            curr = df.iloc[i]
            if position == 0:
                if (
                    prev["ma_short"] <= prev["ma_long"]
                    and curr["ma_short"] > curr["ma_long"]
                ):
                    entry_price = curr["종가"]
                    position = 1
            elif position > 0:
                if (
                    prev["ma_short"] >= prev["ma_long"]
                    and curr["ma_short"] < curr["ma_long"]
                ):
                    exit_price = curr["종가"]
                    pnl = (exit_price - entry_price) / entry_price * 100
                    trades.append(pnl)
                    position = 0
        if position > 0:
            pnl = (df.iloc[-1]["종가"] - entry_price) / entry_price * 100
            trades.append(pnl)
        return bt._calculate_metrics(f"이평크로스({short}/{long})", trades)

    def _orig_backtest_rsi_reversal(self, df):
        bt = StockBacktester()
        df = df.copy()
        delta = df["종가"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
        trades = []
        position = 0
        entry_price = 0
        for i in range(15, len(df)):
            prev = df.iloc[i - 1]
            curr = df.iloc[i]
            if position == 0:
                if prev["rsi"] < 30 and curr["rsi"] >= 30:
                    entry_price = curr["종가"]
                    position = 1
            elif position > 0 and curr["rsi"] >= 70:
                pnl = (curr["종가"] - entry_price) / entry_price * 100
                trades.append(pnl)
                position = 0
        if position > 0:
            pnl = (df.iloc[-1]["종가"] - entry_price) / entry_price * 100
            trades.append(pnl)
        return bt._calculate_metrics("RSI역추세", trades)

    def test_ma_crossover_bit_identical(self):
        bt = StockBacktester()
        for seed in (7, 21, 42):
            df = _kr_ohlcv(seed=seed, n=200)
            for short, long in ((5, 20), (10, 30)):
                assert bt.backtest_ma_crossover(
                    df, short, long
                ) == self._orig_backtest_ma_crossover(df, short, long)

    def test_rsi_reversal_bit_identical(self):
        bt = StockBacktester()
        for seed in (7, 21, 42):
            df = _kr_ohlcv(seed=seed, n=200)
            assert bt.backtest_rsi_reversal(df) == self._orig_backtest_rsi_reversal(df)


class TestIndexAnalyzerGolden:
    def test_analyze_index_bit_identical(self, monkeypatch):
        rng = np.random.default_rng(777)
        n = 60
        close = 2600.0 + np.cumsum(rng.normal(0.0, 15.0, n))
        volume = rng.integers(300_000, 900_000, n).astype(float)
        df = pd.DataFrame({"Close": close, "Volume": volume})

        class _FakeFdr:
            @staticmethod
            def DataReader(code, start, end):  # noqa: N802 (external API name)
                return df

        monkeypatch.setattr(market_analyzers_mod, "fdr", _FakeFdr, raising=False)
        monkeypatch.setattr(market_analyzers_mod, "FDR_AVAILABLE", True)

        analyzer = object.__new__(IndexAnalyzer)
        analyzer.start_date = datetime(2026, 5, 1)
        analyzer.end_date = datetime(2026, 7, 1)
        got = analyzer._analyze_index("KOSPI", "KS11")
        assert got is not None

        rsi = _orig_rsi_series(df["Close"], 14).iloc[-1]
        ma5 = df["Close"].rolling(5).mean().iloc[-1]
        ma20 = df["Close"].rolling(20).mean().iloc[-1]
        price = df["Close"].iloc[-1]
        assert got.rsi == round(rsi, 0)
        if price > ma5 > ma20:
            want_trend = "상승"
        elif price < ma5 < ma20:
            want_trend = "하락"
        else:
            want_trend = "횡보"
        assert got.trend == want_trend
        assert got.price == round(price, 2)
        assert got.volume_ratio == round(
            df["Volume"].tail(5).mean() / df["Volume"].tail(20).mean(), 2
        )


class TestTechnicalAnalyzerForFuturesGolden:
    def test_analyze_bit_identical(self, monkeypatch):
        fixed = datetime(2026, 7, 8, 10, 30, 0)

        class _FakeDatetime:
            @staticmethod
            def now():
                return fixed

        monkeypatch.setattr(market_analyzers_mod, "datetime", _FakeDatetime)

        analyzer = object.__new__(TechnicalAnalyzerForFutures)
        got = analyzer.analyze()

        # Replay the module's seeded sample-data generation verbatim.
        np.random.seed(int(fixed.timestamp()) % 1000 + 5)
        days = 120
        base_price = 350
        returns = np.random.normal(0.0005, 0.012, days)
        prices = base_price * np.exp(np.cumsum(returns))
        df = pd.DataFrame(
            {
                "close": prices,
                "high": prices * (1 + np.random.uniform(0, 0.015, days)),
                "low": prices * (1 - np.random.uniform(0, 0.015, days)),
            }
        )
        ma5 = df["close"].rolling(5).mean().iloc[-1]
        ma20 = df["close"].rolling(20).mean().iloc[-1]
        ma60 = df["close"].rolling(60).mean().iloc[-1]
        rsi = _orig_rsi_series(df["close"], 14).iloc[-1]
        macd_hist = _orig_macd_hist_adjust_true(df["close"])

        assert got["ma5"] == round(ma5, 2)
        assert got["ma20"] == round(ma20, 2)
        assert got["ma60"] == round(ma60, 2)
        assert got["rsi"] == round(rsi, 0)
        assert got["macd_hist"] == round(macd_hist, 4)


class TestCalcMomentumMetricsGolden:
    def _orig(self, close: pd.Series, lookback: int) -> dict[str, float]:
        metrics: dict[str, float] = {}
        if close is None or len(close) < 2:
            return metrics

        def _ret(days: int) -> float:
            if len(close) <= days:
                return 0.0
            prev = float(close.iloc[-days - 1])
            cur = float(close.iloc[-1])
            return ((cur / prev) - 1.0) * 100 if prev else 0.0

        metrics["ret_5d"] = _ret(5)
        metrics["ret_20d"] = _ret(20)
        metrics["ret_60d"] = _ret(60)
        window = close.tail(min(len(close), lookback))
        high = float(window.max()) if len(window) else 0.0
        metrics["high_lookback"] = high
        metrics["high_proximity"] = float(close.iloc[-1] / high) if high else 0.0
        return metrics

    def test_seeded_series_bit_identical(self):
        for seed in range(20):
            rng = np.random.default_rng(seed + 880)
            n = int(rng.integers(1, 130))
            close = pd.Series(30_000.0 + np.cumsum(rng.normal(0.0, 200.0, n)))
            for lookback in (10, 52, 260):
                assert calc_momentum_metrics(close, lookback) == self._orig(
                    close, lookback
                )

    def test_zero_base_and_short(self):
        # len 6, leading 0 -> ret_5d hits the zero-base guard (prev == 0 -> 0.0)
        close = pd.Series([0.0, 110.0, 120.0, 130.0, 140.0, 150.0])
        assert calc_momentum_metrics(close, 60) == self._orig(close, 60)
        one = pd.Series([100.0])
        assert calc_momentum_metrics(one, 60) == self._orig(one, 60) == {}
