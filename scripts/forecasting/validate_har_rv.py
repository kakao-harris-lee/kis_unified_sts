#!/usr/bin/env python3
"""Validate raw-vs-log HAR-RV fits from local minute bars.

This is a repo-local gate helper for the log-RV migration. It intentionally
reads operator-provided CSV/Parquet bars and writes a JSON decision report; it
does not fetch data or mutate runtime config.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.forecasting.refit_har_rv import _load_minute_bars
from shared.forecasting.config import HARRVConfig
from shared.forecasting.realized_variance import daily_rv_series
from shared.forecasting.volatility_har_rv import VolatilityForecaster

_KST = ZoneInfo("Asia/Seoul")


def _fit_target(
    rv: pd.Series,
    bars: pd.DataFrame,
    *,
    target: str,
    min_r2_oos: float,
    history_days: int,
    holdout_days: int,
) -> dict[str, Any]:
    cfg = HARRVConfig(
        history_days=history_days,
        holdout_days=holdout_days,
        min_r2_oos=min_r2_oos,
        rv_target=target,
    )
    forecaster = VolatilityForecaster(cfg)
    forecaster.fit(rv)
    if forecaster._coefficients is None:
        raise RuntimeError("fit completed without coefficients")

    latest_close = float(bars["close"].iloc[-1])
    asof = bars.index.max()
    if isinstance(asof, pd.Timestamp):
        asof_dt = asof.to_pydatetime()
    else:
        asof_dt = datetime.now(UTC)
    forecast = forecaster.forecast(asof_dt, current_close=latest_close)

    return {
        "target": target,
        "fit_ok": True,
        "r2_oos": float(forecaster._coefficients.r2_oos),
        "forecast_pct": float(forecast.forecast_pct),
        "rv_history_days": int(len(rv)),
        "error": None,
    }


def _failed_target(target: str, rv_history_days: int, exc: Exception) -> dict[str, Any]:
    return {
        "target": target,
        "fit_ok": False,
        "r2_oos": None,
        "forecast_pct": None,
        "rv_history_days": int(rv_history_days),
        "error": str(exc),
    }


def validate_from_file(
    bars_path: str | Path,
    *,
    code: str | None = None,
    start: str | None = None,
    end: str | None = None,
    min_r2_oos: float = 0.10,
    history_days: int = 60,
    holdout_days: int = 7,
) -> dict[str, Any]:
    bars = _load_minute_bars(bars_path, code=code, start=start, end=end)
    if bars.empty:
        raise ValueError("no minute bars found for requested file/filter")

    rv = daily_rv_series(bars)
    rv = rv[pd.notna(rv)]
    if rv.empty:
        raise ValueError("no regular-session daily RV could be computed")

    targets: dict[str, dict[str, Any]] = {}
    for target in ("raw", "log"):
        try:
            targets[target] = _fit_target(
                rv,
                bars,
                target=target,
                min_r2_oos=min_r2_oos,
                history_days=history_days,
                holdout_days=holdout_days,
            )
        except Exception as exc:  # noqa: BLE001 - report target-level fit failure
            targets[target] = _failed_target(target, len(rv), exc)

    return {
        "generated_at_kst": datetime.now(_KST).isoformat(),
        "bars_path": str(bars_path),
        "code": code,
        "start": start,
        "end": end,
        "min_r2_oos": float(min_r2_oos),
        "history_days": int(history_days),
        "holdout_days": int(holdout_days),
        "rv_history_days": int(len(rv)),
        "rv_start": str(rv.index.min()),
        "rv_end": str(rv.index.max()),
        "targets": targets,
    }


def _write_report(report: dict[str, Any], out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return out


def _build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Validate HAR-RV raw vs log targets from local CSV/Parquet bars."
    )
    ap.add_argument(
        "--bars",
        required=True,
        help="CSV or Parquet bars file with datetime and close columns",
    )
    ap.add_argument("--code", default=None, help="optional contract code filter")
    ap.add_argument(
        "--start",
        default=None,
        help="optional UTC or timezone-aware lower bound, e.g. 2026-01-01",
    )
    ap.add_argument(
        "--end",
        default=None,
        help="optional UTC or timezone-aware exclusive upper bound, e.g. 2026-06-01",
    )
    ap.add_argument("--out", required=True, help="output validation JSON path")
    ap.add_argument("--min-r2-oos", type=float, default=0.10)
    ap.add_argument("--history-days", type=int, default=60)
    ap.add_argument("--holdout-days", type=int, default=7)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    try:
        report = validate_from_file(
            args.bars,
            code=args.code,
            start=args.start,
            end=args.end,
            min_r2_oos=args.min_r2_oos,
            history_days=args.history_days,
            holdout_days=args.holdout_days,
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"ERROR: HAR-RV validation input failed: {exc}", file=sys.stderr)
        return 2

    try:
        out = _write_report(report, args.out)
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(
            f"ERROR: could not write HAR-RV validation report: {exc}", file=sys.stderr
        )
        return 3

    print(f"wrote HAR-RV validation report to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
