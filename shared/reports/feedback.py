"""Unified performance feedback report engine (Phase 6A — read-only).

Pure ``compute`` + ``render`` functions over already-loaded runtime data. The
engine performs NO I/O against Redis/Telegram/strategy paths and never mutates
any execution/gate state — it only turns ledger rows, market-structure close
rows, hedge-advice history, and a backtest-expectation artifact into a report
dict (the 6B UI/JSON contract) plus a rendered Markdown page.

Design references:
- Roadmap docs/plans/2026-07-02-unified-investment-system-roadmap.md §Phase 6.
- Design doc docs/통합_투자_시스템_전략_설계서.md §8 (주기별 리뷰) / §8.2
  (트랙별 성공/중단 판정 기준).

Missing / insufficient data is always made explicit (``missing`` markers,
``verdict: insufficient_evidence`` / ``deferred``) — the engine never
synthesises a value it does not have. In particular slippage is computed ONLY
from real per-fill requested/filled prices; absent that, it is reported as
``null`` with a missing marker, never fabricated.
"""

from __future__ import annotations

import glob
import json
import math
import os
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from shared.portfolio.config import TRACK_CORE, TRACK_FUTURES, TRACK_STOCK

# Track render order — stable across every report kind (6B contract).
TRACK_IDS: tuple[str, ...] = (TRACK_STOCK, TRACK_FUTURES, TRACK_CORE)

# Breaker-stage severity ordering for "deepest stage reached" in a month.
_STAGE_ORDER: dict[str, int] = {
    "NORMAL": 0,
    "REDUCE": 1,
    "HALT_NEW": 2,
    "FULL_STOP": 3,
}

_DAYS_PER_YEAR = 365.25


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------


def _finite(value: float | None, ndigits: int) -> float | None:
    """Round to ``ndigits``; map None/non-finite to None (strict-JSON safe)."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return round(f, ndigits) if math.isfinite(f) else None


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _months_between(start: date, end: date) -> int:
    """Whole calendar months from ``start`` to ``end`` (day-of-month aware)."""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


# ---------------------------------------------------------------------------
# Per-track trade + slippage metrics
# ---------------------------------------------------------------------------


def compute_trade_metrics(trades: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Win rate, avg win/loss ratio, expectancy (EV/trade), realized PnL.

    ``avg_win_loss`` is the payoff ratio ``mean(win) / mean(|loss|)`` and is
    ``None`` when either side is empty (cannot divide — reported honestly, not
    as ``inf``). ``expectancy`` is the exact per-trade EV ``mean(pnl)`` over the
    trades that carry a realized PnL.
    """
    pnls = [p for t in trades if (p := _float_or_none(t.get("pnl"))) is not None]
    n = len(trades)
    if not pnls:
        return {
            "trades": n,
            "win_rate": None,
            "avg_win_loss": None,
            "expectancy": None,
            "realized_pnl": 0.0,
        }
    winners = [p for p in pnls if p > 0]
    losers = [-p for p in pnls if p < 0]
    avg_win = statistics.fmean(winners) if winners else None
    avg_loss = statistics.fmean(losers) if losers else None
    avg_win_loss = (
        avg_win / avg_loss
        if avg_win is not None and avg_loss not in (None, 0)
        else None
    )
    return {
        "trades": n,
        "win_rate": _finite(len(winners) / len(pnls), 4),
        "avg_win_loss": _finite(avg_win_loss, 4),
        "expectancy": _finite(statistics.fmean(pnls), 2),
        "realized_pnl": _finite(sum(pnls), 2),
    }


def compute_slippage(fills: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Adverse slippage from real per-fill requested/filled prices.

    Returns ``None`` when NOT A SINGLE fill carries both a positive
    ``requested_price`` and a ``filled_price`` — the caller then records an
    explicit missing marker. Never synthesises a slippage figure.

    ``avg_bps`` is the mean adverse move in basis points; ``total_cost`` is the
    signed adverse cost in price×quantity units (KRW-equivalent). ``coverage``
    is the fraction of fills that carried usable prices.
    """
    used_bps: list[float] = []
    total_cost = 0.0
    for fill in fills:
        payload = (
            fill.get("payload") if isinstance(fill.get("payload"), Mapping) else {}
        )
        requested = _float_or_none(payload.get("requested_price"))
        filled = _float_or_none(payload.get("filled_price"))
        if filled is None:
            filled = _float_or_none(fill.get("price"))
        if requested is None or requested <= 0 or filled is None:
            continue
        side = str(payload.get("side") or fill.get("side") or "").lower()
        qty = _float_or_none(payload.get("quantity")) or _float_or_none(
            fill.get("quantity")
        )
        qty = abs(qty) if qty is not None else 0.0
        # Adverse = paying more on a buy / receiving less on a sell.
        adverse = (
            (filled - requested) if side in ("buy", "long") else (requested - filled)
        )
        used_bps.append(adverse / requested * 10_000.0)
        total_cost += adverse * qty
    if not used_bps:
        return None
    return {
        "avg_bps": _finite(statistics.fmean(used_bps), 4),
        "total_cost": _finite(total_cost, 2),
        "fills": len(used_bps),
        "fills_total": len(fills),
        "coverage": _finite(len(used_bps) / len(fills), 4) if fills else 0.0,
    }


def _by_strategy(trades: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per-strategy trade-metric breakdown (``strategy`` field driven)."""
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for trade in trades:
        key = str(trade.get("strategy") or "unknown")
        groups.setdefault(key, []).append(trade)
    out: dict[str, Any] = {}
    for name, group in sorted(groups.items()):
        metrics = compute_trade_metrics(group)
        out[name] = {
            "trades": metrics["trades"],
            "win_rate": metrics["win_rate"],
            "expectancy": metrics["expectancy"],
            "realized_pnl": metrics["realized_pnl"],
        }
    return out


def _track_block(
    trades: Sequence[Mapping[str, Any]],
    fills: Sequence[Mapping[str, Any]],
    *,
    track_id: str,
    missing: list[str],
) -> dict[str, Any]:
    """One track's full metric block; records a missing slippage marker."""
    block = compute_trade_metrics(trades)
    slippage = compute_slippage(fills)
    block["slippage"] = slippage
    if slippage is None and (trades or fills):
        missing.append(f"track_{track_id.lower()}_slippage")
    block["by_strategy"] = _by_strategy(trades)
    return block


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass
class WeeklyInput:
    """Weekly report inputs (per-track trades/fills over the week window)."""

    period_label: str
    start: date
    end: date
    generated_at: str
    tracks_trades: Mapping[str, Sequence[Mapping[str, Any]]]
    tracks_fills: Mapping[str, Sequence[Mapping[str, Any]]]


@dataclass
class MonthlyInput:
    """Monthly report inputs."""

    period_label: str
    start: date
    end: date
    generated_at: str
    tracks_trades: Mapping[str, Sequence[Mapping[str, Any]]]
    tracks_fills: Mapping[str, Sequence[Mapping[str, Any]]]
    equity_rows: Sequence[Mapping[str, Any]]
    market_rows: Sequence[Mapping[str, Any]]
    hedge_rows: Sequence[Mapping[str, Any]]
    risk_band_column: str = "risk_band"
    risk_score_column: str = "risk_score"


@dataclass
class QuarterlyTrackBInput:
    """§8.2 Track B rolling material."""

    rolling_months: int
    backtest_ratio: float
    realized_pnl: float | None
    slippage_total_cost: float | None
    capital_base: float | None
    expectation: Mapping[str, Any] | None  # from load_backtest_expectation


@dataclass
class QuarterlyTrackCInput:
    """§8.2 Track C cumulative-EV material."""

    trades: Sequence[Mapping[str, Any]]
    inception: date | None
    period_end: date
    breakeven_months: int
    ev_checkpoint_months: int
    ev_final_months: int


@dataclass
class QuarterlyTrackAInput:
    """§8.2 Track A benchmark material."""

    equity_rows: Sequence[Mapping[str, Any]]  # portfolio_equity_daily (track_a_equity)
    benchmark_rows: Sequence[Mapping[str, Any]]
    benchmark_column: str
    min_history_years: int
    period_end: date


@dataclass
class QuarterlyInput:
    """Quarterly report inputs (§8.2 judgment material — produce only)."""

    period_label: str
    start: date
    end: date
    generated_at: str
    tracks_trades: Mapping[str, Sequence[Mapping[str, Any]]]
    tracks_fills: Mapping[str, Sequence[Mapping[str, Any]]]
    track_b: QuarterlyTrackBInput
    track_c: QuarterlyTrackCInput
    track_a: QuarterlyTrackAInput


# ---------------------------------------------------------------------------
# Backtest-expectation artifact (pure filesystem read)
# ---------------------------------------------------------------------------


def load_backtest_expectation(reports_dir: str) -> dict[str, Any] | None:
    """Newest ``experiment run`` artifact → aggregate expected return.

    The nightly stock-experiment job writes ``{id}_{YYYYMMDD}_{HHMMSS}.json``
    (shared/backtest/experiment_runner.py) with a ``summaries[]`` list, each
    carrying ``total_return_pct``. The backtest expectation is the mean of
    those returns across the strategies that ran. Returns ``None`` when the
    directory is absent/empty or no summary carries a return — the caller then
    marks the Track B verdict ``insufficient_evidence``.
    """
    if not reports_dir or not os.path.isdir(reports_dir):
        return None
    files = sorted(glob.glob(os.path.join(reports_dir, "*.json")))
    if not files:
        return None
    newest = files[-1]
    try:
        with open(newest, encoding="utf-8") as handle:
            report = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    summaries = report.get("summaries") or []
    returns = [
        r
        for s in summaries
        if (r := _float_or_none(s.get("total_return_pct"))) is not None
    ]
    if not returns:
        return None
    return {
        "source": os.path.basename(newest),
        "expectation_pct": _finite(statistics.fmean(returns), 4),
        "n_strategies": len(returns),
    }


# ---------------------------------------------------------------------------
# Weekly
# ---------------------------------------------------------------------------


def compute_weekly(inp: WeeklyInput) -> dict[str, Any]:
    """Weekly per-track (B/C, A if any) trade/slippage report (설계서 §8.1)."""
    missing: list[str] = []
    tracks: dict[str, Any] = {}
    for track_id in TRACK_IDS:
        tracks[track_id] = _track_block(
            inp.tracks_trades.get(track_id, []),
            inp.tracks_fills.get(track_id, []),
            track_id=track_id,
            missing=missing,
        )
    return {
        "kind": "weekly",
        "period_label": inp.period_label,
        "generated_at": inp.generated_at,
        "window": {"start": inp.start.isoformat(), "end": inp.end.isoformat()},
        "tracks": tracks,
        "missing": missing,
    }


# ---------------------------------------------------------------------------
# Monthly
# ---------------------------------------------------------------------------


def _equity_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Month equity curve summary from portfolio_equity_daily rows."""
    ordered = sorted(rows, key=lambda r: str(r.get("trade_date", "")))
    if not ordered:
        return None
    totals = [
        v for r in ordered if (v := _float_or_none(r.get("total_equity"))) is not None
    ]
    if not totals:
        return None
    first = ordered[0]
    month_start = _float_or_none(first.get("month_start_equity")) or totals[0]
    month_end = totals[-1]
    peaks = [
        v
        for r in ordered
        if (v := _float_or_none(r.get("month_peak_equity"))) is not None
    ]
    month_peak = max(peaks) if peaks else max(totals)
    mdds = [
        v
        for r in ordered
        if (v := _float_or_none(r.get("monthly_mdd_pct"))) is not None
    ]
    deepest_mdd = min(mdds) if mdds else None
    stage_reached = "NORMAL"
    for row in ordered:
        stage = str(row.get("stage") or "NORMAL")
        if _STAGE_ORDER.get(stage, 0) > _STAGE_ORDER.get(stage_reached, 0):
            stage_reached = stage
    monthly_return = (
        (month_end - month_start) / month_start * 100.0 if month_start else None
    )
    return {
        "month_start": _finite(month_start, 2),
        "month_end": _finite(month_end, 2),
        "month_peak": _finite(month_peak, 2),
        "month_low": _finite(min(totals), 2),
        "monthly_return_pct": _finite(monthly_return, 4),
        "monthly_mdd_pct": _finite(deepest_mdd, 4),
        "stage_reached": stage_reached,
    }


def _track_contribution(
    tracks_trades: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Track PnL / total PnL contribution (설계서 §8.1 monthly)."""
    pnls: dict[str, float] = {}
    for track_id in TRACK_IDS:
        pnls[track_id] = sum(
            p
            for t in tracks_trades.get(track_id, [])
            if (p := _float_or_none(t.get("pnl"))) is not None
        )
    total = sum(pnls.values())
    out: dict[str, Any] = {"total_pnl": _finite(total, 2)}
    for track_id in TRACK_IDS:
        out[track_id] = {
            "realized_pnl": _finite(pnls[track_id], 2),
            "contribution_pct": (
                _finite(pnls[track_id] / total * 100.0, 4) if total else None
            ),
        }
    return out


def _risk_band_residency(
    rows: Sequence[Mapping[str, Any]], band_column: str, score_column: str
) -> dict[str, Any] | None:
    """Days-in-band residency + mean risk score from market_structure close."""
    if not rows:
        return None
    days_in_band: dict[str, int] = {}
    scores: list[float] = []
    for row in rows:
        band = row.get(band_column)
        if band is not None and str(band) != "":
            days_in_band[str(band)] = days_in_band.get(str(band), 0) + 1
        if (score := _float_or_none(row.get(score_column))) is not None:
            scores.append(score)
    if not days_in_band and not scores:
        return None
    return {
        "days_in_band": dict(sorted(days_in_band.items())),
        "avg_risk_score": _finite(statistics.fmean(scores), 4) if scores else None,
        "trading_days": len(rows),
    }


def _hedge_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Hedge-advisory occurrence summary (advisory-only history)."""
    if not rows:
        return None
    active = [r for r in rows if int(r.get("advisory_active") or 0) == 1]
    recommended = [
        v
        for r in rows
        if (v := _float_or_none(r.get("recommended_short_contracts"))) is not None
    ]
    bands = sorted(
        {str(r.get("band")) for r in rows if r.get("band") not in (None, "")}
    )
    return {
        "rows": len(rows),
        "advisory_active_events": len(active),
        "max_recommended_short_contracts": (
            int(max(recommended)) if recommended else 0
        ),
        "bands_seen": bands,
    }


def compute_monthly(inp: MonthlyInput) -> dict[str, Any]:
    """Monthly 1-page report (설계서 §8.1: 자산 곡선·기여도·MDD·리스크·헤지)."""
    missing: list[str] = []
    tracks: dict[str, Any] = {}
    for track_id in TRACK_IDS:
        tracks[track_id] = _track_block(
            inp.tracks_trades.get(track_id, []),
            inp.tracks_fills.get(track_id, []),
            track_id=track_id,
            missing=missing,
        )

    equity = _equity_summary(inp.equity_rows)
    if equity is None:
        missing.append("equity_curve")
    risk_bands = _risk_band_residency(
        inp.market_rows, inp.risk_band_column, inp.risk_score_column
    )
    if risk_bands is None:
        missing.append("market_risk_bands")
    hedge = _hedge_summary(inp.hedge_rows)
    if hedge is None:
        missing.append("hedge_advice")

    return {
        "kind": "monthly",
        "period_label": inp.period_label,
        "generated_at": inp.generated_at,
        "window": {"start": inp.start.isoformat(), "end": inp.end.isoformat()},
        "tracks": tracks,
        "equity": equity,
        "contribution": _track_contribution(inp.tracks_trades),
        "risk_bands": risk_bands,
        "hedge": hedge,
        "missing": missing,
    }


# ---------------------------------------------------------------------------
# Quarterly (§8.2 judgment material — verdicts are produce-only)
# ---------------------------------------------------------------------------


def compute_quarter_track_b(inp: QuarterlyTrackBInput) -> dict[str, Any]:
    """§8.2 Track B: 6mo realized vs (expectation − slippage) × ratio."""
    realized_return_pct = (
        _finite(inp.realized_pnl / inp.capital_base * 100.0, 4)
        if inp.realized_pnl is not None and inp.capital_base
        else None
    )
    slippage_pct = (
        _finite(inp.slippage_total_cost / inp.capital_base * 100.0, 4)
        if inp.slippage_total_cost is not None and inp.capital_base
        else None
    )
    expectation_pct = (
        _float_or_none(inp.expectation.get("expectation_pct"))
        if inp.expectation
        else None
    )
    result: dict[str, Any] = {
        "rolling_months": inp.rolling_months,
        "backtest_ratio": inp.backtest_ratio,
        "realized_return_pct": realized_return_pct,
        "backtest_expectation_pct": expectation_pct,
        "backtest_source": inp.expectation.get("source") if inp.expectation else None,
        "slippage_pct": slippage_pct,
        "threshold_pct": None,
        "verdict": "insufficient_evidence",
    }
    if expectation_pct is None or realized_return_pct is None:
        return result
    drag = slippage_pct if slippage_pct is not None else 0.0
    threshold = (expectation_pct - drag) * inp.backtest_ratio
    result["threshold_pct"] = _finite(threshold, 4)
    result["verdict"] = "meets" if realized_return_pct >= threshold else "below"
    return result


def compute_quarter_track_c(inp: QuarterlyTrackCInput) -> dict[str, Any]:
    """§8.2 Track C: cumulative EV positivity + 3/6/12-month checkpoints."""
    metrics = compute_trade_metrics(inp.trades)
    cumulative = metrics["realized_pnl"]
    expectancy = metrics["expectancy"]
    months_elapsed = (
        _months_between(inp.inception, inp.period_end) if inp.inception else None
    )
    checkpoints = {
        "breakeven": months_elapsed is not None
        and months_elapsed >= inp.breakeven_months,
        "ev_checkpoint": months_elapsed is not None
        and months_elapsed >= inp.ev_checkpoint_months,
        "ev_final": months_elapsed is not None
        and months_elapsed >= inp.ev_final_months,
    }
    ev_positive = cumulative is not None and cumulative > 0

    if metrics["trades"] == 0 or months_elapsed is None:
        verdict = "insufficient_evidence"
    elif checkpoints["ev_final"] and not ev_positive:
        verdict = "review_termination"
    elif checkpoints["ev_checkpoint"] and not ev_positive:
        verdict = "reduce_capital_50"
    elif checkpoints["breakeven"] and cumulative is not None and cumulative < 0:
        verdict = "below_breakeven"
    else:
        verdict = "on_track"

    return {
        "verdict": verdict,
        "cumulative_realized_pnl": cumulative,
        "expectancy": expectancy,
        "ev_positive": ev_positive,
        "trades": metrics["trades"],
        "inception": inp.inception.isoformat() if inp.inception else None,
        "months_elapsed": months_elapsed,
        "checkpoints": checkpoints,
    }


def _series_return_pct(
    rows: Sequence[Mapping[str, Any]], value_key: str, date_key: str = "trade_date"
) -> float | None:
    """First→last percent change of a value column ordered by date."""
    points = sorted(
        (
            (str(r.get(date_key, "")), v)
            for r in rows
            if (v := _float_or_none(r.get(value_key))) is not None
        ),
        key=lambda p: p[0],
    )
    if len(points) < 2 or points[0][1] == 0:
        return None
    return _finite((points[-1][1] - points[0][1]) / points[0][1] * 100.0, 4)


def compute_quarter_track_a(inp: QuarterlyTrackAInput) -> dict[str, Any]:
    """§8.2 Track A: benchmark-relative return; <3yr history → deferred."""
    equity_dates = sorted(
        str(r.get("trade_date", ""))
        for r in inp.equity_rows
        if _float_or_none(r.get("track_a_equity")) is not None
    )
    result: dict[str, Any] = {
        "benchmark_column": inp.benchmark_column,
        "min_history_years": inp.min_history_years,
        "history_years": None,
        "track_return_pct": None,
        "benchmark_return_pct": None,
        "excess_return_pct": None,
        "verdict": "insufficient_evidence",
    }
    if not equity_dates:
        return result

    try:
        earliest = date.fromisoformat(equity_dates[0])
    except ValueError:
        return result
    history_years = (inp.period_end - earliest).days / _DAYS_PER_YEAR
    result["history_years"] = _finite(history_years, 2)

    if history_years < inp.min_history_years:
        result["verdict"] = "deferred"
        return result

    track_return = _series_return_pct(inp.equity_rows, "track_a_equity")
    benchmark_return = _series_return_pct(inp.benchmark_rows, inp.benchmark_column)
    result["track_return_pct"] = track_return
    result["benchmark_return_pct"] = benchmark_return
    if track_return is not None and benchmark_return is not None:
        result["excess_return_pct"] = _finite(track_return - benchmark_return, 4)
        result["verdict"] = (
            "outperform" if track_return >= benchmark_return else "underperform"
        )
    return result


def compute_quarterly(inp: QuarterlyInput) -> dict[str, Any]:
    """Quarterly §8.2 material (produce-only; decisions stay with operator)."""
    missing: list[str] = []
    tracks: dict[str, Any] = {}
    for track_id in TRACK_IDS:
        tracks[track_id] = _track_block(
            inp.tracks_trades.get(track_id, []),
            inp.tracks_fills.get(track_id, []),
            track_id=track_id,
            missing=missing,
        )

    track_b = compute_quarter_track_b(inp.track_b)
    if track_b["verdict"] == "insufficient_evidence":
        if inp.track_b.expectation is None:
            missing.append("backtest_expectation")
        if inp.track_b.realized_pnl is None or not inp.track_b.capital_base:
            missing.append("track_b_realized_return")
    track_c = compute_quarter_track_c(inp.track_c)
    if track_c["verdict"] == "insufficient_evidence":
        missing.append("track_c_history")
    track_a = compute_quarter_track_a(inp.track_a)
    if track_a["verdict"] == "insufficient_evidence":
        missing.append("track_a_history")

    return {
        "kind": "quarterly",
        "period_label": inp.period_label,
        "generated_at": inp.generated_at,
        "window": {"start": inp.start.isoformat(), "end": inp.end.isoformat()},
        "tracks": tracks,
        "quarterly": {"track_b": track_b, "track_c": track_c, "track_a": track_a},
        "missing": missing,
    }


# ---------------------------------------------------------------------------
# Headline (Redis pointer + Telegram body source)
# ---------------------------------------------------------------------------


def build_headline(report: Mapping[str, Any]) -> dict[str, Any]:
    """Compact headline dict — stored as JSON in Redis, rendered to Telegram."""
    kind = report.get("kind", "")
    tracks = report.get("tracks", {})
    head: dict[str, Any] = {
        "kind": kind,
        "period_label": report.get("period_label", ""),
        "track_b_realized_pnl": tracks.get(TRACK_STOCK, {}).get("realized_pnl"),
        "track_c_realized_pnl": tracks.get(TRACK_FUTURES, {}).get("realized_pnl"),
        "missing": list(report.get("missing", [])),
    }
    if kind == "monthly" and report.get("equity"):
        head["monthly_return_pct"] = report["equity"].get("monthly_return_pct")
        head["stage_reached"] = report["equity"].get("stage_reached")
    if kind == "quarterly":
        quarterly = report.get("quarterly", {})
        head["verdicts"] = {
            t: quarterly.get(f"track_{t.lower()}", {}).get("verdict") for t in TRACK_IDS
        }
    return head


def headline_text(report: Mapping[str, Any]) -> str:
    """One Telegram message body summarising the report (HTML)."""
    kind = str(report.get("kind", "")).upper()
    label = report.get("period_label", "")
    tracks = report.get("tracks", {})
    lines = [f"<b>[{kind}] 성과 피드백 리포트 · {label}</b>"]

    def _track_line(track_id: str, name: str) -> str:
        block = tracks.get(track_id, {})
        pnl = block.get("realized_pnl")
        win = block.get("win_rate")
        n = block.get("trades", 0)
        pnl_txt = f"₩{pnl:,.0f}" if isinstance(pnl, (int, float)) else "-"
        win_txt = f"{win:.1%}" if isinstance(win, (int, float)) else "-"
        return f"{name}: {n}건 · 승률 {win_txt} · 실현 {pnl_txt}"

    lines.append(_track_line(TRACK_STOCK, "트랙 B"))
    lines.append(_track_line(TRACK_FUTURES, "트랙 C"))

    if kind == "MONTHLY" and report.get("equity"):
        ret = report["equity"].get("monthly_return_pct")
        stage = report["equity"].get("stage_reached")
        if isinstance(ret, (int, float)):
            lines.append(f"월간 수익률 {ret:.2f}% · 최심 stage {stage}")
    if kind == "QUARTERLY":
        quarterly = report.get("quarterly", {})
        verdicts = " · ".join(
            f"{t} {quarterly.get(f'track_{t.lower()}', {}).get('verdict', '-')}"
            for t in TRACK_IDS
        )
        lines.append(f"§8.2 판정자료: {verdicts}")

    missing = report.get("missing", [])
    if missing:
        lines.append(f"결측: {', '.join(missing)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _fmt_num(value: Any, suffix: str = "", pct: bool = False) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        if pct:
            return f"{value:.2f}%"
        return f"{value:,.2f}{suffix}"
    return str(value)


def _render_track_table(tracks: Mapping[str, Any]) -> list[str]:
    lines = [
        "| Track | Trades | Win rate | Avg W/L | Expectancy | Realized PnL | Slippage |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    labels = {
        TRACK_STOCK: "B (stock)",
        TRACK_FUTURES: "C (futures)",
        TRACK_CORE: "A (core)",
    }
    for track_id in TRACK_IDS:
        block = tracks.get(track_id, {})
        slip = block.get("slippage")
        if isinstance(slip, Mapping):
            slip_txt = (
                f"{slip['avg_bps']:.2f} bps ({slip['fills']}/{slip['fills_total']})"
            )
        elif block.get("trades", 0):
            # Traded, but no fill carried usable prices — honestly missing.
            slip_txt = "missing"
        else:
            slip_txt = "—"
        win = block.get("win_rate")
        lines.append(
            f"| {labels[track_id]} | {block.get('trades', 0)} | "
            f"{_fmt_num(win * 100 if isinstance(win, (int, float)) else None, pct=False)}"
            f"{'%' if isinstance(win, (int, float)) else ''} | "
            f"{_fmt_num(block.get('avg_win_loss'))} | "
            f"{_fmt_num(block.get('expectancy'))} | "
            f"{_fmt_num(block.get('realized_pnl'))} | {slip_txt} |"
        )
    return lines


def _render_by_strategy(tracks: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    labels = {TRACK_STOCK: "B", TRACK_FUTURES: "C", TRACK_CORE: "A"}
    for track_id in TRACK_IDS:
        by_strategy = tracks.get(track_id, {}).get("by_strategy") or {}
        if not by_strategy:
            continue
        lines.append(f"\n#### Track {labels[track_id]} — 전략별 분해")
        lines.append("| Strategy | Trades | Win rate | Expectancy | Realized PnL |")
        lines.append("|---|---:|---:|---:|---:|")
        for name, metrics in by_strategy.items():
            win = metrics.get("win_rate")
            win_txt = f"{win * 100:.1f}%" if isinstance(win, (int, float)) else "—"
            lines.append(
                f"| {name} | {metrics.get('trades', 0)} | {win_txt} | "
                f"{_fmt_num(metrics.get('expectancy'))} | "
                f"{_fmt_num(metrics.get('realized_pnl'))} |"
            )
    return lines


def _render_header(report: Mapping[str, Any]) -> list[str]:
    window = report.get("window", {})
    return [
        f"# {str(report.get('kind', '')).title()} 성과 피드백 리포트 — "
        f"{report.get('period_label', '')}",
        "",
        f"- 생성: {report.get('generated_at', '')} (KST)",
        f"- 구간: {window.get('start', '')} → {window.get('end', '')}",
        "- 성격: 읽기 전용 분석 (전략/집행/게이트에 영향 없음)",
        "",
    ]


def _render_missing(report: Mapping[str, Any]) -> list[str]:
    missing = report.get("missing", [])
    if not missing:
        return ["", "_결측 항목 없음._"]
    return ["", "### 결측 / 근거 부족", "", *[f"- `{m}`" for m in missing]]


def render_weekly_md(report: Mapping[str, Any]) -> str:
    lines = _render_header(report)
    lines.append("## 트랙별 주간 성과 (§8.1)")
    lines.append("")
    lines.extend(_render_track_table(report.get("tracks", {})))
    lines.extend(_render_by_strategy(report.get("tracks", {})))
    lines.extend(_render_missing(report))
    return "\n".join(lines) + "\n"


def render_monthly_md(report: Mapping[str, Any]) -> str:
    lines = _render_header(report)
    equity = report.get("equity")
    lines.append("## 통합 자산 곡선 (§8.1)")
    lines.append("")
    if equity:
        lines.append(
            f"- 월초 {_fmt_num(equity.get('month_start'))} · "
            f"월말 {_fmt_num(equity.get('month_end'))} · "
            f"최고 {_fmt_num(equity.get('month_peak'))} · "
            f"최저 {_fmt_num(equity.get('month_low'))}"
        )
        lines.append(
            f"- 월간 수익률 {_fmt_num(equity.get('monthly_return_pct'), pct=True)} · "
            f"월간 MDD {_fmt_num(equity.get('monthly_mdd_pct'), pct=True)} · "
            f"도달 stage `{equity.get('stage_reached')}`"
        )
    else:
        lines.append("- _자산 곡선 데이터 없음 (portfolio_equity_daily 비어 있음)._")

    lines.append("")
    lines.append("## 트랙별 기여도")
    lines.append("")
    contribution = report.get("contribution", {})
    lines.append(f"- 총 실현 PnL: {_fmt_num(contribution.get('total_pnl'))}")
    for track_id in TRACK_IDS:
        block = contribution.get(track_id, {})
        lines.append(
            f"- 트랙 {track_id}: {_fmt_num(block.get('realized_pnl'))} "
            f"(기여 {_fmt_num(block.get('contribution_pct'), pct=True)})"
        )

    lines.append("")
    lines.append("## 트랙별 성과 상세")
    lines.append("")
    lines.extend(_render_track_table(report.get("tracks", {})))

    lines.append("")
    lines.append("## Market Risk Score 밴드 체류")
    lines.append("")
    risk = report.get("risk_bands")
    if risk:
        for band, days in risk.get("days_in_band", {}).items():
            lines.append(f"- `{band}`: {days}일")
        lines.append(f"- 평균 risk_score: {_fmt_num(risk.get('avg_risk_score'))}")
    else:
        lines.append("- _market_structure 종가 데이터 없음._")

    lines.append("")
    lines.append("## 헤지 권고 발생")
    lines.append("")
    hedge = report.get("hedge")
    if hedge:
        lines.append(
            f"- 이력 {hedge.get('rows')}건 · advisory_active {hedge.get('advisory_active_events')}건 · "
            f"최대 권고 short {hedge.get('max_recommended_short_contracts')}계약"
        )
    else:
        lines.append("- _헤지 권고 이력 없음._")

    lines.extend(_render_missing(report))
    return "\n".join(lines) + "\n"


def render_quarterly_md(report: Mapping[str, Any]) -> str:
    lines = _render_header(report)
    lines.append("## §8.2 트랙별 판정 자료 (산출만 — 결정은 운영자)")
    lines.append("")
    quarterly = report.get("quarterly", {})

    tb = quarterly.get("track_b", {})
    lines.append("### 트랙 B — 6개월 롤링 실전 vs 백테스트 기대")
    lines.append(
        f"- 판정: **{tb.get('verdict')}** "
        f"(롤링 {tb.get('rolling_months')}개월, ratio {tb.get('backtest_ratio')})"
    )
    lines.append(f"- 실전 수익률: {_fmt_num(tb.get('realized_return_pct'), pct=True)}")
    lines.append(
        f"- 백테스트 기대: {_fmt_num(tb.get('backtest_expectation_pct'), pct=True)} "
        f"(source: {tb.get('backtest_source') or '—'})"
    )
    lines.append(f"- 슬리피지 차감: {_fmt_num(tb.get('slippage_pct'), pct=True)}")
    lines.append(f"- 임계치: {_fmt_num(tb.get('threshold_pct'), pct=True)}")

    tc = quarterly.get("track_c", {})
    lines.append("")
    lines.append("### 트랙 C — 누적 EV / 체크포인트")
    lines.append(f"- 판정: **{tc.get('verdict')}**")
    lines.append(
        f"- 누적 실현 PnL: {_fmt_num(tc.get('cumulative_realized_pnl'))} · "
        f"EV/trade {_fmt_num(tc.get('expectancy'))} · EV 양수 {tc.get('ev_positive')}"
    )
    lines.append(
        f"- 개시일 {tc.get('inception') or '—'} · 경과 {tc.get('months_elapsed')}개월"
    )
    checkpoints = tc.get("checkpoints", {})
    lines.append(
        f"- 체크포인트: 본전 {checkpoints.get('breakeven')} · "
        f"6개월 {checkpoints.get('ev_checkpoint')} · 12개월 {checkpoints.get('ev_final')}"
    )

    ta = quarterly.get("track_a", {})
    lines.append("")
    lines.append("### 트랙 A — 벤치마크 대비")
    lines.append(f"- 판정: **{ta.get('verdict')}**")
    lines.append(
        f"- 이력 {_fmt_num(ta.get('history_years'))}년 "
        f"(최소 {ta.get('min_history_years')}년)"
    )
    lines.append(
        f"- 트랙 수익률 {_fmt_num(ta.get('track_return_pct'), pct=True)} vs "
        f"벤치마크({ta.get('benchmark_column')}) "
        f"{_fmt_num(ta.get('benchmark_return_pct'), pct=True)} · "
        f"초과 {_fmt_num(ta.get('excess_return_pct'), pct=True)}"
    )

    lines.append("")
    lines.append("## 트랙별 분기 성과")
    lines.append("")
    lines.extend(_render_track_table(report.get("tracks", {})))
    lines.extend(_render_missing(report))
    return "\n".join(lines) + "\n"


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render a report dict to Markdown (dispatch on ``kind``)."""
    kind = report.get("kind")
    if kind == "weekly":
        return render_weekly_md(report)
    if kind == "monthly":
        return render_monthly_md(report)
    if kind == "quarterly":
        return render_quarterly_md(report)
    raise ValueError(f"unknown report kind: {kind!r}")


def to_json(report: Mapping[str, Any]) -> str:
    """Serialize a report to strict JSON (indent=2, allow_nan=False)."""
    return json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
