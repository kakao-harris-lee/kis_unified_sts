"""
Technical Analyzers and Backtesters

Stock and Futures technical analysis, backtesting engines.
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .data_classes import (
    BacktestResult,
    MarketBias,
    Signal,
    TechnicalAnalysis,
)

logger = logging.getLogger(__name__)


# ============================================================
# Stock Technical Analyzer
# ============================================================


class StockTechnicalAnalyzer:
    """주식 기술적 분석"""

    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0

    @staticmethod
    def calculate_macd(prices: pd.Series) -> Tuple[float, float, float]:
        """MACD 계산"""
        ema12 = prices.ewm(span=12, adjust=False).mean()
        ema26 = prices.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        return (
            macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else 0,
            signal.iloc[-1] if not pd.isna(signal.iloc[-1]) else 0,
            hist.iloc[-1] if not pd.isna(hist.iloc[-1]) else 0
        )

    @staticmethod
    def calculate_bollinger(prices: pd.Series, period: int = 20) -> float:
        """볼린저 밴드 위치 계산 (0~1)"""
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

    @staticmethod
    def calculate_ma(prices: pd.Series, period: int) -> float:
        """이동평균 계산"""
        ma = prices.rolling(window=period).mean()
        return ma.iloc[-1] if not pd.isna(ma.iloc[-1]) else prices.iloc[-1]

    def analyze(self, df: pd.DataFrame) -> TechnicalAnalysis:
        """종합 기술적 분석"""
        prices = df['종가']

        rsi = self.calculate_rsi(prices)
        macd, macd_signal, macd_hist = self.calculate_macd(prices)
        bb_position = self.calculate_bollinger(prices)
        ma5 = self.calculate_ma(prices, 5)
        ma20 = self.calculate_ma(prices, 20)
        ma60 = self.calculate_ma(prices, 60) if len(prices) >= 60 else ma20

        # 추세 판단
        if ma5 > ma20 * 1.02:
            trend = "상승"
        elif ma5 < ma20 * 0.98:
            trend = "하락"
        else:
            trend = "횡보"

        # 신호 결정
        signal = self._determine_signal(rsi, macd_hist, bb_position, trend, prices.iloc[-1], ma5, ma20)

        return TechnicalAnalysis(
            rsi=round(rsi, 2),
            macd=round(macd, 2),
            macd_signal=round(macd_signal, 2),
            macd_hist=round(macd_hist, 2),
            bb_position=round(bb_position, 2),
            ma5=round(ma5, 0),
            ma20=round(ma20, 0),
            ma60=round(ma60, 0),
            trend=trend,
            signal=signal
        )

    def _determine_signal(self, rsi, macd_hist, bb_pos, trend, price, ma5, ma20) -> Signal:
        """매매 신호 결정"""
        score = 0

        # RSI
        if rsi < 30:
            score += 2
        elif rsi < 40:
            score += 1
        elif rsi > 70:
            score -= 2
        elif rsi > 60:
            score -= 1

        # MACD
        if macd_hist > 0:
            score += 1
        else:
            score -= 1

        # 볼린저 밴드
        if bb_pos < 0.2:
            score += 1
        elif bb_pos > 0.8:
            score -= 1

        # 추세
        if trend == "상승":
            score += 1
        elif trend == "하락":
            score -= 1

        # 이동평균
        if price > ma5 > ma20:
            score += 1
        elif price < ma5 < ma20:
            score -= 1

        # 최종 신호 결정
        if score >= 4:
            return Signal.STRONG_BUY
        elif score >= 2:
            return Signal.BUY
        elif score <= -4:
            return Signal.STRONG_SELL
        elif score <= -2:
            return Signal.SELL
        else:
            return Signal.HOLD


class FuturesTechnicalAnalyzer:
    """선물 기술적 분석"""

    def analyze(self) -> Dict:
        """선물 기술적 분석 (샘플 데이터 기반)"""
        np.random.seed(int(pd.Timestamp.now().timestamp()) % 1000 + 2)

        days = 120
        base_price = 350
        returns = np.random.normal(0.0005, 0.012, days)
        prices = base_price * np.exp(np.cumsum(returns))

        df = pd.DataFrame({
            'close': prices,
            'high': prices * (1 + np.random.uniform(0, 0.015, days)),
            'low': prices * (1 - np.random.uniform(0, 0.015, days)),
        })

        index_price = df['close'].iloc[-1]
        index_change = (df['close'].iloc[-1] / df['close'].iloc[-2] - 1) * 100

        ma5 = df['close'].rolling(5).mean().iloc[-1]
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        ma60 = df['close'].rolling(60).mean().iloc[-1]

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        # MACD
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        macd_hist = (macd - signal).iloc[-1]

        # 피벗 포인트
        pivot = (df['high'].iloc[-1] + df['low'].iloc[-1] + df['close'].iloc[-1]) / 3
        r1 = 2 * pivot - df['low'].iloc[-1]
        s1 = 2 * pivot - df['high'].iloc[-1]

        # 추세 판단
        trend_short = "상승" if index_price > ma5 else "하락"
        trend_mid = "상승" if ma5 > ma20 else "하락"
        trend_long = "상승" if ma20 > ma60 else "하락"

        # 점수 계산
        score = 0
        if trend_short == "상승":
            score += 10
        else:
            score -= 10
        if trend_mid == "상승":
            score += 15
        else:
            score -= 15
        if trend_long == "상승":
            score += 15
        else:
            score -= 15

        if rsi < 30:
            score += 15
        elif rsi < 40:
            score += 5
        elif rsi > 70:
            score -= 15
        elif rsi > 60:
            score -= 5

        if macd_hist > 0:
            score += 10
        else:
            score -= 10

        score = max(-100, min(100, score * 1.2))

        # 바이어스 결정
        if score >= 30:
            bias = MarketBias.STRONG_BULLISH
        elif score >= 10:
            bias = MarketBias.BULLISH
        elif score <= -30:
            bias = MarketBias.STRONG_BEARISH
        elif score <= -10:
            bias = MarketBias.BEARISH
        else:
            bias = MarketBias.NEUTRAL

        return {
            "index_price": round(index_price, 2),
            "index_change": round(index_change, 2),
            "ma5": round(ma5, 2),
            "ma20": round(ma20, 2),
            "ma60": round(ma60, 2),
            "rsi": round(rsi, 0),
            "macd_hist": round(macd_hist, 4),
            "pivot": round(pivot, 2),
            "resistance_1": round(r1, 2),
            "support_1": round(s1, 2),
            "trend_short": trend_short,
            "trend_mid": trend_mid,
            "trend_long": trend_long,
            "score": round(score, 0),
            "bias": bias.value
        }


# ============================================================
# Stock Backtester
# ============================================================


class StockBacktester:
    """주식 백테스팅"""

    def __init__(self, initial_capital: float = 10_000_000):
        self.initial_capital = initial_capital

    def backtest_volatility_breakout(self, df: pd.DataFrame, k: float = 0.5) -> BacktestResult:
        """변동성 돌파 전략"""
        trades = []

        for i in range(1, len(df)):
            prev = df.iloc[i-1]
            curr = df.iloc[i]

            prev_range = prev['고가'] - prev['저가']
            target = curr['시가'] + prev_range * k

            if curr['고가'] >= target:
                entry_price = target
                exit_price = curr['종가']
                pnl = (exit_price - entry_price) / entry_price * 100
                trades.append(pnl)

        return self._calculate_metrics(f"변동성돌파(K={k})", trades)

    def backtest_ma_crossover(self, df: pd.DataFrame, short: int = 5, long: int = 20) -> BacktestResult:
        """이동평균 크로스오버"""
        df = df.copy()
        df['ma_short'] = df['종가'].rolling(short).mean()
        df['ma_long'] = df['종가'].rolling(long).mean()

        trades = []
        position = 0
        entry_price = 0

        for i in range(long, len(df)):
            prev = df.iloc[i-1]
            curr = df.iloc[i]

            if position == 0:
                if prev['ma_short'] <= prev['ma_long'] and curr['ma_short'] > curr['ma_long']:
                    entry_price = curr['종가']
                    position = 1
            elif position > 0:
                if prev['ma_short'] >= prev['ma_long'] and curr['ma_short'] < curr['ma_long']:
                    exit_price = curr['종가']
                    pnl = (exit_price - entry_price) / entry_price * 100
                    trades.append(pnl)
                    position = 0

        if position > 0:
            pnl = (df.iloc[-1]['종가'] - entry_price) / entry_price * 100
            trades.append(pnl)

        return self._calculate_metrics(f"이평크로스({short}/{long})", trades)

    def backtest_rsi_reversal(self, df: pd.DataFrame) -> BacktestResult:
        """RSI 역추세 전략"""
        df = df.copy()

        delta = df['종가'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        trades = []
        position = 0
        entry_price = 0

        for i in range(15, len(df)):
            prev = df.iloc[i-1]
            curr = df.iloc[i]

            if position == 0:
                if prev['rsi'] < 30 and curr['rsi'] >= 30:
                    entry_price = curr['종가']
                    position = 1
            elif position > 0:
                if curr['rsi'] >= 70:
                    pnl = (curr['종가'] - entry_price) / entry_price * 100
                    trades.append(pnl)
                    position = 0

        if position > 0:
            pnl = (df.iloc[-1]['종가'] - entry_price) / entry_price * 100
            trades.append(pnl)

        return self._calculate_metrics("RSI역추세", trades)

    def run_all_strategies(self, df: pd.DataFrame) -> List[BacktestResult]:
        """모든 전략 백테스트"""
        results = []

        for k in [0.4, 0.5, 0.6]:
            results.append(self.backtest_volatility_breakout(df, k))

        results.append(self.backtest_ma_crossover(df, 5, 20))
        results.append(self.backtest_ma_crossover(df, 10, 30))
        results.append(self.backtest_rsi_reversal(df))

        return results

    def _calculate_metrics(self, strategy_name: str, trades: List[float]) -> BacktestResult:
        """백테스트 메트릭 계산"""
        if len(trades) == 0:
            return BacktestResult(strategy_name, 0, 0, 0, 0, 0, 0, 0)

        trades = np.array(trades)
        wins = trades[trades > 0]
        losses = trades[trades <= 0]

        total_return = np.sum(trades)
        win_rate = len(wins) / len(trades) * 100 if len(trades) > 0 else 0
        avg_profit = np.mean(wins) if len(wins) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0

        cumulative = np.cumsum(trades)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0

        sharpe_ratio = np.mean(trades) / np.std(trades) * np.sqrt(252) if len(trades) > 1 and np.std(trades) > 0 else 0

        return BacktestResult(
            strategy_name=strategy_name,
            total_return=round(total_return, 2),
            win_rate=round(win_rate, 1),
            max_drawdown=round(max_drawdown, 2),
            sharpe_ratio=round(sharpe_ratio, 2),
            trade_count=len(trades),
            avg_profit=round(avg_profit, 2),
            avg_loss=round(avg_loss, 2)
        )


# ============================================================
# News Analyzer
# ============================================================


class StockNewsAnalyzer:
    """주식 뉴스 분석"""

    def __init__(self):
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def analyze(self, code: str, name: str) -> Dict:
        """뉴스 분석"""
        return {
            "sentiment": "중립",
            "key_events": [],
            "news_count": 0,
            "implications": "특이사항 없음"
        }
