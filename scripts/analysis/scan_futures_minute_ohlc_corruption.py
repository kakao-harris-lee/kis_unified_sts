#!/usr/bin/env python3
"""Scan the futures-minute Parquet store for OHLC corruption.

Detects the KIS duplicate-timestamp divergence signature that the bar-density
completeness gate cannot see: days that carry a full bar count but contain
internally-inconsistent / phantom-offset bars.

Two signatures are reported per (code, date):

1. ``ohlc_violations`` — bars where ``high < max(open, close, low)`` or
   ``low > min(open, close, high)`` (a literal ordering violation).  The fixed
   ingest never emits these; any here are legacy-corrupt bars still on disk.
2. ``phantom_wick`` — a *cluster* of bars whose wick (the gap between high/low
   and the body) exceeds ``--wick-pct`` of price.  A divergent phantom series
   runs as a sustained parallel offset, so it shows up as many similarly-sized
   large wicks within one day.  A genuinely volatile session produces scattered,
   not clustered-and-uniform, large wicks.

This is a lower bound on corruption: the legacy aggregator's Frankenstein output
depends on the interleaving order, so some raw-divergent days do not surface a
visible wick.  Use ``check_futures_backfill_integrity.py`` to confirm a specific
day against the live KIS response.

Usage:
    python -m scripts.analysis.scan_futures_minute_ohlc_corruption
    python -m scripts.analysis.scan_futures_minute_ohlc_corruption --code 101S6000
    python -m scripts.analysis.scan_futures_minute_ohlc_corruption --wick-pct 1.0 --min-cluster 8 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date

from shared.storage.config import StorageConfig
from shared.storage.market_data_store import ParquetMarketDataStore

# Defaults: a day with >= MIN_CLUSTER bars whose wick exceeds WICK_PCT of price,
# where the median of those large wicks is itself >= WICK_PCT, is flagged.
_DEFAULT_WICK_PCT: float = 1.0
_DEFAULT_MIN_CLUSTER: int = 8


@dataclass
class DayReport:
    """Per-(code, date) corruption findings."""

    code: str
    trade_date: date
    bars: int
    ohlc_violations: int
    big_wick_bars: int
    median_big_wick_pct: float
    max_wick_pct: float
    flagged: bool = field(default=False)


def _excluded(code: str) -> bool:
    """The KOSPI200 index (0001) is not a futures contract; skip it."""
    return code == "0001"


def scan_store(
    *,
    root: str | None = None,
    codes: list[str] | None = None,
    wick_pct: float = _DEFAULT_WICK_PCT,
    min_cluster: int = _DEFAULT_MIN_CLUSTER,
) -> list[DayReport]:
    """Scan the futures-minute store and return flagged day reports.

    Args:
        root: Optional Parquet root override (defaults to configured store).
        codes: Optional explicit code list; defaults to all futures codes found.
        wick_pct: Per-bar wick threshold as a percent of close.
        min_cluster: Minimum number of large-wick bars in a day to flag it.

    Returns:
        Sorted list of flagged :class:`DayReport` (one per corrupt code/date).
    """
    import duckdb

    storage_config = StorageConfig.load_or_default()
    parquet_root = root or storage_config.market_data.parquet.root
    base = f"{parquet_root}/futures/minute"

    if codes is None:
        store = ParquetMarketDataStore(parquet_root, asset_class="futures")
        # dataset_manifest does not enumerate codes; discover from the filesystem.
        import glob
        import os

        codes = sorted(
            os.path.basename(p).split("=", 1)[1] for p in glob.glob(f"{base}/code=*")
        )
        _ = store  # constructed to validate the store path resolves

    threshold = wick_pct / 100.0
    con = duckdb.connect()
    reports: list[DayReport] = []
    for code in codes:
        if _excluded(code):
            continue
        glob_path = f"{base}/code={code}/**/*.parquet"
        try:
            df = con.execute(
                """
                SELECT CAST(datetime AS DATE) AS d,
                       count(*) AS n,
                       sum(
                           CASE WHEN high < GREATEST(open, close, low) - 1e-9
                                  OR low > LEAST(open, close, high) + 1e-9
                                THEN 1 ELSE 0 END
                       ) AS ohlc_viol,
                       sum(
                           CASE WHEN GREATEST(
                                        high - GREATEST(open, close),
                                        LEAST(open, close) - low
                                    ) / NULLIF(close, 0) > ?
                                THEN 1 ELSE 0 END
                       ) AS big_wick,
                       median(
                           GREATEST(
                               high - GREATEST(open, close),
                               LEAST(open, close) - low
                           ) / NULLIF(close, 0)
                       ) FILTER (
                           WHERE GREATEST(
                                     high - GREATEST(open, close),
                                     LEAST(open, close) - low
                                 ) / NULLIF(close, 0) > ?
                       ) AS med_big_wick,
                       max(
                           GREATEST(
                               high - GREATEST(open, close),
                               LEAST(open, close) - low
                           ) / NULLIF(close, 0)
                       ) AS max_wick
                FROM read_parquet(?, hive_partitioning=1)
                GROUP BY 1
                ORDER BY 1
                """,
                [threshold, threshold, glob_path],
            ).df()
        except Exception as exc:  # pragma: no cover - missing/empty partitions
            print(f"  {code}: skip ({exc})", file=sys.stderr)
            continue

        for row in df.itertuples(index=False):
            med_big = (
                float(row.med_big_wick) if row.med_big_wick == row.med_big_wick else 0.0
            )
            flagged = bool(row.ohlc_viol) or (
                int(row.big_wick) >= min_cluster and med_big >= threshold
            )
            if not flagged:
                continue
            trade_day = row.d
            # DuckDB returns a pandas Timestamp for CAST(... AS DATE); normalise.
            trade_day = trade_day.date() if hasattr(trade_day, "date") else trade_day
            reports.append(
                DayReport(
                    code=code,
                    trade_date=trade_day,
                    bars=int(row.n),
                    ohlc_violations=int(row.ohlc_viol),
                    big_wick_bars=int(row.big_wick),
                    median_big_wick_pct=round(med_big * 100, 2),
                    max_wick_pct=round(float(row.max_wick) * 100, 2),
                    flagged=True,
                )
            )

    reports.sort(key=lambda r: (r.code, r.trade_date))
    return reports


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Parquet root override")
    parser.add_argument(
        "--code",
        action="append",
        dest="codes",
        help="Restrict to a code (repeatable); default all futures codes",
    )
    parser.add_argument(
        "--wick-pct",
        type=float,
        default=_DEFAULT_WICK_PCT,
        help=f"Per-bar wick threshold (%% of close); default {_DEFAULT_WICK_PCT}",
    )
    parser.add_argument(
        "--min-cluster",
        type=int,
        default=_DEFAULT_MIN_CLUSTER,
        help=f"Min large-wick bars to flag a day; default {_DEFAULT_MIN_CLUSTER}",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    reports = scan_store(
        root=args.root,
        codes=args.codes,
        wick_pct=args.wick_pct,
        min_cluster=args.min_cluster,
    )
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "code": r.code,
                        "date": r.trade_date.isoformat(),
                        "bars": r.bars,
                        "ohlc_violations": r.ohlc_violations,
                        "big_wick_bars": r.big_wick_bars,
                        "median_big_wick_pct": r.median_big_wick_pct,
                        "max_wick_pct": r.max_wick_pct,
                    }
                    for r in reports
                ],
                indent=2,
            )
        )
        return 0

    if not reports:
        print("No corrupt futures-minute sessions found.")
        return 0

    by_code: dict[str, int] = {}
    for r in reports:
        by_code[r.code] = by_code.get(r.code, 0) + 1
    print(f"Flagged {len(reports)} corrupt (code, date) sessions:\n")
    print(
        f"{'code':<10} {'date':<12} {'bars':>5} {'ohlc_v':>7} "
        f"{'wick_n':>7} {'med%':>6} {'max%':>6}"
    )
    for r in reports:
        print(
            f"{r.code:<10} {r.trade_date.isoformat():<12} {r.bars:>5} "
            f"{r.ohlc_violations:>7} {r.big_wick_bars:>7} "
            f"{r.median_big_wick_pct:>6} {r.max_wick_pct:>6}"
        )
    print(
        "\nPer-code totals: "
        + ", ".join(f"{c}={n}" for c, n in sorted(by_code.items()))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
