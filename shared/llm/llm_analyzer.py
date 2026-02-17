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
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
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
        technical_data = self._collect_technical_data(code, technical_data)
        backtest_data = self._collect_backtest_data(
            code, backtest_data, technical_data
        )

        llm_result = await self._run_llm_analysis(
            code, name, technical_data, backtest_data, market_data
        )
        if llm_result is not None:
            return llm_result

        return self._fallback_analysis(code, name, technical_data, backtest_data)

    def _collect_technical_data(
        self,
        code: str,
        technical_data: dict | None,
    ) -> dict | None:
        if technical_data is not None:
            return technical_data

        df = self._stock_collector.get_stock_history(code, 60)
        if df is None or len(df) < 30:
            return None

        tech = self._tech_analyzer.analyze(df)
        return {
            "rsi": tech.rsi,
            "macd_hist": tech.macd_hist,
            "bb_position": tech.bb_position,
            "trend": tech.trend,
        }

    def _collect_backtest_data(
        self,
        code: str,
        backtest_data: dict | None,
        technical_data: dict | None,
    ) -> dict | None:
        if backtest_data is not None or not technical_data:
            return backtest_data

        df = self._stock_collector.get_stock_history(code, 60)
        if df is None or len(df) < 30:
            return None

        bt_results = self._backtester.run_all_strategies(df)
        if not bt_results:
            return None

        best = max(bt_results, key=lambda x: x.total_return)
        return {
            "win_rate": best.win_rate,
            "total_return": best.total_return,
            "strategy": best.strategy_name,
        }

    async def _run_llm_analysis(
        self,
        code: str,
        name: str,
        technical_data: dict | None,
        backtest_data: dict | None,
        market_data: dict | None,
    ) -> AnalysisResult | None:
        if not await self.initialize():
            return None

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
            return None

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
        score, reasons, risks = self._fallback_score_components(technical, backtest)
        recommendation = self._fallback_recommendation(score)
        reasons, risks = self._fallback_defaults(reasons, risks)

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

    def _fallback_score_components(
        self,
        technical: Optional[Dict],
        backtest: Optional[Dict],
    ) -> tuple[int, List[str], List[str]]:
        score = 0
        reasons: List[str] = []
        risks: List[str] = []
        if technical:
            score += self._fallback_score_technical(technical, reasons, risks)
        if backtest:
            score += self._fallback_score_backtest(backtest, reasons, risks)
        return score, reasons, risks

    @staticmethod
    def _fallback_score_technical(technical: Dict, reasons: List[str], risks: List[str]) -> int:
        score = 0
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
        return score

    @staticmethod
    def _fallback_score_backtest(backtest: Dict, reasons: List[str], risks: List[str]) -> int:
        score = 0
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
        return score

    @staticmethod
    def _fallback_recommendation(score: int) -> str:
        if score >= 40:
            return "강력매수"
        if score >= 20:
            return "매수"
        if score <= -40:
            return "강력매도"
        if score <= -20:
            return "매도"
        return "관망"

    @staticmethod
    def _fallback_defaults(reasons: List[str], risks: List[str]) -> tuple[List[str], List[str]]:
        if not reasons:
            reasons = ["분석 데이터 부족"]
        if not risks:
            risks = ["데이터 불충분으로 판단 불확실"]
        return reasons, risks


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

    def _collect_market_frames(self) -> tuple[list["pd.DataFrame"], list[str]]:
        market_kospi = self.stock_collector.collect("KOSPI")
        market_kosdaq = self.stock_collector.collect("KOSDAQ")
        frames: list["pd.DataFrame"] = []
        markets: list[str] = []
        if market_kospi is not None and len(market_kospi) > 0:
            frames.append(market_kospi)
            markets.append("KOSPI")
        if market_kosdaq is not None and len(market_kosdaq) > 0:
            frames.append(market_kosdaq)
            markets.append("KOSDAQ")
        return frames, markets

    def _merge_market_frames(self, frames: list["pd.DataFrame"]) -> Optional["pd.DataFrame"]:
        if not frames:
            return None
        if len(frames) == 1:
            return frames[0]
        import pandas as pd

        return pd.concat(frames, axis=0)

    def _prepare_market_df(
        self,
        market_df: "pd.DataFrame",
    ) -> tuple[Optional["pd.DataFrame"], bool, Optional[Dict[str, Any]]]:
        if market_df is None or len(market_df) == 0:
            logger.error("Failed to collect market data")
            return None, False, None

        required_cols = ["종가", "시가", "거래량", "시가총액"]
        missing_cols = [c for c in required_cols if c not in market_df.columns]
        if missing_cols:
            logger.error(f"Market data missing columns: {missing_cols}")
            error_meta = {"_excluded": {"_error": [f"missing_columns:{','.join(missing_cols)}"]}}
            return None, False, error_meta

        trade_value_fallback = False
        if "거래대금" not in market_df.columns:
            trade_value_fallback = True
            market_df = market_df.copy()
            market_df["거래대금"] = market_df["종가"] * market_df["거래량"]

        market_df["거래대금"] = pd.to_numeric(market_df["거래대금"], errors="coerce")
        market_df["시가총액"] = pd.to_numeric(market_df["시가총액"], errors="coerce")
        market_df["거래량"] = pd.to_numeric(market_df["거래량"], errors="coerce")
        market_df = market_df.dropna(subset=["거래대금", "시가총액", "거래량", "종가", "시가"])
        return market_df, trade_value_fallback, None

    def _filter_market_df(self, market_df: "pd.DataFrame") -> "pd.DataFrame":
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
        return filtered

    def _build_screened_stocks(
        self,
        top_volume: "pd.DataFrame",
    ) -> tuple[list[StockInfo], Dict[str, List[str]]]:
        stocks: list[StockInfo] = []
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
        return stocks, excluded

    def _collect_stock_history(
        self,
        stock: StockInfo,
        history_days: int,
    ) -> tuple[Optional["pd.DataFrame"], Optional[List[str]]]:
        df = self.stock_collector.get_stock_history(stock.code, history_days)
        if df is None or len(df) < int(self.config.stock_min_history_days):
            reason = [f"history_insufficient:{0 if df is None else len(df)}"]
            return None, reason

        required_hist_cols = ["종가", "고가", "저가", "거래량"]
        missing_hist_cols = [c for c in required_hist_cols if c not in df.columns]
        if missing_hist_cols:
            return None, [f"history_missing:{','.join(missing_hist_cols)}"]

        if "거래대금" not in df.columns:
            df = df.copy()
            df["거래대금"] = df["종가"] * df["거래량"]
        return df, None

    def _compute_liquidity_metrics(
        self,
        df: "pd.DataFrame",
        stock: StockInfo,
    ) -> tuple[Optional[Dict[str, Any]], Optional[List[str]]]:
        lookback = max(1, int(self.config.stock_volume_lookback_days))
        vol_window = df["거래량"].tail(lookback + 1)
        avg_volume = float(vol_window.iloc[:-1].mean()) if len(vol_window) > 1 else float(vol_window.mean())
        stock.volume_ratio = round((stock.volume / avg_volume) if avg_volume > 0 else 1.0, 2)
        if avg_volume < float(self.config.stock_min_avg_volume):
            return None, [f"min_avg_volume:{int(avg_volume)}"]

        trade_window = df["거래대금"].tail(lookback + 1)
        avg_trade_value = float(trade_window.iloc[:-1].mean()) if len(trade_window) > 1 else float(trade_window.mean())
        if avg_trade_value < float(self.config.stock_min_trade_value):
            return None, [f"min_avg_trade_value:{int(avg_trade_value)}"]

        return {
            "avg_volume": avg_volume,
            "avg_trade_value": avg_trade_value,
        }, None

    def _compute_risk_metrics(self, df: "pd.DataFrame") -> Dict[str, Any]:
        close = df["종가"].astype(float)
        returns = close.pct_change()
        momentum = self._calc_momentum_metrics(close, int(self.config.stock_momentum_lookback_days))
        consecutive_up = self._calc_consecutive_up(returns)
        atr_pct = self._calc_atr_pct(df)
        max_dd = self._calc_max_drawdown(close)
        volatility = float(returns.std() * np.sqrt(252)) if returns is not None else 0.0
        return {
            "momentum": momentum,
            "consecutive_up": consecutive_up,
            "atr_pct": atr_pct,
            "max_drawdown_pct": max_dd,
            "volatility": volatility,
        }

    def _collect_external_sources(
        self,
        stock: StockInfo,
    ) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        mk_news: Dict[str, Any] = {}
        try:
            mk_news = self.mk_news_collector.collect(stock.code)
            all_news = mk_news.get("market_news", []) + mk_news.get("stock_news", [])
            mk_news["sentiment"] = self.mk_news_collector.analyze_sentiment(all_news).value
        except Exception as e:
            logger.debug(f"MK news failed for {stock.code}: {e}")

        dart_data: Dict[str, Any] = {}
        try:
            corp_code = self._dart_corp_mapper.get_corp_code(stock.code)
            dart_data = (
                self.dart_collector.collect(corp_code)
                if corp_code
                else {"error": "corp_code_not_found"}
            )
        except Exception as e:
            logger.debug(f"DART data failed for {stock.code}: {e}")

        ksd_data: Dict[str, Any] = {}
        try:
            ksd_data = self.ksd_collector.collect(stock.code)
        except Exception as e:
            logger.debug(f"KSD data failed for {stock.code}: {e}")

        krx_stock_info: Dict[str, Any] = {}
        try:
            krx_stock_info = self.krx_collector.get_stock_info(stock.code) or {}
        except Exception as e:
            logger.debug(f"KRX stock info failed for {stock.code}: {e}")

        return mk_news, dart_data, ksd_data, krx_stock_info

    def _build_screening_metrics(
        self,
        stock: StockInfo,
        liquidity: Dict[str, Any],
        risk: Dict[str, Any],
        risk_hits: List[str],
    ) -> Dict[str, Any]:
        return {
            "avg_volume": round(float(liquidity.get("avg_volume", 0.0)), 2),
            "avg_trade_value": round(float(liquidity.get("avg_trade_value", 0.0)), 2),
            "volume_ratio": stock.volume_ratio,
            "trade_value": round(stock.trade_value, 2),
            "turnover": round(stock.turnover, 6),
            "momentum": risk.get("momentum", {}),
            "consecutive_up": int(risk.get("consecutive_up", 0)),
            "atr_pct": round(float(risk.get("atr_pct", 0.0)), 4),
            "max_drawdown_pct": round(float(risk.get("max_drawdown_pct", 0.0)), 4),
            "volatility": round(float(risk.get("volatility", 0.0)), 4),
            "risk_keywords": risk_hits,
        }

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
        self,
        mode: str = "all",
        send_telegram: bool = True,
        *,
        intraday: bool = False,
    ) -> tuple[list[StockTradingPlan], FuturesTradingPlan | None, dict]:
        """전체 분석 실행

        Args:
            mode: "all", "stock" (선물 분석 비활성화)
            send_telegram: 텔레그램 알림 전송 여부
            intraday: 장중 경량 갱신 모드 (backtest, DART, KSD, LLM scoring 생략)

        Returns:
            (stock_plans, futures_plan, analysis_data)
        """
        mode_label = f"{mode}/intraday" if intraday else mode
        logger.info(f"Starting unified analysis - mode: {mode_label}")
        snapshot_id = datetime.now().strftime("%Y%m%dT%H%M%S")

        stock_plans = []
        stock_analysis = {}
        futures_plan = None
        futures_analysis = {}

        # 주식 분석
        if mode in ["all", "stock"]:
            stock_plans, stock_analysis = await self._analyze_stocks(
                intraday=intraday
            )

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

    async def _analyze_stocks(
        self, *, intraday: bool = False
    ) -> tuple[list[StockTradingPlan], dict]:
        """주식 분석 (다중 데이터 소스 활용)"""
        return await _stock_analysis.analyze_stocks(self, intraday=intraday)

    async def _analyze_futures(self) -> tuple[FuturesTradingPlan | None, dict]:
        """선물 분석"""
        logger.info("Starting futures analysis")

        missing_sources: list[str] = []

        def _record_missing(err: DataUnavailableError):
            label = err.source if not err.detail else f"{err.source}:{err.detail}"
            missing_sources.append(label)

        global_data = self._collect_futures_global(_record_missing)
        events, high_events = self._collect_futures_events(_record_missing)
        flow_data = self._collect_futures_flow(_record_missing, missing_sources)
        technical = self._collect_futures_technical(_record_missing)
        overall_score = self._compute_futures_score(global_data, flow_data, technical, high_events)
        overall_bias = self._determine_futures_bias(overall_score)

        direction, confidence, entry, stop_loss, take_profit, entry_cond = self._build_futures_strategy(
            overall_score, technical
        )

        position = "풀" if confidence == "높음" else "하프" if confidence == "중간" else "쿼터"
        time_horizon = "장중" if high_events else "오버나이트"

        catalysts, risks = self._build_futures_catalysts_and_risks(
            global_data,
            flow_data,
            high_events,
            technical,
            missing_sources,
        )

        plan = self._build_futures_plan(
            technical,
            direction,
            confidence,
            entry_cond,
            entry,
            stop_loss,
            take_profit,
            position,
            time_horizon,
            risks,
            catalysts,
        )

        analysis_data = self._build_futures_analysis_data(
            overall_score,
            overall_bias,
            global_data,
            flow_data,
            technical,
            events,
            missing_sources,
        )

        logger.info(f"Futures recommendation: {direction} ({confidence})")
        return plan, analysis_data

    def _collect_futures_global(
        self,
        record_missing,
    ) -> Optional[Any]:
        try:
            return self.futures_global_collector.collect()
        except DataUnavailableError as e:
            record_missing(e)
        return None

    def _collect_futures_events(
        self,
        record_missing,
    ) -> tuple[List[Any], List[Any]]:
        try:
            events = self.futures_event_collector.collect()
            high_events = [e for e in events if e.importance == "높음"]
            return events, high_events
        except DataUnavailableError as e:
            record_missing(e)
        return [], []

    def _collect_futures_flow(
        self,
        record_missing,
        missing_sources: List[str],
    ) -> Optional[Any]:
        try:
            flow_data, flow_missing = self.futures_flow_collector.collect()
            missing_sources.extend([f"futures_flow:{m}" for m in flow_missing])
            return flow_data
        except DataUnavailableError as e:
            record_missing(e)
        return None

    def _collect_futures_technical(
        self,
        record_missing,
    ) -> Optional[Dict[str, Any]]:
        try:
            return self.futures_tech_analyzer.analyze()
        except DataUnavailableError as e:
            record_missing(e)
        return None

    def _compute_futures_score(
        self,
        global_data,
        flow_data,
        technical,
        high_events: List[Any],
    ) -> float:
        score_components: List[Tuple[float, float]] = []
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
        return overall_score

    @staticmethod
    def _determine_futures_bias(overall_score: float) -> MarketBias:
        if overall_score >= 30:
            return MarketBias.STRONG_BULLISH
        if overall_score >= 15:
            return MarketBias.BULLISH
        if overall_score <= -30:
            return MarketBias.STRONG_BEARISH
        if overall_score <= -15:
            return MarketBias.BEARISH
        return MarketBias.NEUTRAL

    def _build_futures_strategy(
        self,
        overall_score: float,
        technical: Optional[Dict[str, Any]],
    ) -> tuple[str, str, float, float, float, str]:
        insufficient_data = technical is None
        entry = technical["index_price"] if technical else 0.0
        if insufficient_data:
            return "관망", "낮음", entry, 0, 0, "데이터 부족으로 관망"

        if overall_score >= 25:
            confidence = "높음" if overall_score >= 40 else "중간"
            stop_loss = entry - self.config.futures_stop_loss_pt
            take_profit = entry + self.config.futures_take_profit_pt
            entry_cond = f"5일선({technical['ma5']:.2f}) 돌파 또는 시가 진입"
            return "롱", confidence, entry, stop_loss, take_profit, entry_cond

        if overall_score <= -25:
            confidence = "높음" if overall_score <= -40 else "중간"
            stop_loss = entry + self.config.futures_stop_loss_pt
            take_profit = entry - self.config.futures_take_profit_pt
            entry_cond = f"5일선({technical['ma5']:.2f}) 이탈 또는 시가 진입"
            return "숏", confidence, entry, stop_loss, take_profit, entry_cond

        return "관망", "낮음", entry, 0, 0, "조건 충족 시까지 대기"

    def _build_futures_catalysts_and_risks(
        self,
        global_data,
        flow_data,
        high_events: List[Any],
        technical: Optional[Dict[str, Any]],
        missing_sources: List[str],
    ) -> tuple[List[str], List[str]]:
        catalysts: List[str] = []
        risks: List[str] = []

        self._append_global_catalysts(global_data, catalysts)
        self._append_flow_catalysts(flow_data, catalysts)
        self._append_flow_risks(flow_data, risks)
        self._append_market_risks(global_data, high_events, technical, risks)
        self._append_missing_source_risks(missing_sources, risks)

        return catalysts, risks

    @staticmethod
    def _append_global_catalysts(global_data, catalysts: List[str]) -> None:
        if global_data and global_data.sp500_change_pct > 0.5:
            catalysts.append(f"미국 증시 강세 ({global_data.sp500_change_pct:+.1f}%)")

    @staticmethod
    def _append_flow_catalysts(flow_data, catalysts: List[str]) -> None:
        if flow_data and flow_data.foreign_futures_5d is not None and flow_data.foreign_futures_5d > 15000:
            catalysts.append(f"외국인 5일 순매수 ({flow_data.foreign_futures_5d:+,.0f})")
        if flow_data and flow_data.basis is not None and flow_data.basis < -1:
            catalysts.append(f"선물 저평가 (베이시스 {flow_data.basis:.2f}pt)")

    @staticmethod
    def _append_flow_risks(flow_data, risks: List[str]) -> None:
        if not flow_data or flow_data.microstructure_score is None:
            return
        if flow_data.microstructure_score <= -6:
            risks.append(f"단기 주문흐름 매도 우위 (점수 {flow_data.microstructure_score:+.1f})")

    @staticmethod
    def _append_market_risks(
        global_data,
        high_events: List[Any],
        technical: Optional[Dict[str, Any]],
        risks: List[str],
    ) -> None:
        if global_data and global_data.vix > 20:
            risks.append(f"VIX {global_data.vix:.1f} 상승")
        if high_events:
            risks.append(f"주요 이벤트: {high_events[0].event}")
        if technical and technical["rsi"] > 70:
            risks.append(f"RSI {technical['rsi']:.0f} 과매수")
        elif technical and technical["rsi"] < 30:
            risks.append(f"RSI {technical['rsi']:.0f} 과매도")

    @staticmethod
    def _append_missing_source_risks(missing_sources: List[str], risks: List[str]) -> None:
        if missing_sources:
            risks.append(f"데이터 누락: {', '.join(missing_sources)}")

    def _build_futures_plan(
        self,
        technical: Optional[Dict[str, Any]],
        direction: str,
        confidence: str,
        entry_cond: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        position: str,
        time_horizon: str,
        risks: List[str],
        catalysts: List[str],
    ) -> Optional[FuturesTradingPlan]:
        if technical is None:
            return None
        return FuturesTradingPlan(
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

    @staticmethod
    def _build_futures_analysis_data(
        overall_score: float,
        overall_bias: MarketBias,
        global_data,
        flow_data,
        technical,
        events: List[Any],
        missing_sources: List[str],
    ) -> Dict[str, Any]:
        return {
            "overall_score": round(overall_score, 1),
            "overall_bias": overall_bias.value,
            "global": asdict(global_data) if global_data else None,
            "flow": asdict(flow_data) if flow_data else None,
            "technical": technical,
            "events": [asdict(e) for e in events[:5]] if events else [],
            "missing_sources": missing_sources,
        }

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
    notifier=None,
    mode: str = "all",
    send_telegram: bool = True,
    *,
    intraday: bool = False,
) -> tuple[list[StockTradingPlan], FuturesTradingPlan | None, dict]:
    """Convenience function for unified analysis"""
    analyzer = get_unified_analyzer(notifier=notifier)
    return await analyzer.run_full_analysis(
        mode=mode, send_telegram=send_telegram, intraday=intraday
    )


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
