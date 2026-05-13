#!/usr/bin/env python3
"""Standalone HAR-RV refit: fetch bars → daily RV → fit → persist.

Run via `scripts/cron/forecasting.sh refit` or directly. Writes the fitted model
to Redis (`forecast:vol:model`) and a fit row to `kospi.har_rv_fits`.
The running daemon picks up the new model on SIGUSR1 (reload from Redis).
"""
from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime, timedelta

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROXY_CODE = "101S6000"


def main() -> int:
    from clickhouse_driver import Client

    from shared.db.config import ClickHouseConfig
    from shared.forecasting.config import ForecastingConfig
    from shared.forecasting.realized_variance import daily_rv_series
    from shared.forecasting.volatility_har_rv import VolatilityForecaster
    from shared.streaming.client import RedisClient

    cfg = ForecastingConfig.from_yaml()
    history_days = cfg.har_rv.history_days
    # Fetch a generous window to account for non-trading days.
    lookback_days = int(history_days * 1.6) + 14

    ch_cfg = ClickHouseConfig.from_env(database="kospi")
    ch = Client(
        host=ch_cfg.host,
        port=ch_cfg.port,
        user=ch_cfg.user,
        password=ch_cfg.password,
        database="kospi",
    )

    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    logger.info(
        "Fetching 1m bars for %s since %s (lookback %dd)",
        PROXY_CODE,
        cutoff.isoformat(),
        lookback_days,
    )
    rows = ch.execute(
        "SELECT datetime, open, high, low, close, volume "
        "FROM kospi.kospi200f_1m "
        "WHERE code = %(c)s AND datetime >= %(t)s "
        "ORDER BY datetime",
        {"c": PROXY_CODE, "t": cutoff},
    )
    if not rows:
        logger.error("No bars found — cannot refit")
        return 2

    bars = pd.DataFrame(
        rows, columns=["datetime", "open", "high", "low", "close", "volume"]
    )
    # daily_rv_series expects a tz-aware UTC DatetimeIndex.
    bars["datetime"] = pd.to_datetime(bars["datetime"], utc=True)
    bars = bars.set_index("datetime")
    logger.info("Loaded %d bars", len(bars))

    rv = daily_rv_series(bars)
    logger.info("Computed %d daily RV points", len(rv))
    if len(rv) < max(cfg.har_rv.history_days, 22):
        logger.error(
            "Insufficient RV history: have %d, need >= %d",
            len(rv),
            max(cfg.har_rv.history_days, 22),
        )
        return 3

    forecaster = VolatilityForecaster(cfg.har_rv)
    try:
        forecaster.fit(rv)
    except ValueError as e:
        logger.error("Fit failed: %s", e)
        return 4

    coef = forecaster._coefficients
    assert coef is not None
    logger.info(
        "Fit OK: beta_d=%.3f beta_w=%.3f beta_m=%.3f R²_oos=%.3f n_obs=%d",
        coef.beta_d,
        coef.beta_w,
        coef.beta_m,
        coef.r2_oos,
        coef.n_obs_used,
    )

    redis = RedisClient.get_client()
    blob = forecaster.to_json()
    redis.set("forecast:vol:model", blob)
    logger.info("Wrote model JSON to Redis (forecast:vol:model, %d bytes)", len(blob))

    ch.execute(
        "INSERT INTO kospi.har_rv_fits "
        "(fit_date, beta_0, beta_d, beta_w, beta_m, r2_in_sample, r2_oos, "
        " n_obs_used, confidence, model_version) VALUES",
        [
            {
                "fit_date": datetime.now(UTC).date(),
                "beta_0": coef.beta_0,
                "beta_d": coef.beta_d,
                "beta_w": coef.beta_w,
                "beta_m": coef.beta_m,
                "r2_in_sample": coef.r2_in_sample,
                "r2_oos": coef.r2_oos,
                "n_obs_used": coef.n_obs_used,
                "confidence": min(max(coef.r2_oos, 0.0), 1.0),
                "model_version": forecaster.MODEL_VERSION,
            }
        ],
    )
    logger.info("Inserted fit row into kospi.har_rv_fits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
