#!/usr/bin/env python3
"""Historical HAR-RV recompute for backtest replay (spec 2026-05-21 P0-③ T2).

Fits VolatilityForecaster ONCE on a training window of daily RV (from
kospi.kospi200f_1m), then applies the frozen coefficients to every
15-minute timestamp in the OOS window. Writes vol_forecasts rows
tagged model_version='har_rv_v1_recompute' so they are never confused
with live publishes (har_rv_v1). Look-ahead-safe: train_end < test_start
is enforced.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.forecasting.config import HARRVConfig
from shared.forecasting.realized_variance import daily_rv_series
from shared.forecasting.volatility_har_rv import VolatilityForecaster

RECOMPUTE_MODEL_VERSION = "har_rv_v1_recompute"
_PROXY_CODE = "101S6000"  # connected futures, same as live forecaster

# Use a permissive config for historical recompute: we don't want the tool to
# abort just because OOS R² is low over the training holdout window — the caller
# has already decided to use this window.
_RECOMPUTE_HAR_CFG = HARRVConfig(min_r2_oos=-1.0)


def _validate_split(train_end: dt.date, test_start: dt.date) -> None:
    if test_start <= train_end:
        raise ValueError(
            f"train/test overlap: train_end={train_end} >= test_start={test_start}"
        )


def _fetch_minute_candles(client, start: dt.date, end: dt.date) -> pd.DataFrame:
    """Fetch 1-minute bars from ClickHouse, returning UTC-indexed DataFrame."""
    rows = client.execute(
        "SELECT datetime, open, high, low, close, volume "
        "FROM kospi.kospi200f_1m "
        "WHERE code = %(c)s AND datetime >= %(s)s AND datetime < %(e)s "
        "ORDER BY datetime",
        {"c": _PROXY_CODE, "s": start, "e": end},
    )
    df = pd.DataFrame(
        rows, columns=["datetime", "open", "high", "low", "close", "volume"]
    )
    if not df.empty:
        # daily_rv_series expects a DataFrame with a tz-aware UTC DatetimeIndex
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
        df = df.set_index("datetime")
    return df


def _insert_rows(client, rows: list[tuple]) -> int:
    if client is None or not rows:
        return 0
    client.execute(
        "INSERT INTO kospi.vol_forecasts "
        "(asof, horizon_minutes, forecast_pct, forecast_atr_equivalent, "
        "regime_percentile, model_version) VALUES",
        rows,
    )
    return len(rows)


def recompute_and_insert(
    train_rv: pd.Series,
    test_minutes: pd.DatetimeIndex,
    current_close: float,
    client,
) -> int:
    """Fit on train_rv, forecast at every test_minutes timestamp, insert.

    Args:
        train_rv: daily realized variance Series, indexed by date objects.
        test_minutes: timestamps at which to produce forecasts.
        current_close: most recent close price (for ATR-equivalent calc).
        client: ClickHouse client (None in tests — _insert_rows handles it).

    Returns:
        Number of rows written.
    """
    forecaster = VolatilityForecaster(_RECOMPUTE_HAR_CFG)
    forecaster.fit(train_rv)
    rows: list[tuple] = []
    for ts in test_minutes:
        asof = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        if getattr(asof, "tzinfo", None) is not None:
            asof = asof.replace(tzinfo=None)
        vf = forecaster.forecast(asof, current_close=current_close)
        rows.append((
            asof,
            vf.horizon_minutes,
            vf.forecast_pct,
            vf.forecast_atr_equivalent,
            vf.regime_percentile,
            RECOMPUTE_MODEL_VERSION,
        ))
    return _insert_rows(client, rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--train-start", required=True, help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--train-end", required=True, help="YYYY-MM-DD (exclusive)")
    ap.add_argument("--test-start", required=True, help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--test-end", required=True, help="YYYY-MM-DD (exclusive)")
    ap.add_argument("--cadence-minutes", type=int, default=15,
                    help="Forecast cadence in minutes (default: 15)")
    a = ap.parse_args(argv)

    ts_d = dt.date.fromisoformat(a.train_start)
    te_d = dt.date.fromisoformat(a.train_end)
    xs_d = dt.date.fromisoformat(a.test_start)
    xe_d = dt.date.fromisoformat(a.test_end)
    _validate_split(te_d, xs_d)

    from clickhouse_driver import Client

    from shared.db.config import ClickHouseConfig

    ch_cfg = ClickHouseConfig.from_env(database="kospi")
    client = Client(
        host=ch_cfg.host,
        port=ch_cfg.port,
        user=ch_cfg.user,
        password=ch_cfg.password,
        database="kospi",
    )

    train_df = _fetch_minute_candles(client, ts_d, te_d)
    if train_df.empty:
        print(f"ERROR: no minute candles in train window {ts_d}..{te_d}")
        return 2
    train_rv = daily_rv_series(train_df)

    test_minutes = pd.date_range(
        start=f"{xs_d.isoformat()} 09:00",
        end=f"{xe_d.isoformat()} 15:30",
        freq=f"{a.cadence_minutes}min",
    )
    test_df = _fetch_minute_candles(client, xs_d, xe_d)
    last_close = float(test_df["close"].iloc[-1]) if not test_df.empty else 380.0

    n = recompute_and_insert(train_rv, test_minutes, last_close, client)
    print(f"wrote {n} vol_forecasts rows (model_version={RECOMPUTE_MODEL_VERSION})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
