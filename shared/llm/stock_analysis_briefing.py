"""Detailed single-stock briefing helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from .data_classes import BacktestResult, Signal, StockDetailedBriefing

if TYPE_CHECKING:
    from .unified_trading_analyzer import UnifiedTradingAnalyzer

logger = logging.getLogger("shared.llm.stock_analysis")


def generate_detailed_briefing(
    analyzer: UnifiedTradingAnalyzer,
    code: str,
) -> StockDetailedBriefing | None:
    """Generate a detailed briefing for a single stock code."""
    try:
        name, hist_df = _get_briefing_history(analyzer, code)
        if hist_df is None:
            return None

        current_price, change_pct, volume, volume_ratio = _get_briefing_price_stats(
            hist_df
        )
        market_cap = _get_briefing_market_cap(analyzer, code)

        tech = analyzer.stock_tech_analyzer.analyze(hist_df)
        best = _get_briefing_best_backtest(analyzer, hist_df)

        news_headlines, news_sentiment = _get_briefing_news(analyzer, code)
        dart_disclosures = _get_briefing_dart(analyzer, code)
        short_selling_status = _get_briefing_short_selling(analyzer, code)
        investor_trend = _get_briefing_investor_trend(analyzer)

        entry_price, stop_loss, take_profit = _get_briefing_entry_levels(
            current_price, best
        )
        confidence = _get_briefing_confidence(best)
        selection_reasons = _get_briefing_reasons(
            tech, best, volume_ratio, news_sentiment
        )
        risk_factors = _get_briefing_risks(tech, best, volume_ratio, news_sentiment)

        briefing = StockDetailedBriefing(
            code=code,
            name=name,
            generated_at=analyzer.datetime_str,
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
            investor_trend=investor_trend,
        )

        return briefing

    except Exception as e:
        logger.error(f"Error generating briefing for {code}: {e}")
        return None


def _get_briefing_history(
    analyzer: UnifiedTradingAnalyzer,
    code: str,
) -> tuple[str, pd.DataFrame | None]:
    name = analyzer.stock_collector.get_stock_name(code)
    if not name:
        logger.warning(f"Could not find stock name for {code}")
        return "", None

    hist_df = analyzer.stock_collector.get_stock_history(code, 60)
    if hist_df is None or len(hist_df) < 30:
        logger.warning(f"Insufficient history data for {code}")
        return name, None
    return name, hist_df


def _get_briefing_price_stats(
    hist_df: pd.DataFrame,
) -> tuple[float, float, int, float]:
    current_price = float(hist_df["종가"].iloc[-1])
    prev_price = float(hist_df["종가"].iloc[-2])
    change_pct = (current_price - prev_price) / prev_price * 100

    volume = int(hist_df["거래량"].iloc[-1])
    avg_volume = hist_df["거래량"].mean()
    volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
    return current_price, change_pct, volume, volume_ratio


def _get_briefing_market_cap(
    analyzer: UnifiedTradingAnalyzer,
    code: str,
) -> float:
    try:
        for mkt in ("KOSPI", "KOSDAQ"):
            market_df = analyzer.stock_collector.collect(mkt)
            if market_df is not None and code in market_df.index:
                return float(market_df.loc[code, "시가총액"])
    except Exception:
        pass
    return 0.0


def _get_briefing_best_backtest(
    analyzer: UnifiedTradingAnalyzer,
    hist_df: pd.DataFrame,
) -> BacktestResult | None:
    bt_results = analyzer.stock_backtester.run_all_strategies(hist_df)
    return max(bt_results, key=lambda x: x.total_return) if bt_results else None


def _get_briefing_news(
    analyzer: UnifiedTradingAnalyzer,
    code: str,
) -> tuple[list[str], str]:
    news_headlines: list[str] = []
    news_sentiment = "중립"
    try:
        mk_news = analyzer.mk_news_collector.collect(code)
        all_news = mk_news.get("market_news", []) + mk_news.get("stock_news", [])
        news_headlines = [n.get("title", "") for n in all_news[:5]]
        news_sentiment = analyzer.mk_news_collector.analyze_sentiment(all_news).value
    except Exception:
        pass
    return news_headlines, news_sentiment


def _get_briefing_dart(
    analyzer: UnifiedTradingAnalyzer,
    code: str,
) -> list[str]:
    dart_disclosures: list[str] = []
    try:
        corp_code = analyzer._dart_corp_mapper.get_corp_code(code)
        dart_data = (
            analyzer.dart_collector.collect(corp_code)
            if corp_code
            else {"error": "corp_code_not_found"}
        )
        disclosures = dart_data.get("recent_disclosures", [])
        dart_disclosures = [d.get("report_nm", "") for d in disclosures[:3]]
    except Exception:
        pass
    return dart_disclosures


def _get_briefing_short_selling(
    analyzer: UnifiedTradingAnalyzer,
    code: str,
) -> str:
    short_selling_status = ""
    try:
        ksd_data = analyzer.ksd_collector.collect(code)
        ss = ksd_data.get("short_selling", {})
        if ss.get("status") == "available":
            short_selling_status = "공매도 가능"
    except Exception:
        pass
    return short_selling_status


def _get_briefing_investor_trend(
    analyzer: UnifiedTradingAnalyzer,
) -> str:
    investor_trend = ""
    try:
        krx_data = analyzer.krx_collector.collect()
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
    except Exception:
        pass
    return investor_trend


def _get_briefing_entry_levels(
    current_price: float,
    best: BacktestResult | None,
) -> tuple[float, float, float]:
    entry_price = current_price
    if best and "변동성" in best.strategy_name:
        sl_pct, tp_pct = 0.05, 0.08
    else:
        sl_pct, tp_pct = 0.07, 0.12
    stop_loss = entry_price * (1 - sl_pct)
    take_profit = entry_price * (1 + tp_pct)
    return entry_price, stop_loss, take_profit


def _get_briefing_confidence(best: BacktestResult | None) -> str:
    if best and best.win_rate >= 55:
        return "높음"
    if best and best.win_rate >= 48:
        return "중간"
    return "낮음"


def _get_briefing_reasons(
    tech,
    best: BacktestResult | None,
    volume_ratio: float,
    news_sentiment: str,
) -> list[str]:
    selection_reasons: list[str] = []
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
    return selection_reasons


def _get_briefing_risks(
    tech,
    best: BacktestResult | None,
    volume_ratio: float,
    news_sentiment: str,
) -> list[str]:
    risk_factors: list[str] = []
    if tech.rsi > 70:
        risk_factors.append("RSI 과매수 상태")
    if best and best.max_drawdown > 10:
        risk_factors.append(f"최대 낙폭 {best.max_drawdown:.1f}%")
    if volume_ratio < 0.5:
        risk_factors.append("거래량 부족")
    if news_sentiment in ["부정", "매우 부정"]:
        risk_factors.append(f"부정적 뉴스: {news_sentiment}")
    return risk_factors
