#!/usr/bin/env python3
"""Rebuild continuous 101S6000 minute bars from A01* full-size contracts.

Default: dry-run report + CSV export.
Apply mode: delete old 101S6000 rows in range and reinsert rebuilt rows.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from clickhouse_driver import Client
from dotenv import load_dotenv


@dataclass
class RebuildSummary:
    rows: int
    days: int
    start: str
    end: str
    zero_volume_ratio: float
    phantom_ratio: float


def _connect(database: str) -> Client:
    return Client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_NATIVE_PORT", "9000")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=database,
    )


def _load_minute_by_contract(
    client: Client,
    database: str,
    table: str,
    start: str | None,
    end: str | None,
) -> pd.DataFrame:
    where = "code LIKE 'A01%%'"
    params: dict[str, str] = {}
    if start:
        where += " AND datetime >= %(start)s"
        params["start"] = start
    if end:
        where += " AND datetime <= %(end)s"
        params["end"] = end

    rows = client.execute(
        f"""
        SELECT
            code,
            toStartOfMinute(datetime) AS dt,
            argMin(open, datetime) AS open,
            max(high) AS high,
            min(low) AS low,
            argMax(close, datetime) AS close,
            sum(volume) AS volume
        FROM {database}.{table}
        WHERE {where}
        GROUP BY code, dt
        ORDER BY dt, code
        """,
        params,
    )
    df = pd.DataFrame(
        rows,
        columns=["code", "datetime", "open", "high", "low", "close", "volume"],
    )
    return df


def _build_continuous(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    dfx = df.copy()
    dfx["date"] = pd.to_datetime(dfx["datetime"]).dt.date

    # Daily dominant contract by total volume.
    daily = (
        dfx.groupby(["date", "code"], as_index=False)["volume"]
        .sum()
        .sort_values(["date", "volume", "code"], ascending=[True, False, True])
    )
    daily_front = daily.drop_duplicates(subset=["date"], keep="first")

    merged = dfx.merge(
        daily_front[["date", "code"]].rename(columns={"code": "front_code"}),
        on="date",
        how="inner",
    )
    merged = merged[merged["code"] == merged["front_code"]].copy()
    merged.sort_values("datetime", inplace=True)

    merged["source_code"] = merged["code"]
    merged["code"] = "101S6000"
    merged = merged[["code", "datetime", "open", "high", "low", "close", "volume", "source_code"]]
    return merged.reset_index(drop=True)


def _summarize(df: pd.DataFrame) -> RebuildSummary:
    if df.empty:
        return RebuildSummary(0, 0, "", "", 0.0, 0.0)
    close_diff = df["close"].diff().abs().fillna(0)
    zero = df["volume"] == 0
    return RebuildSummary(
        rows=int(len(df)),
        days=int(df["datetime"].dt.date.nunique()),
        start=str(df["datetime"].min()),
        end=str(df["datetime"].max()),
        zero_volume_ratio=float(zero.mean()),
        phantom_ratio=float((zero & (close_diff > 0)).mean()),
    )


def _apply_to_clickhouse(
    client: Client,
    database: str,
    table: str,
    rebuilt: pd.DataFrame,
) -> None:
    if rebuilt.empty:
        return
    start = rebuilt["datetime"].min().strftime("%Y-%m-%d %H:%M:%S")
    end = rebuilt["datetime"].max().strftime("%Y-%m-%d %H:%M:%S")

    client.execute(
        f"""
        ALTER TABLE {database}.{table}
        DELETE WHERE code = '101S6000'
          AND datetime >= %(start)s
          AND datetime <= %(end)s
        """,
        {"start": start, "end": end},
    )

    values = [
        (
            "101S6000",
            row.datetime.to_pydatetime(),
            float(row.open),
            float(row.high),
            float(row.low),
            float(row.close),
            int(row.volume),
        )
        for row in rebuilt.itertuples(index=False)
    ]
    client.execute(
        f"""
        INSERT INTO {database}.{table}
        (code, datetime, open, high, low, close, volume)
        VALUES
        """,
        values,
    )


def main() -> int:
    load_dotenv(".env")

    parser = argparse.ArgumentParser(
        description="Rebuild continuous 101S6000 from A01* contracts"
    )
    parser.add_argument("--database", default="kospi")
    parser.add_argument("--table", default="kospi200f_1m")
    parser.add_argument("--start", default=None, help="YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--end", default=None, help="YYYY-MM-DD HH:MM:SS")
    parser.add_argument(
        "--output-csv",
        default="data/kospi200f_1m_rebuilt_from_a01.csv",
        help="Output CSV path",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply replacement to ClickHouse table",
    )
    args = parser.parse_args()

    client = _connect(args.database)
    raw = _load_minute_by_contract(
        client,
        database=args.database,
        table=args.table,
        start=args.start,
        end=args.end,
    )
    rebuilt = _build_continuous(raw)
    summary = _summarize(rebuilt)

    if args.output_csv:
        os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)
        rebuilt.to_csv(args.output_csv, index=False)

    print("=== Rebuild Summary ===")
    print(f"rows: {summary.rows}")
    print(f"days: {summary.days}")
    print(f"range: {summary.start} ~ {summary.end}")
    print(f"zero_volume_ratio: {summary.zero_volume_ratio:.6f}")
    print(f"phantom_ratio: {summary.phantom_ratio:.6f}")
    if not rebuilt.empty:
        front_mix = (
            rebuilt.groupby("source_code")["datetime"]
            .count()
            .sort_values(ascending=False)
            .head(10)
        )
        print("top source_code counts:")
        for code, count in front_mix.items():
            print(f"  {code}: {int(count)}")

    if args.apply:
        _apply_to_clickhouse(client, args.database, args.table, rebuilt)
        print("Applied rebuilt 101S6000 rows to ClickHouse.")
    else:
        print("Dry-run only. Use --apply to write back to ClickHouse.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
