from __future__ import annotations

import json

from scripts.analysis.futures_session_health_report import (
    MatrixSummary,
    RedisSummary,
    TradeSummary,
    _derive_issues,
    _load_matrix_summary,
)
from scripts.analysis.rl_paper_profile_matrix import parse_paper_log


def test_parse_paper_log_flags_abnormal_termination_and_unmatched_entries(tmp_path):
    log_path = tmp_path / "session.log"
    log_path.write_text(
        "\n".join(
            [
                "[matrix] profile=rl_mppo_spread6",
                "2026-04-14 10:06:00,582 - services.trading.strategy_manager - INFO - Entry signals: 1 from 1 strategies",
                "2026-04-14 10:06:00,583 - services.trading.orchestrator - INFO - Entry executed: KOSPI200선물 (A05605) @ 896.14 x 1 [strategy=rl_mppo, direction=SHORT, confidence=0.64, regime=BEAR_MODERATE, mode=slippage_guard, slippage=+1.00t]",
                "[matrix] exit_code=-9",
            ]
        ),
        encoding="utf-8",
    )

    metrics = parse_paper_log(log_path, profile="rl_mppo_spread6")

    assert metrics["exit_code"] == -9
    assert metrics["abnormal_termination"] is True
    assert metrics["unmatched_entries"] == 1


def test_load_matrix_summary_tracks_incomplete_profiles(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    summary_path = run_dir / "paper_profile_matrix_summary_20260414_154008.json"
    summary_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "profile": "rl_mppo_spread6",
                        "entry_signals": 1,
                        "entries": 1,
                        "exits": 0,
                        "blocked_total": 0,
                        "blocks_wide_spread": 0,
                        "blocks_insufficient_depth": 0,
                        "blocks_volatility_cooldown": 0,
                        "blocks_cross_asset_wide_spread": 0,
                        "abnormal_termination": True,
                        "unmatched_entries": 1,
                        "uptrend_score": -17.0,
                    },
                    {
                        "profile": "rl_mppo_profile_uptrend_spike_guard",
                        "entry_signals": 2,
                        "entries": 2,
                        "exits": 2,
                        "blocked_total": 0,
                        "blocks_wide_spread": 0,
                        "blocks_insufficient_depth": 0,
                        "blocks_volatility_cooldown": 0,
                        "blocks_cross_asset_wide_spread": 0,
                        "abnormal_termination": False,
                        "unmatched_entries": 0,
                        "uptrend_score": 8.0,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    summary = _load_matrix_summary(str(run_dir))

    assert summary.abnormal_termination_count == 1
    assert summary.unmatched_entries == 1
    assert summary.incomplete_profiles == ["rl_mppo_spread6"]


def test_derive_issues_flags_incomplete_matrix_runs():
    trade_summary = TradeSummary(
        trade_count=1,
        total_pnl=-1.0,
        avg_pnl=-1.0,
        win_rate=0.0,
        gross_win=0.0,
        gross_loss=-1.0,
        eod_count=0,
        eod_ratio=0.0,
        late_eod_count=0,
        slippage_coverage_count=1,
        slippage_coverage_ratio=100.0,
        avg_abs_slippage_ticks=1.0,
        by_exit_reason={"rl_exit": 1},
        by_strategy={
            "rl_mppo": {
                "trades": 1.0,
                "win_rate": 0.0,
                "total_pnl": -1.0,
                "avg_pnl": -1.0,
                "eod_ratio": 0.0,
            }
        },
    )
    matrix_summary = MatrixSummary(
        found=True,
        summary_path="/tmp/summary.json",
        signals=3,
        entries=3,
        exits=2,
        blocked_total=0,
        blocks_wide_spread=0,
        blocks_insufficient_depth=0,
        blocks_volatility_cooldown=0,
        blocks_cross_asset_wide_spread=0,
        fill_rate=100.0,
        spread_block_ratio=0.0,
        top_profile="rl_mppo",
        top_profile_score=1.0,
        abnormal_termination_count=1,
        unmatched_entries=1,
        incomplete_profiles=["rl_mppo_spread6"],
    )
    redis_summary = RedisSummary(
        state="stopped",
        open_positions_count=0,
        open_position_entry_days={},
        signals_count=0,
        trades_count=0,
    )

    issues = _derive_issues(trade_summary, matrix_summary, redis_summary)

    assert any("ended abnormally" in item for item in issues)
    assert any("unmatched entries" in item for item in issues)
    assert any("Incomplete matrix profiles detected" in item for item in issues)
