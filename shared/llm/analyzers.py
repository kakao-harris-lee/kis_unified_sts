"""
Technical Analyzers and Backtesters

Stock and Futures technical analysis, backtesting engines.
"""
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

from shared.calendar import MarketCalendar
from shared.collector.historical.futures import KIS_SHORT_CODES, KOSPI200F_FRONT_CODE
from shared.config.secrets import SecretsManager
from shared.kis.auth import KISAuthConfig, KISAuthManager

from .config import LLMConfig
from .data_classes import (
    BacktestResult,
    MarketBias,
    Signal,
    TechnicalAnalysis,
)
from .errors import DataUnavailableError
from .krx_api_client import KRXOpenAPIClient

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
        prices = df["종가"]
        indicators = self._compute_indicators(prices)
        trend = self._compute_trend(indicators.ma5, indicators.ma20)
        signal = self._determine_signal(
            indicators.rsi,
            indicators.macd_hist,
            indicators.bb_position,
            trend,
            indicators.last_price,
            indicators.ma5,
            indicators.ma20,
        )

        return self._build_analysis(indicators, trend, signal)

    @dataclass
    class _IndicatorSet:
        rsi: float
        macd: float
        macd_signal: float
        macd_hist: float
        bb_position: float
        ma5: float
        ma20: float
        ma60: float
        last_price: float

    def _compute_indicators(self, prices: pd.Series) -> "StockTechnicalAnalyzer._IndicatorSet":
        rsi = self.calculate_rsi(prices)
        macd, macd_signal, macd_hist = self.calculate_macd(prices)
        bb_position = self.calculate_bollinger(prices)
        ma5 = self.calculate_ma(prices, 5)
        ma20 = self.calculate_ma(prices, 20)
        ma60 = self.calculate_ma(prices, 60) if len(prices) >= 60 else ma20
        return StockTechnicalAnalyzer._IndicatorSet(
            rsi=rsi,
            macd=macd,
            macd_signal=macd_signal,
            macd_hist=macd_hist,
            bb_position=bb_position,
            ma5=ma5,
            ma20=ma20,
            ma60=ma60,
            last_price=float(prices.iloc[-1]),
        )

    @staticmethod
    def _compute_trend(ma5: float, ma20: float) -> str:
        if ma5 > ma20 * 1.02:
            return "상승"
        if ma5 < ma20 * 0.98:
            return "하락"
        return "횡보"

    @staticmethod
    def _build_analysis(
        indicators: "StockTechnicalAnalyzer._IndicatorSet",
        trend: str,
        signal: Signal,
    ) -> TechnicalAnalysis:
        return TechnicalAnalysis(
            rsi=round(indicators.rsi, 2),
            macd=round(indicators.macd, 2),
            macd_signal=round(indicators.macd_signal, 2),
            macd_hist=round(indicators.macd_hist, 2),
            bb_position=round(indicators.bb_position, 2),
            ma5=round(indicators.ma5, 0),
            ma20=round(indicators.ma20, 0),
            ma60=round(indicators.ma60, 0),
            trend=trend,
            signal=signal,
        )

    def _determine_signal(self, rsi, macd_hist, bb_pos, trend, price, ma5, ma20) -> Signal:
        """매매 신호 결정"""
        score = 0
        score += self._score_rsi(rsi)
        score += self._score_macd(macd_hist)
        score += self._score_bollinger(bb_pos)
        score += self._score_trend(trend)
        score += self._score_moving_average(price, ma5, ma20)
        return self._signal_from_score(score)

    @staticmethod
    def _score_rsi(rsi: float) -> int:
        if rsi < 30:
            return 2
        if rsi < 40:
            return 1
        if rsi > 70:
            return -2
        if rsi > 60:
            return -1
        return 0

    @staticmethod
    def _score_macd(macd_hist: float) -> int:
        return 1 if macd_hist > 0 else -1

    @staticmethod
    def _score_bollinger(bb_pos: float) -> int:
        if bb_pos < 0.2:
            return 1
        if bb_pos > 0.8:
            return -1
        return 0

    @staticmethod
    def _score_trend(trend: str) -> int:
        if trend == "상승":
            return 1
        if trend == "하락":
            return -1
        return 0

    @staticmethod
    def _score_moving_average(price: float, ma5: float, ma20: float) -> int:
        if price > ma5 > ma20:
            return 1
        if price < ma5 < ma20:
            return -1
        return 0

    @staticmethod
    def _signal_from_score(score: int) -> Signal:
        if score >= 4:
            return Signal.STRONG_BUY
        if score >= 2:
            return Signal.BUY
        if score <= -4:
            return Signal.STRONG_SELL
        if score <= -2:
            return Signal.SELL
        return Signal.HOLD


class FuturesTechnicalAnalyzer:
    """선물 기술적 분석"""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig.from_env()
        self._calendar = MarketCalendar()
        self._krx_client = KRXOpenAPIClient(self.config)

    def analyze(self) -> Dict:
        """선물 기술적 분석 (실제 데이터 우선, 실패 시 샘플)"""
        df = self._build_price_frame()
        if df is None or len(df) < 2:
            raise DataUnavailableError("futures_technical", "price_data_unavailable")

        index_price, index_change = self._compute_index_metrics(df)
        ma5, ma20, ma60 = self._compute_moving_averages(df, index_price)
        rsi = self._compute_rsi(df)
        macd_hist = self._compute_macd_hist(df)
        pivot, r1, s1 = self._compute_pivot_points(df)
        trend_short, trend_mid, trend_long = self._compute_trends(index_price, ma5, ma20, ma60)
        score = self._compute_score(trend_short, trend_mid, trend_long, rsi, macd_hist)
        bias = self._bias_from_score(score)

        return self._build_futures_payload(
            index_price,
            index_change,
            ma5,
            ma20,
            ma60,
            rsi,
            macd_hist,
            pivot,
            r1,
            s1,
            trend_short,
            trend_mid,
            trend_long,
            score,
            bias,
        )

    @staticmethod
    def _compute_index_metrics(df: pd.DataFrame) -> tuple[float, float]:
        index_price = float(df["close"].iloc[-1])
        if len(df) > 1:
            index_change = (float(df["close"].iloc[-1]) / float(df["close"].iloc[-2]) - 1) * 100
        else:
            index_change = 0.0
        return index_price, index_change

    @staticmethod
    def _compute_moving_averages(
        df: pd.DataFrame,
        index_price: float,
    ) -> tuple[float, float, float]:
        ma5 = df["close"].rolling(5).mean().iloc[-1]
        ma20 = df["close"].rolling(20).mean().iloc[-1]
        ma60 = df["close"].rolling(60).mean().iloc[-1]
        if pd.isna(ma5):
            ma5 = index_price
        if pd.isna(ma20):
            ma20 = index_price
        if pd.isna(ma60):
            ma60 = index_price
        return float(ma5), float(ma20), float(ma60)

    @staticmethod
    def _compute_rsi(df: pd.DataFrame) -> float:
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]
        if pd.isna(rsi):
            rsi = 50.0
        return float(rsi)

    @staticmethod
    def _compute_macd_hist(df: pd.DataFrame) -> float:
        ema12 = df["close"].ewm(span=12).mean()
        ema26 = df["close"].ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        return float((macd - signal).iloc[-1])

    @staticmethod
    def _compute_pivot_points(df: pd.DataFrame) -> tuple[float, float, float]:
        high = float(df["high"].iloc[-1])
        low = float(df["low"].iloc[-1])
        close = float(df["close"].iloc[-1])
        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        s1 = 2 * pivot - high
        return pivot, r1, s1

    @staticmethod
    def _compute_trends(
        index_price: float,
        ma5: float,
        ma20: float,
        ma60: float,
    ) -> tuple[str, str, str]:
        trend_short = "상승" if index_price > ma5 else "하락"
        trend_mid = "상승" if ma5 > ma20 else "하락"
        trend_long = "상승" if ma20 > ma60 else "하락"
        return trend_short, trend_mid, trend_long

    def _compute_score(
        self,
        trend_short: str,
        trend_mid: str,
        trend_long: str,
        rsi: float,
        macd_hist: float,
    ) -> float:
        score = 0
        score += self._score_trend(trend_short, 10)
        score += self._score_trend(trend_mid, 15)
        score += self._score_trend(trend_long, 15)
        score += self._score_rsi(rsi)
        score += self._score_macd(macd_hist)
        return max(-100, min(100, score * 1.2))

    @staticmethod
    def _score_trend(trend: str, weight: int) -> int:
        return weight if trend == "상승" else -weight

    @staticmethod
    def _score_rsi(rsi: float) -> int:
        if rsi < 30:
            return 15
        if rsi < 40:
            return 5
        if rsi > 70:
            return -15
        if rsi > 60:
            return -5
        return 0

    @staticmethod
    def _score_macd(macd_hist: float) -> int:
        return 10 if macd_hist > 0 else -10

    @staticmethod
    def _bias_from_score(score: float) -> MarketBias:
        if score >= 30:
            return MarketBias.STRONG_BULLISH
        if score >= 10:
            return MarketBias.BULLISH
        if score <= -30:
            return MarketBias.STRONG_BEARISH
        if score <= -10:
            return MarketBias.BEARISH
        return MarketBias.NEUTRAL

    @staticmethod
    def _build_futures_payload(
        index_price: float,
        index_change: float,
        ma5: float,
        ma20: float,
        ma60: float,
        rsi: float,
        macd_hist: float,
        pivot: float,
        r1: float,
        s1: float,
        trend_short: str,
        trend_mid: str,
        trend_long: str,
        score: float,
        bias: MarketBias,
    ) -> Dict:
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
            "bias": bias.value,
        }

    def _build_price_frame(self) -> Optional[pd.DataFrame]:
        """KRX 일봉 + KIS 분봉(가능 시)로 가격 프레임 구성"""
        history = self._fetch_krx_history()
        intraday = self._fetch_kis_intraday()

        if history is None and intraday is None:
            return None

        if history is None and intraday is not None:
            df = intraday.copy()
            df = df[["close", "high", "low"]]
            df["open"] = df["close"]
            return df

        df = history if history is not None else pd.DataFrame()
        if intraday is not None and len(intraday) > 0 and len(df) > 0:
            last = intraday.iloc[-1]
            df.iloc[-1, df.columns.get_loc("open")] = float(last["open"])
            df.iloc[-1, df.columns.get_loc("high")] = float(last["high"])
            df.iloc[-1, df.columns.get_loc("low")] = float(last["low"])
            df.iloc[-1, df.columns.get_loc("close")] = float(last["close"])
        return df

    def _fetch_krx_history(self) -> Optional[pd.DataFrame]:
        """KRX Open API로 KOSPI200 선물 일봉 히스토리 수집"""
        if not self.config.krx_api_key:
            return None

        days = max(5, int(self.config.krx_analysis_days))
        dates = self._get_recent_trading_dates(days)
        rows = []

        for date_str in reversed(dates):
            futures_list = self._krx_client.get_kospi200_futures(date_str)
            if not futures_list:
                continue
            fut = max(futures_list, key=lambda f: f.volume)
            close = float(fut.close_price)
            rows.append(
                {
                    "date": date_str,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                }
            )

        if not rows:
            return None

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
        df = df.sort_values("date").reset_index(drop=True)
        return df[["open", "high", "low", "close"]]

    def _fetch_kis_intraday(self) -> Optional[pd.DataFrame]:
        """KIS 선물 분봉(근월물) 수집"""
        app_key = SecretsManager.kis_app_key("futures") or ""
        app_secret = SecretsManager.kis_app_secret("futures") or ""
        if not app_key or not app_secret:
            return None

        market = SecretsManager.kis_market("futures")
        is_real = str(market).lower() != "mock"

        config = KISAuthConfig(app_key=app_key, app_secret=app_secret, is_real=is_real)
        auth = KISAuthManager.get_instance(config)

        code = os.environ.get("LLM_FUTURES_CODE", "") or KIS_SHORT_CODES.get(
            "kospi_front", KOSPI200F_FRONT_CODE
        )

        date_str = self._get_last_trading_date()
        url = f"{config.base_url}/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice"
        headers = auth.get_auth_headers()
        headers["tr_id"] = "FHKIF03020200"
        headers["custtype"] = "P"
        params = {
            "FID_COND_MRKT_DIV_CODE": "F",
            "FID_INPUT_ISCD": code,
            "FID_HOUR_CLS_CODE": "1",
            "FID_PW_DATA_INCU_YN": "Y",
            "FID_FAKE_TICK_INCU_YN": "N",
            "FID_INPUT_DATE_1": date_str,
            "FID_INPUT_HOUR_1": "",
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("rt_cd") != "0":
                return None

            rows = self._parse_kis_ohlcv(code, date_str, data)
            if not rows:
                return None
            df = pd.DataFrame(
                rows, columns=["code", "datetime", "open", "high", "low", "close", "volume"]
            )
            df = df.sort_values("datetime")
            return df
        except Exception:
            return None

    def _get_last_trading_date(self) -> str:
        now = datetime.now()
        today = now.date()

        if now.time() < self._calendar.MARKET_OPEN_TIME:
            target = self._calendar.get_previous_market_day(today)
        elif self._calendar.is_market_day(today):
            target = today
        else:
            target = self._calendar.get_previous_market_day(today)

        return target.strftime("%Y%m%d")

    def _get_recent_trading_dates(self, days: int) -> List[str]:
        dates = []
        current = datetime.strptime(self._get_last_trading_date(), "%Y%m%d").date()
        while len(dates) < days:
            dates.append(current.strftime("%Y%m%d"))
            current = self._calendar.get_previous_market_day(current)
        return dates

    @staticmethod
    def _parse_kis_ohlcv(code: str, date_str: str, data: dict) -> List[Tuple]:
        rows = []
        output = data.get("output2", []) or data.get("output1", []) or data.get("output", [])
        if not output:
            return rows

        def _first_present(item: dict, keys: List[str], default: float = 0.0):
            for k in keys:
                v = item.get(k)
                if v is not None and (not isinstance(v, str) or v.strip()):
                    return v
            return default

        for item in output:
            if not isinstance(item, dict):
                continue
            time_str = _first_present(
                item,
                ["stck_cntg_hour", "futs_cntg_hour", "cntg_hour", "bsop_hour", "hour"],
                "",
            )
            if not time_str:
                continue
            if len(time_str) == 4:
                time_str = f"{time_str}00"
            try:
                dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
            except ValueError:
                continue

            o = _first_present(item, ["futs_oprc", "open", "stck_oprc", "oprc"], 0)
            h = _first_present(item, ["futs_hgpr", "high", "stck_hgpr", "hgpr"], 0)
            l = _first_present(item, ["futs_lwpr", "low", "stck_lwpr", "lwpr"], 0)
            c = _first_present(
                item, ["futs_prpr", "close", "stck_prpr", "stck_clpr", "prpr"], 0
            )
            v = _first_present(item, ["cntg_vol", "acml_vol", "volume"], 0)

            try:
                rows.append(
                    (
                        code,
                        dt,
                        float(o or 0),
                        float(h or 0),
                        float(l or 0),
                        float(c or 0),
                        int(v or 0),
                    )
                )
            except (TypeError, ValueError):
                continue

        return rows



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

    def analyze(self, _code: str, _name: str) -> Dict:
        """뉴스 분석"""
        return {
            "sentiment": "중립",
            "key_events": [],
            "news_count": 0,
            "implications": "특이사항 없음"
        }
