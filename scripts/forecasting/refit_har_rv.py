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

import logging
import os
import sys
from typing import Any

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


def main() -> int:
    print(
        "ERROR: External-DB-backed HAR refit was removed. "
        "Use a Parquet/CSV-based forecasting refit flow."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
