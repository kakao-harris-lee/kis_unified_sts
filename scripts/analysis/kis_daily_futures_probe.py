"""Probe: KIS daily futures chart API depth and quality.

Tests the 선물옵션기간별시세(일/주/월/년) API (FHKIF03020100) against
101S6000 (continuous near-month KOSPI200 future) to determine:

- How far back KIS returns daily settlement bars
- Per-call bar count cap
- OHLC sanity and data quality

Usage (throttled — only a few calls):
    .venv/bin/python scripts/analysis/kis_daily_futures_probe.py

Requirements: KIS_FUTURES_APP_KEY / KIS_FUTURES_APP_SECRET in environment.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import date, timedelta

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = "https://openapi.koreainvestment.com:9443"
DAILY_CHART_PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-daily-fuopchartprice"
TR_ID = "FHKIF03020100"
# The daily futures API requires a LEGACY A-code (e.g. A01612 continuous near-
# month). The auto-rolling short-code "101S6000" returns rt_cd=0 with an EMPTY
# output2 (silent failure) → would print a false GATE=FAIL. Override via argv[1].
SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "A01612"
RPS_CEIL = 2  # stay well below 5 rps limit; probe only
_MIN_INTERVAL = 1.0 / RPS_CEIL


def _load_credentials() -> tuple[str, str]:
    app_key = os.environ.get("KIS_FUTURES_APP_KEY", "")
    app_secret = os.environ.get("KIS_FUTURES_APP_SECRET", "")
    if not app_key or not app_secret:
        # Try loading from .env directly
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("KIS_FUTURES_APP_KEY="):
                        app_key = line.split("=", 1)[1].strip()
                    elif line.startswith("KIS_FUTURES_APP_SECRET="):
                        app_secret = line.split("=", 1)[1].strip()
    return app_key, app_secret


def _get_token(app_key: str, app_secret: str) -> str:
    """Fetch OAuth token. Uses ~/.cache/kis_token_futures.json if valid."""
    cache_path = os.path.expanduser("~/.cache/kis_token_futures.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                data = json.load(f)
            token = data.get("access_token") or data.get("token")
            expires_at = float(data.get("expires_at", 0))
            if token and time.time() < expires_at - 120:
                logger.info("[probe] Reusing cached futures token")
                return token
        except Exception:
            pass

    logger.info("[probe] Fetching new OAuth token …")
    resp = requests.post(
        f"{BASE_URL}/oauth2/tokenP",
        json={
            "grant_type": "client_credentials",
            "appkey": app_key,
            "appsecret": app_secret,
        },
        timeout=30,
    )
    data = resp.json()
    if "access_token" not in data:
        raise SystemExit(f"Token fetch failed: {data}")

    token = data["access_token"]
    expires_in = int(data.get("expires_in", 86400))
    expires_at = time.time() + expires_in

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump({"access_token": token, "expires_at": expires_at}, f)

    logger.info(f"[probe] Token obtained, expires in {expires_in}s")
    return token


def _fetch_daily_bars(
    session: requests.Session,
    token: str,
    app_key: str,
    app_secret: str,
    start_date: date,
    end_date: date,
) -> dict:
    """One call to the daily chart API for [start_date, end_date]."""
    headers = {
        "Authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": TR_ID,
        "content-type": "application/json; charset=utf-8",
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": "F",
        "FID_INPUT_ISCD": SYMBOL,
        "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
        "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
        "FID_PERIOD_DIV_CODE": "D",
    }
    resp = session.get(
        f"{BASE_URL}{DAILY_CHART_PATH}", headers=headers, params=params, timeout=15
    )
    if resp.status_code >= 400:
        return {"error": f"HTTP {resp.status_code}", "text": resp.text[:300]}
    try:
        return resp.json()
    except Exception as e:
        return {"error": f"json parse: {e}", "text": resp.text[:300]}


def _throttle(last_call: float) -> float:
    """Sleep until _MIN_INTERVAL has elapsed; return new last_call time."""
    elapsed = time.monotonic() - last_call
    gap = _MIN_INTERVAL - elapsed
    if gap > 0:
        time.sleep(gap)
    return time.monotonic()


def probe() -> int:
    """Run probe; return 0 on success, 1 on hard limit."""
    app_key, app_secret = _load_credentials()
    if not app_key:
        logger.error("[probe] KIS_FUTURES_APP_KEY not found")
        return 1

    token = _get_token(app_key, app_secret)
    session = requests.Session()
    session.verify = True

    today = date.today()
    last_call = time.monotonic() - _MIN_INTERVAL  # allow immediate first call

    print()
    print("=" * 72)
    print(f"KIS DAILY FUTURES API PROBE — {SYMBOL}")
    print("=" * 72)

    # -----------------------------------------------------------------------
    # TEST 1: Recent 100 days — confirm the API works and shows bar count
    # -----------------------------------------------------------------------
    start_recent = today - timedelta(days=100)
    last_call = _throttle(last_call)
    logger.info(f"[probe] Call 1: {start_recent} -> {today}")
    data1 = _fetch_daily_bars(session, token, app_key, app_secret, start_recent, today)

    if "error" in data1:
        print(f"FATAL — Call 1 failed: {data1}")
        return 1

    rt_cd = data1.get("rt_cd", "?")
    bars1 = data1.get("output2", []) or []
    print(f"\n[Call 1] {start_recent} -> {today}  rt_cd={rt_cd}  bars={len(bars1)}")
    if bars1:
        first_bar = bars1[-1]  # API returns newest-first
        last_bar = bars1[0]
        print(f"  newest bar date : {last_bar.get('stck_bsop_date')}")
        print(f"  oldest bar date : {first_bar.get('stck_bsop_date')}")
        print(f"  sample bar      : {last_bar}")

    # -----------------------------------------------------------------------
    # TEST 2: Go back 1 year — check if we get ~250 bars or cap at 100
    # -----------------------------------------------------------------------
    start_1y = today - timedelta(days=365)
    last_call = _throttle(last_call)
    logger.info(f"[probe] Call 2: {start_1y} -> {today}")
    data2 = _fetch_daily_bars(session, token, app_key, app_secret, start_1y, today)

    rt_cd2 = data2.get("rt_cd", "?")
    bars2 = data2.get("output2", []) or []
    print(f"\n[Call 2] {start_1y} -> {today}  rt_cd={rt_cd2}  bars={len(bars2)}")
    if bars2:
        print(f"  newest bar : {bars2[0].get('stck_bsop_date')}")
        print(f"  oldest bar : {bars2[-1].get('stck_bsop_date')}")

    # -----------------------------------------------------------------------
    # TEST 3: Go back 3 years — the critical CTA threshold
    # -----------------------------------------------------------------------
    start_3y = today - timedelta(days=3 * 365)
    last_call = _throttle(last_call)
    logger.info(f"[probe] Call 3: {start_3y} -> {today}")
    data3 = _fetch_daily_bars(session, token, app_key, app_secret, start_3y, today)

    rt_cd3 = data3.get("rt_cd", "?")
    bars3 = data3.get("output2", []) or []
    print(f"\n[Call 3] {start_3y} -> {today}  rt_cd={rt_cd3}  bars={len(bars3)}")
    if bars3:
        print(f"  newest bar : {bars3[0].get('stck_bsop_date')}")
        print(f"  oldest bar : {bars3[-1].get('stck_bsop_date')}")

    # -----------------------------------------------------------------------
    # TEST 4: Try oldest possible — go back 5 years to find the real limit
    # -----------------------------------------------------------------------
    start_5y = today - timedelta(days=5 * 365)
    last_call = _throttle(last_call)
    logger.info(f"[probe] Call 4: {start_5y} -> {today}")
    data4 = _fetch_daily_bars(session, token, app_key, app_secret, start_5y, today)

    rt_cd4 = data4.get("rt_cd", "?")
    bars4 = data4.get("output2", []) or []
    print(f"\n[Call 4] {start_5y} -> {today}  rt_cd={rt_cd4}  bars={len(bars4)}")
    if bars4:
        print(f"  newest bar : {bars4[0].get('stck_bsop_date')}")
        print(f"  oldest bar : {bars4[-1].get('stck_bsop_date')}")

    # -----------------------------------------------------------------------
    # TEST 5: Reverse-pagination probe — oldest 100 bars from start_3y window
    # If bars3 was capped at 100 (newest 100 of 3y), probe the oldest end
    # by setting end_date to the oldest bar we got minus 1 day.
    # -----------------------------------------------------------------------
    if bars3:
        oldest_in_3y = bars3[-1].get("stck_bsop_date", "")
        if oldest_in_3y and len(oldest_in_3y) == 8:
            oldest_dt = date(int(oldest_in_3y[:4]), int(oldest_in_3y[4:6]), int(oldest_in_3y[6:]))
            probe_end = oldest_dt - timedelta(days=1)
            last_call = _throttle(last_call)
            logger.info(f"[probe] Call 5 (reverse page): {start_3y} -> {probe_end}")
            data5 = _fetch_daily_bars(
                session, token, app_key, app_secret, start_3y, probe_end
            )
            rt_cd5 = data5.get("rt_cd", "?")
            bars5 = data5.get("output2", []) or []
            print(f"\n[Call 5] {start_3y} -> {probe_end}  rt_cd={rt_cd5}  bars={len(bars5)}")
            if bars5:
                print(f"  newest bar : {bars5[0].get('stck_bsop_date')}")
                print(f"  oldest bar : {bars5[-1].get('stck_bsop_date')}")
        else:
            bars5 = []
    else:
        bars5 = []

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print()
    print("=" * 72)
    print("PROBE SUMMARY")
    print("=" * 72)
    print(f"  Max 100-day window bars  : {len(bars1)} (API call confirmed working)")
    print(f"  1-year window bars       : {len(bars2)} (cap={len(bars2)==100})")
    print(f"  3-year window bars       : {len(bars3)} (cap={len(bars3)==100})")
    print(f"  5-year window bars       : {len(bars4)} (cap={len(bars4)==100})")
    print(f"  Reverse-page bars        : {len(bars5)}")

    # Determine if pagination gives enough coverage
    per_call_cap = 100
    total_bars_accessible_estimate = None

    # If 5y returned < 100 bars, the API limit is less than 5y
    # If 3y returned 100 (capped), there's more data behind it
    # Estimate total accessible via page count
    if bars3:
        oldest_3y_date_str = bars3[-1].get("stck_bsop_date", "")
        if bars5:
            oldest_5y_date_str = bars5[-1].get("stck_bsop_date", "")
        else:
            oldest_5y_date_str = oldest_3y_date_str

        print()
        print("PAGINATION ANALYSIS:")
        print("  Per-call cap       : 100 bars")

        if oldest_5y_date_str:
            oldest_dt = date(
                int(oldest_5y_date_str[:4]),
                int(oldest_5y_date_str[4:6]),
                int(oldest_5y_date_str[6:]),
            )
            span_years = (today - oldest_dt).days / 365.25
            total_bdays_estimate = int((today - oldest_dt).days * 5 / 7)
            pages_needed = -(-total_bdays_estimate // per_call_cap)  # ceiling div
            print(f"  Oldest date found  : {oldest_dt}  ({span_years:.1f}y ago)")
            print(f"  Est. total bars    : ~{total_bdays_estimate} business days")
            print(f"  Pages needed       : ~{pages_needed} calls @ 100/call @ ≤2 rps")
            print(f"  Est. collect time  : ~{pages_needed/RPS_CEIL:.0f}s")
            span_years_found = span_years
        else:
            span_years_found = 0
    else:
        span_years_found = 0
        print("\nFATAL — 3-year probe returned no bars (API may not support futures daily)")

    print()
    # Gate decision
    if span_years_found >= 2.5:
        print(f"GATE RESULT: PASS (found {span_years_found:.1f}y of daily bar history)")
        print("  -> Sufficient depth for CTA walk-forward. Proceed to COLLECT.")
        return 0
    else:
        print(f"GATE RESULT: FAIL (found only {span_years_found:.1f}y of usable history)")
        print("  -> Insufficient for 3-fold WF (~750 daily bars needed). HARD LIMIT.")
        print("  -> Options: KRX settlement data feed / paid vendor / shorter variant.")
        return 1


if __name__ == "__main__":
    sys.exit(probe())
