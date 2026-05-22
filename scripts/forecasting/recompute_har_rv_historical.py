#!/usr/bin/env python3
"""Historical HAR-RV recompute for backtest replay (spec 2026-05-21 P0-③ T2).

Fits VolatilityForecaster ONCE on a training window of daily RV (from
kospi.kospi200f_1m), then applies the frozen coefficients to every
15-minute timestamp in the OOS window. Writes vol_forecasts rows
tagged model_version='har_rv_v1_recompute' so they are never confused
with live publishes (har_rv_v1). Look-ahead-safe: train_end < test_start
is enforced.

NOTE: this tool is not idempotent — vol_forecasts uses plain MergeTree
(no dedup key). Re-running the same window inserts duplicates. To
re-run cleanly:
  ALTER TABLE kospi.vol_forecasts DELETE
   WHERE model_version = 'har_rv_v1_recompute'
     AND asof >= '<test_start>' AND asof < '<test_end+1>';
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections.abc import Callable
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


def _load_candles_from_csv(path: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    """Load OHLCV minute bars from a CSV in the same shape _fetch_minute_candles
    returns (UTC DatetimeIndex, OHLCV columns) over [start, end) — exclusive end.

    Schema: datetime,open,high,low,close,volume (no 'code' column).
    """
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    # Filter to half-open [start, end) window. Use timestamps for comparison
    # so date-boundary semantics match _fetch_minute_candles' SQL `>= s AND < e`.
    s_ts = pd.Timestamp(start, tz="UTC")
    e_ts = pd.Timestamp(end, tz="UTC")
    df = df[(df["datetime"] >= s_ts) & (df["datetime"] < e_ts)]
    df = df.set_index("datetime")
    # Drop any incidental columns (e.g. if CSV happens to have 'code') — keep only OHLCV
    return df[["open", "high", "low", "close", "volume"]]


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


def _resolve(cc, asof):
    """Resolve current_close to a float — accepts either a float or a callable."""
    return cc(asof) if callable(cc) else cc


def recompute_and_insert(
    train_rv: pd.Series,
    test_minutes: pd.DatetimeIndex,
    current_close: float | Callable[[dt.datetime], float],
    client,
    *,
    full_rv: pd.Series | None = None,
) -> int:
    """Fit on train_rv, forecast at every test_minutes timestamp, insert.

    When full_rv is supplied (containing train+OOS daily RV), updates
    VolatilityForecaster._latest_components per OOS day from rolling
    (last_d, last_w, last_m) computed from full_rv history strictly
    BEFORE that day. This walks the model forward correctly through
    the OOS window — mirrors production's daily-refit semantics
    without the cost of a full fit() per day. Without full_rv,
    _latest_components stays frozen at fit() time (backward-compat).

    Args:
        train_rv: daily realized variance Series, indexed by date objects.
        test_minutes: timestamps at which to produce forecasts.
        current_close: close price for ATR-equivalent calc. Either a float
            (applied to every timestamp — simple but biased over long windows)
            or a callable taking the asof datetime and returning the per-
            timestamp close (preferred for multi-day OOS windows).
        client: ClickHouse client (None in tests — _insert_rows handles it).
        full_rv: optional combined daily RV Series (train + OOS), indexed by
            date objects. When supplied, enables rolling-components walk-forward
            so regime_percentile labels vary across OOS days. Look-ahead-safe:
            per-day components are built from history STRICTLY before day D.

    Returns:
        Number of rows written.
    """
    forecaster = VolatilityForecaster(_RECOMPUTE_HAR_CFG)
    forecaster.fit(train_rv)
    rows: list[tuple] = []
    last_day_seen = None
    for ts in test_minutes:
        asof = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        if getattr(asof, "tzinfo", None) is not None:
            asof = asof.replace(tzinfo=None)
        # Rolling-components walk-forward: refresh _latest_components ONCE per day.
        if full_rv is not None:
            D = asof.date()
            if last_day_seen != D:
                history_before = full_rv.loc[full_rv.index < D]
                if len(history_before) >= 22:
                    last_d = float(history_before.iloc[-1])
                    last_w = float(history_before.iloc[-5:].mean())
                    last_m = float(history_before.iloc[-22:].mean())
                    forecaster._latest_components = (last_d, last_w, last_m)
                last_day_seen = D
        vf = forecaster.forecast(asof, current_close=_resolve(current_close, asof))
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
    ap.add_argument("--test-end", required=True, help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--cadence-minutes", type=int, default=15,
                    help="Forecast cadence in minutes (default: 15)")
    ap.add_argument("--candles-csv", default=None,
                    help="path to clean OHLCV CSV (datetime,open,high,low,close,volume); "
                         "if set, train+test fetches use this CSV instead of ClickHouse")
    a = ap.parse_args(argv)

    ts_d = dt.date.fromisoformat(a.train_start)
    te_d = dt.date.fromisoformat(a.train_end)
    xs_d = dt.date.fromisoformat(a.test_start)
    xe_d = dt.date.fromisoformat(a.test_end)
    _validate_split(te_d, xs_d)
    if xe_d < xs_d:
        print(f"ERROR: test window inverted: test_end={xe_d} < test_start={xs_d}")
        return 2

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

    if a.candles_csv:
        train_df = _load_candles_from_csv(a.candles_csv, ts_d, te_d)
    else:
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
    if a.candles_csv:
        test_df = _load_candles_from_csv(
            a.candles_csv, xs_d, xe_d + dt.timedelta(days=1)
        )
    else:
        test_df = _fetch_minute_candles(client, xs_d, xe_d + dt.timedelta(days=1))

    # Build the FULL daily RV series (train + test) for rolling-components walk-forward.
    # This mirrors production's daily-refit semantics: _latest_components updates
    # per OOS day from history STRICTLY before that day. Look-ahead-safe because
    # the per-day component is built from days BEFORE day D.
    if not test_df.empty:
        full_df = pd.concat([train_df, test_df]).sort_index()
        full_rv = daily_rv_series(full_df)
    else:
        full_rv = train_rv

    current_close_arg: float | Callable[[dt.datetime], float]
    if not test_df.empty:
        # _fetch_minute_candles returns a UTC-DatetimeIndex df; strip tz for
        # tz-naive asof lookups (matches ClickHouse DateTime64 storage).
        tdf = test_df.copy()
        tdf.index = tdf.index.tz_convert(None)
        daily_close = tdf["close"].resample("1D").last().ffill()
        fallback_close = float(test_df["close"].iloc[-1])

        def close_for(asof: dt.datetime) -> float:
            try:
                v = daily_close.asof(pd.Timestamp(asof))
                return float(v) if pd.notna(v) and float(v) > 0 else fallback_close
            except Exception:
                return fallback_close

        current_close_arg = close_for
    else:
        current_close_arg = 380.0

    n = recompute_and_insert(train_rv, test_minutes, current_close_arg, client, full_rv=full_rv)
    print(f"wrote {n} vol_forecasts rows (model_version={RECOMPUTE_MODEL_VERSION})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
