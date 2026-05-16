from __future__ import annotations

import csv
import json
from pathlib import Path

import scripts.analysis.evaluate_stock_strategy_candidates as mod


def _targets(**overrides):
    data = {
        "min_closed_trades": 3,
        "min_windows": 2,
        "min_monthly_expected_return_pct": 10.0,
        "min_win_rate_pct": 55.0,
        "target_win_rate_max_pct": 60.0,
        "max_mdd_pct": 10.0,
        "require_positive_equity_slope": True,
        "strict_win_rate_band": True,
    }
    data.update(overrides)
    return mod.CandidateTargets(**data)


def _write_metrics(
    path: Path,
    *,
    strategy: str = "daily_pullback",
    start: str = "2026-04-17",
    end: str = "2026-05-15",
    trades: int = 5,
    monthly: float = 10.5,
    win_rate: float = 58.0,
    mdd: float = 5.0,
    overrides: list[str] | None = None,
    order_amount: float = 10_000_000.0,
) -> None:
    payload = {
        "strategy": strategy,
        "timeframe": "daily",
        "tier": "all",
        "scope_label": "all_AAA_BBB",
        "symbols_selected": ["AAA", "BBB"],
        "strategy_overrides": overrides or [],
        "start": start,
        "end": end,
        "total_trades": trades,
        "monthly_expected_return_pct": monthly,
        "win_rate": win_rate,
        "max_drawdown_pct": mdd,
        "total_return_pct": 2.0,
        "config": {
            "order_amount_per_stock": order_amount,
            "max_positions": 5,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_trades(path: Path, pnls: list[float]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["entry_time", "exit_time", "pnl"])
        writer.writeheader()
        for idx, pnl in enumerate(pnls):
            writer.writerow(
                {
                    "entry_time": f"2026-05-{idx + 1:02d}T09:00:00",
                    "exit_time": f"2026-05-{idx + 1:02d}T15:00:00",
                    "pnl": pnl,
                }
            )


def test_equity_shape_requires_positive_slope_and_ending_equity(tmp_path):
    up = tmp_path / "up_trades.csv"
    down = tmp_path / "down_trades.csv"
    _write_trades(up, [100.0, -20.0, 80.0])
    _write_trades(down, [100.0, -120.0, -20.0])

    up_slope, up_verdict = mod._equity_shape_from_trades(up)
    down_slope, down_verdict = mod._equity_shape_from_trades(down)

    assert up_slope > 0
    assert up_verdict is True
    assert down_slope < 0
    assert down_verdict is False


def test_evaluate_metrics_file_flags_objective_gaps(tmp_path):
    metrics = tmp_path / "candidate_metrics.json"
    trades = tmp_path / "candidate_trades.csv"
    _write_metrics(metrics, trades=2, monthly=8.0, win_rate=50.0, mdd=12.0)
    _write_trades(trades, [100.0, -200.0])

    _, window = mod.evaluate_metrics_file(metrics, _targets())
    codes = {issue.code for issue in window.issues}

    assert window.verdict == "FAIL"
    assert "insufficient_closed_trades" in codes
    assert "monthly_expected_return_below_target" in codes
    assert "win_rate_below_target" in codes
    assert "mdd_above_target" in codes
    assert "equity_curve_not_upward" in codes


def test_strict_win_rate_band_can_fail_high_win_rate(tmp_path):
    metrics = tmp_path / "candidate_metrics.json"
    trades = tmp_path / "candidate_trades.csv"
    _write_metrics(metrics, win_rate=100.0)
    _write_trades(trades, [100.0, 120.0, 80.0, 90.0, 110.0])

    _, strict = mod.evaluate_metrics_file(metrics, _targets(strict_win_rate_band=True))
    _, loose = mod.evaluate_metrics_file(metrics, _targets(strict_win_rate_band=False))

    assert any(
        issue.code == "win_rate_above_target_band" and issue.severity == "FAIL"
        for issue in strict.issues
    )
    assert any(
        issue.code == "win_rate_above_target_band" and issue.severity == "WARN"
        for issue in loose.issues
    )


def test_build_reports_groups_same_candidate_across_windows(tmp_path):
    recent = tmp_path / "recent_metrics.json"
    long = tmp_path / "long_metrics.json"
    _write_metrics(recent, start="2026-04-17", end="2026-05-15")
    _write_metrics(long, start="2023-05-17", end="2026-05-15")
    _write_trades(tmp_path / "recent_trades.csv", [100.0, 80.0, -20.0, 70.0, 60.0])
    _write_trades(tmp_path / "long_trades.csv", [20.0, 30.0, -10.0, 40.0, 50.0])

    reports = mod.build_reports([recent, long], _targets())

    assert len(reports) == 1
    assert reports[0].verdict == "PASS"
    assert [w.label for w in reports[0].windows] == [
        "2023-05-17~2026-05-15",
        "2026-04-17~2026-05-15",
    ]


def test_build_reports_fails_single_window_candidates(tmp_path):
    metrics = tmp_path / "single_metrics.json"
    _write_metrics(metrics)
    _write_trades(tmp_path / "single_trades.csv", [100.0, 80.0, -20.0, 70.0, 60.0])

    reports = mod.build_reports([metrics], _targets(min_windows=2))

    assert reports[0].verdict == "FAIL"
    assert [issue.code for issue in reports[0].issues] == [
        "insufficient_backtest_windows"
    ]
