#!/usr/bin/env python3
"""Rebuild continuous 101S6000 minute bars from A01* full-size contracts.

Default: dry-run report + CSV export.
Apply mode was removed with the external DB writer; the script now produces a dry-run
summary and optional CSV from Parquet source data.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from shared.storage.config import StorageConfig
from shared.storage.market_data_store import ParquetMarketDataStore


@dataclass
class RebuildSummary:
    rows: int
    days: int
    start: str
    end: str
    zero_volume_ratio: float
    phantom_ratio: float


def _store() -> ParquetMarketDataStore:
    storage_config = StorageConfig.load_or_default()
    return ParquetMarketDataStore(
        storage_config.market_data.parquet.root,
        asset_class="futures",
    )


def _load_minute_by_contract(
    store: ParquetMarketDataStore,
    start: str | None,
    end: str | None,
) -> pd.DataFrame:
    dataset_dir = store.root / "futures" / "minute"
    codes = sorted(
        path.name.removeprefix("code=")
        for path in dataset_dir.glob("code=A01*")
        if path.is_dir()
    )
    frames = [store.get_minute_bars(code, start=start, end=end) for code in codes]
    frames = [df for df in frames if not df.empty]
    if not frames:
        return pd.DataFrame(
            columns=["code", "datetime", "open", "high", "low", "close", "volume"]
        )
    return pd.concat(frames, ignore_index=True).sort_values(["datetime", "code"])


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
    merged = merged[
        ["code", "datetime", "open", "high", "low", "close", "volume", "source_code"]
    ]
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


def main() -> int:
    load_dotenv(".env")

    parser = argparse.ArgumentParser(
        description="Rebuild continuous 101S6000 from A01* contracts"
    )
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
        help="Removed; write the generated CSV through the Parquet backfill path",
    )
    args = parser.parse_args()

    if args.apply:
        raise SystemExit("--apply was removed; use the Parquet backfill path")

    store = _store()
    raw = _load_minute_by_contract(
        store,
        start=args.start,
        end=args.end,
    )
    rebuilt = _build_continuous(raw)
    summary = _summarize(rebuilt)

    if args.output_csv:
        output_path = Path(args.output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rebuilt.to_csv(output_path, index=False)

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

    print(
        "Dry-run only. Generated output should be imported through the Parquet backfill path."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
