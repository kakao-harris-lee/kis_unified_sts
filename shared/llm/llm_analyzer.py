"""
LLM-based Stock and Futures Analyzers

Provider-agnostic LLM integration for intelligent market analysis.
"""

import asyncio
import json
import logging
import os
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from shared.kis.auth import KISAuthConfig
from shared.kis.client import KISClient

from . import llm_scoring as _llm_scoring
from . import reporting as _reporting
from . import stock_analysis as _stock_analysis
from . import stock_screening as _stock_screening
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
    StockDetailedBriefing,
    StockInfo,
    StockTradingPlan,
    TechnicalAnalysis,
)
from .errors import DataUnavailableError
from .identifiers import DARTCorpCodeMapper
from .prompt_cache import LLMPromptCache, PromptCacheConfig
from .schema import normalize_analysis_result_payload

logger = logging.getLogger(__name__)


# ============================================================
# Configuration
# ============================================================


class UnifiedConfig:
    """통합 분석 설정"""

    # 주식 스크리닝
    STOCK_MIN_PRICE = 5000
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
    """LLM 기반 종목 분석기 (Legacy Compatible)"""

    def __init__(self, api_key: str | None = None):
        """
        Args:
            api_key: LLM API 키 (None이면 provider별 환경변수 사용)
        """
        self.provider = os.environ.get("LLM_PROVIDER", "openai").strip().lower()
        if self.provider not in ("openai", "claude"):
            self.provider = "openai"

        default_model = (
            "claude-3-5-haiku-latest" if self.provider == "claude" else "gpt-4o-mini"
        )
        self.model = os.environ.get("LLM_MODEL", default_model)
        self.max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "1500"))
        self.temperature = float(os.environ.get("LLM_TEMPERATURE", "0.3"))
        self.strict_json_schema = (
            os.environ.get("LLM_STRICT_JSON_SCHEMA", "true").lower() == "true"
        )
        self.batch_size = max(1, int(os.environ.get("LLM_BATCH_SIZE", "10")))
        self.prompt_cache = LLMPromptCache(
            PromptCacheConfig(
                enabled=os.environ.get("LLM_PROMPT_CACHE_ENABLED", "true").lower()
                == "true",
                ttl_seconds=max(
                    60, int(os.environ.get("LLM_PROMPT_CACHE_TTL_SECONDS", "21600"))
                ),
                key_prefix=os.environ.get(
                    "LLM_PROMPT_CACHE_PREFIX", "llm:prompt_cache"
                ),
            )
        )

        resolved_key = api_key
        if not resolved_key:
            if self.provider == "claude":
                resolved_key = os.environ.get("ANTHROPIC_API_KEY", "")
            else:
                resolved_key = os.environ.get("OPENAI_API_KEY", "")
        self.api_key = resolved_key or ""
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
            logger.warning("LLM API key not set. Using rule-based analysis.")
            return False

        try:
            if self.provider == "claude":
                from anthropic import AsyncAnthropic

                self.client = AsyncAnthropic(api_key=self.api_key)
                logger.info("Anthropic API connected successfully")
            else:
                import openai

                self.client = openai.AsyncOpenAI(api_key=self.api_key)
                logger.info("OpenAI API connected successfully")
            self._initialized = True
            return True
        except ImportError:
            pkg = "anthropic" if self.provider == "claude" else "openai"
            logger.error(f"{pkg} package not installed. Run: pip install {pkg}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize {self.provider} client: {e}")
            return False

    async def analyze_stock(
        self,
        code: str,
        name: str,
        technical_data: dict | None = None,
        backtest_data: dict | None = None,
        market_data: dict | None = None,
    ) -> AnalysisResult | None:
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

        # LLM 분석 시도
        if await self.initialize():
            prompt = self._build_prompt(
                code, name, technical_data, backtest_data, market_data
            )
            system_prompt = (
                "당신은 전문 퀀트 트레이더입니다. "
                "주어진 데이터를 분석하여 JSON 형식으로만 응답합니다."
            )
            cache_key = LLMPromptCache.build_key(
                key_prefix=self.prompt_cache.config.key_prefix,
                provider=self.provider,
                model=self.model,
                system_prompt=system_prompt,
                user_prompt=prompt,
                extra={"temperature": self.temperature, "max_tokens": self.max_tokens},
            )
            try:
                cached = self.prompt_cache.get(cache_key)
                if cached:
                    return self._parse_response(code, name, cached)

                if self.provider == "claude":
                    response = await self.client.messages.create(
                        model=self.model,
                        system=system_prompt,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                    )
                    text_blocks = [
                        b.text
                        for b in response.content
                        if getattr(b, "type", "") == "text"
                    ]
                    result_text = "\n".join(text_blocks).strip()
                else:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                    )
                    result_text = response.choices[0].message.content or ""
                self.prompt_cache.set(cache_key, result_text)
                return self._parse_response(code, name, result_text)
            except Exception as e:
                logger.warning(f"LLM analysis failed for {name}: {e}")

        return self._fallback_analysis(code, name, technical_data, backtest_data)

    async def analyze_multiple(
        self, stocks: list[dict], max_concurrent: int = 3
    ) -> list[AnalysisResult]:
        """여러 종목 병렬 분석"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_limit(stock: dict) -> AnalysisResult | None:
            async with semaphore:
                return await self.analyze_stock(
                    code=stock.get("code", ""),
                    name=stock.get("name", ""),
                    technical_data=stock.get("technical"),
                    backtest_data=stock.get("backtest"),
                    market_data=stock.get("market"),
                )

        results: list[Any] = []
        for i in range(0, len(stocks), self.batch_size):
            batch = stocks[i : i + self.batch_size]
            tasks = [analyze_with_limit(s) for s in batch]
            part = await asyncio.gather(*tasks, return_exceptions=True)
            results.extend(part)

        return [r for r in results if isinstance(r, AnalysisResult)]

    def _build_prompt(
        self,
        code: str,
        name: str,
        technical: dict | None,
        backtest: dict | None,
        market: dict | None,
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
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())
                if not isinstance(data, dict):
                    raise ValueError("LLM payload is not an object")

                normalized = normalize_analysis_result_payload(data)
                if self.strict_json_schema:
                    if not normalized["key_reasons"]:
                        raise ValueError("Missing key_reasons in strict mode")
                    if not normalized["risk_factors"]:
                        raise ValueError("Missing risk_factors in strict mode")

                return AnalysisResult(
                    code=code,
                    name=name,
                    overall_score=normalized["overall_score"],
                    recommendation=normalized["recommendation"],
                    confidence=normalized["confidence"],
                    key_reasons=normalized["key_reasons"],
                    risk_factors=normalized["risk_factors"],
                    entry_strategy=normalized["entry_strategy"],
                    exit_strategy=normalized["exit_strategy"],
                    position_size=normalized["position_size"],
                    time_horizon=normalized["time_horizon"],
                )
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")

        return self._fallback_analysis(code, name, None, None)

    def _fallback_analysis(
        self,
        code: str,
        name: str,
        technical: dict | None,
        backtest: dict | None,
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
            time_horizon="단기(1-3일)",
        )


# ============================================================
# LLMAnalyzerWithNotification (Legacy Compatible)
# ============================================================


class LLMAnalyzerWithNotification:
    """LLM 분석기 + 텔레그램 알림 통합 (Legacy Compatible)"""

    def __init__(self, notifier=None, api_key: str | None = None):
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
        technical_data: dict | None = None,
        backtest_data: dict | None = None,
        send_notification: bool = True,
    ) -> AnalysisResult | None:
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
        config: LLMConfig | None = None,
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
        self.kis_client: KISClient | None = None
        self._target_price_cache: dict[str, dict[str, Any]] = {}
        if self.config.stock_enable_kis_target_price:
            kis_is_real = os.environ.get("KIS_IS_REAL", "true").lower() == "true"
            kis_cfg = KISAuthConfig(is_real=kis_is_real)
            if kis_cfg.is_real and kis_cfg.app_key and kis_cfg.app_secret:
                self.kis_client = KISClient(kis_cfg)
            else:
                logger.info(
                    "KIS target-price enrichment disabled (missing credentials or mock mode)"
                )
        self._dart_corp_mapper = DARTCorpCodeMapper(
            api_key=getattr(self.dart_collector, "api_key", "") or "",
            cache_path=Path(self.config.output_dir) / "dart_corp_codes.json",
            auto_refresh=bool(getattr(self.dart_collector, "api_key", "")),
        )

        # LLM scoring
        self._scoring_prompt_cache = LLMPromptCache(
            PromptCacheConfig(
                enabled=self.config.llm_prompt_cache_enabled,
                ttl_seconds=self.config.llm_prompt_cache_ttl_seconds,
                key_prefix=f"{self.config.llm_prompt_cache_prefix}:scoring",
            )
        )
        self._scoring_client = None

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
        return _stock_screening.is_preferred_share(name)

    def _name_exclusion_reasons(self, name: str) -> list[str]:
        return _stock_screening.name_exclusion_reasons(name, self.config)

    @staticmethod
    def _find_keyword_hits(texts: list[str], keywords: list[str]) -> list[str]:
        return _stock_screening.find_keyword_hits(texts, keywords)

    @staticmethod
    def _calc_max_drawdown(close: "pd.Series") -> float:
        return _stock_screening.calc_max_drawdown(close)

    @staticmethod
    def _calc_atr_pct(df: "pd.DataFrame", period: int = 14) -> float:
        return _stock_screening.calc_atr_pct(df, period)

    @staticmethod
    def _calc_consecutive_up(returns: "pd.Series") -> int:
        return _stock_screening.calc_consecutive_up(returns)

    @staticmethod
    def _calc_momentum_metrics(close: "pd.Series", lookback: int) -> dict[str, float]:
        return _stock_screening.calc_momentum_metrics(close, lookback)

    @staticmethod
    def _score_target_price_signal(screening: dict[str, Any]) -> float:
        """Score analyst target-price signal from KIS invest-opinion."""
        return _stock_screening.score_target_price_signal(screening)

    async def _collect_target_price_signal(
        self,
        code: str,
        current_price: float,
    ) -> dict[str, Any]:
        return await _llm_scoring.collect_target_price_signal(self, code, current_price)

    def _score_stock_candidate(
        self,
        stock: StockInfo,
        tech: TechnicalAnalysis,
        best: BacktestResult | None,
        news: dict[str, Any],
        screening: dict[str, Any],
    ) -> tuple[float, dict[str, float]]:
        return _stock_screening.score_stock_candidate(
            stock, tech, best, news, screening, self.config
        )

    async def _llm_score_candidate(
        self,
        stock: StockInfo,
        tech: TechnicalAnalysis,
        best: BacktestResult | None,
        news: dict[str, Any],
        screening: dict[str, Any],
    ) -> dict[str, Any]:
        """LLM 기반 종목 확신도 스코어링."""
        return await _llm_scoring.llm_score_candidate(
            self, stock, tech, best, news, screening
        )

    def collect_all_data_sources(self, code: str = None) -> dict:
        """모든 데이터 소스에서 데이터 수집"""
        logger.info(f"Collecting data from all sources{f' for {code}' if code else ''}")

        data = {"collected_at": datetime.now().isoformat(), "code": code, "sources": {}}

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
            mk_data["sentiment"] = self.mk_news_collector.analyze_sentiment(
                all_news
            ).value
            data["sources"]["mk_news"] = mk_data
            logger.debug("MK News data collected")
        except Exception as e:
            logger.warning(f"MK News data collection failed: {e}")
            data["sources"]["mk_news"] = {"error": str(e)}

        return data

    async def run_full_analysis(
        self, mode: str = "all", send_telegram: bool = True
    ) -> tuple[list[StockTradingPlan], FuturesTradingPlan | None, dict]:
        """전체 분석 실행

        Args:
            mode: "all", "stock" (선물 분석 비활성화)
            send_telegram: 텔레그램 알림 전송 여부

        Returns:
            (stock_plans, futures_plan, analysis_data)
        """
        logger.info(f"Starting unified analysis - mode: {mode}")
        snapshot_id = datetime.now().strftime("%Y%m%dT%H%M%S")

        stock_plans = []
        stock_analysis = {}
        futures_plan = None
        futures_analysis = {}

        # 주식 분석
        if mode in ["all", "stock"]:
            stock_plans, stock_analysis = await self._analyze_stocks()

        # 선물 분석 (비활성화)
        if mode in ["all", "futures"]:
            logger.info(
                "Futures analysis disabled: skipping futures data in LLM output"
            )

        # 통합 데이터
        analysis_data = {
            "snapshot_id": snapshot_id,
            "date": self.date,
            "generated_at": self.datetime_str,
            "stock": stock_analysis,
        }

        # 리포트 저장
        if stock_plans or futures_plan:
            self._save_reports(stock_plans, futures_plan, analysis_data, snapshot_id)
            self._save_training_rows(snapshot_id, stock_plans, stock_analysis)

        # 실시간-배치 융합용 LLM 품질 스냅샷 게시(best-effort)
        if stock_analysis:
            self._publish_llm_quality_snapshot(snapshot_id, stock_plans, stock_analysis)

        # 텔레그램 알림
        if send_telegram and self.notifier:
            await self._send_telegram_alerts(
                stock_plans, futures_plan, futures_analysis
            )

        return stock_plans, futures_plan, analysis_data

    async def _analyze_stocks(self) -> tuple[list[StockTradingPlan], dict]:
        """주식 분석 (다중 데이터 소스 활용)"""
        return await _stock_analysis.analyze_stocks(self)

    async def _analyze_futures(self) -> tuple[FuturesTradingPlan | None, dict]:
        """선물 분석"""
        logger.info("Starting futures analysis")

        missing_sources: list[str] = []

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
        events: list[Any] = []
        high_events: list[Any] = []
        try:
            events = self.futures_event_collector.collect()
            high_events = [e for e in events if e.importance == "높음"]
        except DataUnavailableError as e:
            _record_missing(e)

        # 수급
        flow_data = None
        flow_missing: list[str] = []
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
        score_components: list[tuple[float, float]] = []
        if global_data is not None:
            score_components.append(
                (global_data.global_score, self.config.futures_weight_global)
            )
        if flow_data is not None:
            score_components.append(
                (flow_data.flow_score, self.config.futures_weight_flow)
            )
        if technical is not None:
            score_components.append(
                (technical["score"], self.config.futures_weight_technical)
            )

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
            entry = technical["index_price"] if technical else 0.0
            stop_loss = 0
            take_profit = 0
            entry_cond = "데이터 부족으로 관망"
        elif overall_score >= 25:
            direction = "롱"
            confidence = "높음" if overall_score >= 40 else "중간"
            entry = technical["index_price"]
            stop_loss = entry - self.config.futures_stop_loss_pt
            take_profit = entry + self.config.futures_take_profit_pt
            entry_cond = f"5일선({technical['ma5']:.2f}) 돌파 또는 시가 진입"
        elif overall_score <= -25:
            direction = "숏"
            confidence = "높음" if overall_score <= -40 else "중간"
            entry = technical["index_price"]
            stop_loss = entry + self.config.futures_stop_loss_pt
            take_profit = entry - self.config.futures_take_profit_pt
            entry_cond = f"5일선({technical['ma5']:.2f}) 이탈 또는 시가 진입"
        else:
            direction = "관망"
            confidence = "낮음"
            entry = technical["index_price"] if technical else 0.0
            stop_loss = 0
            take_profit = 0
            entry_cond = "조건 충족 시까지 대기"

        position = (
            "풀" if confidence == "높음" else "하프" if confidence == "중간" else "쿼터"
        )
        time_horizon = "장중" if high_events else "오버나이트"

        # 촉매/리스크
        catalysts = []
        if global_data and global_data.sp500_change_pct > 0.5:
            catalysts.append(f"미국 증시 강세 ({global_data.sp500_change_pct:+.1f}%)")
        if (
            flow_data
            and flow_data.foreign_futures_5d is not None
            and flow_data.foreign_futures_5d > 15000
        ):
            catalysts.append(
                f"외국인 5일 순매수 ({flow_data.foreign_futures_5d:+,.0f})"
            )
        if flow_data and flow_data.basis is not None and flow_data.basis < -1:
            catalysts.append(f"선물 저평가 (베이시스 {flow_data.basis:.2f}pt)")
        if flow_data and flow_data.microstructure_score is not None:
            if flow_data.microstructure_score >= 6:
                catalysts.append(
                    f"단기 주문흐름 매수 우위 (점수 {flow_data.microstructure_score:+.1f})"
                )
            elif flow_data.microstructure_score <= -6:
                risks.append(
                    f"단기 주문흐름 매도 우위 (점수 {flow_data.microstructure_score:+.1f})"
                )

        risks = []
        if global_data and global_data.vix > 20:
            risks.append(f"VIX {global_data.vix:.1f} 상승")
        if high_events:
            risks.append(f"주요 이벤트: {high_events[0].event}")
        if technical and technical["rsi"] > 70:
            risks.append(f"RSI {technical['rsi']:.0f} 과매수")
        elif technical and technical["rsi"] < 30:
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
                key_levels=[
                    technical["pivot"],
                    technical["support_1"],
                    technical["resistance_1"],
                ],
                risk_factors=risks,
                catalysts=catalysts,
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
        stock_plans: list[StockTradingPlan],
        futures_plan: FuturesTradingPlan | None,
        futures_analysis: dict,
    ):
        """텔레그램 알림 전송"""
        await _reporting.send_telegram_alerts(
            self, stock_plans, futures_plan, futures_analysis
        )

    def _save_reports(
        self,
        stock_plans: list[StockTradingPlan],
        futures_plan: FuturesTradingPlan | None,
        analysis_data: dict,
        snapshot_id: str,
    ):
        """리포트 저장"""
        _reporting.save_reports(
            self, stock_plans, futures_plan, analysis_data, snapshot_id
        )

    def _build_llm_quality_snapshot(
        self,
        snapshot_id: str,
        stock_plans: list[StockTradingPlan],
        stock_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        return _reporting.build_llm_quality_snapshot(
            self, snapshot_id, stock_plans, stock_analysis
        )

    def _publish_llm_quality_snapshot(
        self,
        snapshot_id: str,
        stock_plans: list[StockTradingPlan],
        stock_analysis: dict[str, Any],
    ) -> None:
        _reporting.publish_llm_quality_snapshot(
            self, snapshot_id, stock_plans, stock_analysis
        )

    def _save_training_rows(
        self,
        snapshot_id: str,
        stock_plans: list[StockTradingPlan],
        stock_analysis: dict[str, Any],
    ) -> None:
        _reporting.save_training_rows(self, snapshot_id, stock_plans, stock_analysis)

    def generate_detailed_briefing(self, code: str) -> StockDetailedBriefing | None:
        """종목 코드에 대한 상세 브리핑 생성"""
        return _stock_analysis.generate_detailed_briefing(self, code)


# ============================================================
# Convenience Functions
# ============================================================


_default_analyzer: LLMAnalyzer | None = None
_default_unified_analyzer: UnifiedTradingAnalyzer | None = None


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
    technical_data: dict | None = None,
    backtest_data: dict | None = None,
) -> AnalysisResult | None:
    """Convenience function for quick stock analysis (Legacy Compatible)"""
    analyzer = get_llm_analyzer()
    return await analyzer.analyze_stock(
        code=code,
        name=name,
        technical_data=technical_data,
        backtest_data=backtest_data,
    )


async def run_unified_analysis(
    notifier=None, mode: str = "all", send_telegram: bool = True
) -> tuple[list[StockTradingPlan], FuturesTradingPlan | None, dict]:
    """Convenience function for unified analysis"""
    analyzer = get_unified_analyzer(notifier=notifier)
    return await analyzer.run_full_analysis(mode=mode, send_telegram=send_telegram)


async def get_stock_detail_briefing(
    code: str, notifier=None, send_telegram: bool = True
) -> StockDetailedBriefing | None:
    """종목 상세 브리핑 생성 및 전송 편의 함수"""
    analyzer = get_unified_analyzer(notifier=notifier)
    briefing = analyzer.generate_detailed_briefing(code)

    if briefing and send_telegram and notifier:
        try:
            await notifier.send_message(briefing.to_telegram_message())
        except Exception as e:
            logger.warning(f"Failed to send telegram: {e}")

    return briefing
