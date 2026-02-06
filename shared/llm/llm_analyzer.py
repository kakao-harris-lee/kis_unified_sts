"""
LLM-based Stock and Futures Analyzers

OpenAI GPT integration for intelligent market analysis.
"""
import asyncio
import json
import logging
import os
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .analyzers import (
    FuturesTechnicalAnalyzer,
    StockBacktester,
    StockNewsAnalyzer,
    StockTechnicalAnalyzer,
)
from .collectors import (
    DARTDataCollector,
    FuturesEventCollector,
    FuturesFlowCollector,
    FuturesGlobalCollector,
    KOFIADataCollector,
    KRXDataCollector,
    KSDDataCollector,
    MKStockNewsCollector,
    SEIBRODataCollector,
    StockDataCollector,
)
from .config import LLMConfig
from .data_classes import (
    AnalysisResult,
    BacktestResult,
    FuturesTradingPlan,
    MarketBias,
    Signal,
    StockDetailedBriefing,
    StockInfo,
    StockTradingPlan,
    TechnicalAnalysis,
)
from .errors import DataUnavailableError
from .identifiers import DARTCorpCodeMapper

logger = logging.getLogger(__name__)


# ============================================================
# Configuration
# ============================================================


class UnifiedConfig:
    """통합 분석 설정"""

    # 주식 스크리닝
    STOCK_MIN_PRICE = 5000
    STOCK_MAX_PRICE = 500000
    STOCK_MIN_MARKET_CAP = 500_000_000_000  # 5000억
    STOCK_MAX_MARKET_CAP = 100_000_000_000_000  # 100조
    STOCK_TOP_N_VOLUME = 20
    STOCK_FINAL_SELECTION = 5
    STOCK_BACKTEST_DAYS = 60
    STOCK_MAX_POSITION = 0.2  # 20%

    # 선물 분석 가중치
    FUTURES_WEIGHT_GLOBAL = 0.4
    FUTURES_WEIGHT_FLOW = 0.35
    FUTURES_WEIGHT_TECHNICAL = 0.25
    FUTURES_STOP_LOSS_PT = 3.0
    FUTURES_TAKE_PROFIT_PT = 5.0

    # 출력 디렉토리
    OUTPUT_DIR = "output/llm"


# ============================================================
# LLMAnalyzer (Legacy Compatible)
# ============================================================


class LLMAnalyzer:
    """OpenAI GPT 기반 종목 분석기 (Legacy Compatible)"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: OpenAI API 키 (None이면 환경변수 사용)
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.client = None
        self._initialized = False

        # Internal analyzers
        self._stock_collector = StockDataCollector()
        self._tech_analyzer = StockTechnicalAnalyzer()
        self._backtester = StockBacktester()

    async def initialize(self) -> bool:
        """API 클라이언트 초기화"""
        if self._initialized:
            return True

        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set. Using rule-based analysis.")
            return False

        try:
            import openai
            self.client = openai.AsyncOpenAI(api_key=self.api_key)
            self._initialized = True
            logger.info("OpenAI API connected successfully")
            return True
        except ImportError:
            logger.error("openai package not installed. Run: pip install openai")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            return False

    async def analyze_stock(
        self,
        code: str,
        name: str,
        technical_data: Optional[Dict] = None,
        backtest_data: Optional[Dict] = None,
        market_data: Optional[Dict] = None,
    ) -> Optional[AnalysisResult]:
        """종목 종합 분석 (Legacy Compatible)"""
        # 기술적 데이터가 없으면 직접 수집
        if technical_data is None:
            df = self._stock_collector.get_stock_history(code, 60)
            if df is not None and len(df) >= 30:
                tech = self._tech_analyzer.analyze(df)
                technical_data = {
                    "rsi": tech.rsi,
                    "macd_hist": tech.macd_hist,
                    "bb_position": tech.bb_position,
                    "trend": tech.trend,
                }

        # 백테스트 데이터가 없으면 직접 수집
        if backtest_data is None and technical_data:
            df = self._stock_collector.get_stock_history(code, 60)
            if df is not None and len(df) >= 30:
                bt_results = self._backtester.run_all_strategies(df)
                if bt_results:
                    best = max(bt_results, key=lambda x: x.total_return)
                    backtest_data = {
                        "win_rate": best.win_rate,
                        "total_return": best.total_return,
                        "strategy": best.strategy_name,
                    }

        # OpenAI 분석 시도
        if await self.initialize():
            prompt = self._build_prompt(code, name, technical_data, backtest_data, market_data)
            try:
                response = await self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "당신은 전문 퀀트 트레이더입니다. 주어진 데이터를 분석하여 JSON 형식으로만 응답합니다."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1500,
                    temperature=0.3,
                )
                result_text = response.choices[0].message.content
                return self._parse_response(code, name, result_text)
            except Exception as e:
                logger.warning(f"LLM analysis failed for {name}: {e}")

        return self._fallback_analysis(code, name, technical_data, backtest_data)

    async def analyze_multiple(
        self,
        stocks: List[Dict],
        max_concurrent: int = 3
    ) -> List[AnalysisResult]:
        """여러 종목 병렬 분석"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_limit(stock: Dict) -> Optional[AnalysisResult]:
            async with semaphore:
                return await self.analyze_stock(
                    code=stock.get("code", ""),
                    name=stock.get("name", ""),
                    technical_data=stock.get("technical"),
                    backtest_data=stock.get("backtest"),
                    market_data=stock.get("market"),
                )

        tasks = [analyze_with_limit(s) for s in stocks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [r for r in results if isinstance(r, AnalysisResult)]

    def _build_prompt(
        self,
        code: str,
        name: str,
        technical: Optional[Dict],
        backtest: Optional[Dict],
        market: Optional[Dict],
    ) -> str:
        """분석 프롬프트 생성"""
        technical_str = json.dumps(technical or {}, ensure_ascii=False, indent=2)
        backtest_str = json.dumps(backtest or {}, ensure_ascii=False, indent=2)
        market_str = json.dumps(market or {}, ensure_ascii=False, indent=2)

        return f"""다음 종목을 분석하여 매매 판단을 내려주세요.

## 종목 정보
- 종목코드: {code}
- 종목명: {name}

## 기술적 분석 데이터
{technical_str}

## 백테스트 결과
{backtest_str}

## 시장 데이터
{market_str}

## 요청사항
위 데이터를 종합하여 다음 JSON 형식으로만 응답해주세요:

```json
{{
    "overall_score": (숫자, -100~+100),
    "recommendation": ("강력매수" | "매수" | "관망" | "매도" | "강력매도"),
    "confidence": ("높음" | "중간" | "낮음"),
    "key_reasons": ["이유1", "이유2", "이유3"],
    "risk_factors": ["리스크1", "리스크2"],
    "entry_strategy": "진입 전략",
    "exit_strategy": "손절/익절 전략",
    "position_size": (숫자, 0~1),
    "time_horizon": ("단기(1-3일)" | "중기(1-2주)")
}}
```

JSON만 출력하고 다른 설명은 생략해주세요."""

    def _parse_response(self, code: str, name: str, response: str) -> AnalysisResult:
        """API 응답 파싱"""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return AnalysisResult(
                    code=code,
                    name=name,
                    overall_score=int(data.get("overall_score", 0)),
                    recommendation=data.get("recommendation", "관망"),
                    confidence=data.get("confidence", "중간"),
                    key_reasons=data.get("key_reasons", [])[:5],
                    risk_factors=data.get("risk_factors", [])[:3],
                    entry_strategy=data.get("entry_strategy", ""),
                    exit_strategy=data.get("exit_strategy", ""),
                    position_size=min(1.0, max(0.0, float(data.get("position_size", 0.1)))),
                    time_horizon=data.get("time_horizon", "단기(1-3일)")
                )
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")

        return self._fallback_analysis(code, name, None, None)

    def _fallback_analysis(
        self,
        code: str,
        name: str,
        technical: Optional[Dict],
        backtest: Optional[Dict],
    ) -> AnalysisResult:
        """API 실패 시 규칙 기반 분석"""
        score = 0
        reasons = []
        risks = []

        if technical:
            rsi = technical.get("rsi", 50)
            if rsi < 30:
                score += 20
                reasons.append(f"RSI 과매도 ({rsi:.1f})")
            elif rsi > 70:
                score -= 20
                risks.append(f"RSI 과매수 ({rsi:.1f})")

            macd_hist = technical.get("macd_hist", 0)
            if macd_hist > 0:
                score += 10
                reasons.append("MACD 상승 신호")
            elif macd_hist < 0:
                score -= 10
                risks.append("MACD 하락 신호")

        if backtest:
            win_rate = backtest.get("win_rate", 50)
            total_return = backtest.get("total_return", 0)

            if win_rate >= 55:
                score += 15
                reasons.append(f"백테스트 승률 우수 ({win_rate:.1f}%)")
            elif win_rate < 45:
                score -= 15
                risks.append(f"백테스트 승률 저조 ({win_rate:.1f}%)")

            if total_return > 5:
                score += 10
                reasons.append(f"백테스트 수익률 양호 ({total_return:+.1f}%)")

        if score >= 40:
            recommendation = "강력매수"
        elif score >= 20:
            recommendation = "매수"
        elif score <= -40:
            recommendation = "강력매도"
        elif score <= -20:
            recommendation = "매도"
        else:
            recommendation = "관망"

        if not reasons:
            reasons = ["분석 데이터 부족"]
        if not risks:
            risks = ["데이터 불충분으로 판단 불확실"]

        return AnalysisResult(
            code=code,
            name=name,
            overall_score=score,
            recommendation=recommendation,
            confidence="낮음",
            key_reasons=reasons,
            risk_factors=risks,
            entry_strategy="추가 분석 필요",
            exit_strategy="표준 손절선 적용 (-1.5%)",
            position_size=0.1,
            time_horizon="단기(1-3일)"
        )


# ============================================================
# LLMAnalyzerWithNotification (Legacy Compatible)
# ============================================================


class LLMAnalyzerWithNotification:
    """LLM 분석기 + 텔레그램 알림 통합 (Legacy Compatible)"""

    def __init__(self, notifier=None, api_key: Optional[str] = None):
        """
        Args:
            notifier: TelegramNotifier 인스턴스
            api_key: OpenAI API 키
        """
        self.analyzer = LLMAnalyzer(api_key=api_key)
        self.notifier = notifier

    async def analyze_and_notify(
        self,
        code: str,
        name: str,
        technical_data: Optional[Dict] = None,
        backtest_data: Optional[Dict] = None,
        send_notification: bool = True,
    ) -> Optional[AnalysisResult]:
        """분석 후 텔레그램 알림 전송"""
        result = await self.analyzer.analyze_stock(
            code=code,
            name=name,
            technical_data=technical_data,
            backtest_data=backtest_data,
        )

        if result and send_notification and self.notifier:
            try:
                message = result.to_telegram_message()
                await self.notifier.send_message(message)
                logger.info(f"Sent LLM analysis notification for {name}")
            except Exception as e:
                logger.warning(f"Failed to send notification: {e}")

        return result


# ============================================================
# UnifiedTradingAnalyzer
# ============================================================


class UnifiedTradingAnalyzer:
    """통합 트레이딩 분석기 (주식 + 선물)

    데이터 소스:
    - pykrx: 주식 시세 (기본)
    - KRX (data.krx.co.kr): 거래소 공식 데이터, 투자자별 동향
    - SEIBRO (seibro.or.kr): 증권정보, 배당, 주주현황
    - DART (dart.fss.or.kr): 공시정보, 재무제표
    - KSD (ksd.or.kr): 공매도, 대차잔고, 대량보유
    - KOFIA (freesis.kofia.or.kr): 펀드, 채권, 투자자동향
    - MK Stock (stock.mk.co.kr): 증권뉴스, 테마, 분석
    """

    def __init__(
        self,
        notifier=None,
        dart_api_key: str | None = None,
        config: Optional[LLMConfig] = None,
        config_path: str | Path | None = None,
    ):
        """
        Args:
            notifier: TelegramNotifier 인스턴스
            dart_api_key: DART API 키 (없으면 환경변수 DART_API_KEY 사용)
            config: LLMConfig (None이면 기본 설정 로드)
            config_path: LLM 설정 YAML 경로 (config가 None일 때만 사용)
        """
        self.notifier = notifier
        self.config = config or LLMConfig.load(config_path)

        # Stock analyzers
        self.stock_collector = StockDataCollector()
        self.stock_tech_analyzer = StockTechnicalAnalyzer()
        self.stock_backtester = StockBacktester()
        self.stock_news_analyzer = StockNewsAnalyzer()

        # Korean Financial Data Source Collectors
        self.krx_collector = KRXDataCollector()
        self.seibro_collector = SEIBRODataCollector()
        self.dart_collector = DARTDataCollector(api_key=dart_api_key)
        self.ksd_collector = KSDDataCollector()
        self.kofia_collector = KOFIADataCollector()
        self.mk_news_collector = MKStockNewsCollector()
        self._dart_corp_mapper = DARTCorpCodeMapper(
            api_key=getattr(self.dart_collector, "api_key", "") or "",
            cache_path=Path(self.config.output_dir) / "dart_corp_codes.json",
            auto_refresh=bool(getattr(self.dart_collector, "api_key", "")),
        )

        # Futures analyzers
        self.futures_global_collector = FuturesGlobalCollector(self.config)
        self.futures_flow_collector = FuturesFlowCollector(self.config)
        self.futures_event_collector = FuturesEventCollector()
        self.futures_tech_analyzer = FuturesTechnicalAnalyzer(self.config)

        # Output
        self.date = datetime.now().strftime("%Y%m%d")
        self.datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(self.config.output_dir, exist_ok=True)

    def _is_preferred_share(self, name: str) -> bool:
        normalized = name.strip()
        return (
            "우선주" in normalized
            or normalized.endswith("우")
            or normalized.endswith("우B")
            or normalized.endswith("우C")
        )

    def _name_exclusion_reasons(self, name: str) -> List[str]:
        reasons: List[str] = []

        if self.config.stock_exclude_preferred_shares and self._is_preferred_share(name):
            reasons.append("preferred_share")

        for kw in self.config.stock_exclude_name_keywords:
            if kw and kw in name:
                reasons.append(f"name_keyword:{kw}")

        return reasons

    @staticmethod
    def _find_keyword_hits(texts: List[str], keywords: List[str]) -> List[str]:
        hits: List[str] = []
        if not keywords:
            return hits

        for t in texts:
            if not t:
                continue
            for kw in keywords:
                if kw and kw in t and kw not in hits:
                    hits.append(kw)
        return hits

    @staticmethod
    def _calc_max_drawdown(close: "pd.Series") -> float:
        if close is None or len(close) < 2:
            return 0.0
        roll_max = close.cummax()
        drawdown = (close / roll_max) - 1.0
        return float(abs(drawdown.min())) if len(drawdown) else 0.0

    @staticmethod
    def _calc_atr_pct(df: "pd.DataFrame", period: int = 14) -> float:
        if df is None or len(df) < period + 1:
            return 0.0
        high = df["고가"].astype(float)
        low = df["저가"].astype(float)
        close = df["종가"].astype(float)
        prev_close = close.shift(1)
        tr = (high - low).abs()
        tr = tr.combine((high - prev_close).abs(), max)
        tr = tr.combine((low - prev_close).abs(), max)
        atr = tr.rolling(period).mean().iloc[-1]
        last_close = close.iloc[-1]
        if pd.isna(atr) or last_close == 0:
            return 0.0
        return float(atr / last_close)

    @staticmethod
    def _calc_consecutive_up(returns: "pd.Series") -> int:
        if returns is None or len(returns) == 0:
            return 0
        count = 0
        for val in reversed(returns.dropna().tolist()):
            if val > 0:
                count += 1
            else:
                break
        return count

    @staticmethod
    def _calc_momentum_metrics(close: "pd.Series", lookback: int) -> Dict[str, float]:
        metrics: Dict[str, float] = {}
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

    def _score_stock_candidate(
        self,
        stock: StockInfo,
        tech: TechnicalAnalysis,
        best: BacktestResult,
        news: Dict[str, Any],
        screening: Dict[str, Any],
    ) -> tuple[float, Dict[str, float]]:
        momentum = screening.get("momentum", {})
        ret_5d = float(momentum.get("ret_5d", 0.0))
        ret_20d = float(momentum.get("ret_20d", 0.0))
        ret_60d = float(momentum.get("ret_60d", 0.0))
        high_prox = float(momentum.get("high_proximity", 0.0))
        consecutive_up = int(screening.get("consecutive_up", 0))

        momentum_raw = ret_5d * 0.6 + ret_20d * 0.3 + ret_60d * 0.1
        momentum_score = max(min(momentum_raw, 20.0), -20.0)
        if high_prox >= 0.95:
            momentum_score += 5
        elif high_prox <= 0.75:
            momentum_score -= 5
        if consecutive_up >= 3:
            momentum_score += 3

        signal_map = {
            Signal.STRONG_BUY: 12,
            Signal.BUY: 6,
            Signal.HOLD: 0,
            Signal.SELL: -6,
            Signal.STRONG_SELL: -12,
        }
        technical_score = float(signal_map.get(tech.signal, 0))

        win_rate_score = (best.win_rate - 50) * 0.6
        total_return = max(min(best.total_return, 30.0), -30.0)
        return_score = total_return * 0.4
        backtest_score = win_rate_score + return_score
        if best.trade_count < 10:
            backtest_score *= 0.8

        sentiment = news.get("sentiment", "중립")
        news_score = 0.0
        if sentiment in ["긍정", "매우 긍정"]:
            news_score += 5
        elif sentiment in ["부정", "매우 부정"]:
            news_score -= 5

        risk_hits = screening.get("risk_keywords", [])
        if risk_hits:
            news_score -= min(len(risk_hits) * 2, 6)

        liquidity_score = 0.0
        trade_value = float(stock.trade_value or 0.0)
        min_trade_value = float(self.config.stock_min_trade_value)
        if trade_value >= min_trade_value * 3:
            liquidity_score += 6
        elif trade_value >= min_trade_value * 2:
            liquidity_score += 4
        elif trade_value >= min_trade_value:
            liquidity_score += 2
        else:
            liquidity_score -= 4

        turnover = float(stock.turnover or 0.0)
        min_turnover = float(self.config.stock_min_turnover)
        if turnover >= min_turnover * 2:
            liquidity_score += 3
        elif turnover >= min_turnover:
            liquidity_score += 1

        if stock.volume_ratio >= 2.0:
            liquidity_score += 3
        elif stock.volume_ratio >= 1.5:
            liquidity_score += 1

        risk_penalty = 0.0
        atr_pct = float(screening.get("atr_pct", 0.0))
        max_dd = float(screening.get("max_drawdown_pct", 0.0))
        volatility = float(screening.get("volatility", 0.0))

        if atr_pct >= self.config.stock_max_atr_pct:
            risk_penalty += 6
        elif atr_pct >= self.config.stock_max_atr_pct * 0.8:
            risk_penalty += 3

        if max_dd >= self.config.stock_max_drawdown_pct:
            risk_penalty += 6
        elif max_dd >= self.config.stock_max_drawdown_pct * 0.8:
            risk_penalty += 3

        if volatility >= 0.6:
            risk_penalty += 3

        weights = {
            "momentum": self.config.stock_score_weight_momentum,
            "technical": self.config.stock_score_weight_technical,
            "backtest": self.config.stock_score_weight_backtest,
            "news": self.config.stock_score_weight_news,
            "liquidity": self.config.stock_score_weight_liquidity,
            "risk": self.config.stock_score_weight_risk,
        }

        total_score = (
            momentum_score * weights["momentum"]
            + technical_score * weights["technical"]
            + backtest_score * weights["backtest"]
            + news_score * weights["news"]
            + liquidity_score * weights["liquidity"]
            - risk_penalty * weights["risk"]
        )

        breakdown = {
            "momentum": momentum_score,
            "technical": technical_score,
            "backtest": backtest_score,
            "news": news_score,
            "liquidity": liquidity_score,
            "risk_penalty": risk_penalty,
            "total": total_score,
        }

        return total_score, breakdown

    def collect_all_data_sources(self, code: str = None) -> Dict:
        """모든 데이터 소스에서 데이터 수집"""
        logger.info(f"Collecting data from all sources{f' for {code}' if code else ''}")

        data = {
            "collected_at": datetime.now().isoformat(),
            "code": code,
            "sources": {}
        }

        # KRX 데이터
        try:
            krx_data = self.krx_collector.collect()
            if code:
                krx_data["stock_info"] = self.krx_collector.get_stock_info(code)
            data["sources"]["krx"] = krx_data
            logger.debug("KRX data collected")
        except Exception as e:
            logger.warning(f"KRX data collection failed: {e}")
            data["sources"]["krx"] = {"error": str(e)}

        # SEIBRO 데이터
        try:
            data["sources"]["seibro"] = self.seibro_collector.collect(code)
            logger.debug("SEIBRO data collected")
        except Exception as e:
            logger.warning(f"SEIBRO data collection failed: {e}")
            data["sources"]["seibro"] = {"error": str(e)}

        # DART 공시 데이터
        try:
            corp_code = self._dart_corp_mapper.get_corp_code(code) if code else None
            data["sources"]["dart"] = (
                self.dart_collector.collect(corp_code)
                if corp_code
                else {"error": "corp_code_not_found"}
            )
            logger.debug("DART data collected")
        except Exception as e:
            logger.warning(f"DART data collection failed: {e}")
            data["sources"]["dart"] = {"error": str(e)}

        # KSD 데이터
        try:
            data["sources"]["ksd"] = self.ksd_collector.collect(code)
            logger.debug("KSD data collected")
        except Exception as e:
            logger.warning(f"KSD data collection failed: {e}")
            data["sources"]["ksd"] = {"error": str(e)}

        # KOFIA 데이터
        try:
            data["sources"]["kofia"] = self.kofia_collector.collect()
            logger.debug("KOFIA data collected")
        except Exception as e:
            logger.warning(f"KOFIA data collection failed: {e}")
            data["sources"]["kofia"] = {"error": str(e)}

        # MK Stock 뉴스
        try:
            mk_data = self.mk_news_collector.collect(code)
            all_news = mk_data.get("market_news", []) + mk_data.get("stock_news", [])
            mk_data["sentiment"] = self.mk_news_collector.analyze_sentiment(all_news).value
            data["sources"]["mk_news"] = mk_data
            logger.debug("MK News data collected")
        except Exception as e:
            logger.warning(f"MK News data collection failed: {e}")
            data["sources"]["mk_news"] = {"error": str(e)}

        return data

    async def run_full_analysis(
        self,
        mode: str = "all",
        send_telegram: bool = True
    ) -> Tuple[List[StockTradingPlan], Optional[FuturesTradingPlan], Dict]:
        """전체 분석 실행

        Args:
            mode: "all", "stock" (선물 분석 비활성화)
            send_telegram: 텔레그램 알림 전송 여부

        Returns:
            (stock_plans, futures_plan, analysis_data)
        """
        logger.info(f"Starting unified analysis - mode: {mode}")

        stock_plans = []
        stock_analysis = {}
        futures_plan = None
        futures_analysis = {}

        # 주식 분석
        if mode in ["all", "stock"]:
            stock_plans, stock_analysis = await self._analyze_stocks()

        # 선물 분석 (비활성화)
        if mode in ["all", "futures"]:
            logger.info("Futures analysis disabled: skipping futures data in LLM output")

        # 통합 데이터
        analysis_data = {
            "date": self.date,
            "generated_at": self.datetime_str,
            "stock": stock_analysis,
        }

        # 리포트 저장
        if stock_plans or futures_plan:
            self._save_reports(stock_plans, futures_plan, analysis_data)

        # 텔레그램 알림
        if send_telegram and self.notifier:
            await self._send_telegram_alerts(stock_plans, futures_plan, futures_analysis)

        return stock_plans, futures_plan, analysis_data

    async def _analyze_stocks(self) -> Tuple[List[StockTradingPlan], Dict]:
        """주식 분석 (다중 데이터 소스 활용)"""
        logger.info("Starting stock analysis with multiple data sources")

        # KOSPI + KOSDAQ (best-effort).
        market_kospi = self.stock_collector.collect("KOSPI")
        market_kosdaq = self.stock_collector.collect("KOSDAQ")
        frames = []
        markets = []
        if market_kospi is not None and len(market_kospi) > 0:
            frames.append(market_kospi)
            markets.append("KOSPI")
        if market_kosdaq is not None and len(market_kosdaq) > 0:
            frames.append(market_kosdaq)
            markets.append("KOSDAQ")

        if not frames:
            market_df = None
        elif len(frames) == 1:
            market_df = frames[0]
        else:
            import pandas as pd

            market_df = pd.concat(frames, axis=0)
        if market_df is None or len(market_df) == 0:
            logger.error("Failed to collect market data")
            return [], {}

        required_cols = ["종가", "시가", "거래량", "시가총액"]
        missing_cols = [c for c in required_cols if c not in market_df.columns]
        if missing_cols:
            logger.error(f"Market data missing columns: {missing_cols}")
            return [], {"_excluded": {"_error": [f"missing_columns:{','.join(missing_cols)}"]}}

        trade_value_fallback = False
        if "거래대금" not in market_df.columns:
            trade_value_fallback = True
            market_df["거래대금"] = market_df["종가"] * market_df["거래량"]

        market_df["거래대금"] = pd.to_numeric(market_df["거래대금"], errors="coerce")
        market_df["시가총액"] = pd.to_numeric(market_df["시가총액"], errors="coerce")
        market_df["거래량"] = pd.to_numeric(market_df["거래량"], errors="coerce")
        market_df = market_df.dropna(subset=["거래대금", "시가총액", "거래량", "종가", "시가"])

        # KRX 투자자별 거래동향 수집
        krx_data = {}
        try:
            krx_data = self.krx_collector.collect()
            logger.info("KRX investor/program trading data collected")
        except Exception as e:
            logger.warning(f"KRX data collection failed: {e}")

        # 필터링
        filtered = market_df[
            (market_df["종가"] >= self.config.stock_min_price)
            & (market_df["종가"] <= self.config.stock_max_price)
            & (market_df["시가총액"] >= self.config.stock_min_market_cap)
            & (market_df["시가총액"] <= self.config.stock_max_market_cap)
            & (market_df["거래대금"] >= self.config.stock_min_trade_value)
        ].copy()

        filtered["거래대금비율"] = (
            filtered["거래대금"] / filtered["시가총액"].replace(0, np.nan)
        )
        filtered = filtered[filtered["거래대금비율"] >= self.config.stock_min_turnover]

        filtered["등락률"] = (filtered["종가"] - filtered["시가"]) / filtered["시가"] * 100

        top_volume = filtered.nlargest(self.config.stock_top_n_volume, "거래량")

        stocks = []
        excluded: Dict[str, List[str]] = {}
        for code in top_volume.index:
            row = top_volume.loc[code]
            name = self.stock_collector.get_stock_name(code)
            name_exclusions = self._name_exclusion_reasons(name)
            if name_exclusions:
                excluded[code] = name_exclusions
                continue
            stocks.append(StockInfo(
                code=code, name=name,
                price=row['종가'], change_pct=round(row['등락률'], 2),
                volume=int(row['거래량']), volume_ratio=1.0,
                market_cap=row['시가총액'],
                trade_value=float(row.get("거래대금", 0.0)),
                turnover=float(row.get("거래대금비율", 0.0)),
            ))

        logger.info(f"Screened {len(stocks)} stocks (excluded={len(excluded)}) from {markets}")

        # 개별 분석
        candidates = []
        analysis_results: Dict[str, Any] = {"_excluded": excluded}

        for stock in stocks[: self.config.stock_top_n_volume]:
            history_days = max(
                int(self.config.stock_backtest_days),
                int(self.config.stock_history_days),
                int(self.config.stock_momentum_lookback_days),
            )
            df = self.stock_collector.get_stock_history(stock.code, history_days)
            if df is None or len(df) < int(self.config.stock_min_history_days):
                analysis_results["_excluded"][stock.code] = [
                    f"history_insufficient:{0 if df is None else len(df)}"
                ]
                continue

            required_hist_cols = ["종가", "고가", "저가", "거래량"]
            missing_hist_cols = [c for c in required_hist_cols if c not in df.columns]
            if missing_hist_cols:
                analysis_results["_excluded"][stock.code] = [
                    f"history_missing:{','.join(missing_hist_cols)}"
                ]
                continue

            if "거래대금" not in df.columns:
                df["거래대금"] = df["종가"] * df["거래량"]

            # Volume ratio and liquidity filter (per-stock)
            lookback = max(1, int(self.config.stock_volume_lookback_days))
            vol_window = df["거래량"].tail(lookback + 1)
            avg_volume = float(vol_window.iloc[:-1].mean()) if len(vol_window) > 1 else float(vol_window.mean())
            stock.volume_ratio = round((stock.volume / avg_volume) if avg_volume > 0 else 1.0, 2)
            if avg_volume < float(self.config.stock_min_avg_volume):
                analysis_results["_excluded"][stock.code] = [f"min_avg_volume:{int(avg_volume)}"]
                continue

            trade_window = df["거래대금"].tail(lookback + 1)
            avg_trade_value = float(trade_window.iloc[:-1].mean()) if len(trade_window) > 1 else float(trade_window.mean())
            if avg_trade_value < float(self.config.stock_min_trade_value):
                analysis_results["_excluded"][stock.code] = [f"min_avg_trade_value:{int(avg_trade_value)}"]
                continue

            # Momentum & risk metrics
            close = df["종가"].astype(float)
            returns = close.pct_change()
            momentum = self._calc_momentum_metrics(close, int(self.config.stock_momentum_lookback_days))
            consecutive_up = self._calc_consecutive_up(returns)
            atr_pct = self._calc_atr_pct(df)
            max_dd = self._calc_max_drawdown(close)
            volatility = float(returns.std() * np.sqrt(252)) if returns is not None else 0.0

            if atr_pct > float(self.config.stock_max_atr_pct):
                analysis_results["_excluded"][stock.code] = [f"atr_pct:{atr_pct:.2%}"]
                continue
            if max_dd > float(self.config.stock_max_drawdown_pct):
                analysis_results["_excluded"][stock.code] = [f"max_drawdown:{max_dd:.2%}"]
                continue

            tech = self.stock_tech_analyzer.analyze(df)
            bt_results = self.stock_backtester.run_all_strategies(df)
            if not bt_results:
                analysis_results["_excluded"][stock.code] = ["backtest_empty"]
                continue

            best = max(bt_results, key=lambda x: x.total_return)
            if best.trade_count < int(self.config.stock_min_backtest_trades):
                analysis_results["_excluded"][stock.code] = [
                    f"backtest_trades:{best.trade_count}"
                ]
                continue
            if best.win_rate < float(self.config.stock_min_backtest_win_rate):
                analysis_results["_excluded"][stock.code] = [
                    f"backtest_win_rate:{best.win_rate:.1f}"
                ]
                continue

            # MK 뉴스 수집
            mk_news = {}
            try:
                mk_news = self.mk_news_collector.collect(stock.code)
                all_news = mk_news.get("market_news", []) + mk_news.get("stock_news", [])
                mk_news["sentiment"] = self.mk_news_collector.analyze_sentiment(all_news).value
            except Exception as e:
                logger.debug(f"MK news failed for {stock.code}: {e}")

            # DART 공시 확인
            dart_data = {}
            try:
                corp_code = self._dart_corp_mapper.get_corp_code(stock.code)
                dart_data = (
                    self.dart_collector.collect(corp_code)
                    if corp_code
                    else {"error": "corp_code_not_found"}
                )
            except Exception as e:
                logger.debug(f"DART data failed for {stock.code}: {e}")

            # KSD 공매도 확인
            ksd_data = {}
            try:
                ksd_data = self.ksd_collector.collect(stock.code)
            except Exception as e:
                logger.debug(f"KSD data failed for {stock.code}: {e}")

            # KRX 종목 상태(가능 시) 확인 → blacklist 키워드 탐지
            krx_stock_info: Dict[str, Any] = {}
            try:
                krx_stock_info = self.krx_collector.get_stock_info(stock.code) or {}
            except Exception as e:
                logger.debug(f"KRX stock info failed for {stock.code}: {e}")

            texts_to_scan: List[str] = [stock.name]
            texts_to_scan.extend([n.get("title", "") for n in mk_news.get("stock_news", [])])
            texts_to_scan.extend([n.get("title", "") for n in mk_news.get("market_news", [])])
            texts_to_scan.append(json.dumps(krx_stock_info, ensure_ascii=False, default=str))
            if dart_data.get("recent_disclosures"):
                texts_to_scan.extend(
                    [d.get("report_nm", "") for d in dart_data.get("recent_disclosures", [])]
                )

            blacklist_hits = self._find_keyword_hits(texts_to_scan, self.config.stock_blacklist)
            keyword_hits = self._find_keyword_hits(texts_to_scan, self.config.stock_keyword_filter)
            if blacklist_hits or keyword_hits:
                reasons: List[str] = []
                reasons.extend([f"blacklist:{kw}" for kw in blacklist_hits])
                reasons.extend([f"keyword:{kw}" for kw in keyword_hits])
                analysis_results["_excluded"][stock.code] = reasons
                continue

            risk_hits = self._find_keyword_hits(texts_to_scan, self.config.stock_risk_keywords)

            # 기존 news 분석에 MK 뉴스 통합
            news = self.stock_news_analyzer.analyze(stock.code, stock.name)
            if mk_news.get("sentiment"):
                news["sentiment"] = mk_news["sentiment"]
            if mk_news.get("stock_news"):
                news["mk_headlines"] = [n.get("title") for n in mk_news["stock_news"][:3]]

            screening_metrics = {
                "avg_volume": round(avg_volume, 2),
                "avg_trade_value": round(avg_trade_value, 2),
                "volume_ratio": stock.volume_ratio,
                "trade_value": round(stock.trade_value, 2),
                "turnover": round(stock.turnover, 6),
                "momentum": momentum,
                "consecutive_up": consecutive_up,
                "atr_pct": round(atr_pct, 4),
                "max_drawdown_pct": round(max_dd, 4),
                "volatility": round(volatility, 4),
                "risk_keywords": risk_hits,
            }

            screening_score, score_breakdown = self._score_stock_candidate(
                stock, tech, best, news, screening_metrics
            )

            analysis_results[stock.code] = {
                "technical": asdict(tech),
                "backtest": [asdict(b) for b in bt_results],
                "news": news,
                "screening": {
                    "metrics": screening_metrics,
                    "score": round(screening_score, 2),
                    "score_breakdown": {k: round(v, 2) for k, v in score_breakdown.items()},
                },
                "data_sources": {
                    "mk_news": mk_news,
                    "dart": dart_data,
                    "ksd": ksd_data,
                    "krx_stock_info": krx_stock_info,
                }
            }

            if tech.signal in [Signal.STRONG_BUY, Signal.BUY] or best.win_rate >= float(self.config.stock_min_backtest_win_rate):
                candidates.append((screening_score, stock, tech, best, news, dart_data, ksd_data, screening_metrics))

        # KRX 데이터 추가
        analysis_results["_market_data"] = {"krx": krx_data}

        # 스크리닝 메타 요약
        excluded_counts: Dict[str, int] = {}
        for _code, reasons in analysis_results.get("_excluded", {}).items():
            for reason in reasons:
                key = reason.split(":", 1)[0]
                excluded_counts[key] = excluded_counts.get(key, 0) + 1

        analysis_results["_screening_meta"] = {
            "trade_value_fallback": trade_value_fallback,
            "excluded_count": len(analysis_results.get("_excluded", {})),
            "excluded_reasons": excluded_counts,
            "filters": {
                "min_trade_value": self.config.stock_min_trade_value,
                "min_turnover": self.config.stock_min_turnover,
                "min_avg_volume": self.config.stock_min_avg_volume,
                "min_history_days": self.config.stock_min_history_days,
                "max_atr_pct": self.config.stock_max_atr_pct,
                "max_drawdown_pct": self.config.stock_max_drawdown_pct,
                "min_backtest_trades": self.config.stock_min_backtest_trades,
                "min_backtest_win_rate": self.config.stock_min_backtest_win_rate,
            },
        }

        # 최종 선정
        candidates.sort(key=lambda x: x[0], reverse=True)
        final = candidates[: self.config.stock_final_selection]

        # 매매 계획 생성
        plans = []
        for _score, stock, tech, best, news, dart, ksd, screening in final:
            entry = stock.price

            if "변동성" in best.strategy_name:
                sl_pct, tp_pct = 0.05, 0.08
            else:
                sl_pct, tp_pct = 0.07, 0.12

            stop_loss = entry * (1 - sl_pct)
            take_profit = entry * (1 + tp_pct)

            if best.win_rate >= 55:
                position, confidence = self.config.stock_max_position, "높음"
            elif best.win_rate >= 48:
                position, confidence = self.config.stock_max_position * 0.7, "중간"
            else:
                position, confidence = self.config.stock_max_position * 0.5, "낮음"

            reasons = []
            if tech.signal in [Signal.STRONG_BUY, Signal.BUY]:
                reasons.append(f"기술적 신호: {tech.signal.value}")
            if tech.rsi < 40:
                reasons.append(f"RSI 과매도 ({tech.rsi})")
            if stock.volume_ratio > 2:
                reasons.append(f"거래량 급증 ({stock.volume_ratio:.1f}배)")
            if best.win_rate > 50:
                reasons.append(f"백테스트 승률 {best.win_rate}%")
            if news.get("sentiment") in ["긍정", "매우 긍정"]:
                reasons.append(f"뉴스 감성: {news.get('sentiment')}")

            momentum = screening.get("momentum", {})
            ret_20d = momentum.get("ret_20d")
            if ret_20d is not None and ret_20d > 3:
                reasons.append(f"20일 상승률 {ret_20d:.1f}%")
            high_prox = momentum.get("high_proximity")
            if high_prox is not None and high_prox >= 0.9:
                reasons.append(f"52주 고점 근접 ({high_prox:.0%})")
            atr_pct = screening.get("atr_pct")
            if atr_pct is not None and atr_pct < 0.04:
                reasons.append(f"변동성 안정 (ATR {atr_pct:.1%})")

            key_events = news.get("mk_headlines", news.get("key_events", []))

            plans.append(StockTradingPlan(
                code=stock.code,
                name=stock.name,
                strategy=best.strategy_name,
                entry_price=round(entry, 0),
                stop_loss=round(stop_loss, 0),
                take_profit=round(take_profit, 0),
                position_size=round(position, 2),
                confidence=confidence,
                reasons=reasons,
                news_sentiment=news.get("sentiment", "중립"),
                key_events=key_events[:3] if key_events else []
            ))

        logger.info(f"Final stock recommendations: {len(plans)}")
        return plans, analysis_results

    async def _analyze_futures(self) -> Tuple[Optional[FuturesTradingPlan], Dict]:
        """선물 분석"""
        logger.info("Starting futures analysis")

        missing_sources: List[str] = []

        def _record_missing(err: DataUnavailableError):
            label = err.source if not err.detail else f"{err.source}:{err.detail}"
            missing_sources.append(label)

        # 글로벌 시장
        global_data = None
        try:
            global_data = self.futures_global_collector.collect()
        except DataUnavailableError as e:
            _record_missing(e)

        # 경제 이벤트
        events: List[Any] = []
        high_events: List[Any] = []
        try:
            events = self.futures_event_collector.collect()
            high_events = [e for e in events if e.importance == "높음"]
        except DataUnavailableError as e:
            _record_missing(e)

        # 수급
        flow_data = None
        flow_missing: List[str] = []
        try:
            flow_data, flow_missing = self.futures_flow_collector.collect()
            missing_sources.extend([f"futures_flow:{m}" for m in flow_missing])
        except DataUnavailableError as e:
            _record_missing(e)

        # 기술적 분석
        technical = None
        try:
            technical = self.futures_tech_analyzer.analyze()
        except DataUnavailableError as e:
            _record_missing(e)

        # 종합 판단
        score_components: List[Tuple[float, float]] = []
        if global_data is not None:
            score_components.append((global_data.global_score, self.config.futures_weight_global))
        if flow_data is not None:
            score_components.append((flow_data.flow_score, self.config.futures_weight_flow))
        if technical is not None:
            score_components.append((technical["score"], self.config.futures_weight_technical))

        if score_components:
            total_weight = sum(w for _s, w in score_components) or 1.0
            overall_score = sum(s * w for s, w in score_components) / total_weight
        else:
            overall_score = 0.0

        if high_events:
            overall_score *= 0.8

        if overall_score >= 30:
            overall_bias = MarketBias.STRONG_BULLISH
        elif overall_score >= 15:
            overall_bias = MarketBias.BULLISH
        elif overall_score <= -30:
            overall_bias = MarketBias.STRONG_BEARISH
        elif overall_score <= -15:
            overall_bias = MarketBias.BEARISH
        else:
            overall_bias = MarketBias.NEUTRAL

        # 전략 생성
        insufficient_data = len(score_components) < 2 or technical is None
        if insufficient_data:
            direction = "관망"
            confidence = "낮음"
            entry = technical['index_price'] if technical else 0.0
            stop_loss = 0
            take_profit = 0
            entry_cond = "데이터 부족으로 관망"
        elif overall_score >= 25:
            direction = "롱"
            confidence = "높음" if overall_score >= 40 else "중간"
            entry = technical['index_price']
            stop_loss = entry - self.config.futures_stop_loss_pt
            take_profit = entry + self.config.futures_take_profit_pt
            entry_cond = f"5일선({technical['ma5']:.2f}) 돌파 또는 시가 진입"
        elif overall_score <= -25:
            direction = "숏"
            confidence = "높음" if overall_score <= -40 else "중간"
            entry = technical['index_price']
            stop_loss = entry + self.config.futures_stop_loss_pt
            take_profit = entry - self.config.futures_take_profit_pt
            entry_cond = f"5일선({technical['ma5']:.2f}) 이탈 또는 시가 진입"
        else:
            direction = "관망"
            confidence = "낮음"
            entry = technical['index_price'] if technical else 0.0
            stop_loss = 0
            take_profit = 0
            entry_cond = "조건 충족 시까지 대기"

        position = "풀" if confidence == "높음" else "하프" if confidence == "중간" else "쿼터"
        time_horizon = "장중" if high_events else "오버나이트"

        # 촉매/리스크
        catalysts = []
        if global_data and global_data.sp500_change_pct > 0.5:
            catalysts.append(f"미국 증시 강세 ({global_data.sp500_change_pct:+.1f}%)")
        if flow_data and flow_data.foreign_futures_5d is not None and flow_data.foreign_futures_5d > 15000:
            catalysts.append(f"외국인 5일 순매수 ({flow_data.foreign_futures_5d:+,.0f})")
        if flow_data and flow_data.basis is not None and flow_data.basis < -1:
            catalysts.append(f"선물 저평가 (베이시스 {flow_data.basis:.2f}pt)")
        if flow_data and flow_data.microstructure_score is not None:
            if flow_data.microstructure_score >= 6:
                catalysts.append(f"단기 주문흐름 매수 우위 (점수 {flow_data.microstructure_score:+.1f})")
            elif flow_data.microstructure_score <= -6:
                risks.append(f"단기 주문흐름 매도 우위 (점수 {flow_data.microstructure_score:+.1f})")

        risks = []
        if global_data and global_data.vix > 20:
            risks.append(f"VIX {global_data.vix:.1f} 상승")
        if high_events:
            risks.append(f"주요 이벤트: {high_events[0].event}")
        if technical and technical['rsi'] > 70:
            risks.append(f"RSI {technical['rsi']:.0f} 과매수")
        elif technical and technical['rsi'] < 30:
            risks.append(f"RSI {technical['rsi']:.0f} 과매도")

        if missing_sources:
            risks.append(f"데이터 누락: {', '.join(missing_sources)}")

        plan = None
        if technical is not None:
            plan = FuturesTradingPlan(
                direction=direction,
                confidence=confidence,
                entry_condition=entry_cond,
                entry_price=round(entry, 2),
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                position_size=position,
                time_horizon=time_horizon,
                key_levels=[technical['pivot'], technical['support_1'], technical['resistance_1']],
                risk_factors=risks,
                catalysts=catalysts
            )

        analysis_data = {
            "overall_score": round(overall_score, 1),
            "overall_bias": overall_bias.value,
            "global": asdict(global_data) if global_data else None,
            "flow": asdict(flow_data) if flow_data else None,
            "technical": technical,
            "events": [asdict(e) for e in events[:5]] if events else [],
            "missing_sources": missing_sources,
        }

        logger.info(f"Futures recommendation: {direction} ({confidence})")
        return plan, analysis_data

    async def _send_telegram_alerts(
        self,
        stock_plans: List[StockTradingPlan],
        futures_plan: Optional[FuturesTradingPlan],
        futures_analysis: Dict
    ):
        """텔레그램 알림 전송"""
        if not self.notifier:
            return

        try:
            # 헤더 메시지
            header = f"""
🚀 <b>통합 트레이딩 브리핑</b>
━━━━━━━━━━━━━━━━━━━━
📅 {self.datetime_str}
"""
            await self.notifier.send_message(header, is_critical=True)

            missing_sources = futures_analysis.get("missing_sources") if futures_analysis else None
            if missing_sources:
                missing_text = "\n".join(f"  • {m}" for m in missing_sources)
                await self.notifier.send_message(
                    f"⚠️ <b>선물 데이터 누락</b>\n{missing_text}",
                    is_critical=True,
                )

            # 선물 브리핑
            if futures_plan:
                await self.notifier.send_message(futures_plan.to_telegram_message(), is_critical=True)

            # 주식 요약
            if stock_plans:
                stocks_header = f"""
📈 <b>주식 추천 ({len(stock_plans)}개)</b>
━━━━━━━━━━━━━━━━━━━━
"""
                await self.notifier.send_message(stocks_header)

                for plan in stock_plans[:3]:
                    await self.notifier.send_message(plan.to_telegram_message())

            # 체크리스트
            checklist = """
📋 <b>체크리스트</b>
━━━━━━━━━━━━━━━━━━━━
☐ 08:30 - 장전 점검
☐ 09:00 - 장 시작
☐ 15:30 - 결과 기록
━━━━━━━━━━━━━━━━━━━━
⚠️ <i>투자의 책임은 본인에게 있습니다</i>
"""
            await self.notifier.send_message(checklist)

            logger.info("Telegram alerts sent successfully")
        except Exception as e:
            logger.error(f"Failed to send Telegram alerts: {e}")

    def _save_reports(
        self,
        stock_plans: List[StockTradingPlan],
        futures_plan: Optional[FuturesTradingPlan],
        analysis_data: Dict
    ):
        """리포트 저장"""
        json_data = {
            "date": self.date,
            "generated_at": self.datetime_str,
            "stock_plans": [asdict(p) for p in stock_plans],
            "futures_plan": asdict(futures_plan) if futures_plan else None,
            "analysis": analysis_data
        }

        json_path = os.path.join(self.config.output_dir, f"unified_data_{self.date}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Report saved: {json_path}")

    def generate_detailed_briefing(self, code: str) -> Optional[StockDetailedBriefing]:
        """종목 코드에 대한 상세 브리핑 생성"""
        try:
            name = self.stock_collector.get_stock_name(code)
            if not name:
                logger.warning(f"Could not find stock name for {code}")
                return None

            hist_df = self.stock_collector.get_stock_history(code, 60)
            if hist_df is None or len(hist_df) < 30:
                logger.warning(f"Insufficient history data for {code}")
                return None

            current_price = float(hist_df['종가'].iloc[-1])
            prev_price = float(hist_df['종가'].iloc[-2])
            change_pct = (current_price - prev_price) / prev_price * 100

            volume = int(hist_df['거래량'].iloc[-1])
            avg_volume = hist_df['거래량'].mean()
            volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

            try:
                market_cap = 0.0
                for mkt in ("KOSPI", "KOSDAQ"):
                    market_df = self.stock_collector.collect(mkt)
                    if market_df is not None and code in market_df.index:
                        market_cap = float(market_df.loc[code, "시가총액"])
                        break
            except:
                market_cap = 0.0

            tech = self.stock_tech_analyzer.analyze(hist_df)

            bt_results = self.stock_backtester.run_all_strategies(hist_df)
            if bt_results:
                best = max(bt_results, key=lambda x: x.total_return)
            else:
                best = None

            news_headlines = []
            news_sentiment = "중립"
            try:
                mk_news = self.mk_news_collector.collect(code)
                all_news = mk_news.get("market_news", []) + mk_news.get("stock_news", [])
                news_headlines = [n.get("title", "") for n in all_news[:5]]
                news_sentiment = self.mk_news_collector.analyze_sentiment(all_news).value
            except:
                pass

            dart_disclosures = []
            try:
                corp_code = self._dart_corp_mapper.get_corp_code(code)
                dart_data = (
                    self.dart_collector.collect(corp_code)
                    if corp_code
                    else {"error": "corp_code_not_found"}
                )
                disclosures = dart_data.get("recent_disclosures", [])
                dart_disclosures = [d.get("report_nm", "") for d in disclosures[:3]]
            except:
                pass

            short_selling_status = ""
            try:
                ksd_data = self.ksd_collector.collect(code)
                ss = ksd_data.get("short_selling", {})
                if ss.get("status") == "available":
                    short_selling_status = "공매도 가능"
            except:
                pass

            investor_trend = ""
            try:
                krx_data = self.krx_collector.collect()
                inv_data = krx_data.get("investor_trading", {})
                if inv_data:
                    foreign_net = inv_data.get("foreign_net", 0)
                    inst_net = inv_data.get("institution_net", 0)
                    if foreign_net > 0 and inst_net > 0:
                        investor_trend = "외인+기관 순매수"
                    elif foreign_net > 0:
                        investor_trend = "외인 순매수"
                    elif inst_net > 0:
                        investor_trend = "기관 순매수"
                    else:
                        investor_trend = "개인 순매수"
            except:
                pass

            entry_price = current_price
            if best and "변동성" in best.strategy_name:
                sl_pct, tp_pct = 0.05, 0.08
            else:
                sl_pct, tp_pct = 0.07, 0.12
            stop_loss = entry_price * (1 - sl_pct)
            take_profit = entry_price * (1 + tp_pct)

            if best and best.win_rate >= 55:
                confidence = "높음"
            elif best and best.win_rate >= 48:
                confidence = "중간"
            else:
                confidence = "낮음"

            selection_reasons = []
            if tech.signal in [Signal.STRONG_BUY, Signal.BUY]:
                selection_reasons.append(f"기술적 신호: {tech.signal.value}")
            if tech.rsi < 40:
                selection_reasons.append(f"RSI 과매도 ({tech.rsi:.1f})")
            elif tech.rsi > 60:
                selection_reasons.append(f"RSI 강세 ({tech.rsi:.1f})")
            if volume_ratio > 2:
                selection_reasons.append(f"거래량 급증 ({volume_ratio:.1f}배)")
            if best:
                selection_reasons.append(f"백테스트 승률 {best.win_rate:.1f}%")
            if news_sentiment in ["긍정", "매우 긍정"]:
                selection_reasons.append(f"뉴스 감성: {news_sentiment}")

            risk_factors = []
            if tech.rsi > 70:
                risk_factors.append("RSI 과매수 상태")
            if best and best.max_drawdown > 10:
                risk_factors.append(f"최대 낙폭 {best.max_drawdown:.1f}%")
            if volume_ratio < 0.5:
                risk_factors.append("거래량 부족")
            if news_sentiment in ["부정", "매우 부정"]:
                risk_factors.append(f"부정적 뉴스: {news_sentiment}")

            briefing = StockDetailedBriefing(
                code=code,
                name=name,
                generated_at=self.datetime_str,
                current_price=current_price,
                change_pct=round(change_pct, 2),
                market_cap=market_cap,
                volume=volume,
                volume_ratio=round(volume_ratio, 2),
                rsi=round(tech.rsi, 2),
                macd_hist=round(tech.macd_hist, 2),
                bb_position=round(tech.bb_position, 2),
                trend=tech.trend,
                ma5=round(tech.ma5, 2),
                ma20=round(tech.ma20, 2),
                ma60=round(tech.ma60, 2),
                tech_signal=tech.signal.value,
                best_strategy=best.strategy_name if best else "N/A",
                backtest_win_rate=round(best.win_rate, 2) if best else 0,
                backtest_return=round(best.total_return, 2) if best else 0,
                backtest_trades=best.trade_count if best else 0,
                backtest_max_drawdown=round(best.max_drawdown, 2) if best else 0,
                entry_price=entry_price,
                stop_loss=round(stop_loss, 0),
                take_profit=round(take_profit, 0),
                position_size=0.2,
                confidence=confidence,
                time_horizon="단기 (1-5일)",
                selection_reasons=selection_reasons,
                risk_factors=risk_factors,
                news_sentiment=news_sentiment,
                news_headlines=news_headlines,
                dart_disclosures=dart_disclosures,
                short_selling_status=short_selling_status,
                investor_trend=investor_trend
            )

            return briefing

        except Exception as e:
            logger.error(f"Error generating briefing for {code}: {e}")
            return None


# ============================================================
# Convenience Functions
# ============================================================


_default_analyzer: Optional[LLMAnalyzer] = None
_default_unified_analyzer: Optional[UnifiedTradingAnalyzer] = None


def get_llm_analyzer() -> LLMAnalyzer:
    """Get or create default LLM analyzer instance (Legacy Compatible)"""
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = LLMAnalyzer()
    return _default_analyzer


def get_unified_analyzer(notifier=None) -> UnifiedTradingAnalyzer:
    """Get or create default unified analyzer instance"""
    global _default_unified_analyzer
    if _default_unified_analyzer is None:
        _default_unified_analyzer = UnifiedTradingAnalyzer(notifier=notifier)
    return _default_unified_analyzer


async def analyze_stock_with_llm(
    code: str,
    name: str,
    technical_data: Optional[Dict] = None,
    backtest_data: Optional[Dict] = None,
) -> Optional[AnalysisResult]:
    """Convenience function for quick stock analysis (Legacy Compatible)"""
    analyzer = get_llm_analyzer()
    return await analyzer.analyze_stock(
        code=code,
        name=name,
        technical_data=technical_data,
        backtest_data=backtest_data,
    )


async def run_unified_analysis(
    notifier=None,
    mode: str = "all",
    send_telegram: bool = True
) -> Tuple[List[StockTradingPlan], Optional[FuturesTradingPlan], Dict]:
    """Convenience function for unified analysis"""
    analyzer = get_unified_analyzer(notifier=notifier)
    return await analyzer.run_full_analysis(mode=mode, send_telegram=send_telegram)


async def get_stock_detail_briefing(
    code: str,
    notifier=None,
    send_telegram: bool = True
) -> Optional[StockDetailedBriefing]:
    """종목 상세 브리핑 생성 및 전송 편의 함수"""
    analyzer = get_unified_analyzer(notifier=notifier)
    briefing = analyzer.generate_detailed_briefing(code)

    if briefing and send_telegram and notifier:
        try:
            await notifier.send_message(briefing.to_telegram_message())
        except Exception as e:
            logger.warning(f"Failed to send telegram: {e}")

    return briefing
