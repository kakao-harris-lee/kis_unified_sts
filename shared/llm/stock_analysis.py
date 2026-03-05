"""Stock analysis pipeline and detailed briefing.

The two largest analysis functions extracted from UnifiedTradingAnalyzer:
``analyze_stocks`` (screening → scoring → plan generation) and
``generate_detailed_briefing`` (single-stock deep dive).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from .data_classes import (
    BacktestResult,
    Signal,
    StockDetailedBriefing,
    StockInfo,
    StockTradingPlan,
)
from .llm_scoring import collect_target_price_signal, llm_score_candidate
from .stock_screening import (
    calc_atr_pct,
    calc_consecutive_up,
    calc_max_drawdown,
    calc_momentum_metrics,
    find_keyword_hits,
    name_exclusion_reasons,
    score_stock_candidate,
    score_theme_relevance,
)

if TYPE_CHECKING:
    from .llm_analyzer import UnifiedTradingAnalyzer

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Full stock analysis pipeline
# ------------------------------------------------------------------


def _collect_market_frames(
    analyzer: "UnifiedTradingAnalyzer",
) -> tuple[list["pd.DataFrame"], list[str]]:
    market_kospi = analyzer.stock_collector.collect("KOSPI")
    market_kosdaq = analyzer.stock_collector.collect("KOSDAQ")
    frames: list["pd.DataFrame"] = []
    markets: list[str] = []
    if market_kospi is not None and len(market_kospi) > 0:
        frames.append(market_kospi)
        markets.append("KOSPI")
    if market_kosdaq is not None and len(market_kosdaq) > 0:
        frames.append(market_kosdaq)
        markets.append("KOSDAQ")
    return frames, markets


def _merge_market_frames(
    frames: list["pd.DataFrame"],
) -> Optional["pd.DataFrame"]:
    if not frames:
        return None
    if len(frames) == 1:
        return frames[0]
    return pd.concat(frames, axis=0)


def _prepare_market_df(
    market_df: "pd.DataFrame",
) -> tuple[Optional["pd.DataFrame"], bool, Optional[dict]]:
    if market_df is None or len(market_df) == 0:
        logger.error("Failed to collect market data")
        return None, False, None

    required_cols = ["종가", "시가", "거래량", "시가총액"]
    missing_cols = [c for c in required_cols if c not in market_df.columns]
    if missing_cols:
        logger.error(f"Market data missing columns: {missing_cols}")
        return None, False, {
            "_excluded": {"_error": [f"missing_columns:{','.join(missing_cols)}"]}
        }

    trade_value_fallback = False
    if "거래대금" not in market_df.columns:
        trade_value_fallback = True
        market_df = market_df.copy()
        market_df["거래대금"] = market_df["종가"] * market_df["거래량"]

    market_df["거래대금"] = pd.to_numeric(market_df["거래대금"], errors="coerce")
    market_df["시가총액"] = pd.to_numeric(market_df["시가총액"], errors="coerce")
    market_df["거래량"] = pd.to_numeric(market_df["거래량"], errors="coerce")
    market_df = market_df.dropna(
        subset=["거래대금", "시가총액", "거래량", "종가", "시가"]
    )
    return market_df, trade_value_fallback, None


def _filter_market_df(
    market_df: "pd.DataFrame",
    config,
) -> "pd.DataFrame":
    filtered = market_df[
        (market_df["종가"] >= config.stock_min_price)
        & (market_df["시가총액"] >= config.stock_min_market_cap)
        & (market_df["시가총액"] <= config.stock_max_market_cap)
        & (market_df["거래대금"] >= config.stock_min_trade_value)
    ].copy()

    filtered["거래대금비율"] = filtered["거래대금"] / filtered["시가총액"].replace(
        0, np.nan
    )
    filtered = filtered[filtered["거래대금비율"] >= config.stock_min_turnover]
    filtered["등락률"] = (filtered["종가"] - filtered["시가"]) / filtered["시가"] * 100
    return filtered


def _load_sector_theme_data(
    analyzer: "UnifiedTradingAnalyzer",
    markets: list[str],
) -> tuple[dict[str, str], dict[str, str]]:
    sector_classifications: dict[str, str] = {}
    sector_rotation: dict[str, str] = {}
    try:
        from .market_analyzers import ETFFlowAnalyzer

        etf_flows = ETFFlowAnalyzer(analyzer.config).analyze()
        sector_rotation = {e.sector: e.signal for e in etf_flows}
        logger.info(
            f"Theme data loaded: {len(sector_classifications)} stocks, "
            f"{len(sector_rotation)} sector signals"
        )
    except Exception as e:
        logger.warning(f"Theme/sector data collection failed (scoring disabled): {e}")
    return sector_classifications, sector_rotation


def _collect_krx_market_data(analyzer: "UnifiedTradingAnalyzer") -> dict[str, Any]:
    krx_data: dict[str, Any] = {}
    try:
        krx_data = analyzer.krx_collector.collect()
        logger.info("KRX investor/program trading data collected")
    except Exception as e:
        logger.warning(f"KRX data collection failed: {e}")
    return krx_data


def _build_screened_stocks(
    analyzer: "UnifiedTradingAnalyzer",
    top_volume: "pd.DataFrame",
    config,
) -> tuple[list[StockInfo], dict[str, list[str]], dict[str, dict[str, Any]]]:
    stocks: list[StockInfo] = []
    excluded: dict[str, list[str]] = {}
    excluded_features: dict[str, dict[str, Any]] = {}
    for code in top_volume.index:
        row = top_volume.loc[code]
        name = analyzer.stock_collector.get_stock_name(code)
        name_exclusions = name_exclusion_reasons(name, config)
        if name_exclusions:
            excluded[code] = name_exclusions
            excluded_features[code] = {
                "price": float(row.get("종가", 0)),
                "change_pct": float(row.get("등락률", 0)),
                "volume": float(row.get("거래량", 0)),
                "market_cap": float(row.get("시가총액", 0)),
                "trade_value": float(row.get("거래대금", 0)),
                "turnover": float(row.get("거래대금비율", 0)),
            }
            continue
        stocks.append(
            StockInfo(
                code=code,
                name=name,
                price=row["종가"],
                change_pct=round(row["등락률"], 2),
                volume=int(row["거래량"]),
                volume_ratio=1.0,
                market_cap=row["시가총액"],
                trade_value=float(row.get("거래대금", 0.0)),
                turnover=float(row.get("거래대금비율", 0.0)),
            )
        )
    return stocks, excluded, excluded_features


def _compute_liquidity_metrics(
    df: "pd.DataFrame",
    stock: StockInfo,
    config,
) -> tuple[float, float]:
    lookback = max(1, int(config.stock_volume_lookback_days))
    vol_window = df["거래량"].tail(lookback + 1)
    avg_volume = (
        float(vol_window.iloc[:-1].mean())
        if len(vol_window) > 1
        else float(vol_window.mean())
    )
    stock.volume_ratio = round(
        (stock.volume / avg_volume) if avg_volume > 0 else 1.0, 2
    )

    trade_window = df["거래대금"].tail(lookback + 1)
    avg_trade_value = (
        float(trade_window.iloc[:-1].mean())
        if len(trade_window) > 1
        else float(trade_window.mean())
    )
    return avg_volume, avg_trade_value


def _collect_mk_news(
    analyzer: "UnifiedTradingAnalyzer",
    stock: StockInfo,
    intraday: bool,
) -> dict[str, Any]:
    mk_news: dict[str, Any] = {}
    try:
        mk_news = analyzer.mk_news_collector.collect(stock.code)
        if intraday:
            # Intraday mode keeps only per-symbol headlines for lower latency and
            # to avoid repeatedly scoring the same market headlines each symbol.
            stock_news = mk_news.get("stock_news", [])
            mk_news = {
                "market_news": [],
                "stock_news": stock_news,
                "analysis": [],
                "theme_news": [],
            }
            all_news = stock_news
        else:
            all_news = mk_news.get("market_news", []) + mk_news.get("stock_news", [])
        mk_news["sentiment"] = (
            analyzer.mk_news_collector.analyze_sentiment(all_news).value
        )
    except Exception as e:
        logger.debug(f"MK news failed for {stock.code}: {e}")
    return mk_news


def _collect_dart_data(
    analyzer: "UnifiedTradingAnalyzer",
    stock: StockInfo,
    intraday: bool,
) -> dict[str, Any]:
    dart_data: dict[str, Any] = {}
    if intraday:
        return dart_data
    try:
        corp_code = analyzer._dart_corp_mapper.get_corp_code(stock.code)
        dart_data = (
            analyzer.dart_collector.collect(corp_code)
            if corp_code
            else {"error": "corp_code_not_found"}
        )
    except Exception as e:
        logger.debug(f"DART data failed for {stock.code}: {e}")
    return dart_data


def _collect_ksd_data(
    analyzer: "UnifiedTradingAnalyzer",
    stock: StockInfo,
    intraday: bool,
) -> dict[str, Any]:
    ksd_data: dict[str, Any] = {}
    if intraday:
        return ksd_data
    try:
        ksd_data = analyzer.ksd_collector.collect(stock.code)
    except Exception as e:
        logger.debug(f"KSD data failed for {stock.code}: {e}")
    return ksd_data


def _collect_krx_stock_info(
    analyzer: "UnifiedTradingAnalyzer",
    stock: StockInfo,
) -> dict[str, Any]:
    try:
        return analyzer.krx_collector.get_stock_info(stock.code) or {}
    except Exception as e:
        logger.debug(f"KRX stock info failed for {stock.code}: {e}")
        return {}


def _build_texts_to_scan(
    stock: StockInfo,
    mk_news: dict[str, Any],
    krx_stock_info: dict[str, Any],
    dart_data: dict[str, Any],
) -> list[str]:
    texts_to_scan: list[str] = [stock.name]
    texts_to_scan.extend([n.get("title", "") for n in mk_news.get("stock_news", [])])
    texts_to_scan.extend(
        [n.get("title", "") for n in mk_news.get("market_news", [])]
    )
    texts_to_scan.append(json.dumps(krx_stock_info, ensure_ascii=False, default=str))
    if dart_data.get("recent_disclosures"):
        texts_to_scan.extend(
            [
                d.get("report_nm", "")
                for d in dart_data.get("recent_disclosures", [])
            ]
        )
    return texts_to_scan


def _build_news_payload(
    analyzer: "UnifiedTradingAnalyzer",
    stock: StockInfo,
    mk_news: dict[str, Any],
    intraday: bool,
) -> dict[str, Any]:
    if intraday:
        mk_news_count = len(mk_news.get("market_news", [])) + len(
            mk_news.get("stock_news", [])
        )
        payload: dict[str, Any] = {
            "sentiment": mk_news.get("sentiment", "중립"),
            "news_count": mk_news_count,
        }
        if mk_news.get("stock_news"):
            payload["mk_headlines"] = [n.get("title") for n in mk_news["stock_news"][:3]]
        return payload

    news = analyzer.stock_news_analyzer.analyze(stock.code, stock.name)
    if mk_news.get("sentiment"):
        news["sentiment"] = mk_news["sentiment"]
    if mk_news.get("stock_news"):
        news["mk_headlines"] = [n.get("title") for n in mk_news["stock_news"][:3]]
    mk_news_count = len(mk_news.get("market_news", [])) + len(
        mk_news.get("stock_news", [])
    )
    news["news_count"] = mk_news_count
    return news


async def _build_target_signal(
    analyzer: "UnifiedTradingAnalyzer",
    stock: StockInfo,
    intraday: bool,
) -> dict[str, Any]:
    if intraday:
        return {
            "available": False,
            "target_price": 0.0,
            "latest_target_price": 0.0,
            "target_upside_pct": 0.0,
            "target_opinion": "",
            "target_date": "",
            "target_sample_count": 0,
        }
    return await collect_target_price_signal(
        analyzer, stock.code, current_price=float(stock.price)
    )


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
    is_new_listing: bool,
) -> dict[str, Any]:
    return {
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
        "target_upside_pct": round(float(target_signal["target_upside_pct"]), 2),
        "target_opinion": target_signal["target_opinion"],
        "target_date": target_signal["target_date"],
        "target_sample_count": int(target_signal["target_sample_count"]),
        "is_new_listing": is_new_listing,
    }


async def _analyze_stock_candidate(
    analyzer: "UnifiedTradingAnalyzer",
    stock: StockInfo,
    config,
    intraday: bool,
    sector_classifications: dict[str, str],
    sector_rotation: dict[str, str],
) -> tuple[
    Optional[tuple],
    Optional[dict[str, Any]],
    Optional[list[str]],
    Optional[dict[str, Any]],
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

    texts_to_scan = _build_texts_to_scan(stock, mk_news, krx_stock_info, dart_data)
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
    news = _build_news_payload(analyzer, stock, mk_news, intraday)
    target_signal = await _build_target_signal(analyzer, stock, intraday)
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
        is_new_listing,
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
    analyzer: "UnifiedTradingAnalyzer",
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
    key_events = news.get("mk_headlines", news.get("key_events", []))

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

    _append_momentum_reasons(reasons, screening)
    _append_target_price_reasons(reasons, screening)
    _append_theme_reasons(reasons, screening)

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
        target_opinion = str(screening.get("target_opinion", "")).strip()
        if target_opinion and any(
            kw in target_opinion.lower() for kw in ["매수", "buy", "outperform"]
        ):
            reasons.append(f"KIS 투자의견: {target_opinion}")


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
        top_reasons = sorted(
            reasons_tally.items(), key=lambda x: x[1], reverse=True
        )[:5]
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


async def analyze_stocks(
    analyzer: UnifiedTradingAnalyzer,
    *,
    intraday: bool = False,
) -> tuple[list[StockTradingPlan], dict]:
    """Run the stock analysis pipeline.

    Args:
        analyzer: The unified trading analyzer instance.
        intraday: If True, run lightweight mode (skip backtest, DART, KSD,
                  LLM scoring) for fast intraday refresh.
    """
    mode_label = "intraday-refresh" if intraday else "full"
    logger.info(f"Starting stock analysis ({mode_label})")

    # KOSPI + KOSDAQ (best-effort).
    frames, markets = _collect_market_frames(analyzer)
    market_df = _merge_market_frames(frames)
    market_df, trade_value_fallback, error_meta = _prepare_market_df(market_df)
    if market_df is None:
        return [], error_meta or {}

    # KRX 투자자별 거래동향 수집
    krx_data = _collect_krx_market_data(analyzer)

    config = analyzer.config

    sector_classifications, sector_rotation = _load_sector_theme_data(
        analyzer, markets
    )

    filtered = _filter_market_df(market_df, config)

    top_volume = filtered.nlargest(config.stock_top_n_volume, "거래량")

    stocks, excluded, excluded_features = _build_screened_stocks(
        analyzer, top_volume, config
    )

    logger.info(
        f"Screened {len(stocks)} stocks (excluded={len(excluded)}) from {markets}"
    )

    # 개별 분석
    candidates = []
    analysis_results = _initialize_analysis_results(excluded, excluded_features)

    for stock in stocks[: config.stock_top_n_volume]:
        (
            candidate,
            analysis_entry,
            excluded_reason,
            excluded_feature,
        ) = await _analyze_stock_candidate(
            analyzer,
            stock,
            config,
            intraday,
            sector_classifications,
            sector_rotation,
        )
        _update_analysis_results_with_candidate(
            analysis_results,
            stock,
            analysis_entry,
            excluded_reason,
            excluded_feature,
        )
        if candidate is not None:
            candidates.append(candidate)

    # KRX 데이터 추가
    _attach_market_data(analysis_results, krx_data)

    analysis_results["_screening_meta"] = _build_screening_meta(
        analysis_results,
        config,
        intraday,
        trade_value_fallback,
    )

    # LLM 스코어링 (confidence factor 보정) — intraday: skip for speed
    if config.stock_llm_scoring_enabled and candidates and not intraday:
        llm_results = await _run_llm_scoring(analyzer, candidates)
        candidates = _apply_llm_scoring_results(
            analysis_results, candidates, llm_results
        )

    # (#5) 최소 스코어 임계값 미달 후보 제거
    min_score = config.stock_min_recommendation_score
    candidates, filtered_out = _filter_candidates_by_min_score(
        candidates, min_score
    )
    if filtered_out:
        logger.info(
            f"Min score filter: {filtered_out} candidates below {min_score} removed"
        )

    # 최종 선정
    final = _select_final_candidates(candidates, config.stock_final_selection)

    # 매매 계획 생성
    plans = []
    for _score, stock, tech, best, news, _dart, _ksd, screening in final:
        plans.append(
            _build_stock_trading_plan(
                stock,
                tech,
                best,
                news,
                screening,
                config,
            )
        )

    logger.info(f"Final stock recommendations: {len(plans)}")
    return plans, analysis_results


# ------------------------------------------------------------------
# Detailed stock briefing
# ------------------------------------------------------------------


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
        risk_factors = _get_briefing_risks(
            tech, best, volume_ratio, news_sentiment
        )

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
) -> tuple[str, Optional["pd.DataFrame"]]:
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
    hist_df: "pd.DataFrame",
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
    hist_df: "pd.DataFrame",
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
