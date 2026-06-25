"""Tests for local HAR-RV raw-vs-log validation reports."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.forecasting import validate_har_rv


def _synthetic_validation_bars(days: int = 90, code: str = "A01606") -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-02", periods=days, tz="Asia/Seoul")
    phi = 0.92
    mu = np.log(1e-4)
    log_rv = np.empty(days)
    log_rv[0] = mu
    for i in range(1, days):
        seasonal = 0.03 * np.sin(i / 4.0)
        log_rv[i] = (1.0 - phi) * mu + phi * log_rv[i - 1] + seasonal

    rows: list[dict[str, object]] = []
    price = 380.0
    bars_per_day = 18
    for day, rv in zip(dates, np.exp(log_rv), strict=True):
        step = float(np.sqrt(rv / (bars_per_day - 1)))
        for minute in range(bars_per_day):
            ts = day.normalize() + pd.Timedelta(hours=9, minutes=5 * minute)
            if minute > 0:
                direction = 1.0 if minute % 2 else -1.0
                price *= float(np.exp(direction * step))
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


def test_validate_main_writes_raw_and_log_report_from_csv(tmp_path: Path):
    bars_path = tmp_path / "bars.csv"
    out_path = tmp_path / "har_rv_validation.json"
    _synthetic_validation_bars().to_csv(bars_path, index=False)

    rc = validate_har_rv.main(
        [
            "--bars",
            str(bars_path),
            "--code",
            "A01606",
            "--out",
            str(out_path),
            "--min-r2-oos",
            "-1.0",
        ]
    )

    assert rc == 0
    report = json.loads(out_path.read_text())
    assert report["bars_path"] == str(bars_path)
    assert report["code"] == "A01606"
    assert report["rv_history_days"] >= 60
    assert set(report["targets"]) == {"raw", "log"}
    for target, metrics in report["targets"].items():
        assert metrics["target"] == target
        assert metrics["fit_ok"] is True
        assert metrics["rv_history_days"] == report["rv_history_days"]
        assert metrics["error"] is None
        assert isinstance(metrics["r2_oos"], float)
        assert metrics["forecast_pct"] > 0


def test_validate_main_reports_target_failure_without_failing_cli(
    tmp_path: Path, monkeypatch
):
    bars_path = tmp_path / "bars.parquet"
    out_path = tmp_path / "har_rv_validation.json"
    _synthetic_validation_bars().to_parquet(bars_path)

    original_fit_target = validate_har_rv._fit_target

    def fail_log_target(*args, **kwargs):
        if kwargs["target"] == "log":
            raise ValueError("synthetic OOS gate rejection")
        return original_fit_target(*args, **kwargs)

    monkeypatch.setattr(validate_har_rv, "_fit_target", fail_log_target)

    rc = validate_har_rv.main(
        [
            "--bars",
            str(bars_path),
            "--out",
            str(out_path),
            "--min-r2-oos",
            "-1.0",
        ]
    )

    assert rc == 0
    report = json.loads(out_path.read_text())
    assert report["targets"]["raw"]["fit_ok"] is True
    assert report["targets"]["raw"]["error"] is None
    assert report["targets"]["log"]["fit_ok"] is False
    assert report["targets"]["log"]["r2_oos"] is None
    assert report["targets"]["log"]["forecast_pct"] is None
    assert "synthetic OOS gate rejection" in report["targets"]["log"]["error"]
