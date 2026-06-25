#!/usr/bin/env python3
"""Standalone HAR-RV refit: fetch bars → daily RV → fit → persist.

Run via `scripts/cron/forecasting.sh refit` or directly. Writes the fitted model
to Redis (`forecast:vol:model`) and a fit row to `kospi.har_rv_fits`.
The running daemon picks up the new model on SIGUSR1 (reload from Redis).

Symbol policy (CRITICAL): fetch the *active near-month* contract code
(A016xx / A017xx convention), NOT the synthetic continuous series 101S6000.

The synthetic continuous series is chronically polluted by stale/missing
days that surface as physically-impossible RV outliers (~15% of train days
had RV > 5× median; max ~161× median ≈ 1258% annualized vol). HAR-RV fits
on that data routinely fail with R² OOS ≪ -1, blocking the daily refit.
See PR #329 investigation for the full root-cause analysis.

Contract-code resolution: auto-detected from the most-recent-volume A01* code
in CH so quarterly rolls don't require manual env updates. Override via
FORECAST_REFIT_CODE env var if needed (e.g. forcing a specific contract for
back-testing or recovery).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.forecasting.config import HARRVConfig
from shared.forecasting.realized_variance import daily_rv_series
from shared.forecasting.volatility_har_rv import VolatilityForecaster

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Hard fallback used only if both env-var override is unset AND auto-resolve
# fails. A01606 is the active near-month as of 2026-05-23.
_FALLBACK_PROXY_CODE = "A01606"

# Minimum 1m-bar count in the resolution window for a contract to be eligible.
# Without this, a stray single bar of an illiquid far-month (e.g. A01612, 1 bar
# / vol=18) can win when the active near-month has a brief data gap, and its
# degenerate recent RV produces a NaN OOS R² that blocks the refit.
_MIN_RESOLVE_BARS = 30


def _resolve_proxy_code(ch: Any) -> str:
    """Return the current near-month A01* contract code.

    Order of precedence:
      1. FORECAST_REFIT_CODE env var (operator override / pinning).
      2. A01* code with the most volume over the last 5 calendar days that
         also has >= ``_MIN_RESOLVE_BARS`` bars in that window — so a stray
         single-bar far-month cannot win when the active contract has a brief
         ingestion gap (auto-handles quarterly rolls + short data gaps).
      3. Hard-coded fallback (_FALLBACK_PROXY_CODE).
    """
    env = os.environ.get("FORECAST_REFIT_CODE")
    if env:
        logger.info("FORECAST_REFIT_CODE override = %s", env)
        return env
    try:
        rows = ch.execute(
            "SELECT code, sum(volume) AS v, count() AS bars "
            "FROM kospi.kospi200f_1m "
            "WHERE code LIKE 'A01%' AND datetime >= now() - INTERVAL 5 DAY "
            "GROUP BY code HAVING bars >= %(min_bars)s "
            "ORDER BY v DESC LIMIT 1",
            {"min_bars": _MIN_RESOLVE_BARS},
        )
        if rows and rows[0][0]:
            logger.info(
                "Auto-resolved near-month code by volume: %s (vol=%d, bars=%d)",
                rows[0][0],
                rows[0][1],
                rows[0][2],
            )
            return rows[0][0]
        logger.warning(
            "No A01* contract with >= %d bars in last 5d — falling back to %s",
            _MIN_RESOLVE_BARS,
            _FALLBACK_PROXY_CODE,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "auto-resolve failed: %s — falling back to %s", e, _FALLBACK_PROXY_CODE
        )
    return _FALLBACK_PROXY_CODE


def _load_minute_bars(
    path: str | Path,
    *,
    code: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Load local minute bars from CSV or Parquet with a UTC DatetimeIndex."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        df = pd.read_parquet(p)
    elif suffix == ".csv":
        df = pd.read_csv(p)
    else:
        raise ValueError(f"unsupported bars file extension: {p.suffix}")

    if "datetime" not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index().rename(columns={df.index.name or "index": "datetime"})
        else:
            raise ValueError("bars file must include a datetime column")
    if "close" not in df.columns:
        raise ValueError("bars file must include a close column")

    if code is not None and "code" in df.columns:
        df = df[df["code"].astype(str) == code]

    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    if start is not None:
        start_ts = pd.Timestamp(start, tz="UTC")
        df = df[df["datetime"] >= start_ts]
    if end is not None:
        end_ts = pd.Timestamp(end, tz="UTC")
        df = df[df["datetime"] < end_ts]

    df = df.sort_values("datetime").set_index("datetime")
    return df


def refit_from_file(
    bars_path: str | Path,
    out_path: str | Path,
    cfg: HARRVConfig,
    *,
    code: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> Path:
    """Fit HAR-RV from a local bars file and write serialized model JSON."""
    bars = _load_minute_bars(bars_path, code=code, start=start, end=end)
    if bars.empty:
        raise ValueError("no minute bars found for requested file/filter")

    rv = daily_rv_series(bars)
    forecaster = VolatilityForecaster(cfg)
    forecaster.fit(rv)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(forecaster.to_json())
    return out


def _build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "Refit HAR-RV from local CSV/Parquet minute bars and write model JSON."
        )
    )
    ap.add_argument(
        "--bars",
        "--input",
        dest="bars",
        required=True,
        help="CSV or Parquet bars file with datetime and close columns",
    )
    ap.add_argument("--out", required=True, help="output model JSON path")
    ap.add_argument("--code", default=None, help="optional contract code filter")
    ap.add_argument(
        "--start",
        default=None,
        help="optional UTC lower bound, e.g. 2026-01-01",
    )
    ap.add_argument(
        "--end",
        default=None,
        help="optional UTC exclusive upper bound, e.g. 2026-06-01",
    )
    ap.add_argument(
        "--rv-target",
        choices=["raw", "log"],
        default="raw",
        help="fit target mode (default: raw)",
    )
    ap.add_argument("--history-days", type=int, default=60)
    ap.add_argument("--holdout-days", type=int, default=7)
    ap.add_argument("--min-r2-oos", type=float, default=0.10)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    cfg = HARRVConfig(
        history_days=args.history_days,
        holdout_days=args.holdout_days,
        min_r2_oos=args.min_r2_oos,
        rv_target=args.rv_target,
    )
    try:
        out = refit_from_file(
            args.bars,
            args.out,
            cfg,
            code=args.code,
            start=args.start,
            end=args.end,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: HAR-RV refit failed: {exc}", file=sys.stderr)
        return 2
    print(f"wrote HAR-RV model JSON to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
