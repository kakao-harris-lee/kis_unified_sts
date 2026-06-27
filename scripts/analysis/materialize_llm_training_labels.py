#!/usr/bin/env python3
"""Materialize horizon labels for LLM training rows.

Input:
  - training rows JSONL (default: output/llm/training_rows.jsonl)
  - trade outcomes JSONL (default: output/llm/trade_outcomes.jsonl)

Output:
  - labeled JSONL (default: output/llm/training_rows_labeled.jsonl)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def _parse_yyyymmdd(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y%m%d")
    except Exception:
        return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                continue
    return out


def _build_trade_outcome_map(
    events: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    entry_map: dict[str, dict[str, Any]] = {}
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for e in events:
        et = str(e.get("event", ""))
        pid = str(e.get("position_id", ""))
        if not pid:
            continue
        if et == "entry":
            entry_map[pid] = e
            continue
        if et != "exit":
            continue
        entry = entry_map.get(pid, {})
        snapshot_id = str(e.get("snapshot_id") or entry.get("snapshot_id") or "")
        code = str(e.get("code") or entry.get("code") or "")
        if not snapshot_id or not code:
            continue
        out[(snapshot_id, code)] = {
            "trade_pnl": e.get("trade_pnl"),
            "trade_pnl_pct": e.get("trade_pnl_pct"),
            "hold_seconds": e.get("hold_seconds"),
            "exit_reason": e.get("reason"),
        }
    return out


def _load_daily_closes_from_parquet(
    code: str,
    start_date: datetime,
    end_date: datetime,
) -> list[tuple[datetime, float]]:
    try:
        from shared.backtest.daily_adapter import load_stock_daily_from_parquet
    except Exception:
        return []

    try:
        df = load_stock_daily_from_parquet(
            code,
            start_date=start_date.date(),
            end_date=end_date.date(),
        )
    except Exception:
        return []

    closes: list[tuple[datetime, float]] = []
    for row in df.itertuples(index=False):
        dt = getattr(row, "datetime", None)
        close = getattr(row, "close", None)
        if dt is None or close is None:
            continue
        try:
            if isinstance(dt, datetime):
                ts = dt
            else:
                ts = datetime.combine(dt, datetime.min.time())
            closes.append((ts, float(close)))
        except Exception:
            continue
    return closes


def _fetch_forward_returns(
    code: str, base_date: datetime, horizons: list[int]
) -> dict[int, float | None]:
    start = base_date - timedelta(days=10)
    end = base_date + timedelta(days=max(horizons) * 3 + 10)
    closes = _load_daily_closes_from_parquet(code, start, end)
    if not closes:
        return dict.fromkeys(horizons)

    base_idx = None
    for i, (ts, _) in enumerate(closes):
        if ts.date() <= base_date.date():
            base_idx = i
        else:
            break
    if base_idx is None:
        return dict.fromkeys(horizons)

    base_price = float(closes[base_idx][1])
    if base_price <= 0:
        return dict.fromkeys(horizons)

    out: dict[int, float | None] = {}
    for h in horizons:
        target_idx = base_idx + h
        if target_idx >= len(closes):
            out[h] = None
            continue
        target = float(closes[target_idx][1])
        out[h] = ((target / base_price) - 1.0) * 100.0
    return out


def materialize(
    training_rows_path: Path,
    trade_outcomes_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    rows = _load_jsonl(training_rows_path)
    events = _load_jsonl(trade_outcomes_path)
    trade_map = _build_trade_outcome_map(events)

    cache: dict[tuple[str, str], dict[int, float | None]] = {}
    written = 0
    with open(output_path, "w", encoding="utf-8") as out_f:
        for row in rows:
            snapshot_id = str(row.get("snapshot_id", ""))
            code = str(row.get("code", ""))
            date_str = str(row.get("date", ""))
            labels = row.get("labels")
            if not isinstance(labels, dict):
                labels = {}
                row["labels"] = labels

            base_date = _parse_yyyymmdd(date_str)
            if code and base_date:
                key = (code, date_str)
                if key not in cache:
                    cache[key] = _fetch_forward_returns(code, base_date, [1, 3, 5])
                fr = cache[key]
                labels["horizon_return_1d"] = fr.get(1)
                labels["horizon_return_3d"] = fr.get(3)
                labels["horizon_return_5d"] = fr.get(5)

            tr = trade_map.get((snapshot_id, code))
            if tr:
                labels["trade_pnl"] = tr.get("trade_pnl")
                labels["trade_pnl_pct"] = tr.get("trade_pnl_pct")
                labels["trade_hold_seconds"] = tr.get("hold_seconds")
                labels["trade_exit_reason"] = tr.get("exit_reason")

            out_f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            written += 1

    return {
        "rows_in": len(rows),
        "events_in": len(events),
        "rows_out": written,
        "output": str(output_path),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Materialize labels for LLM training rows.")
    p.add_argument(
        "--training-rows",
        default="output/llm/training_rows.jsonl",
        help="Path to training rows JSONL",
    )
    p.add_argument(
        "--trade-outcomes",
        default="output/llm/trade_outcomes.jsonl",
        help="Path to trade outcomes JSONL",
    )
    p.add_argument(
        "--output",
        default="output/llm/training_rows_labeled.jsonl",
        help="Output JSONL path",
    )
    args = p.parse_args()

    res = materialize(
        Path(args.training_rows),
        Path(args.trade_outcomes),
        Path(args.output),
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
