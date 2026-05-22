#!/usr/bin/env python3
"""Build a clean kospi200f 1-minute CSV from A01* contracts (spec 2026-05-21 P1-③ T8).

T7 investigation found `kospi.kospi200f_1m WHERE code='101S6000'` is polluted
on ~15% of days (the synthetic-continuous mirror falls back to thinly-traded
far-month contracts when the active near-month wasn't streamed). This helper
selects the dominant-volume A01* contract per day (same logic as
shared/collector/historical/backfill.py:_build_continuous_rows) and writes a
clean CSV with the same schema as data/kospi200f_1m_ch_101S6000.csv. NO
production DB mutation — pure read + CSV write.
"""
from __future__ import annotations

import argparse
import csv as _csv
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def _fetch_a01_rows(client, start: dt.date, end: dt.date) -> list[tuple]:
    """Fetch all A01* contract minute bars over [start, end) — exclusive end."""
    return client.execute(
        "SELECT code, datetime, open, high, low, close, volume "
        "FROM kospi.kospi200f_1m "
        "WHERE code LIKE 'A01%%' AND datetime >= %(s)s AND datetime < %(e)s "
        "ORDER BY datetime, code",
        {"s": start, "e": end},
    )


def select_dominant_per_day(rows: list[tuple]) -> list[tuple]:
    """Keep only rows from the per-day dominant-volume contract.

    Mirrors shared/collector/historical/backfill.py:_build_continuous_rows
    exactly: sum volume per (date, code), pick the (date, code) with the
    largest volume (alphabetical tie-break), then keep ONLY rows whose
    code matches that day's dominant.
    """
    if not rows:
        return []

    daily_volume: dict[dt.date, dict[str, int]] = {}
    for code, ts, _o, _h, _l, _c, volume in rows:
        d = ts.date()
        daily_volume.setdefault(d, {})
        daily_volume[d][code] = daily_volume[d].get(code, 0) + int(volume or 0)

    dominant_by_day: dict[dt.date, str] = {}
    for d, contract_volume in daily_volume.items():
        dominant_by_day[d] = sorted(
            contract_volume.items(), key=lambda item: (-item[1], item[0])
        )[0][0]

    return [r for r in rows if dominant_by_day.get(r[1].date()) == r[0]]


def filter_to_single_code(rows: list[tuple], code: str) -> list[tuple]:
    """Keep ONLY rows from the specified contract code. Days with no data
    from that code are dropped (no fallback). This is the safer alternative
    to dominant-volume selection when you know which near-month is the
    legitimate active contract for the period."""
    return [r for r in rows if r[0] == code]


def write_csv(out_path: Path, rows: list[tuple]) -> int:
    """Write OHLCV rows in the schema the gate runner / backtest CSV loader expects.

    Schema parity with data/kospi200f_1m_ch_101S6000.csv:
    datetime, open, high, low, close, volume (NO 'code' column).
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["datetime", "open", "high", "low", "close", "volume"])
        for _code, ts, o, hi, lo, c, v in rows:
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
            w.writerow([ts_str, o, hi, lo, c, int(v)])
    return len(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (inclusive)")
    ap.add_argument(
        "--end",
        required=True,
        help="YYYY-MM-DD (inclusive); fetch is [start, end+1day) internally",
    )
    ap.add_argument("--out", required=True, help="output CSV path")
    ap.add_argument(
        "--single-code", default=None,
        help="if set, write ONLY this contract code's bars (bypasses dominant-"
             "volume selection); days lacking this code's data are dropped")
    a = ap.parse_args(argv)
    s = dt.date.fromisoformat(a.start)
    e_inclusive = dt.date.fromisoformat(a.end)
    e_exclusive = e_inclusive + dt.timedelta(days=1)

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

    raw = _fetch_a01_rows(client, s, e_exclusive)
    if a.single_code:
        clean = filter_to_single_code(raw, a.single_code)
    else:
        clean = select_dominant_per_day(raw)
    n = write_csv(Path(a.out), clean)
    mode = f"single_code={a.single_code}" if a.single_code else "dominant-volume"
    print(
        f"wrote {n} rows to {a.out}  "
        f"(mode={mode}; window {s} → {e_inclusive}; "
        f"{len(raw)} raw A01* rows seen)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
