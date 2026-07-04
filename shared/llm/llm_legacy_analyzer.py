"""Legacy-compatible single-stock LLM analyzer."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

from .analyzers import StockBacktester, StockTechnicalAnalyzer
from .collectors import StockDataCollector
from .data_classes import AnalysisResult
from .prompt_cache import LLMPromptCache, PromptCacheConfig
from .schema import normalize_analysis_result_payload

logger = logging.getLogger("shared.llm.llm_analyzer")


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
        backtest_data = self._collect_backtest_data(code, backtest_data, technical_data)

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
                    b.text for b in response.content if getattr(b, "type", "") == "text"
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
        technical: dict | None,
        backtest: dict | None,
    ) -> tuple[int, list[str], list[str]]:
        score = 0
        reasons: list[str] = []
        risks: list[str] = []
        if technical:
            score += self._fallback_score_technical(technical, reasons, risks)
        if backtest:
            score += self._fallback_score_backtest(backtest, reasons, risks)
        return score, reasons, risks

    @staticmethod
    def _fallback_score_technical(
        technical: dict, reasons: list[str], risks: list[str]
    ) -> int:
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
    def _fallback_score_backtest(
        backtest: dict, reasons: list[str], risks: list[str]
    ) -> int:
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
    def _fallback_defaults(
        reasons: list[str], risks: list[str]
    ) -> tuple[list[str], list[str]]:
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
