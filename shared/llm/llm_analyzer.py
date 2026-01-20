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
from typing import Any, Dict, List, Optional, Tuple

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
    FuturesTradingPlan,
    MarketBias,
    Signal,
    StockDetailedBriefing,
    StockInfo,
    StockTradingPlan,
)

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

    def __init__(self, notifier=None, dart_api_key: str = None):
        """
        Args:
            notifier: TelegramNotifier 인스턴스
            dart_api_key: DART API 키 (없으면 환경변수 DART_API_KEY 사용)
        """
        self.notifier = notifier

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

        # Futures analyzers
        self.futures_global_collector = FuturesGlobalCollector()
        self.futures_flow_collector = FuturesFlowCollector()
        self.futures_event_collector = FuturesEventCollector()
        self.futures_tech_analyzer = FuturesTechnicalAnalyzer()

        # Output
        self.date = datetime.now().strftime("%Y%m%d")
        self.datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(UnifiedConfig.OUTPUT_DIR, exist_ok=True)

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
            data["sources"]["dart"] = self.dart_collector.collect(code)
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
            mode: "all", "stock", "futures"
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

        # 선물 분석
        if mode in ["all", "futures"]:
            futures_plan, futures_analysis = await self._analyze_futures()

        # 통합 데이터
        analysis_data = {
            "date": self.date,
            "generated_at": self.datetime_str,
            "stock": stock_analysis,
            "futures": futures_analysis,
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

        market_df = self.stock_collector.collect()
        if market_df is None or len(market_df) == 0:
            logger.error("Failed to collect market data")
            return [], {}

        # KRX 투자자별 거래동향 수집
        krx_data = {}
        try:
            krx_data = self.krx_collector.collect()
            logger.info("KRX investor/program trading data collected")
        except Exception as e:
            logger.warning(f"KRX data collection failed: {e}")

        # 필터링
        filtered = market_df[
            (market_df['종가'] >= UnifiedConfig.STOCK_MIN_PRICE) &
            (market_df['종가'] <= UnifiedConfig.STOCK_MAX_PRICE) &
            (market_df['시가총액'] >= UnifiedConfig.STOCK_MIN_MARKET_CAP) &
            (market_df['시가총액'] <= UnifiedConfig.STOCK_MAX_MARKET_CAP)
        ].copy()

        filtered['거래량비율'] = filtered['거래량'] / filtered['거래량'].mean()
        filtered['등락률'] = (filtered['종가'] - filtered['시가']) / filtered['시가'] * 100

        top_volume = filtered.nlargest(UnifiedConfig.STOCK_TOP_N_VOLUME, '거래량')

        stocks = []
        for code in top_volume.index:
            row = top_volume.loc[code]
            name = self.stock_collector.get_stock_name(code)
            stocks.append(StockInfo(
                code=code, name=name,
                price=row['종가'], change_pct=round(row['등락률'], 2),
                volume=int(row['거래량']), volume_ratio=round(row['거래량비율'], 2),
                market_cap=row['시가총액']
            ))

        logger.info(f"Screened {len(stocks)} stocks")

        # 개별 분석
        candidates = []
        analysis_results = {}

        for stock in stocks[:UnifiedConfig.STOCK_TOP_N_VOLUME]:
            df = self.stock_collector.get_stock_history(stock.code, UnifiedConfig.STOCK_BACKTEST_DAYS)
            if df is None or len(df) < 30:
                continue

            tech = self.stock_tech_analyzer.analyze(df)
            bt_results = self.stock_backtester.run_all_strategies(df)

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
                dart_data = self.dart_collector.collect(stock.code)
            except Exception as e:
                logger.debug(f"DART data failed for {stock.code}: {e}")

            # KSD 공매도 확인
            ksd_data = {}
            try:
                ksd_data = self.ksd_collector.collect(stock.code)
            except Exception as e:
                logger.debug(f"KSD data failed for {stock.code}: {e}")

            # 기존 news 분석에 MK 뉴스 통합
            news = self.stock_news_analyzer.analyze(stock.code, stock.name)
            if mk_news.get("sentiment"):
                news["sentiment"] = mk_news["sentiment"]
            if mk_news.get("stock_news"):
                news["mk_headlines"] = [n.get("title") for n in mk_news["stock_news"][:3]]

            analysis_results[stock.code] = {
                "technical": asdict(tech),
                "backtest": [asdict(b) for b in bt_results],
                "news": news,
                "data_sources": {
                    "mk_news": mk_news,
                    "dart": dart_data,
                    "ksd": ksd_data,
                }
            }

            if bt_results:
                best = max(bt_results, key=lambda x: x.total_return)
                if tech.signal in [Signal.STRONG_BUY, Signal.BUY] or best.win_rate >= 45:
                    candidates.append((stock, tech, best, news, dart_data, ksd_data))

        # KRX 데이터 추가
        analysis_results["_market_data"] = {"krx": krx_data}

        # 최종 선정
        def score_candidate(c):
            stock, tech, best, news, dart, ksd = c
            score = best.win_rate * 0.3 + best.total_return * 0.3

            if tech.signal in [Signal.STRONG_BUY, Signal.BUY]:
                score += 20
            if news.get("sentiment") in ["긍정", "매우 긍정"]:
                score += 15
            elif news.get("sentiment") in ["부정", "매우 부정"]:
                score -= 15

            if dart.get("recent_disclosures"):
                score += 5

            return score

        candidates.sort(key=score_candidate, reverse=True)
        final = candidates[:UnifiedConfig.STOCK_FINAL_SELECTION]

        # 매매 계획 생성
        plans = []
        for stock, tech, best, news, dart, ksd in final:
            entry = stock.price

            if "변동성" in best.strategy_name:
                sl_pct, tp_pct = 0.05, 0.08
            else:
                sl_pct, tp_pct = 0.07, 0.12

            stop_loss = entry * (1 - sl_pct)
            take_profit = entry * (1 + tp_pct)

            if best.win_rate >= 55:
                position, confidence = UnifiedConfig.STOCK_MAX_POSITION, "높음"
            elif best.win_rate >= 48:
                position, confidence = UnifiedConfig.STOCK_MAX_POSITION * 0.7, "중간"
            else:
                position, confidence = UnifiedConfig.STOCK_MAX_POSITION * 0.5, "낮음"

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

    async def _analyze_futures(self) -> Tuple[FuturesTradingPlan, Dict]:
        """선물 분석"""
        logger.info("Starting futures analysis")

        # 글로벌 시장
        global_data = self.futures_global_collector.collect()

        # 경제 이벤트
        events = self.futures_event_collector.collect()
        high_events = [e for e in events if e.importance == "높음"]

        # 수급
        flow_data = self.futures_flow_collector.collect()

        # 기술적 분석
        technical = self.futures_tech_analyzer.analyze()

        # 종합 판단
        overall_score = (
            global_data.global_score * UnifiedConfig.FUTURES_WEIGHT_GLOBAL +
            flow_data.flow_score * UnifiedConfig.FUTURES_WEIGHT_FLOW +
            technical['score'] * UnifiedConfig.FUTURES_WEIGHT_TECHNICAL
        )

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
        if overall_score >= 25:
            direction = "롱"
            confidence = "높음" if overall_score >= 40 else "중간"
            entry = technical['index_price']
            stop_loss = entry - UnifiedConfig.FUTURES_STOP_LOSS_PT
            take_profit = entry + UnifiedConfig.FUTURES_TAKE_PROFIT_PT
            entry_cond = f"5일선({technical['ma5']:.2f}) 돌파 또는 시가 진입"
        elif overall_score <= -25:
            direction = "숏"
            confidence = "높음" if overall_score <= -40 else "중간"
            entry = technical['index_price']
            stop_loss = entry + UnifiedConfig.FUTURES_STOP_LOSS_PT
            take_profit = entry - UnifiedConfig.FUTURES_TAKE_PROFIT_PT
            entry_cond = f"5일선({technical['ma5']:.2f}) 이탈 또는 시가 진입"
        else:
            direction = "관망"
            confidence = "낮음"
            entry = technical['index_price']
            stop_loss = 0
            take_profit = 0
            entry_cond = "조건 충족 시까지 대기"

        position = "풀" if confidence == "높음" else "하프" if confidence == "중간" else "쿼터"
        time_horizon = "장중" if high_events else "오버나이트"

        # 촉매/리스크
        catalysts = []
        if global_data.sp500_change_pct > 0.5:
            catalysts.append(f"미국 증시 강세 ({global_data.sp500_change_pct:+.1f}%)")
        if flow_data.foreign_futures_5d > 15000:
            catalysts.append(f"외국인 5일 순매수 ({flow_data.foreign_futures_5d:+,.0f})")
        if flow_data.basis < -1:
            catalysts.append(f"선물 저평가 (베이시스 {flow_data.basis:.2f}pt)")

        risks = []
        if global_data.vix > 20:
            risks.append(f"VIX {global_data.vix:.1f} 상승")
        if high_events:
            risks.append(f"주요 이벤트: {high_events[0].event}")
        if technical['rsi'] > 70:
            risks.append(f"RSI {technical['rsi']:.0f} 과매수")
        elif technical['rsi'] < 30:
            risks.append(f"RSI {technical['rsi']:.0f} 과매도")

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
            "global": asdict(global_data),
            "flow": asdict(flow_data),
            "technical": technical,
            "events": [asdict(e) for e in events[:5]]
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

        json_path = os.path.join(UnifiedConfig.OUTPUT_DIR, f"unified_data_{self.date}.json")
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
                market_df = self.stock_collector.collect()
                if market_df is not None and code in market_df.index:
                    market_cap = float(market_df.loc[code, '시가총액'])
                else:
                    market_cap = 0.0
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
                dart_data = self.dart_collector.collect(code)
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
