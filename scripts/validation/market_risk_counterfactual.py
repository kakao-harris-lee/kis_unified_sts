#!/usr/bin/env python3
"""Retroactive Market Risk Score gate over paper trades (roadmap §4.4-3).

Applies the §4.2 HIGH-band rule — "score >= 70 blocks NEW LONG entries" — to
trades already recorded in the RuntimeLedger and compares the realized PnL of
would-have-been-blocked trades vs allowed trades. Shorts are never blocked
(long/short symmetry: the gate only vetoes new longs).

Look-ahead safety: for each trade the gate consults only knowledge available
at entry — the same-day ``premarket`` Parquet snapshot when the entry is at or
after the premarket cutoff (08:00 KST), otherwise the latest ``close`` row
strictly before the entry date. Missing/degraded scores fail open (allowed),
matching the RegimeGate PERMISSIVE-on-miss precedent.

Read-only analysis: nothing is written back to the ledger or any runtime path.

Usage:
    python scripts/validation/market_risk_counterfactual.py
    python scripts/validation/market_risk_counterfactual.py \
        --start 2026-01-02 --end 2026-07-01 --tag phase1-gate
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.validation.market_risk_common import (
    KST,
    CounterfactualSettings,
    MarketRiskValidationConfig,
    build_store,
    is_missing,
    load_snapshot_frame,
)

INSUFFICIENT_DATA = "insufficient data"

_DETAIL_ROW_LIMIT = 50


# ---------------------------------------------------------------------------
# Entry-time score lookup (look-ahead safe)
# ---------------------------------------------------------------------------


def parse_entry_kst(value: Any, assume_naive_tz: str) -> datetime | None:
    """Parse a ledger entry timestamp into an aware KST datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(assume_naive_tz))
    return parsed.astimezone(KST)


class ScoreLookup:
    """Score-as-of-entry resolver over the market-structure snapshot rows."""

    def __init__(
        self,
        close_frame: Any,
        premarket_frame: Any,
        settings: CounterfactualSettings,
        premarket_cutoff: time | None,
    ):
        self._settings = settings
        self._premarket_cutoff = premarket_cutoff
        self._close = self._usable_rows(close_frame)
        self._close_days = [day for day, _ in self._close]
        self._premarket = dict(self._usable_rows(premarket_frame))

    def _usable_rows(self, frame: Any) -> list[tuple[date, float]]:
        rows: list[tuple[date, float]] = []
        if frame is None or getattr(frame, "empty", True):
            return rows
        for record in frame.to_dict(orient="records"):
            day = record.get("trade_date")
            if day is None:
                continue
            if self._settings.exclude_degraded and bool(
                record.get("degraded")
                if not is_missing(record.get("degraded"))
                else False
            ):
                continue
            score = next(
                (
                    record.get(name)
                    for name in self._settings.score_columns
                    if not is_missing(record.get(name))
                ),
                None,
            )
            if score is None:
                continue
            rows.append((day, float(score)))
        rows.sort(key=lambda item: item[0])
        return rows

    @property
    def has_scores(self) -> bool:
        return bool(self._close) or bool(self._premarket)

    def score_at_entry(self, entry_kst: datetime) -> tuple[float | None, str | None]:
        """(score, source) known at entry; ``(None, None)`` = fail-open."""
        entry_day = entry_kst.date()
        if (
            self._settings.prefer_premarket
            and self._premarket_cutoff is not None
            and entry_kst.time() >= self._premarket_cutoff
            and entry_day in self._premarket
        ):
            return self._premarket[entry_day], f"premarket:{entry_day.isoformat()}"
        # Latest close row strictly before the entry date (bisect on sorted days).
        import bisect

        index = bisect.bisect_left(self._close_days, entry_day)
        if index > 0:
            day, score = self._close[index - 1]
            return score, f"close:{day.isoformat()}"
        return None, None


# ---------------------------------------------------------------------------
# Trade classification
# ---------------------------------------------------------------------------


def load_trades(
    ledger: Any,
    settings: CounterfactualSettings,
    start: date | None,
    end: date | None,
) -> tuple[list[dict[str, Any]], int]:
    """Ledger trades filtered by asset class and entry-date window (KST).

    Returns ``(trades_with_entry_kst, unparseable_entry_count)``; each kept
    trade gains an ``entry_kst`` key.
    """
    trades = ledger.query_trades({"limit": 0})
    kept: list[dict[str, Any]] = []
    unparseable = 0
    for trade in trades:
        if settings.asset_classes and (
            str(trade.get("asset_class") or "") not in settings.asset_classes
        ):
            continue
        entry_kst = parse_entry_kst(
            trade.get("entry_time"), settings.assume_naive_entry_tz
        )
        if entry_kst is None:
            unparseable += 1
            continue
        entry_day = entry_kst.date()
        if start is not None and entry_day < start:
            continue
        if end is not None and entry_day > end:
            continue
        trade = dict(trade)
        trade["entry_kst"] = entry_kst
        kept.append(trade)
    kept.sort(key=lambda item: item["entry_kst"])
    return kept, unparseable


def classify_trades(
    trades: list[dict[str, Any]],
    lookup: ScoreLookup,
    settings: CounterfactualSettings,
) -> list[dict[str, Any]]:
    """Tag each trade with the entry-time score and the block decision."""
    block_sides = {side.lower() for side in settings.block_sides}
    rows: list[dict[str, Any]] = []
    for trade in trades:
        entry_kst: datetime = trade["entry_kst"]
        score, source = lookup.score_at_entry(entry_kst)
        side = str(trade.get("side") or "").lower()
        blocked = (
            side in block_sides
            and score is not None
            and score >= settings.block_threshold
        )
        pnl = trade.get("pnl")
        rows.append(
            {
                "trade_id": trade.get("id"),
                "asset_class": trade.get("asset_class"),
                "symbol": trade.get("symbol"),
                "strategy": trade.get("strategy"),
                "side": side,
                "entry_kst": entry_kst.isoformat(),
                "score": score,
                "score_source": source,
                "blocked": blocked,
                "pnl": float(pnl) if not is_missing(pnl) else None,
            }
        )
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Blocked-vs-allowed realized PnL aggregates + fail-open counts."""

    def aggregate(group: list[dict[str, Any]]) -> dict[str, Any]:
        pnls = [row["pnl"] for row in group if row["pnl"] is not None]
        return {
            "trades": len(group),
            "pnl_sum": float(sum(pnls)) if pnls else 0.0,
            "pnl_mean": float(sum(pnls) / len(pnls)) if pnls else None,
            "pnl_missing": len(group) - len(pnls),
        }

    blocked = [row for row in rows if row["blocked"]]
    allowed = [row for row in rows if not row["blocked"]]
    summary = {
        "total_trades": len(rows),
        "blocked": aggregate(blocked),
        "allowed": aggregate(allowed),
        "fail_open_no_score": sum(1 for row in rows if row["score"] is None),
        "by_side": {},
    }
    for side in sorted({row["side"] for row in rows}):
        side_rows = [row for row in rows if row["side"] == side]
        summary["by_side"][side] = {
            "blocked": aggregate([row for row in side_rows if row["blocked"]]),
            "allowed": aggregate([row for row in side_rows if not row["blocked"]]),
        }
    # The gate adds value when the PnL it would have blocked is negative.
    summary["blocked_pnl_avoided"] = -summary["blocked"]["pnl_sum"]
    return summary


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _money(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+,.0f}"


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Market Risk Score — counterfactual long-block gate (§4.4-3)",
        "",
        f"- generated_at_kst: {report['generated_at_kst']}",
        f"- ledger: {report['ledger_path']}",
        f"- entry window (KST): {report['window_start'] or 'begin'}"
        f" .. {report['window_end'] or 'end'}",
        f"- rule: score >= {report['block_threshold']:.0f} blocks new"
        f" {'/'.join(report['block_sides'])} entries (fail-open on missing score)",
        "",
        "## Summary",
        "",
        "| group | trades | realized PnL sum | mean PnL | pnl missing |",
        "|---|---|---|---|---|",
    ]
    for name in ("blocked", "allowed"):
        group = summary[name]
        lines.append(
            f"| {name} | {group['trades']} | {_money(group['pnl_sum'])}"
            f" | {_money(group['pnl_mean'])} | {group['pnl_missing']} |"
        )
    lines += [
        "",
        f"- fail-open (no usable score at entry): {summary['fail_open_no_score']}"
        f" trades / unparseable entry_time skipped: {report['unparseable_entries']}",
        f"- PnL the gate would have avoided (−blocked sum):"
        f" {_money(summary['blocked_pnl_avoided'])}"
        f" — positive = gate adds value",
        "",
        "## Per-side breakdown",
        "",
        "| side | blocked n | blocked PnL | allowed n | allowed PnL |",
        "|---|---|---|---|---|",
    ]
    for side, group in summary["by_side"].items():
        lines.append(
            f"| {side or 'n/a'} | {group['blocked']['trades']}"
            f" | {_money(group['blocked']['pnl_sum'])}"
            f" | {group['allowed']['trades']}"
            f" | {_money(group['allowed']['pnl_sum'])} |"
        )

    blocked_rows = [row for row in report["trades"] if row["blocked"]]
    lines += [
        "",
        f"## Blocked trades ({len(blocked_rows)}, first {_DETAIL_ROW_LIMIT})",
        "",
        "| entry (KST) | symbol | strategy | side | score | source | PnL |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in blocked_rows[:_DETAIL_ROW_LIMIT]:
        lines.append(
            f"| {row['entry_kst']} | {row['symbol']} | {row['strategy']}"
            f" | {row['side']} | {row['score']:.1f} | {row['score_source']}"
            f" | {_money(row['pnl'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_reports(
    report: dict[str, Any], out_dir: Path, tag: str | None
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = tag or datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"market_risk_counterfactual_{stamp}.json"
    md_path = out_dir / f"market_risk_counterfactual_{stamp}.md"
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return md_path, json_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _default_ledger_path() -> str:
    from shared.storage import StorageConfig

    return StorageConfig.load_or_default().runtime_storage.sqlite.path


def _build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Retroactive Market Risk Score long-block gate over the"
        " RuntimeLedger paper trades."
    )
    ap.add_argument("--config", default=None, help="market_risk_validation.yaml path")
    ap.add_argument(
        "--ledger",
        default=None,
        help="RuntimeLedger sqlite path (default: config/storage.yaml)",
    )
    ap.add_argument(
        "--parquet-root",
        default=None,
        help="market-data parquet root override (default: config/storage.yaml)",
    )
    ap.add_argument("--start", default=None, help="entry-date window start (KST)")
    ap.add_argument("--end", default=None, help="entry-date window end (KST)")
    ap.add_argument("--out-dir", default=None, help="report dir override")
    ap.add_argument("--tag", default=None, help="report filename tag")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    settings = MarketRiskValidationConfig.load_or_default(args.config).counterfactual

    store = build_store(args.parquet_root)
    close_frame = load_snapshot_frame(store, "close")
    premarket_frame = load_snapshot_frame(store, "premarket")
    lookup = ScoreLookup(
        close_frame,
        premarket_frame,
        settings,
        store.config.snapshots.cutoff_time("premarket"),
    )
    if not lookup.has_scores:
        print(
            f"{INSUFFICIENT_DATA}: no usable score rows in the market-structure"
            f" dataset (columns {settings.score_columns}; run the backfill and"
            " the hindcast --write first)"
        )
        return 0

    ledger_path = args.ledger or _default_ledger_path()
    if not Path(ledger_path).exists():
        print(f"{INSUFFICIENT_DATA}: runtime ledger not found at {ledger_path}")
        return 0

    from shared.storage import SQLiteRuntimeLedger

    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    with SQLiteRuntimeLedger(ledger_path) as ledger:
        trades, unparseable = load_trades(ledger, settings, start, end)
    if not trades:
        print(
            f"{INSUFFICIENT_DATA}: no ledger trades matched"
            f" (window {start} .. {end}, asset_classes="
            f"{settings.asset_classes or 'all'})"
        )
        return 0

    rows = classify_trades(trades, lookup, settings)
    report = {
        "status": "ok",
        "generated_at_kst": datetime.now(KST).isoformat(),
        "ledger_path": str(ledger_path),
        "window_start": start.isoformat() if start else None,
        "window_end": end.isoformat() if end else None,
        "block_threshold": settings.block_threshold,
        "block_sides": settings.block_sides,
        "asset_classes": settings.asset_classes,
        "unparseable_entries": unparseable,
        "summary": summarize(rows),
        "trades": rows,
    }

    out_dir = Path(args.out_dir) if args.out_dir else Path(settings.report_dir)
    md_path, json_path = write_reports(report, out_dir, args.tag)
    print(render_markdown(report))
    print(f"wrote {md_path}")
    print(f"wrote {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
