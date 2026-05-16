from __future__ import annotations

from datetime import date

import pandas as pd

import scripts.analysis.scan_stock_entry_patterns as mod


def _daily_df(code: str, rows: int = 260) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=rows, freq="D")
    base = pd.Series(range(rows), dtype=float)
    close = 100.0 + base * 0.2
    # Inject a mild pullback near the evaluation window.
    close.iloc[-40:-34] = close.iloc[-41] - 1.0
    return pd.DataFrame(
        {
            "code": code,
            "datetime": dates,
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": [1000 + (idx % 20) * 10 for idx in range(rows)],
        }
    )


def test_compute_features_adds_expected_columns():
    df = mod._compute_features(_daily_df("AAA"), (5, 10))

    assert "sma200" in df
    assert "rsi5" in df
    assert "atr_pct" in df
    assert "volume_ratio" in df
    assert "forward_return_10d" in df


def test_mask_for_conditions_supports_base_and_thresholds():
    df = mod._compute_features(_daily_df("AAA"), (5,))
    params = {
        "close_above_sma200": True,
        "atr_pct_min": 0.0,
        "rsi5_max": 100.0,
    }

    mask = mod._mask_for_conditions(df, params)

    assert mask.any()


def test_scan_patterns_uses_loader_and_ranks_results(monkeypatch, tmp_path):
    monkeypatch.setattr(
        mod,
        "STOCK_UNIVERSE",
        [
            {"code": "AAA", "name": "A", "tier": "top"},
            {"code": "BBB", "name": "B", "tier": "top"},
        ],
    )

    def loader(code: str, start: date, end: date) -> pd.DataFrame:
        assert start <= date(2025, 1, 1)
        assert end == date(2025, 9, 17)
        return _daily_df(code)

    config = {
        "output_dir": str(tmp_path),
        "start": "2025-08-01",
        "end": "2025-09-17",
        "warmup_days": 250,
        "tier": "top",
        "horizons": [5, 10],
        "rank_horizon": 5,
        "min_signals": 1,
        "round_trip_cost_pct": 0.0,
        "patterns": [
            {
                "name": "broad_uptrend",
                "description": "test",
                "base": {"close_above_sma200": True},
                "grid": {"atr_pct_min": [0.0], "rsi5_max": [100.0]},
            }
        ],
    }

    results, summary = mod.scan_patterns(config, loader=loader)

    assert summary["symbols_loaded"] == 2
    assert results
    assert results[0].name == "broad_uptrend"
    assert results[0].signals > 0
    assert results[0].rank_horizon == 5


def test_scan_patterns_empty_data_summary_is_reportable(monkeypatch):
    monkeypatch.setattr(
        mod,
        "STOCK_UNIVERSE",
        [{"code": "AAA", "name": "A", "tier": "top"}],
    )

    def loader(_code: str, _start: date, _end: date) -> pd.DataFrame:
        raise ValueError("no data")

    config = {
        "start": "2025-08-01",
        "end": "2025-09-17",
        "warmup_days": 250,
        "tier": "top",
        "horizons": [5],
        "rank_horizon": 5,
        "min_signals": 1,
        "patterns": [],
    }

    results, summary = mod.scan_patterns(config, loader=loader)
    markdown = mod._format_markdown(results, summary)

    assert results == []
    assert summary["start"] == "2025-08-01"
    assert summary["rows"] == 0
    assert "Stock Entry Pattern Scan" in markdown


def test_write_outputs_creates_json_and_markdown(tmp_path):
    result = mod.PatternResult(
        name="x",
        description="desc",
        params={"close_above_sma200": True},
        signals=3,
        unique_symbols=1,
        start="2025-01-01",
        end="2025-02-01",
        rank_horizon=5,
        rank_win_rate_pct=66.67,
        rank_avg_net_return_pct=1.2,
        rank_median_net_return_pct=1.0,
        rank_profit_factor=2.0,
        horizon_metrics={
            "5": {
                "samples": 3.0,
                "win_rate_pct": 66.67,
                "avg_net_return_pct": 1.2,
                "median_net_return_pct": 1.0,
                "profit_factor": 2.0,
            }
        },
        score=20.0,
    )
    summary = {
        "start": "2025-01-01",
        "end": "2025-02-01",
        "symbols_loaded": 1,
        "symbols_requested": 1,
        "rows": 10,
        "targets": {"rank_horizon": 5, "min_signals": 1},
    }

    json_path, md_path = mod.write_outputs([result], summary, tmp_path, top_k=1)

    assert json_path.exists()
    assert md_path.exists()
    assert "Stock Entry Pattern Scan" in md_path.read_text(encoding="utf-8")
