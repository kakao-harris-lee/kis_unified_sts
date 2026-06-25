"""Hermetic tests for the daily/swing CTA data-availability probe.

These exercise the pure resample / clean-run logic on synthetic minute bars.
No real Parquet data, DuckDB files, or network access are touched.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "analysis"
    / "cta_daily_data_probe.py"
)


def _load_probe():
    spec = importlib.util.spec_from_file_location("cta_daily_data_probe", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load_probe()


def _synthetic_minute(day: str, n_bars: int, base: float = 400.0) -> pd.DataFrame:
    """Build ``n_bars`` one-minute rows for a single KST session."""
    start = pd.Timestamp(f"{day} 09:00")
    idx = [start + pd.Timedelta(minutes=i) for i in range(n_bars)]
    closes = [base + i * 0.1 for i in range(n_bars)]
    return pd.DataFrame(
        {
            "datetime": idx,
            "open": closes,
            "high": [c + 0.5 for c in closes],
            "low": [c - 0.5 for c in closes],
            "close": closes,
            "volume": [10] * n_bars,
        }
    )


def test_resample_daily_aggregates_one_session_per_day():
    minute = pd.concat(
        [
            _synthetic_minute("2026-03-03", 400, base=400.0),
            _synthetic_minute("2026-03-04", 410, base=405.0),
        ],
        ignore_index=True,
    )

    daily = probe.resample_daily(minute)

    assert list(daily["date"]) == [
        pd.Timestamp("2026-03-03").date(),
        pd.Timestamp("2026-03-04").date(),
    ]
    # OHLC integrity for day 1.
    row0 = daily.iloc[0]
    assert row0["open"] == pytest.approx(400.0)
    assert row0["close"] == pytest.approx(400.0 + 399 * 0.1)
    assert row0["high"] == pytest.approx(row0["close"] + 0.5)
    assert row0["minute_bars"] == 400
    assert row0["volume"] == 4000


def test_longest_clean_run_counts_contiguous_healthy_sessions():
    # Two consecutive healthy business days, then a multi-day gap, then one more.
    minute = pd.concat(
        [
            _synthetic_minute("2026-03-03", 400),  # Tue, healthy
            _synthetic_minute("2026-03-04", 410),  # Wed, healthy  -> run of 2
            _synthetic_minute("2026-03-20", 400),  # Fri, healthy  -> isolated
        ],
        ignore_index=True,
    )
    daily = probe.resample_daily(minute)

    run_len, start, end = probe.longest_clean_run(daily)

    assert run_len == 2
    assert start == pd.Timestamp("2026-03-03").date()
    assert end == pd.Timestamp("2026-03-04").date()


def test_thin_sessions_excluded_from_clean_run():
    # A thin session (below MIN_HEALTHY_MINUTE_BARS) breaks the contiguous run.
    thin = max(probe.MIN_HEALTHY_MINUTE_BARS - 50, 10)
    minute = pd.concat(
        [
            _synthetic_minute("2026-03-03", 400),  # healthy
            _synthetic_minute("2026-03-04", thin),  # thin -> not counted
            _synthetic_minute("2026-03-05", 400),  # healthy
        ],
        ignore_index=True,
    )
    daily = probe.resample_daily(minute)

    run_len, _, _ = probe.longest_clean_run(daily)

    # The thin middle session prevents a 3-run; healthy sessions are isolated.
    assert run_len == 1


def test_longest_clean_run_empty_when_all_thin():
    thin = max(probe.MIN_HEALTHY_MINUTE_BARS - 50, 10)
    minute = _synthetic_minute("2026-03-03", thin)
    daily = probe.resample_daily(minute)

    run_len, start, end = probe.longest_clean_run(daily)

    assert run_len == 0
    assert start is None and end is None
