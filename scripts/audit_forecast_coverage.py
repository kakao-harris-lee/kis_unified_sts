#!/usr/bin/env python3
"""Coverage audit for vol_forecasts + event_scores (spec 2026-05-21 P0-③ T1).

Reports actual on-disk presence over a window. Distinguishes
model_version='har_rv_v1' (live) from 'har_rv_v1_recompute' (post-hoc)
so the operator knows whether Task 2 (historical recompute) is needed.
Exit code: 0 if vol coverage >= --min-coverage, else 1.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.db.client import get_clickhouse_client
from shared.db.config import ClickHouseConfig


def _get_client():
    return get_clickhouse_client(ClickHouseConfig.from_env())


def _ch_naive(d):
    return d.replace(tzinfo=None) if getattr(d, "tzinfo", None) else d


def audit_window(start: dt.datetime, end: dt.datetime) -> dict:
    cli = _get_client()
    vol = cli.execute(
        "SELECT count() AS total, "
        "countIf(model_version = 'har_rv_v1') AS live, "
        "countIf(model_version = 'har_rv_v1_recompute') AS recompute "
        "FROM kospi.vol_forecasts "
        "WHERE asof >= %(s)s AND asof < %(e)s",
        {"s": _ch_naive(start), "e": _ch_naive(end)},
    )
    ev = cli.execute(
        "SELECT count() FROM kospi.event_scores "
        "WHERE asof >= %(s)s AND asof < %(e)s",
        {"s": _ch_naive(start), "e": _ch_naive(end)},
    )
    total, live, recompute = vol[0] if vol else (0, 0, 0)
    event_total = ev[0][0] if ev else 0
    return {
        "vol_total": int(total),
        "vol_live": int(live),
        "vol_recompute": int(recompute),
        "event_total": int(event_total),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--start", required=True, help="YYYY-MM-DD or ISO datetime")
    ap.add_argument("--end", required=True)
    ap.add_argument(
        "--expected-trading-minutes", type=int, default=0,
        help="expected count; if >0, coverage %% is reported")
    ap.add_argument(
        "--min-coverage", type=float, default=0.90,
        help="exit 1 if vol coverage < this fraction (default 0.90)")
    a = ap.parse_args(argv)
    s = dt.datetime.fromisoformat(a.start)
    e = dt.datetime.fromisoformat(a.end)
    r = audit_window(s, e)
    print(f"window: {s.isoformat()}  →  {e.isoformat()}")
    print(
        f"vol_forecasts: total={r['vol_total']}  "
        f"live={r['vol_live']}  recompute={r['vol_recompute']}")
    print(f"event_scores:  total={r['event_total']}")
    if a.expected_trading_minutes > 0:
        cov = r["vol_total"] / a.expected_trading_minutes
        print(f"coverage: {cov:.1%}  (min={a.min_coverage:.0%})")
        if cov < a.min_coverage:
            print("VERDICT: insufficient — run Task 2 historical recompute")
            return 1
        print("VERDICT: ok")
        return 0
    print(
        "WARNING: --expected-trading-minutes not set; coverage threshold "
        "skipped (counts above are raw)")
    print("VERDICT: ok (no-check)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
