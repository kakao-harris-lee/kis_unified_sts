#!/usr/bin/env python3
"""Probe KIS futures minute-history availability by date."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
from dotenv import load_dotenv

from shared.collector.historical.backfill import fetch_minute_async, parse_ohlcv
from shared.collector.historical.calendar import get_trading_days_range


async def _probe(code: str, start: str, end: str, max_pages: int) -> pd.DataFrame:
    start_d = datetime.strptime(start, "%Y-%m-%d").date()
    end_d = datetime.strptime(end, "%Y-%m-%d").date()
    trading_days = get_trading_days_range(start_d, end_d)

    rows: list[dict] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for d in trading_days:
            date_str = d.strftime("%Y%m%d")
            _, _, data = await fetch_minute_async(
                client,
                code,
                date_str,
                max_pages=max_pages,
            )

            if not isinstance(data, dict):
                rows.append(
                    {
                        "date": str(d),
                        "status": "error",
                        "rt_cd": "",
                        "output2_rows": 0,
                        "output2_dict_rows": 0,
                        "error": "invalid_response",
                    }
                )
                continue

            output2 = data.get("output2", [])
            if not isinstance(output2, list):
                output2 = []

            dict_rows = sum(1 for x in output2 if isinstance(x, dict))
            status = "ok" if data.get("rt_cd") == "0" else "error"

            bars = parse_ohlcv(code, date_str, data) if status == "ok" else []
            bar_count = len(bars)
            bar_start = bars[0][1].isoformat(sep=" ") if bar_count else ""
            bar_end = bars[-1][1].isoformat(sep=" ") if bar_count else ""
            bar_zero_ratio = (
                float(sum(1 for row in bars if int(row[6]) == 0) / bar_count)
                if bar_count
                else 0.0
            )
            bar_total_volume = int(sum(int(row[6]) for row in bars)) if bar_count else 0

            rows.append(
                {
                    "date": str(d),
                    "status": status,
                    "rt_cd": data.get("rt_cd", ""),
                    "output2_rows": len(output2),
                    "output2_dict_rows": dict_rows,
                    "bars": bar_count,
                    "bar_start": bar_start,
                    "bar_end": bar_end,
                    "bar_zero_ratio": bar_zero_ratio,
                    "bar_total_volume": bar_total_volume,
                    "error": data.get("error", ""),
                }
            )
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe KIS futures minute history coverage")
    parser.add_argument("--code", default="A01603")
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--output-csv", default="")
    args = parser.parse_args()

    # Reuse local env for KIS credentials.
    load_dotenv("/home/deploy/project/kis_unified_sts/.env")

    df = asyncio.run(_probe(args.code, args.start, args.end, args.max_pages))
    if df.empty:
        print("No trading days in range.")
        return 1

    with_data = df["output2_dict_rows"] > 0
    with_bars = df["bars"] > 0
    summary = {
        "code": args.code,
        "start": args.start,
        "end": args.end,
        "days_total": int(len(df)),
        "days_with_output2_dict_rows": int(with_data.sum()),
        "days_with_bars": int(with_bars.sum()),
        "median_bars_per_day": float(df.loc[with_bars, "bars"].median()) if with_bars.any() else 0.0,
        "mean_bars_per_day": float(df.loc[with_bars, "bars"].mean()) if with_bars.any() else 0.0,
        "mean_bar_zero_ratio": float(df.loc[with_bars, "bar_zero_ratio"].mean()) if with_bars.any() else 0.0,
        "first_with_data": str(df.loc[with_data, "date"].iloc[0]) if with_data.any() else "",
        "last_with_data": str(df.loc[with_data, "date"].iloc[-1]) if with_data.any() else "",
        "first_with_bars": str(df.loc[with_bars, "date"].iloc[0]) if with_bars.any() else "",
        "last_with_bars": str(df.loc[with_bars, "date"].iloc[-1]) if with_bars.any() else "",
    }
    print(summary)

    if args.output_csv:
        out = Path(args.output_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        print(f"saved={out}")
    else:
        print(df.to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
