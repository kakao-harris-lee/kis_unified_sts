"""Stock analysis pipeline and detailed briefing facade.

Implementation is split by responsibility:
- ``stock_analysis_market``: market-frame preparation and screening seed data
- ``stock_analysis_sources``: news, disclosure, KRX/KSD, and target-price payloads
- ``stock_analysis_candidate``: per-symbol metrics and scoring
- ``stock_analysis_plan``: trading-plan and result aggregation helpers
- ``stock_analysis_pipeline``: end-to-end stock analysis orchestration
- ``stock_analysis_briefing``: single-stock detailed briefing

The public imports from this module are preserved for existing scripts and tests.
"""

from __future__ import annotations

from .stock_analysis_briefing import (
    _get_briefing_best_backtest,
    _get_briefing_confidence,
    _get_briefing_dart,
    _get_briefing_entry_levels,
    _get_briefing_history,
    _get_briefing_investor_trend,
    _get_briefing_market_cap,
    _get_briefing_news,
    _get_briefing_price_stats,
    _get_briefing_reasons,
    _get_briefing_risks,
    _get_briefing_short_selling,
    generate_detailed_briefing,
)
from .stock_analysis_candidate import (
    _analyze_stock_candidate,
    _apply_llm_scoring_results,
    _build_screening_metrics,
    _build_technical_consensus_metrics,
    _run_llm_scoring,
)
from .stock_analysis_market import (
    _analysis_failure_meta,
    _analysis_status,
    _build_screened_stocks,
    _collect_krx_market_data,
    _collect_market_frames,
    _compute_liquidity_metrics,
    _filter_market_df,
    _load_sector_theme_data,
    _merge_market_frames,
    _prepare_market_df,
)
from .stock_analysis_pipeline import analyze_stocks
from .stock_analysis_plan import (
    _append_momentum_reasons,
    _append_nps_reasons,
    _append_target_price_reasons,
    _append_technical_consensus_reasons,
    _append_theme_reasons,
    _attach_market_data,
    _build_plan_key_events,
    _build_plan_reasons,
    _build_screening_meta,
    _build_stock_trading_plan,
    _filter_candidates_by_min_score,
    _get_plan_position,
    _get_plan_price_levels,
    _initialize_analysis_results,
    _log_screening_summary,
    _select_final_candidates,
    _set_analysis_completion_status,
    _update_analysis_results_with_candidate,
)
from .stock_analysis_sources import (
    _attach_scored_news_payload,
    _build_news_payload,
    _build_target_signal,
    _build_texts_to_scan,
    _collect_dart_data,
    _collect_krx_stock_info,
    _collect_ksd_data,
    _collect_mk_news,
    _compact_scored_news_item,
)

__all__ = [
    "analyze_stocks",
    "generate_detailed_briefing",
    "_analysis_failure_meta",
    "_analysis_status",
    "_analyze_stock_candidate",
    "_apply_llm_scoring_results",
    "_append_momentum_reasons",
    "_append_nps_reasons",
    "_append_target_price_reasons",
    "_append_technical_consensus_reasons",
    "_append_theme_reasons",
    "_attach_market_data",
    "_attach_scored_news_payload",
    "_build_news_payload",
    "_build_plan_key_events",
    "_build_plan_reasons",
    "_build_screened_stocks",
    "_build_screening_meta",
    "_build_screening_metrics",
    "_build_stock_trading_plan",
    "_build_target_signal",
    "_build_technical_consensus_metrics",
    "_build_texts_to_scan",
    "_collect_dart_data",
    "_collect_krx_market_data",
    "_collect_krx_stock_info",
    "_collect_ksd_data",
    "_collect_market_frames",
    "_collect_mk_news",
    "_compact_scored_news_item",
    "_compute_liquidity_metrics",
    "_filter_candidates_by_min_score",
    "_filter_market_df",
    "_get_briefing_best_backtest",
    "_get_briefing_confidence",
    "_get_briefing_dart",
    "_get_briefing_entry_levels",
    "_get_briefing_history",
    "_get_briefing_investor_trend",
    "_get_briefing_market_cap",
    "_get_briefing_news",
    "_get_briefing_price_stats",
    "_get_briefing_reasons",
    "_get_briefing_risks",
    "_get_briefing_short_selling",
    "_get_plan_position",
    "_get_plan_price_levels",
    "_initialize_analysis_results",
    "_load_sector_theme_data",
    "_log_screening_summary",
    "_merge_market_frames",
    "_prepare_market_df",
    "_run_llm_scoring",
    "_select_final_candidates",
    "_set_analysis_completion_status",
    "_update_analysis_results_with_candidate",
]
