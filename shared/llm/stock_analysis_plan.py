"""Trading-plan and result aggregation helpers for stock analysis."""

from __future__ import annotations

import logging
from typing import Any

from .data_classes import BacktestResult, Signal, StockInfo, StockTradingPlan
from .stock_analysis_market import _analysis_status

logger = logging.getLogger("shared.llm.stock_analysis")


def _build_stock_trading_plan(
    stock: StockInfo,
    tech,
    best: BacktestResult | None,
    news: dict[str, Any],
    screening: dict[str, Any],
    config,
) -> StockTradingPlan:
    entry = stock.price
    stop_loss, take_profit = _get_plan_price_levels(entry, best)
    position, confidence = _get_plan_position(best, config)
    reasons = _build_plan_reasons(stock, tech, best, news, screening)
    key_events = _build_plan_key_events(news)

    return StockTradingPlan(
        code=stock.code,
        name=stock.name,
        strategy=best.strategy_name if best else "new_listing",
        entry_price=round(entry, 0),
        stop_loss=round(stop_loss, 0),
        take_profit=round(take_profit, 0),
        position_size=round(position, 2),
        confidence=confidence,
        reasons=reasons,
        news_sentiment=news.get("sentiment", "중립"),
        key_events=key_events[:3] if key_events else [],
    )


def _build_plan_key_events(news: dict[str, Any]) -> list[str]:
    events: list[str] = []
    for key in ("mk_headlines", "key_events", "scored_news_headlines"):
        values = news.get(key, [])
        if not isinstance(values, list):
            continue
        for value in values:
            text = str(value or "").strip()
            if text and text not in events:
                events.append(text)
    return events


def _get_plan_price_levels(
    entry: float,
    best: BacktestResult | None,
) -> tuple[float, float]:
    if best is not None and "변동성" in best.strategy_name:
        sl_pct, tp_pct = 0.05, 0.08
    else:
        sl_pct, tp_pct = 0.07, 0.12

    stop_loss = entry * (1 - sl_pct)
    take_profit = entry * (1 + tp_pct)
    return stop_loss, take_profit


def _get_plan_position(
    best: BacktestResult | None,
    config,
) -> tuple[float, str]:
    if best is not None and best.win_rate >= 55:
        return config.stock_max_position, "높음"
    if best is not None and best.win_rate >= 48:
        return config.stock_max_position * 0.7, "중간"
    return config.stock_max_position * 0.5, "낮음"


def _build_plan_reasons(
    stock: StockInfo,
    tech,
    best: BacktestResult | None,
    news: dict[str, Any],
    screening: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if screening.get("is_new_listing"):
        reasons.append("신규 상장 종목")
    if tech.signal in [Signal.STRONG_BUY, Signal.BUY]:
        reasons.append(f"기술적 신호: {tech.signal.value}")
    if tech.rsi < 40:
        reasons.append(f"RSI 과매도 ({tech.rsi})")
    if stock.volume_ratio > 2:
        reasons.append(f"거래량 급증 ({stock.volume_ratio:.1f}배)")
    if best is not None and best.win_rate > 50:
        reasons.append(f"백테스트 승률 {best.win_rate}%")
    if news.get("sentiment") in ["긍정", "매우 긍정"]:
        reasons.append(f"뉴스 감성: {news.get('sentiment')}")
    if news.get("marketaux_scored_news"):
        top_news = news["marketaux_scored_news"][0]
        title = str(top_news.get("title", "")).strip()
        impact = float(top_news.get("impact_score", 0.0) or 0.0)
        if title:
            reasons.append(f"Marketaux 뉴스: {title[:40]} (impact {impact:.2f})")

    _append_momentum_reasons(reasons, screening)
    _append_technical_consensus_reasons(reasons, screening)
    _append_target_price_reasons(reasons, screening)
    _append_theme_reasons(reasons, screening)
    _append_nps_reasons(reasons, screening)

    return reasons


def _append_momentum_reasons(
    reasons: list[str],
    screening: dict[str, Any],
) -> None:
    momentum_data = screening.get("momentum", {})
    ret_20d = momentum_data.get("ret_20d")
    if ret_20d is not None and ret_20d > 3:
        reasons.append(f"20일 상승률 {ret_20d:.1f}%")
    high_prox = momentum_data.get("high_proximity")
    if high_prox is not None and high_prox >= 0.9:
        reasons.append(f"52주 고점 근접 ({high_prox:.0%})")
    atr_pct_v = screening.get("atr_pct")
    if atr_pct_v is not None and atr_pct_v < 0.04:
        reasons.append(f"변동성 안정 (ATR {atr_pct_v:.1%})")


def _append_target_price_reasons(
    reasons: list[str],
    screening: dict[str, Any],
) -> None:
    if screening.get("target_available"):
        target_upside = float(screening.get("target_upside_pct", 0.0))
        if target_upside >= 10.0:
            reasons.append(f"KIS 목표가 괴리 +{target_upside:.1f}%")
        revision_direction = str(screening.get("target_revision_direction", ""))
        revision_pct = float(screening.get("target_revision_30d_pct", 0.0) or 0.0)
        if revision_direction == "up" and revision_pct > 0:
            reasons.append(f"KIS 목표가 리비전 +{revision_pct:.1f}%")
        target_opinion = str(screening.get("target_opinion", "")).strip()
        if target_opinion and any(
            kw in target_opinion.lower() for kw in ["매수", "buy", "outperform"]
        ):
            reasons.append(f"KIS 투자의견: {target_opinion}")


def _append_technical_consensus_reasons(
    reasons: list[str],
    screening: dict[str, Any],
) -> None:
    consensus = screening.get("technical_consensus", {})
    if not isinstance(consensus, dict):
        return

    entry_votes = int(consensus.get("entry_vote_count", 0) or 0)
    exit_votes = int(consensus.get("exit_vote_count", 0) or 0)
    if consensus.get("entry_signal"):
        reasons.append(f"기술지표 합의 진입 신호 ({entry_votes}개)")
    if consensus.get("exit_signal"):
        reasons.append(f"기술지표 합의 청산 주의 ({exit_votes}개)")


def _append_theme_reasons(
    reasons: list[str],
    screening: dict[str, Any],
) -> None:
    theme_matched_name = screening.get("theme_matched", "")
    theme_s_val = float(screening.get("theme_score", 0.0))
    if theme_matched_name and theme_s_val > 0:
        reasons.append(f"주도 테마 연관: {theme_matched_name} ({theme_s_val:+.0f})")
    elif not theme_matched_name and theme_s_val < 0:
        reasons.append("주도 테마 미연관 (감점)")


def _append_nps_reasons(
    reasons: list[str],
    screening: dict[str, Any],
) -> None:
    signal = screening.get("nps_ownership", {})
    if not isinstance(signal, dict) or not signal.get("available"):
        return
    ratio = float(signal.get("holding_ratio_pct", 0.0) or 0.0)
    change = float(signal.get("holding_ratio_change_pctp", 0.0) or 0.0)
    reasons.append(f"국민연금 보유 {ratio:.2f}% ({change:+.2f}%p)")


def _build_screening_meta(
    analysis_results: dict[str, Any],
    config,
    intraday: bool,
    trade_value_fallback: bool,
) -> dict[str, Any]:
    excluded_counts: dict[str, int] = {}
    for _code, reasons in analysis_results.get("_excluded", {}).items():
        for reason in reasons:
            key = reason.split(":", 1)[0]
            excluded_counts[key] = excluded_counts.get(key, 0) + 1

    return {
        "mode": "intraday" if intraday else "full",
        "trade_value_fallback": trade_value_fallback,
        "excluded_count": len(analysis_results.get("_excluded", {})),
        "excluded_reasons": excluded_counts,
        "filters": {
            "min_trade_value": config.stock_min_trade_value,
            "min_turnover": config.stock_min_turnover,
            "min_history_days": config.stock_min_history_days,
            "max_atr_pct": config.stock_max_atr_pct,
            "max_drawdown_pct": config.stock_max_drawdown_pct,
            "min_backtest_trades": config.stock_min_backtest_trades,
            "min_backtest_win_rate": config.stock_min_backtest_win_rate,
            "enable_kis_target_price": config.stock_enable_kis_target_price,
            "target_lookback_days": config.stock_target_lookback_days,
        },
    }


def _filter_candidates_by_min_score(
    candidates: list[tuple],
    min_score: float,
) -> tuple[list[tuple], int]:
    pre_filter_count = len(candidates)
    filtered = [c for c in candidates if c[0] >= min_score]
    removed = pre_filter_count - len(filtered)
    return filtered, removed


def _select_final_candidates(
    candidates: list[tuple],
    final_selection: int,
) -> list[tuple]:
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[:final_selection]


def _initialize_analysis_results(
    excluded: dict[str, list[str]],
    excluded_features: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "_excluded": excluded,
        "_excluded_features": excluded_features,
    }


def _set_analysis_completion_status(
    analysis_results: dict[str, Any],
    *,
    plan_count: int,
    screened_count: int,
    candidate_count: int,
) -> None:
    if plan_count > 0:
        status = _analysis_status(
            "ok",
            "recommendations_generated",
            detail={"plan_count": plan_count},
        )
    elif screened_count == 0:
        status = _analysis_status("empty", "no_stocks_after_screening")
    elif candidate_count == 0:
        status = _analysis_status("empty", "no_candidates_after_analysis")
    else:
        status = _analysis_status(
            "empty",
            "no_candidates_after_final_filters",
            detail={"candidate_count": candidate_count},
        )
    analysis_results["_analysis_status"] = status


def _log_screening_summary(
    stocks: list[StockInfo],
    excluded: dict[str, list[str]],
    markets: list[str],
) -> None:
    logger.info(f"Screening Summary for markets: {', '.join(markets)}")
    logger.info(f" - Initial candidates passed: {len(stocks)}")
    logger.info(f" - Candidates excluded: {len(excluded)}")

    if excluded:
        # Tally up exclusion reasons
        reasons_tally: dict[str, int] = {}
        for r_list in excluded.values():
            for r in r_list:
                key = r.split(":", 1)[0]
                reasons_tally[key] = reasons_tally.get(key, 0) + 1

        # Log top 5
        top_reasons = sorted(reasons_tally.items(), key=lambda x: x[1], reverse=True)[
            :5
        ]
        reasons_msg = ", ".join([f"{k} ({v})" for k, v in top_reasons])
        logger.info(f" - Top exclusion reasons: {reasons_msg}")


def _update_analysis_results_with_candidate(
    analysis_results: dict[str, Any],
    stock: StockInfo,
    analysis_entry: dict[str, Any] | None,
    excluded_reason: list[str] | None,
    excluded_feature: dict[str, Any] | None,
) -> None:
    if excluded_reason:
        analysis_results["_excluded"][stock.code] = excluded_reason
    if excluded_feature:
        analysis_results["_excluded_features"][stock.code] = excluded_feature
    if analysis_entry is not None:
        analysis_results[stock.code] = analysis_entry


def _attach_market_data(
    analysis_results: dict[str, Any],
    krx_data: dict[str, Any],
) -> None:
    analysis_results["_market_data"] = {"krx": krx_data}
