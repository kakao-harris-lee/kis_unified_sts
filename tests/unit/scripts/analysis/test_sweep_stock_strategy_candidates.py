from __future__ import annotations

import subprocess
from pathlib import Path

import scripts.analysis.sweep_stock_strategy_candidates as mod


def _config(tmp_path: Path) -> dict:
    return {
        "output_dir": str(tmp_path / "backtests"),
        "gate_output_dir": str(tmp_path / "gate"),
        "portfolio_script": "scripts/analysis/backtest_portfolio.py",
        "gate_config": "stock_paper_verification.yaml",
        "python": ".venv/bin/python",
        "capital": 100_000_000,
        "tier": "all",
        "symbols": "",
        "max_symbols": 10,
        "min_windows": 2,
        "windows": [
            {"name": "recent", "start": "2026-04-17", "end": "2026-05-15"},
            {"name": "long", "start": "2023-05-17", "end": "2026-05-15"},
        ],
        "candidates": [
            {
                "name": "daily",
                "strategy": "daily_pullback",
                "order_amount_per_stock": [1_000_000, 2_000_000],
                "max_positions": [3],
                "overrides": {
                    "entry.params.min_atr_pct": [0.03, 0.04],
                    "entry.params.enabled": [True],
                    "entry.params.max_return_60d": [None],
                },
            }
        ],
    }


def test_expand_sweep_runs_builds_window_and_parameter_product(tmp_path):
    runs = mod.expand_sweep_runs(_config(tmp_path))

    assert len(runs) == 8
    assert {run.window.name for run in runs} == {"recent", "long"}
    assert {run.order_amount_per_stock for run in runs} == {1_000_000.0, 2_000_000.0}
    assert all(run.max_symbols == 10 for run in runs)


def test_build_backtest_command_uses_configured_fields(tmp_path):
    run = mod.expand_sweep_runs(_config(tmp_path))[0]

    cmd = mod.build_backtest_command(run, _config(tmp_path))

    assert cmd[:3] == [
        ".venv/bin/python",
        "scripts/analysis/backtest_portfolio.py",
        "--strategy",
    ]
    assert "--order-amount-per-stock" in cmd
    assert "--max-positions" in cmd
    assert "--max-symbols" in cmd
    assert "--set" in cmd
    assert "entry.params.enabled=true" in cmd
    assert "entry.params.max_return_60d=null" in cmd


def test_parse_backtest_paths_from_stdout():
    stdout = "return=+1.0%\nmetrics=reports/a_metrics.json\ntrades=reports/a.csv\n"

    assert mod.parse_backtest_paths(stdout) == (
        "reports/a_metrics.json",
        "reports/a.csv",
    )


def test_run_sweep_dry_run_writes_manifest_without_runner(tmp_path):
    manifest = mod.run_sweep(_config(tmp_path), dry_run=True, max_runs=2)

    assert manifest["planned_runs"] == 2
    assert manifest["successful_runs"] == 0
    assert manifest["failed_runs"] == 0
    assert Path(manifest["manifest_path"]).exists()
    assert manifest["runs"][0]["returncode"] is None


def test_run_sweep_filters_candidate_names(tmp_path):
    config = _config(tmp_path)
    config["candidates"].append(
        {
            "name": "skip_me",
            "strategy": "technical_consensus",
            "enabled": False,
            "order_amount_per_stock": [1_000_000],
            "max_positions": [1],
            "overrides": {},
        }
    )

    default_runs = mod.expand_sweep_runs(config)
    manifest = mod.run_sweep(
        config,
        dry_run=True,
        candidate_names={"skip_me"},
    )

    assert all(run.candidate_name != "skip_me" for run in default_runs)
    assert manifest["planned_runs"] == 2
    assert {run["candidate_name"] for run in manifest["runs"]} == {"skip_me"}


def test_run_sweep_executes_runner_and_records_paths(tmp_path, monkeypatch):
    metrics = tmp_path / "backtests" / "run_metrics.json"
    trades = tmp_path / "backtests" / "run_trades.csv"
    metrics.parent.mkdir(parents=True, exist_ok=True)
    metrics.write_text(
        """
        {
          "strategy": "daily_pullback",
          "timeframe": "daily",
          "tier": "all",
          "scope_label": "all_AAA",
          "symbols_selected": ["AAA"],
          "strategy_overrides": [],
          "start": "2026-04-17",
          "end": "2026-05-15",
          "total_trades": 5,
          "monthly_expected_return_pct": 10.5,
          "win_rate": 58.0,
          "max_drawdown_pct": 5.0,
          "total_return_pct": 2.0,
          "config": {"order_amount_per_stock": 1000000, "max_positions": 3}
        }
        """,
        encoding="utf-8",
    )
    trades.write_text(
        "entry_time,exit_time,pnl\n"
        "2026-05-01T09:00:00,2026-05-01T15:00:00,100\n"
        "2026-05-02T09:00:00,2026-05-02T15:00:00,90\n"
        "2026-05-03T09:00:00,2026-05-03T15:00:00,-10\n"
        "2026-05-04T09:00:00,2026-05-04T15:00:00,80\n"
        "2026-05-05T09:00:00,2026-05-05T15:00:00,70\n",
        encoding="utf-8",
    )

    def fake_runner(cmd, *, cwd, capture_output, text, check):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=f"metrics={metrics}\ntrades={trades}\n",
            stderr="",
        )

    monkeypatch.setattr(
        mod.gate,
        "load_targets",
        lambda *_args, **_kwargs: mod.gate.CandidateTargets(
            min_closed_trades=1,
            min_windows=1,
            min_monthly_expected_return_pct=10.0,
            min_win_rate_pct=55.0,
            target_win_rate_max_pct=60.0,
            max_mdd_pct=10.0,
            require_positive_equity_slope=True,
            strict_win_rate_band=True,
        ),
    )

    manifest = mod.run_sweep(
        _config(tmp_path),
        dry_run=False,
        max_runs=1,
        runner=fake_runner,
    )

    assert manifest["successful_runs"] == 1
    assert manifest["gate"]["pass_count"] == 1
    assert Path(manifest["gate"]["json_path"]).exists()
