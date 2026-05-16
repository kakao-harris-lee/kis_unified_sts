"""LLM-based scoring and target-price collection.

Async functions extracted from UnifiedTradingAnalyzer that call
external APIs (KIS invest-opinion, LLM providers).
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from .data_classes import BacktestResult, StockInfo, TechnicalAnalysis
from .prompt_cache import LLMPromptCache
from .schema import normalize_scoring_payload

if TYPE_CHECKING:
    from .llm_analyzer import UnifiedTradingAnalyzer

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# KIS target-price signal collection
# ------------------------------------------------------------------


async def collect_target_price_signal(
    analyzer: UnifiedTradingAnalyzer,
    code: str,
    current_price: float,
) -> dict[str, Any]:
    """Collect analyst target-price signal from KIS invest-opinion API."""
    base = {
        "available": False,
        "target_price": 0.0,
        "latest_target_price": 0.0,
        "latest_target_upside_pct": 0.0,
        "target_upside_pct": 0.0,
        "target_opinion": "",
        "target_date": "",
        "target_latest_broker": "",
        "target_sample_count": 0,
        "target_coverage_count": 0,
        "target_dispersion_pct": 0.0,
        "target_revision_30d_pct": 0.0,
        "target_revision_direction": "",
        "target_staleness_days": 0,
        "target_opinion_distribution": {},
        "target_recent_reports": [],
    }

    if not analyzer.config.stock_enable_kis_target_price:
        return base
    if code in analyzer._target_price_cache:
        return analyzer._target_price_cache[code]
    if not analyzer.kis_client or not analyzer.kis_client.config.is_real:
        return base

    try:
        summary = await analyzer.kis_client.summarize_target_price(
            code,
            current_price=float(current_price),
            lookback_days=int(analyzer.config.stock_target_lookback_days),
            recent_days=int(getattr(analyzer.config, "stock_target_recent_days", 30)),
        )
        signal = {
            "available": bool(summary.get("available", False)),
            "target_price": float(summary.get("target_price", 0.0)),
            "latest_target_price": float(summary.get("latest_target_price", 0.0)),
            "latest_target_upside_pct": float(
                summary.get("latest_target_upside_pct", 0.0)
            ),
            "target_upside_pct": float(summary.get("upside_pct", 0.0)),
            "target_opinion": str(summary.get("opinion", "")).strip(),
            "target_date": str(summary.get("date", "")).strip(),
            "target_latest_broker": str(summary.get("latest_broker", "")).strip(),
            "target_sample_count": int(summary.get("sample_count", 0)),
            "target_coverage_count": int(summary.get("coverage_count", 0)),
            "target_dispersion_pct": float(summary.get("dispersion_pct", 0.0)),
            "target_revision_30d_pct": float(summary.get("revision_30d_pct", 0.0)),
            "target_revision_direction": str(
                summary.get("revision_direction", "")
            ).strip(),
            "target_staleness_days": int(summary.get("staleness_days", 0)),
            "target_opinion_distribution": dict(
                summary.get("opinion_distribution", {})
            ),
            "target_recent_reports": list(summary.get("recent_reports", []))[:5],
        }
    except Exception as e:
        logger.debug(f"KIS target-price lookup failed for {code}: {e}")
        signal = base

    analyzer._target_price_cache[code] = signal
    return signal


# ------------------------------------------------------------------
# LLM confidence scoring
# ------------------------------------------------------------------


async def llm_score_candidate(
    analyzer: UnifiedTradingAnalyzer,
    stock: StockInfo,
    tech: TechnicalAnalysis,
    best: BacktestResult | None,
    news: dict[str, Any],
    screening: dict[str, Any],
) -> dict[str, Any]:
    """LLM-based conviction scoring for a stock candidate.

    Returns a dict with keys: confidence_factor, conviction, key_insight,
    risk_concern, override_recommendation.
    """
    default_result = {
        "confidence_factor": 1.0,
        "conviction": "medium",
        "key_insight": "",
        "risk_concern": None,
        "override_recommendation": None,
    }

    if not analyzer.config.stock_llm_scoring_enabled:
        return default_result

    api_key = analyzer.config.api_key
    if not api_key:
        return default_result

    # Build payload
    payload = {
        "code": stock.code,
        "name": stock.name,
        "price": float(stock.price),
        "change_pct": stock.change_pct,
        "market_cap": float(stock.market_cap),
        "volume_ratio": stock.volume_ratio,
        "trade_value": float(stock.trade_value),
        "turnover": float(stock.turnover),
        "technical": {
            "signal": tech.signal.value,
            "rsi": tech.rsi,
            "macd_hist": tech.macd_hist,
            "bb_position": tech.bb_position,
            "trend": tech.trend,
        },
        "screening": {
            "momentum": screening.get("momentum", {}),
            "atr_pct": screening.get("atr_pct"),
            "max_drawdown_pct": screening.get("max_drawdown_pct"),
            "volatility": screening.get("volatility"),
            "is_new_listing": screening.get("is_new_listing", False),
            "nps_ownership": screening.get("nps_ownership", {}),
        },
        "news_sentiment": news.get("sentiment", "중립"),
        "scored_news": news.get("marketaux_scored_news", []),
    }
    technical_consensus = screening.get("technical_consensus")
    if technical_consensus:
        payload["technical_consensus"] = technical_consensus
    if best is not None:
        payload["backtest"] = {
            "strategy": best.strategy_name,
            "win_rate": best.win_rate,
            "total_return": best.total_return,
            "trade_count": best.trade_count,
        }
    if screening.get("target_available"):
        payload["target_price"] = {
            "consensus_target": screening.get("target_price"),
            "latest_target": screening.get("latest_target_price"),
            "upside_pct": screening.get("target_upside_pct"),
            "latest_upside_pct": screening.get("latest_target_upside_pct"),
            "opinion": screening.get("target_opinion"),
            "date": screening.get("target_date"),
            "latest_broker": screening.get("target_latest_broker"),
            "coverage_count": screening.get("target_coverage_count"),
            "sample_count": screening.get("target_sample_count"),
            "dispersion_pct": screening.get("target_dispersion_pct"),
            "revision_30d_pct": screening.get("target_revision_30d_pct"),
            "revision_direction": screening.get("target_revision_direction"),
            "staleness_days": screening.get("target_staleness_days"),
            "opinion_distribution": screening.get("target_opinion_distribution", {}),
            "recent_reports": screening.get("target_recent_reports", []),
        }

    system_prompt = (
        "당신은 전문 퀀트 트레이더입니다. "
        "주어진 데이터를 기반으로 종목의 매매 확신도를 평가합니다. "
        "technical_consensus는 RSI/Williams %R/MACD 기반 타이밍 보조 신호입니다. "
        "JSON 형식으로만 응답합니다."
    )
    user_prompt = f"""다음 종목의 매매 확신도를 평가해주세요.

## 종목 데이터
{json.dumps(payload, ensure_ascii=False, indent=2)}

## 요청사항
위 데이터를 종합하여 다음 JSON 형식으로만 응답해주세요:
```json
{{
    "confidence_factor": (0.5~1.5, 1.0=중립, >1.0=확신 상승, <1.0=확신 하락),
    "conviction": ("high" | "medium" | "low"),
    "key_insight": "핵심 판단 근거 (1-2문장)",
    "risk_concern": "주요 우려사항 또는 null",
    "override_recommendation": ("strong_buy" | "buy" | "hold" | "sell" | null)
}}
```"""

    scoring_model = analyzer.config.stock_llm_scoring_model or analyzer.config.model
    scoring_max_tokens = analyzer.config.stock_llm_scoring_max_tokens
    scoring_temperature = analyzer.config.stock_llm_scoring_temperature

    cache_key = LLMPromptCache.build_key(
        key_prefix=analyzer._scoring_prompt_cache.config.key_prefix,
        provider=analyzer.config.llm_provider,
        model=scoring_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        extra={
            "temperature": scoring_temperature,
            "max_tokens": scoring_max_tokens,
        },
    )

    try:
        cached = analyzer._scoring_prompt_cache.get(cache_key)
        if cached:
            parsed = json.loads(
                re.search(r"\{[\s\S]*\}", cached).group()  # type: ignore[union-attr]
            )
            return normalize_scoring_payload(parsed)

        # Initialize client lazily
        if analyzer._scoring_client is None:
            if analyzer.config.llm_provider == "claude":
                from anthropic import AsyncAnthropic

                analyzer._scoring_client = AsyncAnthropic(api_key=api_key)
            else:
                import openai

                analyzer._scoring_client = openai.AsyncOpenAI(api_key=api_key)

        if analyzer.config.llm_provider == "claude":
            response = await analyzer._scoring_client.messages.create(
                model=scoring_model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=scoring_max_tokens,
                temperature=scoring_temperature,
            )
            text_blocks = [
                b.text for b in response.content if getattr(b, "type", "") == "text"
            ]
            result_text = "\n".join(text_blocks).strip()
        else:
            response = await analyzer._scoring_client.chat.completions.create(
                model=scoring_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=scoring_max_tokens,
                temperature=scoring_temperature,
            )
            result_text = response.choices[0].message.content or ""

        analyzer._scoring_prompt_cache.set(cache_key, result_text)

        match = re.search(r"\{[\s\S]*\}", result_text)
        if not match:
            logger.warning(f"LLM scoring: no JSON in response for {stock.code}")
            return default_result

        parsed = json.loads(match.group())
        return normalize_scoring_payload(parsed)

    except Exception as e:
        logger.warning(f"LLM scoring failed for {stock.code}: {e}")
        return default_result
