"""LLM analyzer public compatibility facade.

The implementation is split into:
- ``llm_legacy_analyzer`` for single-stock provider-backed analysis
- ``unified_trading_analyzer`` for stock/futures orchestration

Keep this module as the stable import path for existing scripts and services.
"""

from __future__ import annotations

import logging

from .data_classes import (
    AnalysisResult,
    FuturesTradingPlan,
    StockDetailedBriefing,
    StockTradingPlan,
)
from .llm_legacy_analyzer import LLMAnalyzer, LLMAnalyzerWithNotification, UnifiedConfig
from .unified_trading_analyzer import UnifiedTradingAnalyzer

logger = logging.getLogger(__name__)

__all__ = [
    "UnifiedConfig",
    "LLMAnalyzer",
    "LLMAnalyzerWithNotification",
    "UnifiedTradingAnalyzer",
    "get_llm_analyzer",
    "get_unified_analyzer",
    "analyze_stock_with_llm",
    "run_unified_analysis",
    "get_stock_detail_briefing",
]

_default_analyzer: LLMAnalyzer | None = None
_default_unified_analyzer: UnifiedTradingAnalyzer | None = None


def get_llm_analyzer() -> LLMAnalyzer:
    """Get or create default LLM analyzer instance (Legacy Compatible)."""
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = LLMAnalyzer()
    return _default_analyzer


def get_unified_analyzer(notifier=None) -> UnifiedTradingAnalyzer:
    """Get or create default unified analyzer instance."""
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
    """Convenience function for quick stock analysis (Legacy Compatible)."""
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
    """Convenience function for unified analysis."""
    analyzer = get_unified_analyzer(notifier=notifier)
    return await analyzer.run_full_analysis(
        mode=mode, send_telegram=send_telegram, intraday=intraday
    )


async def get_stock_detail_briefing(
    code: str, notifier=None, send_telegram: bool = True
) -> StockDetailedBriefing | None:
    """종목 상세 브리핑 생성 및 전송 편의 함수."""
    analyzer = get_unified_analyzer(notifier=notifier)
    briefing = analyzer.generate_detailed_briefing(code)

    if briefing and send_telegram and notifier:
        try:
            await notifier.send_message(briefing.to_telegram_message())
        except Exception as e:
            logger.warning(f"Failed to send telegram: {e}")

    return briefing
