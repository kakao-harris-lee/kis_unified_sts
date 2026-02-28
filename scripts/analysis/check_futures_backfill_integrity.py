#!/usr/bin/env python3
"""Compare KIS API samples against ClickHouse backfill rows for a single day."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime

import httpx
from clickhouse_driver import Client
from dotenv import load_dotenv

from shared.collector.historical.backfill import fetch_minute_async, parse_ohlcv


def _split_codes(raw: str) -> list[str]:
    if not raw:
        return []
    return [code.strip().upper() for code in raw.split(",") if code.strip()]


def _connect(database: str) -> Client:
    return Client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_NATIVE_PORT", "9000")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=database,
    )


@dataclass
class Stat:
    rows: int
    start: str
    end: str
    zero_volume_ratio: float
    total_volume: int
    non_minute_ratio: float


@dataclass
class CompareResult:
    code: str
    table: str
    trade_date: str
    api: Stat
    db: Stat
    db_vs_api_row_ratio: float
    status: str
    findings: list[str]


def _db_stats(client: Client, database: str, table: str, code: str, day: str) -> Stat:
    row = client.execute(
        f"""
        SELECT
            count() AS rows,
            min(datetime) AS min_dt,
            max(datetime) AS max_dt,
            sum(volume = 0) AS zero_rows,
            sum(volume) AS total_volume,
            countIf(toSecond(datetime) != 0) AS non_minute_rows
        FROM {database}.{table}
        WHERE code = %(code)s AND toDate(datetime) = toDate(%(day)s)
        """,
        {"code": code, "day": day},
    )[0]

    rows = int(row[0] or 0)
    min_dt = row[1]
    max_dt = row[2]
    zero_rows = int(row[3] or 0)
    total_volume = int(row[4] or 0)
    non_minute_rows = int(row[5] or 0)
    return Stat(
        rows=rows,
        start=str(min_dt) if min_dt else "",
        end=str(max_dt) if max_dt else "",
        zero_volume_ratio=(zero_rows / rows) if rows else 0.0,
        total_volume=total_volume,
        non_minute_ratio=(non_minute_rows / rows) if rows else 0.0,
    )


async def _api_stats(code: str, yyyymmdd: str, max_pages: int) -> Stat:
    async with httpx.AsyncClient(timeout=30.0) as client:
        _, _, data = await fetch_minute_async(client, code, yyyymmdd, max_pages=max_pages)

    bars = parse_ohlcv(code, yyyymmdd, data) if isinstance(data, dict) else []
    rows = len(bars)
    if not rows:
        return Stat(rows=0, start="", end="", zero_volume_ratio=0.0, total_volume=0, non_minute_ratio=0.0)

    vols = [int(r[6]) for r in bars]
    zero_rows = sum(1 for v in vols if v == 0)
    return Stat(
        rows=rows,
        start=bars[0][1].isoformat(sep=" "),
        end=bars[-1][1].isoformat(sep=" "),
        zero_volume_ratio=(zero_rows / rows),
        total_volume=int(sum(vols)),
        non_minute_ratio=0.0,
    )


def _evaluate(code: str, table: str, trade_date: str, api: Stat, db: Stat) -> CompareResult:
    findings: list[str] = []
    status = "pass"

    if api.rows == 0:
        status = "fail"
        findings.append("api_rows=0")
    if db.rows == 0 and api.rows > 0:
        status = "fail"
        findings.append("db_rows=0_while_api_has_data")

    row_ratio = float(db.rows / api.rows) if api.rows > 0 else 0.0
    if api.rows > 0 and row_ratio < 0.80:
        status = "fail"
        findings.append(f"db_vs_api_row_ratio={row_ratio:.4f}<0.8000")

    if db.non_minute_ratio > 0:
        status = "fail"
        findings.append(f"db_non_minute_ratio={db.non_minute_ratio:.4f}>0")

    if db.zero_volume_ratio > 0.95:
        status = "fail"
        findings.append(f"db_zero_volume_ratio={db.zero_volume_ratio:.4f}>0.9500")

    return CompareResult(
        code=code,
        table=table,
        trade_date=trade_date,
        api=api,
        db=db,
        db_vs_api_row_ratio=row_ratio,
        status=status,
        findings=findings,
    )


async def _run_for_codes(
    client: Client,
    database: str,
    table: str,
    codes: list[str],
    day: str,
    max_pages: int,
) -> list[CompareResult]:
    yyyymmdd = day.replace("-", "")
    results: list[CompareResult] = []
    for code in codes:
        api = await _api_stats(code, yyyymmdd, max_pages=max_pages)
        db = _db_stats(client, database, table, code, day)
        results.append(_evaluate(code, table, day, api, db))
    return results


def main() -> int:
    load_dotenv(".env")

    parser = argparse.ArgumentParser(description="Check KIS vs ClickHouse backfill integrity")
    parser.add_argument("--date", required=True, help="Trade date YYYY-MM-DD")
    parser.add_argument("--database", default="kospi")
    parser.add_argument("--mini-table", default="kospi_mini_1m")
    parser.add_argument("--futures-table", default="kospi200f_1m")
    parser.add_argument("--mini-codes", default="A05603")
    parser.add_argument("--futures-codes", default="A01603")
    parser.add_argument("--max-pages", type=int, default=260)
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    datetime.strptime(args.date, "%Y-%m-%d")
    mini_codes = _split_codes(args.mini_codes)
    futures_codes = _split_codes(args.futures_codes)

    if not mini_codes and not futures_codes:
        print("No codes provided.")
        return 1

    ch_client = _connect(args.database)

    async def _run() -> list[CompareResult]:
        all_results: list[CompareResult] = []
        if mini_codes:
            all_results.extend(
                await _run_for_codes(
                    ch_client,
                    database=args.database,
                    table=args.mini_table,
                    codes=mini_codes,
                    day=args.date,
                    max_pages=args.max_pages,
                )
            )
        if futures_codes:
            all_results.extend(
                await _run_for_codes(
                    ch_client,
                    database=args.database,
                    table=args.futures_table,
                    codes=futures_codes,
                    day=args.date,
                    max_pages=args.max_pages,
                )
            )
        return all_results

    results = asyncio.run(_run())
    payload = {"results": [asdict(r) for r in results]}

    for r in results:
        print(
            f"[{r.status.upper()}] {r.table}:{r.code} {r.trade_date} "
            f"api_rows={r.api.rows} db_rows={r.db.rows} "
            f"ratio={r.db_vs_api_row_ratio:.4f} db_non_minute={r.db.non_minute_ratio:.4f}"
        )
        if r.findings:
            print(f"  findings={r.findings}")

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"saved={args.output_json}")

    return 0 if all(r.status == "pass" for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
