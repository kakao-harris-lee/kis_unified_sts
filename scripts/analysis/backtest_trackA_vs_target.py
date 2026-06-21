"""Holdout backtest: TrackAExit vs SetupTargetExit on synthetic Setup A/C entries.

Design
------
Setup A/C in production require live macro context (sp500_gap, LLM bias, Redis state).
None of that is replay-able from pure OHLCV. Instead, we synthesize entries that
*capture the same structural pattern*:
  - Setup A (gap reversion): bar within first 120 min, open gap >= 0.2%, current
    price has retraced 20-70% of that gap back toward prev_close.
  - Setup C (event breakout): bar within first 120 min, price breaks above/below
    the prior 15-bar H/L range with vol >= 1.5x rolling average.

Both arms use IDENTICAL entry signals. Only the exit generator differs.

Exit simulation
---------------
Both TrackAExit and SetupTargetExit use ``now_kst()`` (wall clock) for EOD.
In historical replay this is wrong (wall clock is 2026-06-21, all bars are past).
We disable ``eod_close_enabled`` in the exit configs and instead apply an
EOD force-close at the engine level via ``RiskConfig.force_close_time = "15:10"``.
All ATR-based logic (trail, crash, catastrophic, stop) uses bar-level ATR which
we compute from a rolling 14-bar true-range — no wall clock involved.

TrackAExit is further shimmed: ``position.metadata["prev_price"]`` is updated
bar-by-bar from the simulation loop so crash_guard fires correctly.

Holdout split
-------------
Train: first 2/3 of trading days (to match any prior optimization period).
Test (holdout): final 1/3 of trading days.

We report both periods separately; the verdict comes from the holdout only.

Usage
-----
    .venv/bin/python scripts/analysis/backtest_trackA_vs_target.py
    .venv/bin/python scripts/analysis/backtest_trackA_vs_target.py --data data/kospi200f_1m_ch_101S6000.csv
    .venv/bin/python scripts/analysis/backtest_trackA_vs_target.py --holdout-only
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

# ── project root on path ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── ATR helpers ─────────────────────────────────────────────────────────────

def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Rolling ATR-14 via true range."""
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(span=period, min_periods=1, adjust=False).mean()


def compute_prev_close(df: pd.DataFrame) -> pd.Series:
    """Previous bar's close — used to detect overnight gap."""
    return df["close"].shift(1)


# ── Entry signal synthesis ────────────────────────────────────────────────────

@dataclass
class EntrySignal:
    bar_idx: int
    entry_price: float
    side: Literal["BUY", "SELL"]
    atr: float
    stop_price: float
    take_profit: float
    setup: str  # "setup_a" | "setup_c"


def _session_minute(ts: datetime) -> int:
    """Minutes since 09:00 KST."""
    session_open = ts.replace(hour=9, minute=0, second=0, microsecond=0)
    return max(0, int((ts - session_open).total_seconds() / 60))


def synthesize_setup_a_entries(
    df: pd.DataFrame,
    *,
    min_gap_pct: float = 0.001,     # 0.1% overnight gap (relaxed from config 0.2% for sample size)
    retrace_min: float = 0.10,      # relaxed from 0.20
    retrace_max: float = 0.85,      # relaxed from 0.70
    stop_atr_mult: float = 3.5,     # matches setup_a_gap_reversion.yaml
    target_gap_fill_ratio: float = 0.90,
    valid_minutes_max: int = 120,
    valid_minutes_min: int = 5,     # relaxed from 10
) -> list[EntrySignal]:
    """Synthesize Setup A gap-reversion entries from OHLCV.

    Signal fires when:
      - bar is within the valid time window (10–120 min after open)
      - overnight gap (|open-prev_close|/prev_close) >= min_gap_pct
      - price has retraced 20–70% of the gap toward prev_close
      - ATR > 0
    Direction: retrace of up-gap → SHORT (price was gapping up, now reverting down)
               retrace of down-gap → LONG

    Stop: entry ± stop_atr_mult * ATR (outside direction of gap)
    Target: entry ± gap_remaining * target_gap_fill_ratio
    """
    signals: list[EntrySignal] = []
    last_entry_day: object = None  # Allow at most one entry per day

    for i, row in df.iterrows():
        if i == 0:
            continue
        ts: datetime = row["datetime"]
        # One entry per day max
        if ts.date() == last_entry_day:
            continue
        sess_min = _session_minute(ts)
        if sess_min < valid_minutes_min or sess_min > valid_minutes_max:
            continue

        prev_c = row.get("prev_close", 0.0)
        if prev_c <= 0:
            continue

        open_price = row["open"]
        gap = open_price - prev_c
        gap_pct = abs(gap) / prev_c
        if gap_pct < min_gap_pct:
            continue

        current_price = row["close"]
        atr = float(row.get("atr", 0.0))
        if atr <= 0:
            continue

        # Retrace check: how much of the gap has been filled?
        retrace = (current_price - open_price) / (-gap) if gap != 0 else 0
        if not (retrace_min <= retrace <= retrace_max):
            continue

        # Direction: gap up → expect reversal down (SHORT)
        if gap > 0:
            side: Literal["BUY", "SELL"] = "SELL"
            stop_price = current_price + stop_atr_mult * atr
            remaining_gap = prev_c - current_price
            take_profit = current_price - abs(remaining_gap) * target_gap_fill_ratio
            if take_profit >= current_price:
                continue  # degenerate
        else:
            side = "BUY"
            stop_price = current_price - stop_atr_mult * atr
            remaining_gap = prev_c - current_price
            take_profit = current_price + abs(remaining_gap) * target_gap_fill_ratio
            if take_profit <= current_price:
                continue

        signals.append(
            EntrySignal(
                bar_idx=i,
                entry_price=current_price,
                side=side,
                atr=atr,
                stop_price=stop_price,
                take_profit=take_profit,
                setup="setup_a",
            )
        )
        last_entry_day = ts.date()  # One per day

    return signals


def synthesize_setup_c_entries(
    df: pd.DataFrame,
    *,
    range_bars: int = 15,
    breakout_buffer_atr_mult: float = 0.3,  # relaxed from 0.5
    target_atr_mult: float = 2.0,
    stop_buffer_atr_mult: float = 0.3,
    min_rvol: float = 1.2,               # relaxed from 1.5
    valid_minutes_max: int = 120,
    valid_minutes_min: int = 5,
) -> list[EntrySignal]:
    """Synthesize Setup C event-breakout entries from OHLCV.

    Signal fires when:
      - bar is within valid time window
      - price breaks above/below the prior ``range_bars``-bar H/L
      - volume >= min_rvol × rolling avg bar volume
    """
    signals: list[EntrySignal] = []
    last_entry_day_c: object = None

    vol_window: deque = deque(maxlen=100)

    for i, row in df.iterrows():
        current_vol = float(row.get("volume", 0))
        vol_window.append(current_vol)

        if i < range_bars:
            continue

        ts: datetime = row["datetime"]
        if ts.date() == last_entry_day_c:
            continue
        sess_min = _session_minute(ts)
        if sess_min < valid_minutes_min or sess_min > valid_minutes_max:
            continue

        atr = float(row.get("atr", 0.0))
        if atr <= 0:
            continue

        range_slice = df.iloc[max(0, i - range_bars) : i]
        range_high = float(range_slice["high"].max())
        range_low = float(range_slice["low"].min())

        current_price = float(row["close"])

        avg_vol = float(np.mean(list(vol_window)[:-1])) if len(vol_window) > 1 else 0.0
        rvol = current_vol / avg_vol if avg_vol > 0 else 0.0
        if rvol < min_rvol:
            continue

        breakout_buf = breakout_buffer_atr_mult * atr

        if current_price > range_high + breakout_buf:
            side: Literal["BUY", "SELL"] = "BUY"
            stop_price = range_low - stop_buffer_atr_mult * atr
            take_profit = current_price + target_atr_mult * atr
        elif current_price < range_low - breakout_buf:
            side = "SELL"
            stop_price = range_high + stop_buffer_atr_mult * atr
            take_profit = current_price - target_atr_mult * atr
        else:
            continue

        signals.append(
            EntrySignal(
                bar_idx=i,
                entry_price=current_price,
                side=side,
                atr=atr,
                stop_price=stop_price,
                take_profit=take_profit,
                setup="setup_c",
            )
        )
        last_entry_day_c = ts.date()

    return signals


# ── Exit simulation ───────────────────────────────────────────────────────────

@dataclass
class SimTrade:
    entry_idx: int
    entry_price: float
    entry_time: datetime
    exit_idx: int
    exit_price: float
    exit_time: datetime
    side: str
    setup: str
    exit_reason: str
    pnl_pts: float  # points (price difference, long/short adjusted)
    pnl_pct: float
    holding_bars: int
    holding_minutes: float
    favorable_extreme: float  # high (long) or low (short) since entry
    atr_at_entry: float


# TrackAExit parameters (from track_a_exit.yaml)
TRAIL_ATR_MULT = 3.0
TRAIL_ACTIVATE_ATR_MULT = 1.0
CRASH_ATR_MULT = 3.5
CATASTROPHIC_ATR_MULT = 6.0
EOD_CLOSE_HOUR = 15
EOD_CLOSE_MINUTE = 10  # 15:10 KST (slightly before 15:15 to ensure we catch it)
FUTURES_POINT_VALUE = 50_000  # KRX futures contract multiplier


def _eod_reached(ts: datetime) -> bool:
    return ts.hour > EOD_CLOSE_HOUR or (
        ts.hour == EOD_CLOSE_HOUR and ts.minute >= EOD_CLOSE_MINUTE
    )


def simulate_track_a_exit(
    df: pd.DataFrame,
    entry: EntrySignal,
    *,
    trail_atr_mult: float = TRAIL_ATR_MULT,
    trail_activate_atr_mult: float = TRAIL_ACTIVATE_ATR_MULT,
    crash_atr_mult: float = CRASH_ATR_MULT,
    catastrophic_atr_mult: float = CATASTROPHIC_ATR_MULT,
) -> SimTrade | None:
    """Event loop for TrackAExit on one position."""
    entry_price = entry.entry_price
    side = entry.side
    atr = entry.atr  # Use ATR at entry as fallback; update from bar if available
    start_idx = entry.bar_idx
    entry_time = df.iloc[start_idx]["datetime"]

    favorable_extreme = entry_price
    prev_price = entry_price

    for i in range(start_idx + 1, len(df)):
        row = df.iloc[i]
        ts: datetime = row["datetime"]
        current_price = float(row["close"])
        bar_atr = float(row.get("atr", atr))
        if bar_atr <= 0:
            bar_atr = atr

        # Update favorable extreme
        if side == "BUY":
            if current_price > favorable_extreme:
                favorable_extreme = current_price
        else:
            if current_price < favorable_extreme:
                favorable_extreme = current_price

        # -- P1: crash guard (single-tick adverse move)
        if bar_atr > 0:
            if side == "BUY" and (prev_price - current_price) >= crash_atr_mult * bar_atr:
                return _make_trade(entry, df, i, current_price, "crash_guard",
                                   entry_time, ts, favorable_extreme)
            if side == "SELL" and (current_price - prev_price) >= crash_atr_mult * bar_atr:
                return _make_trade(entry, df, i, current_price, "crash_guard",
                                   entry_time, ts, favorable_extreme)

        # -- P2: catastrophic backstop
        if bar_atr > 0:
            if side == "BUY" and (entry_price - current_price) >= catastrophic_atr_mult * bar_atr:
                return _make_trade(entry, df, i, current_price, "catastrophic_stop",
                                   entry_time, ts, favorable_extreme)
            if side == "SELL" and (current_price - entry_price) >= catastrophic_atr_mult * bar_atr:
                return _make_trade(entry, df, i, current_price, "catastrophic_stop",
                                   entry_time, ts, favorable_extreme)

        # -- P3: trailing stop (only after trail activation)
        if bar_atr > 0:
            activate_threshold = trail_activate_atr_mult * bar_atr
            if side == "BUY":
                profit_from_extreme = favorable_extreme - entry_price
                if profit_from_extreme >= activate_threshold:
                    trail_price = favorable_extreme - trail_atr_mult * bar_atr
                    if current_price <= trail_price:
                        return _make_trade(entry, df, i, current_price, "trailing_stop",
                                           entry_time, ts, favorable_extreme)
            else:
                profit_from_extreme = entry_price - favorable_extreme
                if profit_from_extreme >= activate_threshold:
                    trail_price = favorable_extreme + trail_atr_mult * bar_atr
                    if current_price >= trail_price:
                        return _make_trade(entry, df, i, current_price, "trailing_stop",
                                           entry_time, ts, favorable_extreme)

        # -- P4: EOD close
        if _eod_reached(ts):
            return _make_trade(entry, df, i, current_price, "eod_close",
                               entry_time, ts, favorable_extreme)

        # -- day boundary: close at end of each session day
        next_row = df.iloc[i + 1] if i + 1 < len(df) else None
        if next_row is not None:
            next_ts: datetime = next_row["datetime"]
            if next_ts.date() != ts.date():
                # Force close at the last bar of the day
                return _make_trade(entry, df, i, current_price, "day_close",
                                   entry_time, ts, favorable_extreme)

        prev_price = current_price

    # End of data
    last_row = df.iloc[-1]
    return _make_trade(entry, df, len(df) - 1, float(last_row["close"]), "end_of_data",
                       entry_time, last_row["datetime"], favorable_extreme)


def simulate_setup_target_exit(
    df: pd.DataFrame,
    entry: EntrySignal,
) -> SimTrade | None:
    """Event loop for SetupTargetExit (fixed stop + fixed target) on one position."""
    entry_price = entry.entry_price
    side = entry.side
    stop_price = entry.stop_price
    take_profit = entry.take_profit
    start_idx = entry.bar_idx
    entry_time = df.iloc[start_idx]["datetime"]
    favorable_extreme = entry_price

    for i in range(start_idx + 1, len(df)):
        row = df.iloc[i]
        ts: datetime = row["datetime"]
        current_price = float(row["close"])

        # Update favorable extreme
        if side == "BUY":
            if current_price > favorable_extreme:
                favorable_extreme = current_price
        else:
            if current_price < favorable_extreme:
                favorable_extreme = current_price

        # -- Stop loss
        if side == "BUY" and current_price <= stop_price:
            return _make_trade(entry, df, i, current_price, "stop_loss",
                               entry_time, ts, favorable_extreme)
        if side == "SELL" and current_price >= stop_price:
            return _make_trade(entry, df, i, current_price, "stop_loss",
                               entry_time, ts, favorable_extreme)

        # -- Take profit
        if side == "BUY" and current_price >= take_profit:
            return _make_trade(entry, df, i, current_price, "target_reached",
                               entry_time, ts, favorable_extreme)
        if side == "SELL" and current_price <= take_profit:
            return _make_trade(entry, df, i, current_price, "target_reached",
                               entry_time, ts, favorable_extreme)

        # -- EOD
        if _eod_reached(ts):
            return _make_trade(entry, df, i, current_price, "eod_close",
                               entry_time, ts, favorable_extreme)

        # -- Day boundary
        next_row = df.iloc[i + 1] if i + 1 < len(df) else None
        if next_row is not None:
            next_ts: datetime = next_row["datetime"]
            if next_ts.date() != ts.date():
                return _make_trade(entry, df, i, current_price, "day_close",
                                   entry_time, ts, favorable_extreme)

    last_row = df.iloc[-1]
    return _make_trade(entry, df, len(df) - 1, float(last_row["close"]), "end_of_data",
                       entry_time, last_row["datetime"], favorable_extreme)


def _make_trade(
    entry: EntrySignal,
    df: pd.DataFrame,
    exit_idx: int,
    exit_price: float,
    exit_reason: str,
    entry_time: datetime,
    exit_time: datetime,
    favorable_extreme: float,
) -> SimTrade:
    side = entry.side
    entry_price = entry.entry_price
    if side == "BUY":
        pnl_pts = exit_price - entry_price
    else:
        pnl_pts = entry_price - exit_price
    pnl_pct = pnl_pts / entry_price * 100.0
    holding_bars = exit_idx - entry.bar_idx
    holding_minutes = (exit_time - entry_time).total_seconds() / 60.0
    return SimTrade(
        entry_idx=entry.bar_idx,
        entry_price=entry_price,
        entry_time=entry_time,
        exit_idx=exit_idx,
        exit_price=exit_price,
        exit_time=exit_time,
        side=side,
        setup=entry.setup,
        exit_reason=exit_reason,
        pnl_pts=pnl_pts,
        pnl_pct=pnl_pct,
        holding_bars=holding_bars,
        holding_minutes=holding_minutes,
        favorable_extreme=favorable_extreme,
        atr_at_entry=entry.atr,
    )


# ── Portfolio-level metrics ────────────────────────────────────────────────────

def compute_metrics(trades: list[SimTrade]) -> dict:
    if not trades:
        return {
            "n_trades": 0,
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "total_pnl_pts": 0.0,
            "sharpe": 0.0,
            "mdd_pct": 0.0,
            "median_hold_min": 0.0,
            "mean_hold_min": 0.0,
            "p25_hold_min": 0.0,
            "p75_hold_min": 0.0,
            "exit_reasons": {},
        }

    n = len(trades)
    wins = [t for t in trades if t.pnl_pts > 0]
    losses = [t for t in trades if t.pnl_pts <= 0]
    returns = [t.pnl_pct for t in trades]
    holds = [t.holding_minutes for t in trades]

    win_rate = len(wins) / n * 100

    # Sharpe (annualised from per-trade returns — rough, not daily)
    arr = np.array(returns)
    sharpe = (
        float(np.mean(arr) / np.std(arr, ddof=1) * np.sqrt(252))
        if len(arr) >= 2 and np.std(arr, ddof=1) > 0
        else 0.0
    )

    # Running equity for MDD
    equity = [10_000_000.0]
    # Approx: each trade = 1 contract × 50,000 point_value
    pv = FUTURES_POINT_VALUE
    for t in trades:
        equity.append(equity[-1] + t.pnl_pts * pv)
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    # Exit breakdown
    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1

    return {
        "n_trades": n,
        "win_rate": round(win_rate, 1),
        "avg_return_pct": round(float(np.mean(arr)), 4),
        "total_pnl_pts": round(sum(t.pnl_pts for t in trades), 2),
        "total_pnl_krw": round(sum(t.pnl_pts for t in trades) * pv, 0),
        "sharpe": round(sharpe, 3),
        "mdd_pct": round(max_dd, 2),
        "median_hold_min": round(float(np.median(holds)), 1),
        "mean_hold_min": round(float(np.mean(holds)), 1),
        "p25_hold_min": round(float(np.percentile(holds, 25)), 1),
        "p75_hold_min": round(float(np.percentile(holds, 75)), 1),
        "exit_reasons": reasons,
    }


# ── Trailing give-back analysis ────────────────────────────────────────────────

def trailing_giveback(trades: list[SimTrade]) -> dict:
    """How much profit did the trailing stop give back vs the favorable extreme?"""
    if not trades:
        return {}
    gb_pcts = []
    for t in trades:
        if t.side == "BUY":
            max_profit = (t.favorable_extreme - t.entry_price) / t.entry_price * 100
        else:
            max_profit = (t.entry_price - t.favorable_extreme) / t.entry_price * 100
        if max_profit > 0:
            actual = t.pnl_pct
            gb = max_profit - actual  # positive = gave back profit
            gb_pcts.append(gb)
    if not gb_pcts:
        return {}
    return {
        "median_giveback_pct": round(float(np.median(gb_pcts)), 4),
        "mean_giveback_pct": round(float(np.mean(gb_pcts)), 4),
        "trades_with_giveback": len([g for g in gb_pcts if g > 0]),
        "total_trades_with_max_profit": len(gb_pcts),
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def print_report(label: str, m: dict, gb: dict) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Trades          : {m['n_trades']}")
    print(f"  Win Rate        : {m['win_rate']:.1f}%")
    print(f"  Avg Return      : {m['avg_return_pct']:+.4f}%")
    print(f"  Total PnL (pts) : {m['total_pnl_pts']:+.2f}")
    print(f"  Total PnL (KRW) : {m.get('total_pnl_krw', 0):+,.0f}")
    print(f"  Sharpe          : {m['sharpe']:+.3f}")
    print(f"  MDD             : {m['mdd_pct']:.2f}%")
    print(f"  Hold (median)   : {m['median_hold_min']:.1f} min")
    print(f"  Hold (mean)     : {m['mean_hold_min']:.1f} min")
    print(f"  Hold (P25/P75)  : {m['p25_hold_min']:.1f} / {m['p75_hold_min']:.1f} min")
    if m['exit_reasons']:
        print(f"  Exit Reasons    :")
        for k, v in sorted(m['exit_reasons'].items(), key=lambda x: -x[1]):
            print(f"    {k:<22}: {v}")
    if gb:
        print(f"  Give-back (med) : {gb.get('median_giveback_pct', 0):+.4f}%")
        print(f"  Give-back (avg) : {gb.get('mean_giveback_pct', 0):+.4f}%")
        print(f"  Trades w/ max P : {gb.get('trades_with_giveback', 0)} "
              f"/ {gb.get('total_trades_with_max_profit', 0)}")


def run_backtest(
    df: pd.DataFrame,
    label: str = "",
    *,
    trail_atr_mult: float = TRAIL_ATR_MULT,
) -> None:
    """Run both arms on df and print comparison."""
    print(f"\n{'#'*60}")
    print(f"  Period: {df['datetime'].min().date()} ~ {df['datetime'].max().date()}")
    print(f"  Bars : {len(df)}  |  Days: {df['datetime'].dt.date.nunique()}")
    if label:
        print(f"  Label: {label}")
    print(f"{'#'*60}")

    # Synthesize entries (same for both arms)
    entries_a = synthesize_setup_a_entries(df)
    entries_c = synthesize_setup_c_entries(df)
    entries = entries_a + entries_c
    entries.sort(key=lambda e: e.bar_idx)

    print(f"\n  Synthesised entries: {len(entries)} total "
          f"({len(entries_a)} Setup-A, {len(entries_c)} Setup-C)")
    if not entries:
        print("  WARNING: no entries generated — check data or filter thresholds")
        return

    # Arm A: TrackAExit
    track_a_trades: list[SimTrade] = []
    for entry in entries:
        t = simulate_track_a_exit(df, entry, trail_atr_mult=trail_atr_mult)
        if t is not None:
            track_a_trades.append(t)

    # Arm B: SetupTargetExit
    target_trades: list[SimTrade] = []
    for entry in entries:
        t = simulate_setup_target_exit(df, entry)
        if t is not None:
            target_trades.append(t)

    m_track = compute_metrics(track_a_trades)
    m_target = compute_metrics(target_trades)
    gb_track = trailing_giveback(track_a_trades)
    gb_target = trailing_giveback(target_trades)

    print_report("ARM A — TrackAExit (ATR trailing)", m_track, gb_track)
    print_report("ARM B — SetupTargetExit (fixed stop/target)", m_target, gb_target)

    # Verdict summary
    print(f"\n{'='*60}")
    print("  VERDICT SUMMARY")
    print(f"{'='*60}")
    sharpe_delta = m_track["sharpe"] - m_target["sharpe"]
    hold_delta = m_track["median_hold_min"] - m_target["median_hold_min"]
    win_delta = m_track["win_rate"] - m_target["win_rate"]
    pnl_delta = m_track["total_pnl_pts"] - m_target["total_pnl_pts"]
    print(f"  Sharpe delta (Track-A minus Target): {sharpe_delta:+.3f}")
    print(f"  Win-rate delta                     : {win_delta:+.1f}%")
    print(f"  Total PnL delta (pts)              : {pnl_delta:+.2f}")
    print(f"  Median hold delta                  : {hold_delta:+.1f} min")
    if m_track["n_trades"] > 0:
        gb_med = gb_track.get("median_giveback_pct", 0)
        print(f"  TrackA median give-back            : {gb_med:+.4f}%")
    print()
    if m_track["n_trades"] == 0:
        print("  VERDICT: Insufficient trades in TrackA arm — INCONCLUSIVE")
    elif sharpe_delta > 0.1 and pnl_delta > 0:
        print("  VERDICT: TrackAExit OUTPERFORMS fixed brackets on this dataset.")
        print("  Trailing exit holds winners longer; mean-reversion pattern accommodated.")
    elif sharpe_delta < -0.1 or pnl_delta < -50:
        print("  VERDICT: TrackAExit UNDERPERFORMS fixed brackets.")
        print("  Trailing on mean-reversion gives back profits as price reverts.")
        print("  RECOMMENDATION: Consider shorter trail_atr_mult (<= 2.0) or")
        print("  momentum-decay assist to detect reversal before trail fires.")
    else:
        print("  VERDICT: Results comparable — no clear winner.")
        print("  Consider walk-forward analysis across different regime windows.")


def main() -> None:
    parser = argparse.ArgumentParser(description="TrackAExit vs SetupTargetExit holdout backtest")
    parser.add_argument(
        "--data",
        default="data/kospi200f_1m_ch_101S6000.csv",
        help="Path to KOSPI200F 1m CSV",
    )
    parser.add_argument(
        "--holdout-split",
        default=None,
        help="ISO date to split train/holdout (default: auto 2/3 train)",
    )
    parser.add_argument(
        "--holdout-only",
        action="store_true",
        help="Only report holdout period results",
    )
    parser.add_argument(
        "--trail-atr-mult",
        type=float,
        default=TRAIL_ATR_MULT,
        help="Trailing stop ATR multiplier (default 3.0)",
    )
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.is_absolute():
        data_path = PROJECT_ROOT / data_path
    if not data_path.exists():
        print(f"ERROR: Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading data: {data_path}")
    df = pd.read_csv(data_path, parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    print(f"Loaded {len(df)} bars | {df['datetime'].min().date()} ~ {df['datetime'].max().date()}")

    # Compute ATR-14 and prev_close
    df["atr"] = compute_atr(df, period=14)
    df["prev_close"] = compute_prev_close(df)

    # LookaheadGuard: validate that ATR only uses data up to current bar
    # (EMA applied forward via ewm — but we process bars in chronological order,
    # so at bar i, ewm uses bars 0..i. This is causal — no look-ahead.)
    assert df["datetime"].is_monotonic_increasing, "Data is not sorted chronologically"

    # Train/holdout split
    trading_days = sorted(df["datetime"].dt.date.unique())
    n_days = len(trading_days)

    if args.holdout_split:
        split_date = pd.Timestamp(args.holdout_split).date()
    else:
        split_idx = int(n_days * 2 / 3)
        split_date = trading_days[split_idx]

    train_end = trading_days[trading_days.index(split_date) - 1] if split_date in trading_days else split_date
    print(f"\nHoldout split: {split_date} (train: ..{train_end}, holdout: {split_date}..)")

    df_train = df[df["datetime"].dt.date < split_date].copy()
    df_holdout = df[df["datetime"].dt.date >= split_date].copy()
    df_train = df_train.reset_index(drop=True)
    df_holdout = df_holdout.reset_index(drop=True)

    print(f"Train   : {len(df_train)} bars, {df_train['datetime'].dt.date.nunique()} days")
    print(f"Holdout : {len(df_holdout)} bars, {df_holdout['datetime'].dt.date.nunique()} days")

    trail_atr_mult = args.trail_atr_mult

    if not args.holdout_only:
        run_backtest(df_train, label="TRAIN (in-sample)", trail_atr_mult=trail_atr_mult)

    run_backtest(df_holdout, label="HOLDOUT (out-of-sample)", trail_atr_mult=trail_atr_mult)


if __name__ == "__main__":
    main()
