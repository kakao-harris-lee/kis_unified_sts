#!/usr/bin/env python3
"""Audit local futures archive files for volume/phantom contamination."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd


@dataclass
class ArchiveReport:
    path: str
    rows: int
    days: int
    datetime_start: str
    datetime_end: str
    duplicate_datetimes: int
    zero_volume_ratio: float
    phantom_ratio: float
    good_days: int
    bad_days: int
    first_good_day: str
    last_good_day: str
    longest_good_run_days: int
    longest_good_run_start: str
    longest_good_run_end: str
    status: str
    failures: list[str]


def _longest_good_run(dates: list[pd.Timestamp], is_good: list[bool]) -> tuple[int, str, str]:
    best_len = 0
    best_start = ""
    best_end = ""
    cur_len = 0
    cur_start = ""
    cur_end = ""
    for dt, good in zip(dates, is_good, strict=True):
        d = str(dt.date())
        if good:
            if cur_len == 0:
                cur_start = d
            cur_len += 1
            cur_end = d
            if cur_len > best_len:
                best_len = cur_len
                best_start = cur_start
                best_end = cur_end
        else:
            cur_len = 0
            cur_start = ""
            cur_end = ""
    return best_len, best_start, best_end


def audit_file(
    path: Path,
    max_zero_volume_ratio: float,
    max_phantom_ratio: float,
    max_daily_zero_ratio: float,
) -> ArchiveReport:
    df = pd.read_csv(path)
    required = {"datetime", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        return ArchiveReport(
            path=str(path),
            rows=0,
            days=0,
            datetime_start="",
            datetime_end="",
            duplicate_datetimes=0,
            zero_volume_ratio=1.0,
            phantom_ratio=1.0,
            good_days=0,
            bad_days=0,
            first_good_day="",
            last_good_day="",
            longest_good_run_days=0,
            longest_good_run_start="",
            longest_good_run_end="",
            status="fail",
            failures=[f"missing_columns={sorted(missing)}"],
        )

    work = df.copy()
    work["datetime"] = pd.to_datetime(work["datetime"], errors="coerce")
    work = work.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    work["close"] = pd.to_numeric(work["close"], errors="coerce")
    work["volume"] = pd.to_numeric(work["volume"], errors="coerce").fillna(0)
    work["date"] = work["datetime"].dt.normalize()

    rows = len(work)
    dup_cnt = int(work["datetime"].duplicated().sum())
    zero_ratio = float((work["volume"] == 0).mean()) if rows else 0.0
    close_diff = work["close"].diff().abs().fillna(0)
    phantom_ratio = float(((work["volume"] == 0) & (close_diff > 0)).mean()) if rows else 0.0

    daily = work.groupby("date", as_index=True).agg(
        rows=("datetime", "size"),
        zero=("volume", lambda s: int((s == 0).sum())),
    )
    daily["zero_ratio"] = daily["zero"] / daily["rows"]
    good_mask = (daily["zero_ratio"] <= max_daily_zero_ratio).tolist()
    day_index = list(daily.index)
    good_days = int(sum(good_mask))
    bad_days = int(len(good_mask) - good_days)
    longest_run_days, longest_start, longest_end = _longest_good_run(day_index, good_mask)
    first_good = str(day_index[good_mask.index(True)].date()) if good_days else ""
    last_good = str(day_index[len(good_mask) - 1 - good_mask[::-1].index(True)].date()) if good_days else ""

    failures: list[str] = []
    if zero_ratio > max_zero_volume_ratio:
        failures.append(f"zero_volume_ratio={zero_ratio:.6f}>{max_zero_volume_ratio:.6f}")
    if phantom_ratio > max_phantom_ratio:
        failures.append(f"phantom_ratio={phantom_ratio:.6f}>{max_phantom_ratio:.6f}")
    if dup_cnt > 0:
        failures.append(f"duplicate_datetimes={dup_cnt}")
    if good_days == 0:
        failures.append("no_good_day")

    return ArchiveReport(
        path=str(path),
        rows=rows,
        days=int(daily.shape[0]),
        datetime_start=str(work["datetime"].min()) if rows else "",
        datetime_end=str(work["datetime"].max()) if rows else "",
        duplicate_datetimes=dup_cnt,
        zero_volume_ratio=zero_ratio,
        phantom_ratio=phantom_ratio,
        good_days=good_days,
        bad_days=bad_days,
        first_good_day=first_good,
        last_good_day=last_good,
        longest_good_run_days=longest_run_days,
        longest_good_run_start=longest_start,
        longest_good_run_end=longest_end,
        status="pass" if not failures else "fail",
        failures=failures,
    )


def _resolve_paths(paths: Iterable[str], glob_pattern: str) -> list[Path]:
    resolved: list[Path] = [Path(p) for p in paths]
    if not resolved:
        resolved = sorted(Path(".").glob(glob_pattern))
    return [p for p in resolved if p.exists() and p.is_file()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit futures archive CSV files")
    parser.add_argument("--paths", nargs="*", default=[])
    parser.add_argument("--glob", default="data/kospi200f_1m*.csv")
    parser.add_argument("--max-zero-volume-ratio", type=float, default=0.95)
    parser.add_argument("--max-phantom-ratio", type=float, default=0.20)
    parser.add_argument("--max-daily-zero-ratio", type=float, default=0.20)
    parser.add_argument("--json-output", default="")
    args = parser.parse_args()

    files = _resolve_paths(args.paths, args.glob)
    if not files:
        print("No files to audit.")
        return 1

    reports = [
        audit_file(
            path=f,
            max_zero_volume_ratio=args.max_zero_volume_ratio,
            max_phantom_ratio=args.max_phantom_ratio,
            max_daily_zero_ratio=args.max_daily_zero_ratio,
        )
        for f in files
    ]

    payload = {"reports": [asdict(r) for r in reports]}
    if args.json_output:
        out = Path(args.json_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for r in reports:
        print(f"[{r.status.upper()}] {r.path}")
        print(
            f"  rows={r.rows}, days={r.days}, range={r.datetime_start} ~ {r.datetime_end}, "
            f"zero={r.zero_volume_ratio:.6f}, phantom={r.phantom_ratio:.6f}, dup={r.duplicate_datetimes}"
        )
        print(
            f"  good_days={r.good_days}, longest_good_run={r.longest_good_run_days} "
            f"({r.longest_good_run_start} ~ {r.longest_good_run_end})"
        )
        if r.failures:
            print(f"  failures={r.failures}")

    return 0 if all(r.status == "pass" for r in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
