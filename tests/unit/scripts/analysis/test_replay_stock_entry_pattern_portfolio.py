from __future__ import annotations

from dataclasses import asdict

import pandas as pd

import scripts.analysis.replay_stock_entry_pattern_portfolio as mod
from scripts.analysis.scan_stock_entry_patterns import PatternResult, _compute_features


def _raw_daily(code: str, rows: int = 260) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=rows, freq="D")
    close = pd.Series([100.0 + idx * 0.2 for idx in range(rows)])
    close.iloc[-40:-35] = close.iloc[-41] - 1.5
    return pd.DataFrame(
        {
            "code": code,
            "name": code,
            "datetime": dates,
            "open": close - 0.1,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": [1000 + (idx % 20) * 20 for idx in range(rows)],
        }
    )


def _feature_data(codes: tuple[str, ...] = ("AAA", "BBB")) -> pd.DataFrame:
    frames = []
    for code in codes:
        df = _compute_features(_raw_daily(code), (5, 10))
        df = df[
            pd.to_datetime(df["datetime"]).dt.date >= pd.Timestamp("2025-08-01").date()
        ]
        frames.append(df)
    data = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["datetime", "code"])
        .reset_index(drop=True)
    )
    data["date"] = pd.to_datetime(data["datetime"]).dt.date
    data["bar_index"] = data.groupby("code").cumcount()
    for hold_days in (5, 10):
        data[f"exit_datetime_{hold_days}d"] = data.groupby("code")["datetime"].shift(
            -hold_days
        )
        data[f"exit_close_{hold_days}d"] = data.groupby("code")["close"].shift(
            -hold_days
        )
    return data


def _pattern(
    params: dict | None = None,
    *,
    name: str = "test_pullback",
    score: float = 10.0,
) -> PatternResult:
    return PatternResult(
        name=name,
        description="test",
        params=params
        or {
            "close_above_sma200": True,
            "close_below_sma20": True,
            "atr_pct_min": 0.0,
            "rsi5_max": 100.0,
        },
        signals=4,
        unique_symbols=2,
        start="2025-08-01",
        end="2025-09-17",
        rank_horizon=5,
        rank_win_rate_pct=50.0,
        rank_avg_net_return_pct=1.0,
        rank_median_net_return_pct=1.0,
        rank_profit_factor=2.0,
        horizon_metrics={},
        score=score,
    )


def test_replay_signals_applies_portfolio_constraints():
    data = _feature_data()
    spec = mod.ReplaySpec(
        hold_days=5,
        initial_capital=100_000,
        order_amount_per_stock=50_000,
        max_positions=1,
        max_daily_entries=0,
        costs=mod.ReplayCosts(
            commission_rate=0.0,
            slippage_rate=0.0,
            tax_rate=0.0,
        ),
        require_complete_horizon=True,
        entry_sort="code",
    )

    result = mod.replay_signals(data, _pattern(), spec)

    assert result.total_signals > 0
    assert result.completed_signal_candidates <= result.total_signals
    assert result.admitted_trades > 0
    assert result.rejected_max_positions > 0 or result.rejected_existing_position > 0
    assert result.max_drawdown_pct >= 0.0
    assert all(trade.run_id == spec.run_id for trade in result.trades)


def test_replay_pattern_set_deduplicates_same_day_symbol_signals():
    data = _feature_data(("AAA",))
    spec = mod.ReplaySpec(
        hold_days=5,
        initial_capital=100_000,
        order_amount_per_stock=50_000,
        max_positions=1,
        max_daily_entries=0,
        costs=mod.ReplayCosts(
            commission_rate=0.0,
            slippage_rate=0.0,
            tax_rate=0.0,
        ),
        require_complete_horizon=True,
        entry_sort="pattern_priority",
    )
    patterns = [
        _pattern(name="primary", score=20.0),
        _pattern(name="duplicate", score=30.0),
    ]

    single = mod.replay_signals(data, patterns[0], spec)
    combined = mod.replay_pattern_set(data, patterns, spec)

    assert combined.total_signals == single.total_signals * 2
    assert combined.completed_signal_candidates == single.completed_signal_candidates
    assert combined.admitted_trades == single.admitted_trades


def test_run_replay_selects_ranked_pattern(monkeypatch):
    data = _feature_data()
    scan_config = {
        "start": "2025-08-01",
        "end": "2025-09-17",
        "horizons": [5],
        "rank_horizon": 5,
        "min_signals": 1,
        "round_trip_cost_pct": 0.0,
        "patterns": [
            {
                "name": "test_pullback",
                "description": "test",
                "base": {"close_above_sma200": True, "close_below_sma20": True},
                "grid": {"atr_pct_min": [0.0], "rsi5_max": [100.0]},
            }
        ],
    }
    monkeypatch.setattr(mod, "_load_scan_config", lambda _path: scan_config)
    monkeypatch.setattr(
        mod,
        "_load_feature_data",
        lambda _cfg, *, horizons, loader: (
            data,
            {
                "symbols_requested": 2,
                "symbols_loaded": 2,
                "symbols_missing": [],
                "start": "2025-08-01",
                "end": "2025-09-17",
                "data_start": "2025-01-01",
                "rows": len(data),
            },
        ),
    )

    results, patterns, summary = mod.run_replay(
        {
            "scan_config": "unused.yaml",
            "pattern_rank": 1,
            "hold_days": [5],
            "initial_capital": 100_000,
            "order_amount_per_stock": [50_000],
            "max_positions": [1],
            "costs": {
                "commission_rate": 0.0,
                "slippage_rate": 0.0,
                "tax_rate": 0.0,
            },
        }
    )

    assert [pattern.name for pattern in patterns] == ["test_pullback"]
    assert summary["pattern_count"] == 1
    assert summary["runs"] == 1
    assert len(results) == 1
    assert results[0].admitted_trades > 0


def test_run_replay_selects_top_pattern_count(monkeypatch):
    data = _feature_data()
    patterns = [
        _pattern(name="first", score=30.0),
        _pattern(
            {
                "close_above_sma200": True,
                "atr_pct_min": 0.0,
                "rsi5_max": 100.0,
            },
            name="second",
            score=20.0,
        ),
    ]
    monkeypatch.setattr(mod, "_load_scan_config", lambda _path: {})
    monkeypatch.setattr(
        mod,
        "_load_feature_data",
        lambda _cfg, *, horizons, loader: (
            data,
            {
                "symbols_requested": 2,
                "symbols_loaded": 2,
                "symbols_missing": [],
                "start": "2025-08-01",
                "end": "2025-09-17",
                "data_start": "2025-01-01",
                "rows": len(data),
            },
        ),
    )
    monkeypatch.setattr(
        mod, "_rank_patterns", lambda _data, _cfg, *, horizons: patterns
    )

    results, selected, summary = mod.run_replay(
        {
            "scan_config": "unused.yaml",
            "pattern_rank": 0,
            "top_pattern_count": 2,
            "hold_days": [5],
            "initial_capital": 100_000,
            "order_amount_per_stock": [50_000],
            "max_positions": [1],
            "costs": {
                "commission_rate": 0.0,
                "slippage_rate": 0.0,
                "tax_rate": 0.0,
            },
        }
    )

    assert [pattern.name for pattern in selected] == ["first", "second"]
    assert summary["pattern_count"] == 2
    assert summary["pattern_label"].startswith("combo_2:")
    assert len(results) == 1


def test_run_replay_expands_entry_sort_grid(monkeypatch):
    data = _feature_data()
    monkeypatch.setattr(mod, "_load_scan_config", lambda _path: {})
    monkeypatch.setattr(
        mod,
        "_load_feature_data",
        lambda _cfg, *, horizons, loader: (
            data,
            {
                "symbols_requested": 2,
                "symbols_loaded": 2,
                "symbols_missing": [],
                "start": "2025-08-01",
                "end": "2025-09-17",
                "data_start": "2025-01-01",
                "rows": len(data),
            },
        ),
    )
    monkeypatch.setattr(
        mod,
        "_rank_patterns",
        lambda _data, _cfg, *, horizons: [_pattern(name="first")],
    )

    results, _selected, summary = mod.run_replay(
        {
            "scan_config": "unused.yaml",
            "pattern_rank": 1,
            "hold_days": [5],
            "initial_capital": 100_000,
            "order_amount_per_stock": [50_000],
            "max_positions": [1],
            "entry_sort": ["pattern_priority", "rsi5_asc"],
            "costs": {
                "commission_rate": 0.0,
                "slippage_rate": 0.0,
                "tax_rate": 0.0,
            },
        }
    )

    assert summary["runs"] == 2
    assert {result.run_id.split("|sort=")[1] for result in results} == {
        "pattern_priority",
        "rsi5_asc",
    }


def test_write_outputs_creates_json_markdown_and_trades(tmp_path):
    trade = mod.ReplayTrade(
        run_id="hold=5|order=50000|maxpos=1|sort=code",
        code="AAA",
        name="AAA",
        entry_date="2025-08-01",
        exit_date="2025-08-06",
        entry_price=100.0,
        exit_price=105.0,
        quantity=10,
        pnl=50.0,
        pnl_pct=5.0,
        exit_reason="hold_5d",
    )
    result = mod.ReplayResult(
        run_id=trade.run_id,
        hold_days=5,
        order_amount_per_stock=50_000,
        max_positions=1,
        max_daily_entries=0,
        total_signals=1,
        completed_signal_candidates=1,
        admitted_trades=1,
        skipped_incomplete_horizon=0,
        rejected_existing_position=0,
        rejected_max_positions=0,
        rejected_max_daily_entries=0,
        rejected_insufficient_cash=0,
        final_capital=100_050,
        total_return_pct=0.05,
        monthly_expected_return_pct=0.5,
        win_rate_pct=100.0,
        max_drawdown_pct=0.0,
        equity_slope=1.0,
        equity_is_upward=True,
        avg_deployed_pct=50.0,
        avg_pnl_pct=5.0,
        median_pnl_pct=5.0,
        profit_factor=float("inf"),
        trades=[trade],
    )

    json_path, md_path, trades_path = mod.write_outputs(
        [result],
        _pattern(),
        {
            "start": "2025-08-01",
            "end": "2025-09-17",
            "symbols_loaded": 1,
            "symbols_requested": 1,
        },
        tmp_path,
    )

    assert json_path.exists()
    assert md_path.exists()
    assert trades_path.exists()
    assert "Stock Entry Pattern Portfolio Replay" in md_path.read_text(encoding="utf-8")
    assert (
        pd.read_csv(trades_path).to_dict("records")[0]["code"] == asdict(trade)["code"]
    )
