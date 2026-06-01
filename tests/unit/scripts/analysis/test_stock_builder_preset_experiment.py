from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from scripts.analysis.stock_builder_preset_experiment import (
    resolve_symbols,
    run_experiment,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]


def _fake_daily_loader(symbol: str, start: date, end: date) -> pd.DataFrame:
    dates = pd.date_range(start=start, end=end, freq="D")
    base = 100.0 if symbol == "000660" else 80.0
    close = [base + i * 1.2 for i in range(len(dates))]
    return pd.DataFrame(
        {
            "datetime": dates,
            "open": [value - 0.4 for value in close],
            "high": [value + 0.8 for value in close],
            "low": [value - 0.8 for value in close],
            "close": close,
            "volume": [1_000_000 + i * 1000 for i in range(len(dates))],
        }
    )


def test_resolve_symbols_uses_fallback_when_no_explicit_symbols():
    config = {
        "basket_source": {"type": "disabled"},
        "fallback_symbols": ["000660", "000660", "005380"],
    }

    assert resolve_symbols(config) == ["000660", "005380"]


def test_default_config_warmup_covers_52_week_preset():
    config = yaml.safe_load(
        (_REPO_ROOT / "config/stock_builder_preset_experiment.yaml").read_text(
            encoding="utf-8"
        )
    )["experiment"]
    preset_ids = {item["id"] for item in config["presets"]}

    assert "week52_high" in preset_ids
    assert config["warmup_days"] >= 420


def test_run_experiment_keeps_same_symbol_ledgers_independent():
    config = {
        "id": "unit_builder_preset_experiment",
        "start_date": "2026-03-10",
        "end_date": "2026-03-31",
        "warmup_days": 90,
        "symbols": ["000660"],
        "initial_capital": 10_000_000,
        "order_amount_per_stock": 1_000_000,
        "max_positions_per_strategy": 1,
        "min_signal_strength": 0.5,
        "costs": {
            "commission_rate": 0.00015,
            "slippage_rate": 0.0001,
            "tax_rate": 0.0023,
        },
        "presets": [
            {"id": "trend_filter"},
            {"id": "momentum"},
        ],
    }

    result = run_experiment(config, loader=_fake_daily_loader)

    summaries = {item["strategy_id"]: item for item in result["summaries"]}
    assert summaries["trend_filter"]["admitted_entries"] == 1
    assert summaries["momentum"]["admitted_entries"] == 1
    assert summaries["trend_filter"]["open_positions"] == 1
    assert summaries["momentum"]["open_positions"] == 1
    assert summaries["trend_filter"]["positions"][0]["symbol"] == "000660"
    assert summaries["momentum"]["positions"][0]["symbol"] == "000660"


def test_run_experiment_handles_cross_above_preset_with_history():
    config = {
        "id": "unit_builder_cross_experiment",
        "start_date": "2026-03-10",
        "end_date": "2026-03-31",
        "warmup_days": 90,
        "symbols": ["000660"],
        "initial_capital": 10_000_000,
        "order_amount_per_stock": 1_000_000,
        "max_positions_per_strategy": 1,
        "costs": {
            "commission_rate": 0.00015,
            "slippage_rate": 0.0001,
            "tax_rate": 0.0023,
        },
        "presets": [{"id": "golden_cross"}],
    }

    result = run_experiment(config, loader=_fake_daily_loader)

    summary = result["summaries"][0]
    assert summary["strategy_id"] == "golden_cross"
    assert summary["entry_signals"] >= 0
    assert result["data_coverage"]["000660"]["loaded"] is True
