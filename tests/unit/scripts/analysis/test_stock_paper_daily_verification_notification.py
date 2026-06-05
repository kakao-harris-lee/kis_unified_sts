from scripts.analysis.stock_paper_daily_verification import (
    LedgerPositionSnapshot,
    GateIssue,
    RedisSnapshot,
    TradeMetrics,
    VerificationReport,
    _format_notification,
)


def _redis_snapshot() -> RedisSnapshot:
    return RedisSnapshot(
        report_is_trading_day=True,
        status_exists=True,
        status_ttl_seconds=3600,
        status_age_seconds=1.0,
        status_updated_at="2026-05-26T09:10:00+09:00",
        status_publisher_pid="123",
        state="running",
        status_config_capital=10_000_000.0,
        risk_initial_capital=10_000_000.0,
        configured_symbols=0,
        data_provider={},
        data_freshness={},
        daily_signal_count=0,
        signals_list_len=0,
        trades_list_len=0,
        open_positions_count=0,
        candle_cache_symbols=0,
        trade_targets_exists=True,
        trade_targets_count=0,
        universe_exists=True,
        universe_count=0,
        daily_indicators_exists=True,
        daily_indicators_count=0,
        daily_strategy_candidate_count=0,
        daily_strategy_counts={},
    )


def test_stock_paper_notification_escapes_gate_thresholds():
    report = VerificationReport(
        report_date="2026-05-26",
        window_start="2026-05-26T00:00:00+09:00",
        window_end="2026-05-27T00:00:00+09:00",
        generated_at="2026-05-26T10:00:00+09:00",
        verdict="WARN",
        source_errors=[],
        issues=[
            GateIssue(
                severity="WARN",
                code="daily_signal_coverage",
                observed="2/20 < current universe",
                expected=">= 10.00%",
                detail="",
            )
        ],
        trade_metrics=TradeMetrics(),
        active_strategy_names=[],
        active_daily_strategy_names=[],
        active_strategy_since={},
        active_daily_candidate_count=0,
        active_trade_metrics=TradeMetrics(),
        active_issues=[],
        redis_snapshot=_redis_snapshot(),
        ledger_position_snapshot=LedgerPositionSnapshot(),
        markdown_path="reports/daily_verification/stock/2026-05-26.md",
    )

    msg = _format_notification(report)

    assert "2/20 &lt; current universe" in msg
    assert "&gt;= 10.00%" in msg
    assert "observed <" not in msg
