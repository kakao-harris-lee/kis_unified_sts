#!/usr/bin/env python3
"""Compare OVS A/B paper logs by symbol/minute entry timing.

Parses two orchestrator log files and produces:
- combined_entries.csv
- minute_alignment.csv
- summary.md
"""

from __future__ import annotations

import argparse
import re
import warnings
from pathlib import Path

import pandas as pd

TS_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d{3}")
OVS_RE = re.compile(
    r"Opening volume surge ENTRY: (?P<code>\d+)\s+"
    r".*?rvol=(?P<rvol>[-+]?\d+(?:\.\d+)?)\s+"
    r".*?score=(?P<score>[-+]?\d+(?:\.\d+)?)"
)
EXEC_RE = re.compile(
    r"Entry executed:\s+.*?\((?P<code>\d+)\)\s+@\s+(?P<price>[-+]?\d+(?:\.\d+)?)\s+x\s+(?P<qty>\d+)"
)


def _parse_log(path: Path, profile: str) -> pd.DataFrame:
    rows: list[dict] = []
    if not path.exists():
        return pd.DataFrame()

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            ts_m = TS_RE.search(line)
            if not ts_m:
                continue
            ts = pd.to_datetime(ts_m.group("ts"), errors="coerce")
            if pd.isna(ts):
                continue

            ovs_m = OVS_RE.search(line)
            if ovs_m:
                rows.append(
                    {
                        "profile": profile,
                        "event": "signal",
                        "timestamp": ts,
                        "code": ovs_m.group("code"),
                        "score": float(ovs_m.group("score")),
                        "rvol": float(ovs_m.group("rvol")),
                        "price": None,
                        "qty": None,
                        "raw": line.strip(),
                    }
                )
                continue

            ex_m = EXEC_RE.search(line)
            if ex_m:
                rows.append(
                    {
                        "profile": profile,
                        "event": "fill",
                        "timestamp": ts,
                        "code": ex_m.group("code"),
                        "score": None,
                        "rvol": None,
                        "price": float(ex_m.group("price")),
                        "qty": int(ex_m.group("qty")),
                        "raw": line.strip(),
                    }
                )

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    df["minute"] = df["timestamp"].dt.floor("min")
    df["date"] = df["timestamp"].dt.date.astype(str)
    return df


def _build_alignment(df: pd.DataFrame, profile_a: str, profile_b: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    sig = df[df["event"] == "signal"].copy()
    if sig.empty:
        return pd.DataFrame()

    a = sig[sig["profile"] == profile_a].copy()
    b = sig[sig["profile"] == profile_b].copy()

    a = (
        a.groupby(["code", "minute"], as_index=False)
        .agg(
            score_a=("score", "max"),
            count_a=("event", "size"),
            ts_a=("timestamp", "min"),
        )
    )
    b = (
        b.groupby(["code", "minute"], as_index=False)
        .agg(
            score_b=("score", "max"),
            count_b=("event", "size"),
            ts_b=("timestamp", "min"),
        )
    )

    merged = a.merge(b, on=["code", "minute"], how="outer")
    merged["date"] = pd.to_datetime(merged["minute"]).dt.date.astype(str)
    merged["in_a"] = merged["score_a"].notna()
    merged["in_b"] = merged["score_b"].notna()
    merged["state"] = merged.apply(
        lambda r: "both" if (r["in_a"] and r["in_b"]) else ("a_only" if r["in_a"] else "b_only"),
        axis=1,
    )
    return merged.sort_values(["minute", "code"]).reset_index(drop=True)


def _write_summary(path: Path, df: pd.DataFrame, align: pd.DataFrame, a: str, b: str) -> None:
    lines: list[str] = []
    lines.append("# OVS A/B Log Comparison")
    lines.append("")
    if df.empty:
        lines.append("- No parsable events found.")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    lines.append("## Event Counts")
    for prof in (a, b):
        sub = df[df["profile"] == prof]
        sig_n = int((sub["event"] == "signal").sum())
        fill_n = int((sub["event"] == "fill").sum())
        lines.append(f"- {prof}: signal={sig_n}, fill={fill_n}")
    lines.append("")

    if not align.empty:
        lines.append("## Signal Minute Overlap")
        total = len(align)
        both = int((align["state"] == "both").sum())
        a_only = int((align["state"] == "a_only").sum())
        b_only = int((align["state"] == "b_only").sum())
        lines.append(f"- total(code,minute): {total}")
        lines.append(f"- both: {both}")
        lines.append(f"- {a} only: {a_only}")
        lines.append(f"- {b} only: {b_only}")
        if total > 0:
            lines.append(f"- overlap_rate: {both / total * 100.0:.1f}%")
        lines.append("")

        top_a = (
            align[align["state"] == "a_only"]
            .groupby("code")
            .size()
            .sort_values(ascending=False)
            .head(10)
        )
        if len(top_a) > 0:
            lines.append(f"## {a} Only Top Codes")
            for code, n in top_a.items():
                lines.append(f"- {code}: {int(n)}")
            lines.append("")

        top_b = (
            align[align["state"] == "b_only"]
            .groupby("code")
            .size()
            .sort_values(ascending=False)
            .head(10)
        )
        if len(top_b) > 0:
            lines.append(f"## {b} Only Top Codes")
            for code, n in top_b.items():
                lines.append(f"- {code}: {int(n)}")
            lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare OVS A/B log files")
    parser.add_argument("--log-a", required=True)
    parser.add_argument("--log-b", required=True)
    parser.add_argument("--profile-a", default="score_1p8")
    parser.add_argument("--profile-b", default="combo_balanced")
    parser.add_argument("--output-dir", default="artifacts/ovs_ab_compare")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df_a = _parse_log(Path(args.log_a), args.profile_a)
    df_b = _parse_log(Path(args.log_b), args.profile_b)
    if not df_a.empty and not df_b.empty:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            df = pd.concat([df_a, df_b], ignore_index=True)
    elif not df_a.empty:
        df = df_a.copy()
    elif not df_b.empty:
        df = df_b.copy()
    else:
        df = pd.DataFrame()

    combined_path = out_dir / "combined_entries.csv"
    align_path = out_dir / "minute_alignment.csv"
    summary_path = out_dir / "summary.md"

    if df.empty:
        pd.DataFrame().to_csv(combined_path, index=False)
        pd.DataFrame().to_csv(align_path, index=False)
        _write_summary(summary_path, df, pd.DataFrame(), args.profile_a, args.profile_b)
        print(f"No events parsed. Wrote empty outputs to {out_dir}")
        return 0

    df = df.sort_values("timestamp").reset_index(drop=True)
    df.to_csv(combined_path, index=False)

    align = _build_alignment(df, args.profile_a, args.profile_b)
    align.to_csv(align_path, index=False)
    _write_summary(summary_path, df, align, args.profile_a, args.profile_b)

    print(
        f"Wrote comparison: events={len(df)}, aligned={len(align)} -> {out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
