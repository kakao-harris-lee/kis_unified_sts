"""Unit tests for the stock strategy experiment runner (Phase 1).

Drives the real BacktestEngine over an injected synthetic daily series so the
test needs no Parquet store, and asserts the unified report schema + per-strategy
status handling (ok / skipped / error).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pandas as pd

from shared.backtest.experiment_runner import (
    ExperimentSpec,
    run_stock_experiment,
    write_experiment_report,
)

_NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _synthetic_daily(symbol: str, start, end) -> pd.DataFrame:
    """Deterministic business-day OHLCV with a gentle trend + oscillation."""
    dates = pd.bdate_range(start=start, end=end)
    rows = []
    for i, ts in enumerate(dates):
        base = 10_000 + i * 8 + 120 * math.sin(i / 6.0)
        rows.append(
            {
                "datetime": ts.to_pydatetime(),
                "code": symbol,
                "open": base,
                "high": base * 1.012,
                "low": base * 0.988,
                "close": base * (1.004 if i % 3 else 0.996),
                "volume": 100_000 + (i % 7) * 5_000,
            }
        )
    return pd.DataFrame(rows)


def _fake_loader(*, symbol, asset_class, timeframe, start, end):
    """Return synthetic daily bars for known symbols, empty for 'NODATA'."""
    if symbol == "NODATA":
        return pd.DataFrame()
    return _synthetic_daily(symbol, start, end)


def _spec(strategies, symbols=("005930", "000660")) -> ExperimentSpec:
    return ExperimentSpec.from_dict(
        {
            "id": "test_exp",
            "strategies": strategies,
            "symbols": list(symbols),
            "start": "2024-06-01",
            "end": "2026-06-01",
            "initial_capital": 10_000_000,
        }
    )


def test_runs_registry_daily_strategy_and_emits_unified_report():
    spec = _spec([{"type": "registry", "name": "pattern_pullback"}])
    report = run_stock_experiment(spec, bar_loader=_fake_loader, now=_NOW)

    assert report["experiment"]["id"] == "test_exp"
    assert report["experiment"]["start_date"] == "2024-06-01"
    # pattern_pullback is daily → runs cleanly through the engine
    status = {s["strategy_id"]: s["status"] for s in report["status_by_strategy"]}
    assert status["pattern_pullback"] == "ok"

    assert len(report["summaries"]) == 1
    summ = report["summaries"][0]
    assert summ["strategy_id"] == "pattern_pullback"
    # Unified schema carries the real-engine metrics the legacy paper-sim lacked.
    for key in ("sharpe_ratio", "max_drawdown_pct", "win_rate_pct", "final_equity"):
        assert key in summ
    assert summ["engine"] == "backtest_engine"
    assert summ["timeframe"] == "daily"

    # coverage + equity curve present for the loaded symbols
    assert report["data_coverage"]["005930"]["loaded"] is True
    assert "pattern_pullback" in report["equity_curves"]


def test_no_data_symbol_is_skipped_not_silently_dropped():
    spec = _spec([{"type": "registry", "name": "pattern_pullback"}], symbols=["NODATA"])
    report = run_stock_experiment(spec, bar_loader=_fake_loader, now=_NOW)

    status = {s["strategy_id"]: s["status"] for s in report["status_by_strategy"]}
    assert status["pattern_pullback"] == "skipped"
    assert report["summaries"] == []
    assert report["data_coverage"]["NODATA"]["loaded"] is False
    assert report["data_coverage"]["NODATA"]["error"] == "no_data"


def test_unknown_strategy_is_error_not_crash():
    spec = _spec([{"type": "registry", "name": "does_not_exist_strategy"}])
    report = run_stock_experiment(spec, bar_loader=_fake_loader, now=_NOW)

    entry = report["status_by_strategy"][0]
    assert entry["strategy_id"] == "does_not_exist_strategy"
    assert entry["status"] == "error"
    assert entry["error"]


def test_builder_type_recorded_as_skipped():
    spec = _spec([{"type": "builder", "name": "golden_cross"}])
    report = run_stock_experiment(spec, bar_loader=_fake_loader, now=_NOW)

    entry = report["status_by_strategy"][0]
    assert entry["status"] == "skipped"
    assert "builder" in (entry["error"] or "")


def test_window_resolves_from_lookback_when_dates_absent():
    spec = ExperimentSpec.from_dict(
        {
            "id": "t",
            "strategies": [{"type": "registry", "name": "pattern_pullback"}],
            "symbols": ["005930"],
            "lookback_days": 30,
        }
    )
    report = run_stock_experiment(spec, bar_loader=_fake_loader, now=_NOW)
    assert report["experiment"]["end_date"] == "2026-06-01"
    assert report["experiment"]["start_date"] == "2026-05-02"  # 30 days back


def test_write_experiment_report_roundtrip(tmp_path):
    spec = _spec([{"type": "registry", "name": "pattern_pullback"}])
    report = run_stock_experiment(spec, bar_loader=_fake_loader, now=_NOW)
    path = write_experiment_report(report, tmp_path, now=_NOW)
    assert path.exists()
    assert path.name.startswith("test_exp_20260601_")
    import json

    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["experiment"]["id"] == "test_exp"
