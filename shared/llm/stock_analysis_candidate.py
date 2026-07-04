"""Per-symbol candidate analysis and LLM scoring helpers."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from shared.strategy.technical_consensus import (
    TechnicalConsensusConfig,
    build_technical_consensus_from_ohlcv,
)

from .data_classes import BacktestResult, StockInfo
from .institutional_signals import build_nps_ownership_signal
from .llm_scoring import llm_score_candidate
from .stock_analysis_market import _compute_liquidity_metrics
from .stock_analysis_sources import (
    _build_news_payload,
    _build_target_signal,
    _build_texts_to_scan,
    _collect_dart_data,
    _collect_krx_stock_info,
    _collect_ksd_data,
    _collect_mk_news,
)
from .stock_screening import (
    calc_atr_pct,
    calc_consecutive_up,
    calc_max_drawdown,
    calc_momentum_metrics,
    find_keyword_hits,
    score_stock_candidate,
    score_theme_relevance,
)

if TYPE_CHECKING:
    from .unified_trading_analyzer import UnifiedTradingAnalyzer

logger = logging.getLogger("shared.llm.stock_analysis")


def _build_technical_consensus_metrics(
    df: pd.DataFrame,
    config,
) -> dict[str, Any]:
    try:
        consensus_config = TechnicalConsensusConfig.from_dict(
            getattr(config, "stock_technical_consensus", {}) or {}
        )
        consensus = build_technical_consensus_from_ohlcv(
            df,
            config=consensus_config,
            volume_lookback=int(config.stock_volume_lookback_days),
        )
        return consensus.to_dict()
    except Exception as e:
        logger.debug(f"Technical consensus failed: {e}")
        return {}


def _build_screening_metrics(
    stock: StockInfo,
    avg_volume: float,
    avg_trade_value: float,
    momentum: dict[str, Any],
    consecutive_up: int,
    atr_pct_val: float,
    max_dd: float,
    volatility: float,
    risk_hits: list[str],
    target_signal: dict[str, Any],
    nps_ownership: dict[str, Any],
    is_new_listing: bool,
    technical_consensus: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = {
        "avg_volume": round(avg_volume, 2),
        "avg_trade_value": round(avg_trade_value, 2),
        "volume_ratio": stock.volume_ratio,
        "trade_value": round(stock.trade_value, 2),
        "turnover": round(stock.turnover, 6),
        "momentum": momentum,
        "consecutive_up": consecutive_up,
        "atr_pct": round(atr_pct_val, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "volatility": round(volatility, 4),
        "risk_keywords": risk_hits,
        "target_available": target_signal["available"],
        "target_price": round(float(target_signal["target_price"]), 2),
        "latest_target_price": round(float(target_signal["latest_target_price"]), 2),
        "latest_target_upside_pct": round(
            float(target_signal.get("latest_target_upside_pct", 0.0)), 2
        ),
        "target_upside_pct": round(float(target_signal["target_upside_pct"]), 2),
        "target_opinion": target_signal["target_opinion"],
        "target_date": target_signal["target_date"],
        "target_latest_broker": target_signal.get("target_latest_broker", ""),
        "target_sample_count": int(target_signal["target_sample_count"]),
        "target_coverage_count": int(target_signal.get("target_coverage_count", 0)),
        "target_dispersion_pct": round(
            float(target_signal.get("target_dispersion_pct", 0.0)), 2
        ),
        "target_revision_30d_pct": round(
            float(target_signal.get("target_revision_30d_pct", 0.0)), 2
        ),
        "target_revision_direction": target_signal.get("target_revision_direction", ""),
        "target_staleness_days": int(target_signal.get("target_staleness_days", 0)),
        "target_opinion_distribution": target_signal.get(
            "target_opinion_distribution", {}
        ),
        "target_recent_reports": target_signal.get("target_recent_reports", []),
        "nps_ownership": nps_ownership,
        "is_new_listing": is_new_listing,
    }
    if technical_consensus:
        metrics["technical_consensus"] = technical_consensus
    return metrics


async def _analyze_stock_candidate(
    analyzer: UnifiedTradingAnalyzer,
    stock: StockInfo,
    config,
    intraday: bool,
    sector_classifications: dict[str, str],
    sector_rotation: dict[str, str],
    scored_news: list[dict[str, Any]] | None = None,
) -> tuple[
    tuple | None,
    dict[str, Any] | None,
    list[str] | None,
    dict[str, Any] | None,
]:
    history_days = max(
        int(config.stock_backtest_days),
        int(config.stock_history_days),
        int(config.stock_momentum_lookback_days),
    )
    df = analyzer.stock_collector.get_stock_history(stock.code, history_days)
    history_len = 0 if df is None else len(df)

    if df is None or history_len < int(config.stock_new_listing_min_days):
        return (
            None,
            None,
            [f"history_insufficient:{history_len}"],
            {
                "price": stock.price,
                "change_pct": stock.change_pct,
                "volume": stock.volume,
                "market_cap": stock.market_cap,
                "trade_value": stock.trade_value,
                "turnover": stock.turnover,
            },
        )

    is_new_listing = False
    if history_len < int(config.stock_min_history_days):
        is_new_listing = True
        logger.info(
            f"New listing detected: {stock.code} ({stock.name}), "
            f"history={history_len}d"
        )

    required_hist_cols = ["종가", "고가", "저가", "거래량"]
    missing_hist_cols = [c for c in required_hist_cols if c not in df.columns]
    if missing_hist_cols:
        return (
            None,
            None,
            [f"history_missing:{','.join(missing_hist_cols)}"],
            {
                "price": stock.price,
                "change_pct": stock.change_pct,
                "volume": stock.volume,
                "market_cap": stock.market_cap,
                "trade_value": stock.trade_value,
                "turnover": stock.turnover,
            },
        )

    if "거래대금" not in df.columns:
        df["거래대금"] = df["종가"] * df["거래량"]

    avg_volume, avg_trade_value = _compute_liquidity_metrics(df, stock, config)
    if avg_trade_value < float(config.stock_min_trade_value):
        return (
            None,
            None,
            [f"min_avg_trade_value:{int(avg_trade_value)}"],
            {
                "avg_volume": round(avg_volume, 2),
                "avg_trade_value": round(avg_trade_value, 2),
                "price": stock.price,
                "volume": stock.volume,
                "trade_value": stock.trade_value,
                "turnover": stock.turnover,
            },
        )

    close = df["종가"].astype(float)
    returns = close.pct_change()
    momentum = calc_momentum_metrics(close, int(config.stock_momentum_lookback_days))
    consecutive_up = calc_consecutive_up(returns)
    atr_pct_val = calc_atr_pct(df)
    max_dd = calc_max_drawdown(close)
    volatility = float(returns.std() * np.sqrt(252)) if returns is not None else 0.0

    tech = analyzer.stock_tech_analyzer.analyze(df)
    best: BacktestResult | None = None
    bt_results: list[BacktestResult] = []
    if not is_new_listing and not intraday:
        bt_results = analyzer.stock_backtester.run_all_strategies(df)
        if bt_results:
            best = max(bt_results, key=lambda x: x.total_return)

    mk_news = _collect_mk_news(analyzer, stock, intraday)
    dart_data = _collect_dart_data(analyzer, stock, intraday)
    ksd_data = _collect_ksd_data(analyzer, stock, intraday)
    krx_stock_info = _collect_krx_stock_info(analyzer, stock)

    texts_to_scan = _build_texts_to_scan(
        stock, mk_news, krx_stock_info, dart_data, scored_news
    )
    blacklist_hits = find_keyword_hits(texts_to_scan, config.stock_blacklist)
    keyword_hits = find_keyword_hits(texts_to_scan, config.stock_keyword_filter)
    if blacklist_hits or keyword_hits:
        reasons: list[str] = []
        reasons.extend([f"blacklist:{kw}" for kw in blacklist_hits])
        reasons.extend([f"keyword:{kw}" for kw in keyword_hits])
        excl_features: dict[str, Any] = {
            "avg_volume": round(avg_volume, 2),
            "avg_trade_value": round(avg_trade_value, 2),
            "atr_pct": round(atr_pct_val, 4),
            "max_drawdown_pct": round(max_dd, 4),
            "volatility": round(volatility, 4),
            "blacklist_hits": blacklist_hits,
            "keyword_hits": keyword_hits,
        }
        if best is not None:
            excl_features.update(
                {
                    "backtest_best_strategy": best.strategy_name,
                    "backtest_trade_count": best.trade_count,
                    "backtest_win_rate": best.win_rate,
                    "backtest_total_return": best.total_return,
                }
            )
        return None, None, reasons, excl_features

    risk_hits = find_keyword_hits(texts_to_scan, config.stock_risk_keywords)
    news = _build_news_payload(analyzer, stock, mk_news, intraday, scored_news, config)
    target_signal = await _build_target_signal(analyzer, stock, intraday)
    technical_consensus = _build_technical_consensus_metrics(df, config)
    nps_ownership = (
        build_nps_ownership_signal(dart_data, config)
        if dart_data and not dart_data.get("error")
        else {"available": False, "matched_reports": 0}
    )
    if nps_ownership.get("available"):
        dart_data["nps_ownership"] = nps_ownership
    screening_metrics = _build_screening_metrics(
        stock,
        avg_volume,
        avg_trade_value,
        momentum,
        consecutive_up,
        atr_pct_val,
        max_dd,
        volatility,
        risk_hits,
        target_signal,
        nps_ownership,
        is_new_listing,
        technical_consensus,
    )

    industry = sector_classifications.get(stock.code, "")
    theme_s, theme_matched = score_theme_relevance(industry, sector_rotation)
    screening_metrics["industry"] = industry
    screening_metrics["theme_score"] = round(theme_s, 2)
    screening_metrics["theme_matched"] = theme_matched

    screening_score, score_breakdown = score_stock_candidate(
        stock, tech, best, news, screening_metrics, config
    )

    analysis_entry = {
        "technical": asdict(tech),
        "backtest": [asdict(b) for b in bt_results],
        "news": news,
        "screening": {
            "metrics": screening_metrics,
            "score": round(screening_score, 2),
            "score_breakdown": {
                k: round(v, 2) if isinstance(v, (int, float)) else v
                for k, v in score_breakdown.items()
            },
        },
        "data_sources": {
            "mk_news": mk_news,
            "marketaux_scored_news": news.get("marketaux_scored_news", []),
            "dart": dart_data,
            "ksd": ksd_data,
            "krx_stock_info": krx_stock_info,
            "kis_target_price": target_signal,
        },
    }

    candidate = (
        screening_score,
        stock,
        tech,
        best,
        news,
        dart_data,
        ksd_data,
        screening_metrics,
    )
    return candidate, analysis_entry, None, None


async def _run_llm_scoring(
    analyzer: UnifiedTradingAnalyzer,
    candidates: list[tuple],
) -> list[Any]:
    scoring_tasks = [
        llm_score_candidate(analyzer, stock, tech, best, news, screening)
        for (
            _score,
            stock,
            tech,
            best,
            news,
            _dart,
            _ksd,
            screening,
        ) in candidates
    ]
    return await asyncio.gather(*scoring_tasks, return_exceptions=True)


def _apply_llm_scoring_results(
    analysis_results: dict[str, Any],
    candidates: list[tuple],
    llm_results: list[Any],
) -> list[tuple]:
    updated_candidates = []
    for (
        score,
        stock,
        tech,
        best,
        news,
        dart,
        ksd,
        screening,
    ), llm_result in zip(candidates, llm_results):
        if isinstance(llm_result, Exception):
            logger.warning(f"LLM scoring exception for {stock.code}: {llm_result}")
            llm_result = {
                "confidence_factor": 1.0,
                "conviction": "medium",
                "key_insight": "",
                "risk_concern": None,
                "override_recommendation": None,
            }

        if llm_result.get("override_recommendation") == "sell":
            analysis_results["_excluded"][stock.code] = [
                f"llm_veto:{llm_result.get('risk_concern', 'sell_override')}"
            ]
            continue

        adjusted_score = score * llm_result["confidence_factor"]

        if stock.code in analysis_results:
            analysis_results[stock.code]["llm_scoring"] = llm_result
            analysis_results[stock.code]["screening"]["score"] = round(
                adjusted_score, 2
            )

        updated_candidates.append(
            (adjusted_score, stock, tech, best, news, dart, ksd, screening)
        )

    return updated_candidates
