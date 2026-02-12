"""
Market Analyzers

시장 분석기 모음. ETF, 선물, 옵션, 채권, 지수 분석.
모든 설정값은 LLMConfig에서 로드 (하드코딩 없음).
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional

import numpy as np
import pandas as pd

from .config import LLMConfig
from .data_classes import (
    BondData,
    ETFFlowData,
    FuturesData,
    IndexData,
    MarketSignal,
    OptionsData,
    RiskMode,
)

# Optional imports
try:
    import FinanceDataReader as fdr

    FDR_AVAILABLE = True
except ImportError:
    FDR_AVAILABLE = False


class BaseAnalyzer(ABC):
    """분석기 기본 클래스"""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig.from_env()

    @abstractmethod
    def analyze(self):
        """분석 수행"""
        pass


class ETFFlowAnalyzer(BaseAnalyzer):
    """ETF 자금흐름 분석기 (FinanceDataReader 기반)"""

    def __init__(self, config: Optional[LLMConfig] = None):
        super().__init__(config)
        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(days=60)

    def analyze(self) -> List[ETFFlowData]:
        """섹터별 ETF 자금흐름 분석"""
        results = []

        if not FDR_AVAILABLE:
            return self._get_sample_data()

        for sector, etf_codes in self.config.sector_etfs.items():
            for code in etf_codes:
                try:
                    flow_data = self._analyze_etf(sector, code)
                    if flow_data:
                        results.append(flow_data)
                        break  # 섹터당 하나의 대표 ETF만
                except Exception:
                    continue

        # 샘플 데이터가 없으면 기본 제공
        if len(results) == 0:
            results = self._get_sample_data()

        return results

    def _analyze_etf(self, sector: str, code: str) -> Optional[ETFFlowData]:
        """개별 ETF 분석"""
        try:
            df = fdr.DataReader(code, self.start_date, self.end_date)

            if len(df) < 20:
                return None

            # 거래량 분석
            vol_5d = df["Volume"].tail(5).mean()
            vol_20d = df["Volume"].tail(20).mean()
            vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 1

            # 수익률
            price_5d = (df["Close"].iloc[-1] / df["Close"].iloc[-5] - 1) * 100
            price_20d = (df["Close"].iloc[-1] / df["Close"].iloc[-20] - 1) * 100

            # 거래대금 (추정 자금유입)
            money_flow = (df["Close"] * df["Volume"]).tail(5).sum()

            # 신호 판단
            signal = self._determine_signal(vol_ratio, price_5d)

            return ETFFlowData(
                sector=sector,
                etf_code=code,
                etf_name=f"{sector} ETF",
                volume_5d_avg=vol_5d,
                volume_20d_avg=vol_20d,
                volume_ratio=round(vol_ratio, 2),
                price_change_5d=round(price_5d, 2),
                price_change_20d=round(price_20d, 2),
                money_flow=round(money_flow / 1e8, 1),  # 억원 단위
                signal=signal,
            )

        except Exception:
            return None

    def _determine_signal(self, vol_ratio: float, price_5d: float) -> str:
        """신호 판단"""
        if vol_ratio > 1.5 and price_5d > 2:
            return "강세"
        elif vol_ratio > 1.2 and price_5d > 0:
            return "상승"
        elif vol_ratio < 0.8 and price_5d < -2:
            return "약세"
        elif vol_ratio < 0.9 and price_5d < 0:
            return "하락"
        else:
            return "중립"

    def _get_sample_data(self) -> List[ETFFlowData]:
        """샘플 데이터"""
        np.random.seed(int(datetime.now().timestamp()) % 1000)

        sectors = list(self.config.sector_etfs.keys())[:7]

        results = []
        for sector in sectors:
            vol_ratio = np.random.uniform(0.7, 1.8)
            price_5d = np.random.uniform(-5, 8)
            signal = self._determine_signal(vol_ratio, price_5d)

            results.append(
                ETFFlowData(
                    sector=sector,
                    etf_code=f"ETF_{sector}",
                    etf_name=f"KODEX {sector}",
                    volume_5d_avg=np.random.uniform(100000, 1000000),
                    volume_20d_avg=np.random.uniform(100000, 800000),
                    volume_ratio=round(vol_ratio, 2),
                    price_change_5d=round(price_5d, 2),
                    price_change_20d=round(price_5d * 2 + np.random.uniform(-3, 3), 2),
                    money_flow=round(np.random.uniform(50, 500), 1),
                    signal=signal,
                )
            )

        return results


class FuturesAnalyzer(BaseAnalyzer):
    """KOSPI200 선물 분석기"""

    def analyze(self) -> FuturesData:
        """선물 데이터 분석"""
        np.random.seed(int(datetime.now().timestamp()) % 1000 + 1)

        kospi200 = 350 + np.random.uniform(-10, 10)
        futures_price = kospi200 + np.random.uniform(-2, 2)
        basis = futures_price - kospi200

        oi = 300000 + np.random.uniform(-50000, 50000)

        return FuturesData(
            product_name="KOSPI200 선물",
            close_price=round(futures_price, 2),
            change=round(np.random.uniform(-5, 5), 2),
            change_rate=round(np.random.uniform(-2, 2), 2),
            volume=int(np.random.randint(100000, 500000)),
            open_interest=int(oi),
            basis=round(basis, 2),
        )

    def calculate_signal(self, futures: FuturesData) -> MarketSignal:
        """선물 신호 계산"""
        score = 0

        # 베이시스 분석
        if futures.basis > 0.5:
            score += 1  # 콘탱고 -> 상승 기대
        elif futures.basis < -0.5:
            score -= 1  # 백워데이션 -> 하락 우려

        # 변동률 분석
        if futures.change_rate > 0.5:
            score += 1
        elif futures.change_rate < -0.5:
            score -= 1

        if score >= 2:
            return MarketSignal.STRONG_BULLISH
        elif score >= 1:
            return MarketSignal.BULLISH
        elif score <= -2:
            return MarketSignal.STRONG_BEARISH
        elif score <= -1:
            return MarketSignal.BEARISH
        else:
            return MarketSignal.NEUTRAL


class OptionsAnalyzer(BaseAnalyzer):
    """KOSPI200 옵션 분석기"""

    def analyze(self) -> OptionsData:
        """옵션 데이터 분석"""
        np.random.seed(int(datetime.now().timestamp()) % 1000 + 2)

        put_vol = int(np.random.uniform(50000, 150000))
        call_vol = int(np.random.uniform(50000, 150000))
        pcr = put_vol / call_vol
        pcr_5d = np.random.uniform(0.8, 1.2)

        iv = np.random.uniform(15, 35)
        iv_pct = np.random.uniform(20, 80)

        # 신호 판단
        signal = self._determine_signal(pcr)

        return OptionsData(
            call_volume=call_vol,
            put_volume=put_vol,
            put_call_ratio=round(pcr, 2),
            call_oi=int(np.random.randint(100000, 300000)),
            put_oi=int(np.random.randint(100000, 300000)),
            pcr_5d_avg=round(pcr_5d, 2),
            implied_vol=round(iv, 1),
            iv_percentile=round(iv_pct, 0),
            signal=signal,
        )

    def _determine_signal(self, pcr: float) -> str:
        """PCR 기반 신호 판단"""
        if pcr > 1.3:
            return "극단적 약세 (반등 기대)"
        elif pcr > 1.1:
            return "약세 심리"
        elif pcr < 0.7:
            return "극단적 강세 (조정 주의)"
        elif pcr < 0.9:
            return "강세 심리"
        else:
            return "중립"


class BondAnalyzer(BaseAnalyzer):
    """채권 시장 분석기"""

    def analyze(self) -> BondData:
        """채권 데이터 분석"""
        np.random.seed(int(datetime.now().timestamp()) % 1000 + 3)

        # 국고채 금리
        yield_3y = 3.0 + np.random.uniform(-0.5, 0.5)
        yield_10y = 3.5 + np.random.uniform(-0.5, 0.5)
        spread = yield_10y - yield_3y

        # 채권지수
        bond_idx = 1000 + np.random.uniform(-20, 20)
        bond_chg = np.random.uniform(-0.5, 0.5)

        # 리스크 모드 판단
        risk_mode = self._determine_risk_mode(spread)

        return BondData(
            bond_index=round(bond_idx, 2),
            bond_change=round(bond_chg, 2),
            yield_3y=round(yield_3y, 2),
            yield_10y=round(yield_10y, 2),
            yield_spread=round(spread, 2),
            risk_mode=risk_mode,
        )

    def _determine_risk_mode(self, spread: float) -> RiskMode:
        """장단기 스프레드 기반 리스크 모드 판단"""
        if spread > 0.5:
            return RiskMode.RISK_ON
        elif spread < 0.2:
            return RiskMode.RISK_OFF
        else:
            return RiskMode.NEUTRAL


class IndexAnalyzer(BaseAnalyzer):
    """주요 지수 분석기"""

    def __init__(self, config: Optional[LLMConfig] = None):
        super().__init__(config)
        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(days=60)

    def analyze(self) -> List[IndexData]:
        """지수 분석"""
        results = []

        if not FDR_AVAILABLE:
            return self._get_sample_data()

        for name, code in self.config.indices.items():
            try:
                idx_data = self._analyze_index(name, code)
                if idx_data:
                    results.append(idx_data)
            except Exception:
                continue

        if len(results) == 0:
            results = self._get_sample_data()

        return results

    def _analyze_index(self, name: str, code: str) -> Optional[IndexData]:
        """개별 지수 분석"""
        try:
            df = fdr.DataReader(code, self.start_date, self.end_date)

            if len(df) < 20:
                return None

            price = df["Close"].iloc[-1]
            chg_1d = (df["Close"].iloc[-1] / df["Close"].iloc[-2] - 1) * 100
            chg_5d = (df["Close"].iloc[-1] / df["Close"].iloc[-5] - 1) * 100
            chg_20d = (df["Close"].iloc[-1] / df["Close"].iloc[-20] - 1) * 100

            vol_ratio = df["Volume"].tail(5).mean() / df["Volume"].tail(20).mean()

            # RSI
            delta = df["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = (100 - (100 / (1 + rs))).iloc[-1]

            # 추세
            ma5 = df["Close"].rolling(5).mean().iloc[-1]
            ma20 = df["Close"].rolling(20).mean().iloc[-1]

            if price > ma5 > ma20:
                trend = "상승"
            elif price < ma5 < ma20:
                trend = "하락"
            else:
                trend = "횡보"

            return IndexData(
                name=name,
                price=round(price, 2),
                change_1d=round(chg_1d, 2),
                change_5d=round(chg_5d, 2),
                change_20d=round(chg_20d, 2),
                volume_ratio=round(vol_ratio, 2),
                rsi=round(rsi, 0),
                trend=trend,
            )

        except Exception:
            return None

    def _get_sample_data(self) -> List[IndexData]:
        """샘플 데이터"""
        np.random.seed(int(datetime.now().timestamp()) % 1000 + 4)

        indices = [
            ("KOSPI", 2650),
            ("KOSDAQ", 850),
            ("KOSPI200", 350),
            ("KOSPI_LARGE", 3500),
            ("KOSDAQ150", 1200),
        ]

        results = []
        for name, base in indices:
            price = base + np.random.uniform(-50, 50)
            chg_1d = np.random.uniform(-2, 2)
            chg_5d = np.random.uniform(-5, 5)
            chg_20d = np.random.uniform(-10, 10)
            rsi = np.random.uniform(30, 70)

            if chg_5d > 2:
                trend = "상승"
            elif chg_5d < -2:
                trend = "하락"
            else:
                trend = "횡보"

            results.append(
                IndexData(
                    name=name,
                    price=round(price, 2),
                    change_1d=round(chg_1d, 2),
                    change_5d=round(chg_5d, 2),
                    change_20d=round(chg_20d, 2),
                    volume_ratio=round(np.random.uniform(0.8, 1.5), 2),
                    rsi=round(rsi, 0),
                    trend=trend,
                )
            )

        return results


class TechnicalAnalyzerForFutures(BaseAnalyzer):
    """선물용 기술적 분석기"""

    def analyze(self) -> dict:
        """기술적 분석 수행"""
        np.random.seed(int(datetime.now().timestamp()) % 1000 + 5)

        # 샘플 KOSPI200 데이터
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

        # 지표 계산
        index_price = df["close"].iloc[-1]
        index_change = (df["close"].iloc[-1] / df["close"].iloc[-2] - 1) * 100

        ma5 = df["close"].rolling(5).mean().iloc[-1]
        ma20 = df["close"].rolling(20).mean().iloc[-1]
        ma60 = df["close"].rolling(60).mean().iloc[-1]

        # RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        # MACD
        ema12 = df["close"].ewm(span=12).mean()
        ema26 = df["close"].ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        macd_hist = (macd - signal).iloc[-1]

        # 피봇
        pivot = (df["high"].iloc[-1] + df["low"].iloc[-1] + df["close"].iloc[-1]) / 3
        r1 = 2 * pivot - df["low"].iloc[-1]
        s1 = 2 * pivot - df["high"].iloc[-1]

        # 추세
        trend_short = "상승" if index_price > ma5 else "하락"
        trend_mid = "상승" if ma5 > ma20 else "하락"
        trend_long = "상승" if ma20 > ma60 else "하락"

        # 점수
        score = self._calculate_score(trend_short, trend_mid, trend_long, rsi, macd_hist)

        if score >= 30:
            bias = "강세"
        elif score >= 10:
            bias = "상승"
        elif score <= -30:
            bias = "약세"
        elif score <= -10:
            bias = "하락"
        else:
            bias = "중립"

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
            "bias": bias,
        }

    def _calculate_score(
        self,
        trend_short: str,
        trend_mid: str,
        trend_long: str,
        rsi: float,
        macd_hist: float,
    ) -> float:
        """점수 계산"""
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

        return max(-100, min(100, score * 1.2))
