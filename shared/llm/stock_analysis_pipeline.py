"""Top-level stock analysis pipeline orchestration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .data_classes import StockTradingPlan
from .scored_news import collect_scored_news_for_stocks
from .stock_analysis_candidate import (
    _analyze_stock_candidate,
    _apply_llm_scoring_results,
    _run_llm_scoring,
)
from .stock_analysis_market import (
    _build_screened_stocks,
    _collect_krx_market_data,
    _collect_market_frames,
    _filter_market_df,
    _load_sector_theme_data,
    _merge_market_frames,
    _prepare_market_df,
)
from .stock_analysis_plan import (
    _attach_market_data,
    _build_screening_meta,
    _build_stock_trading_plan,
    _filter_candidates_by_min_score,
    _initialize_analysis_results,
    _select_final_candidates,
    _set_analysis_completion_status,
    _update_analysis_results_with_candidate,
)

if TYPE_CHECKING:
    from .unified_trading_analyzer import UnifiedTradingAnalyzer

logger = logging.getLogger("shared.llm.stock_analysis")


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

    sector_classifications, sector_rotation = _load_sector_theme_data(analyzer, markets)

    filtered = _filter_market_df(market_df, config)

    top_volume = filtered.nlargest(config.stock_top_n_volume, "거래량")

    stocks, excluded, excluded_features = _build_screened_stocks(
        analyzer, top_volume, config
    )
    scored_news_by_code = (
        collect_scored_news_for_stocks(stocks, config) if not intraday else {}
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
            scored_news_by_code.get(stock.code, []),
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
    candidates, filtered_out = _filter_candidates_by_min_score(candidates, min_score)
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

    _set_analysis_completion_status(
        analysis_results,
        plan_count=len(plans),
        screened_count=len(stocks),
        candidate_count=len(candidates),
    )

    logger.info(f"Final stock recommendations: {len(plans)}")
    return plans, analysis_results
