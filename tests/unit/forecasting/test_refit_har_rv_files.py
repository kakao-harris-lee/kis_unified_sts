"""Tests for local file-backed HAR-RV refit."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.forecasting import refit_har_rv


def _synthetic_refit_bars(days: int = 82, code: str = "A01606") -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-02", periods=days, tz="Asia/Seoul")
    phi = 0.88
    mu = np.log(1e-4)
    log_rv = np.empty(days)
    log_rv[0] = mu
    for i in range(1, days):
        cycle = 0.02 * np.sin(i / 3.0)
        log_rv[i] = (1.0 - phi) * mu + phi * log_rv[i - 1] + cycle

    rows: list[dict[str, object]] = []
    price = 380.0
    bars_per_day = 12
    for day, rv in zip(dates, np.exp(log_rv), strict=True):
        step = float(np.sqrt(rv / (bars_per_day - 1)))
        for minute in range(bars_per_day):
            ts = day.normalize() + pd.Timedelta(hours=9, minutes=5 * minute)
            if minute > 0:
                price *= float(np.exp(step if minute % 2 else -step))
            rows.append(
                {
                    "code": code,
                    "datetime": ts.tz_convert("UTC"),
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": 100 + minute,
                }
            )
    return pd.DataFrame(rows)


def test_refit_main_writes_log_model_json_from_csv(tmp_path: Path):
    bars_path = tmp_path / "bars.csv"
    out_path = tmp_path / "har_rv_model.json"
    _synthetic_refit_bars().to_csv(bars_path, index=False)

    rc = refit_har_rv.main(
        [
            "--bars",
            str(bars_path),
            "--out",
            str(out_path),
            "--rv-target",
            "log",
            "--min-r2-oos",
            "-1.0",
        ]
    )

    assert rc == 0
    payload = json.loads(out_path.read_text())
    assert payload["target_mode"] == "log"
    assert payload["residual_variance"] > 0
    assert len(payload["rv_history"]) >= 60


def test_load_minute_bars_supports_parquet_code_filter(tmp_path: Path):
    wanted = _synthetic_refit_bars(days=1, code="A01606")
    other = _synthetic_refit_bars(days=1, code="A01706")
    parquet_path = tmp_path / "bars.parquet"
    pd.concat([wanted, other], ignore_index=True).to_parquet(parquet_path)

    loaded = refit_har_rv._load_minute_bars(parquet_path, code="A01606")

    assert set(loaded["code"]) == {"A01606"}
    assert loaded.index.tz is not None
    assert loaded["close"].tolist() == wanted["close"].tolist()


def test_load_minute_bars_accepts_timezone_aware_bounds(tmp_path: Path):
    bars = _synthetic_refit_bars(days=2, code="A01606")
    csv_path = tmp_path / "bars.csv"
    bars.to_csv(csv_path, index=False)

    loaded = refit_har_rv._load_minute_bars(
        csv_path,
        code="A01606",
        start="2026-01-02T09:00:00+09:00",
        end="2026-01-03T00:00:00+09:00",
    )

    assert len(loaded) == 12
    assert loaded.index.min() == pd.Timestamp("2026-01-02T00:00:00Z")
    assert loaded.index.max() == pd.Timestamp("2026-01-02T00:55:00Z")
    np.testing.assert_allclose(loaded["close"].to_numpy(), bars.iloc[:12]["close"])
