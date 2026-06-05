from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import scripts.analysis.stock_paper_daily_verification as mod


@pytest.fixture(autouse=True)
def _market_open(monkeypatch):
    monkeypatch.setattr(mod, "_is_market_open_now", lambda: True)


def _config(**overrides):
    base = {
        "output_dir": Path("reports/test"),
        "lookback_days": 22,
        "monthly_trading_days": 22,
        "initial_capital": 10_000_000.0,
        "notify_on_issues": False,
        "min_daily_signals": 1,
        "min_closed_trades_for_metric_gate": 5,
        "min_monthly_expected_return_pct": 10.0,
        "min_win_rate_pct": 55.0,
        "target_win_rate_max_pct": 60.0,
        "max_mdd_pct": 10.0,
        "require_positive_equity_slope": True,
        "max_reentry_churn_count": 0,
        "reentry_churn_seconds": 3600,
        "min_fresh_ratio": 0.5,
        "require_redis_status": True,
        "max_redis_status_age_seconds": 600.0,
        "require_trade_targets": True,
        "require_daily_indicators": True,
        "skip_live_redis_gates_on_non_trading_day": True,
        "redis_keys": {},
    }
    base.update(overrides)
    return mod.VerificationConfig(**base)


def _redis(**overrides):
    base = {
        "report_is_trading_day": True,
        "status_exists": True,
        "status_ttl_seconds": 86000,
        "status_age_seconds": 400.0,
        "status_updated_at": "2026-05-16T09:00:00+00:00",
        "status_publisher_pid": "12345",
        "state": "running",
        "status_config_capital": 10_000_000.0,
        "risk_initial_capital": 10_000_000.0,
        "configured_symbols": 20,
        "data_provider": {"total_symbols": 20, "fresh_count": 18},
        "data_freshness": {},
        "daily_signal_count": 3,
        "signals_list_len": 20,
        "trades_list_len": 10,
        "open_positions_count": 2,
        "candle_cache_symbols": 20,
        "trade_targets_exists": True,
        "trade_targets_count": 20,
        "universe_exists": True,
        "universe_count": 20,
        "daily_indicators_exists": True,
        "daily_indicators_count": 20,
        "daily_strategy_candidate_count": 0,
        "daily_strategy_counts": {},
    }
    base.update(overrides)
    return mod.RedisSnapshot(**base)


def _ledger(**overrides):
    base = {
        "open_positions_count": 0,
        "open_position_samples": [],
    }
    base.update(overrides)
    return mod.LedgerPositionSnapshot(**base)


def _trade(
    idx: int,
    pnl: float,
    *,
    code: str = "005930",
    strategy: str = "trend_pullback",
    entry: datetime | None = None,
    hold_minutes: int = 30,
):
    entry_date = entry or datetime(2026, 5, 1, 9, 30) + timedelta(days=idx)
    exit_date = entry_date + timedelta(minutes=hold_minutes)
    return mod.TradeRow(
        id=f"t-{idx}",
        code=code,
        name=code,
        strategy=strategy,
        side="long",
        entry_date=entry_date,
        entry_price=100_000.0,
        exit_date=exit_date,
        exit_price=101_000.0,
        quantity=10,
        pnl=pnl,
        pnl_pct=pnl / 1_000_000.0 * 100.0,
        hold_seconds=hold_minutes * 60,
        exit_reason="take_profit" if pnl > 0 else "stop_loss",
    )


def test_trade_summary_measures_objective_metrics():
    rows = [
        _trade(1, 350_000),
        _trade(2, 300_000),
        _trade(3, 250_000),
        _trade(4, -100_000),
        _trade(5, -50_000),
    ]

    metrics = mod.summarize_trades(
        rows,
        initial_capital=10_000_000.0,
        lookback_days=22,
        monthly_trading_days=22,
        reentry_churn_seconds=3600,
    )

    assert metrics.trade_count == 5
    assert metrics.win_rate_pct == 60.0
    assert metrics.total_pnl == 750_000
    assert metrics.monthly_expected_return_pct == 7.5
    assert metrics.max_drawdown_pct < 2.0
    assert metrics.equity_is_upward is True


def test_evaluate_report_flags_objective_failures():
    cfg = _config()
    metrics = mod.TradeMetrics(
        trade_count=5,
        winning_trades=2,
        losing_trades=3,
        win_rate_pct=40.0,
        monthly_expected_return_pct=-2.0,
        max_drawdown_pct=12.5,
        equity_slope_krw_per_trade=-1000.0,
        equity_is_upward=False,
    )

    issues = mod.evaluate_report(cfg, metrics, _redis(daily_signal_count=0))
    codes = {issue.code for issue in issues}

    assert "daily_signals_below_target" in codes
    assert "monthly_expected_return_below_target" in codes
    assert "win_rate_below_target" in codes
    assert "mdd_above_target" in codes
    assert "equity_curve_not_upward" in codes


def test_evaluate_report_flags_ledger_position_mismatch():
    cfg = _config()
    metrics = mod.TradeMetrics(
        trade_count=5,
        winning_trades=3,
        losing_trades=2,
        win_rate_pct=60.0,
        monthly_expected_return_pct=12.0,
        max_drawdown_pct=3.0,
        equity_slope_krw_per_trade=1000.0,
        equity_is_upward=True,
    )

    issues = mod.evaluate_report(
        cfg,
        metrics,
        _redis(open_positions_count=0),
        ledger_position_snapshot=_ledger(
            open_positions_count=1,
            open_position_samples=["108490:external:2026-05-13T12:34:44"],
        ),
    )

    assert [issue.code for issue in issues] == ["ledger_open_positions_exceed_redis"]
    assert "ledger=1 redis=0" in issues[0].observed
    assert "108490:external" in issues[0].observed


def test_non_trading_day_skips_ledger_redis_position_mismatch():
    cfg = _config()
    metrics = mod.TradeMetrics(
        trade_count=5,
        winning_trades=3,
        losing_trades=2,
        win_rate_pct=60.0,
        monthly_expected_return_pct=12.0,
        max_drawdown_pct=3.0,
        equity_slope_krw_per_trade=1000.0,
        equity_is_upward=True,
    )

    issues = mod.evaluate_report(
        cfg,
        metrics,
        _redis(report_is_trading_day=False, open_positions_count=0),
        ledger_position_snapshot=_ledger(
            open_positions_count=3,
            open_position_samples=[
                "001740:external:2026-05-22T11:42:52",
            ],
        ),
    )

    assert issues == []


def test_non_trading_day_skips_live_redis_ttl_gates():
    cfg = _config()
    metrics = mod.TradeMetrics(
        trade_count=5,
        winning_trades=3,
        losing_trades=2,
        win_rate_pct=60.0,
        monthly_expected_return_pct=12.0,
        max_drawdown_pct=3.0,
        equity_slope_krw_per_trade=1000.0,
        equity_is_upward=True,
    )

    issues = mod.evaluate_report(
        cfg,
        metrics,
        _redis(
            report_is_trading_day=False,
            status_exists=False,
            daily_signal_count=0,
            trade_targets_exists=False,
            daily_indicators_exists=False,
            data_provider={"total_symbols": 20, "fresh_count": 0},
        ),
    )

    assert issues == []


def test_non_trading_day_skip_can_be_disabled():
    cfg = _config(skip_live_redis_gates_on_non_trading_day=False)
    metrics = mod.TradeMetrics(
        trade_count=5,
        winning_trades=3,
        losing_trades=2,
        win_rate_pct=60.0,
        monthly_expected_return_pct=12.0,
        max_drawdown_pct=3.0,
        equity_slope_krw_per_trade=1000.0,
        equity_is_upward=True,
    )

    issues = mod.evaluate_report(
        cfg,
        metrics,
        _redis(
            report_is_trading_day=False,
            status_exists=False,
            daily_signal_count=0,
            trade_targets_exists=False,
            daily_indicators_exists=False,
            data_provider={"total_symbols": 20, "fresh_count": 0},
        ),
    )
    codes = {issue.code for issue in issues}

    assert "redis_status_missing" in codes
    assert "daily_signals_below_target" in codes
    assert "trade_targets_missing" in codes
    assert "daily_indicators_missing" in codes
    assert "fresh_ratio_below_target" in codes


def test_after_market_close_skips_intraday_runtime_gates(monkeypatch):
    monkeypatch.setattr(mod, "_is_market_open_now", lambda: False)
    cfg = _config()
    metrics = mod.TradeMetrics(
        trade_count=5,
        winning_trades=3,
        losing_trades=2,
        win_rate_pct=60.0,
        monthly_expected_return_pct=12.0,
        max_drawdown_pct=3.0,
        equity_slope_krw_per_trade=1000.0,
        equity_is_upward=True,
    )

    issues = mod.evaluate_report(
        cfg,
        metrics,
        _redis(
            state="stopped",
            status_age_seconds=3600.0,
            data_provider={},
            daily_signal_count=1,
        ),
    )

    codes = {issue.code for issue in issues}
    assert "runtime_not_running" not in codes
    assert "redis_status_stale" not in codes
    assert "fresh_ratio_below_target" not in codes


def test_market_open_stopped_runtime_fails(monkeypatch):
    monkeypatch.setattr(mod, "_is_market_open_now", lambda: True)
    cfg = _config()
    metrics = mod.TradeMetrics(
        trade_count=5,
        winning_trades=3,
        losing_trades=2,
        win_rate_pct=60.0,
        monthly_expected_return_pct=12.0,
        max_drawdown_pct=3.0,
        equity_slope_krw_per_trade=1000.0,
        equity_is_upward=True,
    )

    issues = mod.evaluate_report(
        cfg,
        metrics,
        _redis(state="stopped", data_provider={}),
    )

    assert "runtime_not_running" in {issue.code for issue in issues}


def test_daily_strategy_watchlist_can_satisfy_trade_target_gate():
    cfg = _config()
    metrics = mod.TradeMetrics(
        trade_count=5,
        winning_trades=3,
        losing_trades=2,
        win_rate_pct=60.0,
        monthly_expected_return_pct=12.0,
        max_drawdown_pct=3.0,
        equity_slope_krw_per_trade=1000.0,
        equity_is_upward=True,
    )

    issues = mod.evaluate_report(
        cfg,
        metrics,
        _redis(
            trade_targets_exists=False,
            daily_strategy_candidate_count=7,
            daily_strategy_counts={"daily_pullback": 6, "vr_composite": 1},
        ),
    )

    assert "trade_targets_missing" not in {issue.code for issue in issues}


def test_active_daily_watchlist_missing_fails_active_scope():
    cfg = _config(min_closed_trades_for_metric_gate=5)
    report = mod.build_report(
        config=cfg,
        report_date=date(2026, 5, 16),
        rows=[_trade(i, -100_000, strategy="momentum_breakout") for i in range(1, 6)],
        redis_snapshot=_redis(
            daily_strategy_counts={}, daily_strategy_candidate_count=0
        ),
        active_strategy_names=["daily_pullback"],
        active_daily_strategy_names=["daily_pullback"],
    )

    assert report.verdict == "FAIL"
    assert report.active_daily_candidate_count == 0
    assert any(
        issue.code == "active_daily_watchlist_missing" for issue in report.active_issues
    )


def test_active_daily_watchlist_reports_candidate_count():
    cfg = _config(min_closed_trades_for_metric_gate=5)
    report = mod.build_report(
        config=cfg,
        report_date=date(2026, 5, 16),
        rows=[],
        redis_snapshot=_redis(
            daily_strategy_counts={"daily_pullback": 6, "vr_composite": 1},
            daily_strategy_candidate_count=7,
        ),
        active_strategy_names=["daily_pullback", "vr_composite"],
        active_daily_strategy_names=["daily_pullback", "vr_composite"],
    )

    assert report.active_daily_strategy_names == ["daily_pullback", "vr_composite"]
    assert report.active_daily_candidate_count == 7
    assert "active_daily_watchlist_missing" not in {
        issue.code for issue in report.active_issues
    }


def test_daily_signal_zero_is_warn_when_active_daily_candidates_are_empty():
    cfg = _config(min_closed_trades_for_metric_gate=5)
    report = mod.build_report(
        config=cfg,
        report_date=date(2026, 5, 16),
        rows=[_trade(i, -100_000, strategy="momentum_breakout") for i in range(1, 6)],
        redis_snapshot=_redis(
            daily_signal_count=0,
            daily_strategy_counts={"pattern_pullback": 0},
            daily_strategy_candidate_count=0,
        ),
        active_strategy_names=["pattern_pullback", "williams_r"],
        active_daily_strategy_names=["pattern_pullback"],
    )

    signal_issue = next(
        issue for issue in report.issues if issue.code == "daily_signals_below_target"
    )
    assert signal_issue.severity == "WARN"
    assert report.verdict == "WARN"
    assert "active_daily_no_candidates" in {
        issue.code for issue in report.active_issues
    }


def test_activation_day_daily_signal_gate_is_warn_with_ready_candidates():
    cfg = _config(min_closed_trades_for_metric_gate=5)
    report = mod.build_report(
        config=cfg,
        report_date=date(2026, 5, 16),
        rows=[],
        redis_snapshot=_redis(
            daily_signal_count=0,
            daily_strategy_counts={"momentum_breakout": 2},
            daily_strategy_candidate_count=2,
        ),
        active_strategy_names=["momentum_breakout"],
        active_strategy_since={"momentum_breakout": datetime(2026, 5, 16, 16, 20)},
    )

    signal_issue = next(
        issue for issue in report.issues if issue.code == "daily_signals_below_target"
    )
    assert signal_issue.severity == "WARN"
    assert signal_issue.expected == "post-activation signal opportunity"
    assert report.active_daily_strategy_names == ["momentum_breakout"]
    assert report.active_daily_candidate_count == 2
    assert "active_daily_no_candidates" not in {
        issue.code for issue in report.active_issues
    }


def test_candidate_coverage_reports_missing_samples():
    coverage = mod._candidate_coverage(
        ["005930", "000660", "999999", "005930"],
        {"005930", "000660"},
    )

    assert coverage == {
        "total": 3,
        "covered": 2,
        "coverage_ratio": 0.6667,
        "missing_sample": ["999999"],
    }


def test_non_trading_day_defers_active_no_trade_gate_when_ready():
    cfg = _config(min_closed_trades_for_metric_gate=5)
    report = mod.build_report(
        config=cfg,
        report_date=date(2026, 5, 17),
        rows=[_trade(i, -100_000, strategy="momentum_breakout") for i in range(1, 6)],
        redis_snapshot=_redis(
            report_is_trading_day=False,
            daily_strategy_counts={"pattern_pullback": 1},
            daily_strategy_candidate_count=1,
        ),
        active_strategy_names=["pattern_pullback"],
        active_daily_strategy_names=["pattern_pullback"],
    )

    assert report.verdict == "PASS"
    assert report.active_daily_candidate_count == 1
    assert report.active_issues == []
    assert any(
        issue.code == "monthly_expected_return_below_target" for issue in report.issues
    )


def test_non_trading_day_still_checks_active_daily_readiness():
    cfg = _config(min_closed_trades_for_metric_gate=5)
    report = mod.build_report(
        config=cfg,
        report_date=date(2026, 5, 17),
        rows=[],
        redis_snapshot=_redis(
            report_is_trading_day=False,
            daily_strategy_counts={},
            daily_strategy_candidate_count=0,
        ),
        active_strategy_names=["pattern_pullback"],
        active_daily_strategy_names=["pattern_pullback"],
    )

    assert report.verdict == "FAIL"
    assert [issue.code for issue in report.active_issues] == [
        "active_daily_watchlist_missing"
    ]


def test_stale_redis_status_fails_on_trading_day():
    cfg = _config(max_redis_status_age_seconds=600.0)
    metrics = mod.TradeMetrics(
        trade_count=5,
        winning_trades=3,
        losing_trades=2,
        win_rate_pct=60.0,
        monthly_expected_return_pct=12.0,
        max_drawdown_pct=3.0,
        equity_slope_krw_per_trade=1000.0,
        equity_is_upward=True,
    )

    issues = mod.evaluate_report(
        cfg,
        metrics,
        _redis(status_age_seconds=1200.0),
    )

    assert any(issue.code == "redis_status_stale" for issue in issues)


def test_redis_status_without_updated_at_fails_on_trading_day():
    cfg = _config(max_redis_status_age_seconds=600.0)
    metrics = mod.TradeMetrics(
        trade_count=5,
        winning_trades=3,
        losing_trades=2,
        win_rate_pct=60.0,
        monthly_expected_return_pct=12.0,
        max_drawdown_pct=3.0,
        equity_slope_krw_per_trade=1000.0,
        equity_is_upward=True,
    )

    issues = mod.evaluate_report(
        cfg,
        metrics,
        _redis(status_updated_at=None, status_age_seconds=None),
    )

    assert any(issue.code == "redis_status_updated_at_missing" for issue in issues)


def test_invalid_redis_status_updated_at_fails_on_trading_day():
    cfg = _config(max_redis_status_age_seconds=600.0)
    metrics = mod.TradeMetrics(
        trade_count=5,
        winning_trades=3,
        losing_trades=2,
        win_rate_pct=60.0,
        monthly_expected_return_pct=12.0,
        max_drawdown_pct=3.0,
        equity_slope_krw_per_trade=1000.0,
        equity_is_upward=True,
    )

    issues = mod.evaluate_report(
        cfg,
        metrics,
        _redis(status_updated_at="not-a-date", status_age_seconds=None),
    )

    assert any(issue.code == "redis_status_updated_at_invalid" for issue in issues)


def test_risk_initial_capital_missing_fails_on_trading_day():
    cfg = _config()
    metrics = mod.TradeMetrics(
        trade_count=5,
        winning_trades=3,
        losing_trades=2,
        win_rate_pct=60.0,
        monthly_expected_return_pct=12.0,
        max_drawdown_pct=3.0,
        equity_slope_krw_per_trade=1000.0,
        equity_is_upward=True,
    )

    issues = mod.evaluate_report(cfg, metrics, _redis(risk_initial_capital=None))

    assert any(issue.code == "risk_initial_capital_missing" for issue in issues)


def test_risk_initial_capital_mismatch_fails_on_trading_day():
    cfg = _config(initial_capital=100_000_000.0)
    metrics = mod.TradeMetrics(
        trade_count=5,
        winning_trades=3,
        losing_trades=2,
        win_rate_pct=60.0,
        monthly_expected_return_pct=12.0,
        max_drawdown_pct=3.0,
        equity_slope_krw_per_trade=1000.0,
        equity_is_upward=True,
    )

    issues = mod.evaluate_report(
        cfg,
        metrics,
        _redis(
            status_config_capital=100_000_000.0,
            risk_initial_capital=10_000_000.0,
        ),
    )

    assert any(issue.code == "risk_initial_capital_mismatch" for issue in issues)


def test_runtime_capital_mismatch_fails_on_trading_day():
    cfg = _config(initial_capital=100_000_000.0)
    metrics = mod.TradeMetrics(
        trade_count=5,
        winning_trades=3,
        losing_trades=2,
        win_rate_pct=60.0,
        monthly_expected_return_pct=12.0,
        max_drawdown_pct=3.0,
        equity_slope_krw_per_trade=1000.0,
        equity_is_upward=True,
    )

    issues = mod.evaluate_report(
        cfg,
        metrics,
        _redis(
            status_config_capital=10_000_000.0,
            risk_initial_capital=10_000_000.0,
        ),
    )

    assert any(issue.code == "runtime_capital_mismatch" for issue in issues)


def test_reentry_churn_counts_same_symbol_strategy_only():
    first = _trade(1, -100_000, code="005930", strategy="trend_pullback")
    second = _trade(
        2,
        50_000,
        code="005930",
        strategy="trend_pullback",
        entry=first.exit_date + timedelta(seconds=120),
    )
    different_strategy = _trade(
        3,
        50_000,
        code="005930",
        strategy="momentum_breakout",
        entry=first.exit_date + timedelta(seconds=300),
    )

    assert mod._count_reentry_churn([first, second, different_strategy], 3600) == 1


def test_build_report_warns_when_trade_sample_is_too_small():
    cfg = _config(min_closed_trades_for_metric_gate=5)
    report = mod.build_report(
        config=cfg,
        report_date=date(2026, 5, 16),
        rows=[_trade(1, 100_000)],
        redis_snapshot=_redis(),
    )

    assert report.verdict == "WARN"
    assert [issue.code for issue in report.issues] == ["insufficient_closed_trades"]


def test_build_report_separates_active_strategy_metrics():
    cfg = _config(min_closed_trades_for_metric_gate=5)
    rows = [
        _trade(1, -500_000, strategy="momentum_breakout"),
        _trade(2, -500_000, strategy="momentum_breakout"),
        _trade(3, 450_000, strategy="trend_pullback"),
        _trade(4, 450_000, strategy="trend_pullback"),
        _trade(5, 350_000, strategy="trend_pullback"),
        _trade(6, -50_000, strategy="trend_pullback"),
        _trade(7, -50_000, strategy="trend_pullback"),
    ]

    report = mod.build_report(
        config=cfg,
        report_date=date(2026, 5, 16),
        rows=rows,
        redis_snapshot=_redis(),
        active_strategy_names=["trend_pullback"],
    )

    assert report.trade_metrics.trade_count == 7
    assert report.trade_metrics.total_pnl == 150_000
    assert report.active_strategy_names == ["trend_pullback"]
    assert report.active_trade_metrics.trade_count == 5
    assert report.active_trade_metrics.total_pnl == 1_150_000
    assert report.active_trade_metrics.win_rate_pct == 60.0
    assert report.active_issues == []
    assert "momentum_breakout" not in report.active_trade_metrics.by_strategy


def test_build_report_filters_active_strategy_metrics_after_activation():
    cfg = _config(min_closed_trades_for_metric_gate=5, target_win_rate_max_pct=100.0)
    rows = [
        *[
            _trade(
                idx,
                -100_000,
                strategy="momentum_breakout",
                entry=datetime(2026, 5, 1, 9, 30) + timedelta(days=idx),
            )
            for idx in range(1, 6)
        ],
        *[
            _trade(
                idx,
                300_000,
                strategy="momentum_breakout",
                entry=datetime(2026, 5, 11, 9, 30) + timedelta(days=idx),
            )
            for idx in range(6, 11)
        ],
    ]

    report = mod.build_report(
        config=cfg,
        report_date=date(2026, 5, 16),
        rows=rows,
        redis_snapshot=_redis(),
        active_strategy_names=["momentum_breakout"],
        active_strategy_since={"momentum_breakout": datetime(2026, 5, 10, 0, 0)},
    )

    assert report.active_strategy_since == {"momentum_breakout": "2026-05-10T00:00:00"}
    assert report.active_trade_metrics.trade_count == 5
    assert report.active_trade_metrics.total_pnl == 1_500_000
    assert report.active_issues == []
    assert report.verdict == "PASS"


def test_build_report_includes_ledger_position_snapshot_in_verdict():
    cfg = _config(min_closed_trades_for_metric_gate=5)
    rows = [
        _trade(1, 350_000),
        _trade(2, 300_000),
        _trade(3, 250_000),
        _trade(4, -100_000),
        _trade(5, -50_000),
    ]

    report = mod.build_report(
        config=cfg,
        report_date=date(2026, 5, 16),
        rows=rows,
        redis_snapshot=_redis(open_positions_count=0),
        ledger_position_snapshot=_ledger(
            open_positions_count=1,
            open_position_samples=["108490:external:2026-05-13T12:34:44"],
        ),
    )

    assert report.verdict == "FAIL"
    assert report.ledger_position_snapshot.open_positions_count == 1
    assert any(
        issue.code == "ledger_open_positions_exceed_redis" for issue in report.issues
    )


def test_active_strategy_scope_warns_when_not_yet_verified():
    cfg = _config(min_closed_trades_for_metric_gate=5)
    report = mod.build_report(
        config=cfg,
        report_date=date(2026, 5, 16),
        rows=[_trade(i, -100_000, strategy="momentum_breakout") for i in range(1, 6)],
        redis_snapshot=_redis(),
        active_strategy_names=["trend_pullback"],
    )

    assert report.verdict == "WARN"
    assert [issue.code for issue in report.active_issues] == ["active_no_closed_trades"]
    assert report.active_issues[0].severity == "WARN"
    assert any(
        issue.code == "monthly_expected_return_below_target" for issue in report.issues
    )


def test_active_verdict_still_fails_operational_gates():
    cfg = _config(min_closed_trades_for_metric_gate=5)
    report = mod.build_report(
        config=cfg,
        report_date=date(2026, 5, 16),
        rows=[_trade(i, -100_000, strategy="momentum_breakout") for i in range(1, 6)],
        redis_snapshot=_redis(status_exists=False),
        active_strategy_names=["trend_pullback"],
    )

    assert report.verdict == "FAIL"
    assert any(issue.code == "redis_status_missing" for issue in report.issues)


def test_load_repo_env_uses_repo_dotenv_without_overriding_existing(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
    monkeypatch.delenv("RUNTIME_STORAGE_SQLITE_PATH", raising=False)
    monkeypatch.setenv("RUNTIME_STORAGE_BACKEND", "already-set")
    (tmp_path / ".env").write_text(
        "RUNTIME_STORAGE_SQLITE_PATH='data/runtime/paper/runtime.db'\n"
        "RUNTIME_STORAGE_BACKEND=file-backend\n",
        encoding="utf-8",
    )

    mod._load_repo_env()

    assert os.environ["RUNTIME_STORAGE_SQLITE_PATH"] == "data/runtime/paper/runtime.db"
    assert os.environ["RUNTIME_STORAGE_BACKEND"] == "already-set"


def test_load_config_default_capital_matches_stock_runtime(monkeypatch):
    monkeypatch.delenv("STOCK_PAPER_INITIAL_CAPITAL", raising=False)

    cfg = mod._load_config()

    assert cfg.initial_capital == 100_000_000.0
