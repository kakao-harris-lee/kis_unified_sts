#!/usr/bin/env python3
"""Audit RL futures OHLCV data quality.

Checks:
- duplicate datetime
- monotonic datetime
- zero-volume ratio
- zero-volume moving-price (phantom) ratio
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass

import pandas as pd
from dotenv import load_dotenv


@dataclass
class QualityReport:
    rows: int
    start: str
    end: str
    duplicate_datetime: int
    monotonic_datetime: bool
    zero_volume_ratio: float
    zero_volume_price_move_ratio: float
    close_min: float
    close_max: float


def analyze_df(df: pd.DataFrame) -> QualityReport:
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)

    close_diff = df["close"].diff().abs().fillna(0)
    zero_volume = df["volume"] == 0

    return QualityReport(
        rows=int(len(df)),
        start=str(df["datetime"].min()),
        end=str(df["datetime"].max()),
        duplicate_datetime=int(df["datetime"].duplicated().sum()),
        monotonic_datetime=bool(df["datetime"].is_monotonic_increasing),
        zero_volume_ratio=float(zero_volume.mean()),
        zero_volume_price_move_ratio=float((zero_volume & (close_diff > 0)).mean()),
        close_min=float(df["close"].min()),
        close_max=float(df["close"].max()),
    )


def load_from_clickhouse(
    database: str,
    table: str,
    symbol: str,
    start_date: str = "",
    end_date: str = "",
) -> pd.DataFrame:
    from clickhouse_driver import Client

    host = os.getenv("CLICKHOUSE_HOST", "localhost")
    user = os.getenv("CLICKHOUSE_USER", "default")
    password = os.getenv("CLICKHOUSE_PASSWORD", "")
    port = int(os.getenv("CLICKHOUSE_NATIVE_PORT", "9000"))

    client = Client(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )
    where_parts = ["code = %(symbol)s"]
    params: dict[str, str] = {"symbol": symbol}
    if start_date:
        where_parts.append("datetime >= %(start_date)s")
        params["start_date"] = start_date
    if end_date:
        where_parts.append("datetime <= %(end_date)s")
        params["end_date"] = end_date

    where_clause = " AND ".join(where_parts)
    rows = client.execute(
        f"""
        SELECT datetime, open, high, low, close, volume
        FROM {database}.{table}
        WHERE {where_clause}
        ORDER BY datetime
        """,
        params,
    )
    return pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])


def main() -> int:
    load_dotenv(".env")

    parser = argparse.ArgumentParser(description="Audit RL futures data quality")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", type=str, help="CSV path")
    src.add_argument("--clickhouse", action="store_true", help="Load from ClickHouse")

    parser.add_argument("--database", type=str, default="kospi")
    parser.add_argument("--table", type=str, default="kospi200f_1m")
    parser.add_argument("--symbol", type=str, default="101S6000")
    parser.add_argument("--start-date", type=str, default="", help="YYYY-MM-DD[ HH:MM:SS]")
    parser.add_argument("--end-date", type=str, default="", help="YYYY-MM-DD[ HH:MM:SS]")
    parser.add_argument("--max-zero-volume-ratio", type=float, default=0.95)
    parser.add_argument("--max-phantom-ratio", type=float, default=0.20)
    args = parser.parse_args()

    if args.csv:
        df = pd.read_csv(args.csv)
        source = {"type": "csv", "path": args.csv}
    else:
        df = load_from_clickhouse(
            args.database,
            args.table,
            args.symbol,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        source = {
            "type": "clickhouse",
            "database": args.database,
            "table": args.table,
            "symbol": args.symbol,
            "start_date": args.start_date,
            "end_date": args.end_date,
        }

    if df.empty:
        print(json.dumps({"source": source, "error": "empty dataset"}, ensure_ascii=False, indent=2))
        return 2

    report = analyze_df(df)
    failures: list[str] = []
    if report.duplicate_datetime > 0:
        failures.append(f"duplicate_datetime={report.duplicate_datetime}")
    if not report.monotonic_datetime:
        failures.append("non_monotonic_datetime")
    if report.zero_volume_ratio > args.max_zero_volume_ratio:
        failures.append(
            f"zero_volume_ratio={report.zero_volume_ratio:.4f}>{args.max_zero_volume_ratio:.4f}"
        )
    if report.zero_volume_price_move_ratio > args.max_phantom_ratio:
        failures.append(
            "zero_volume_price_move_ratio="
            f"{report.zero_volume_price_move_ratio:.4f}>{args.max_phantom_ratio:.4f}"
        )

    print(
        json.dumps(
            {
                "source": source,
                "report": asdict(report),
                "thresholds": {
                    "max_zero_volume_ratio": args.max_zero_volume_ratio,
                    "max_phantom_ratio": args.max_phantom_ratio,
                },
                "status": "fail" if failures else "pass",
                "failures": failures,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
