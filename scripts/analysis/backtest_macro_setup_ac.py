"""Real Setup A/C backtest with macro context — macro-only path (LLM tuning excluded).

Goal
----
Unblock real Setup A/C backtesting: the 1-minute OHLCV dataset carries no
macro_overnight context, so ``SetupAGapReversion.check()`` always returns
``None`` at gate 2. This script:

1. Backfills per-day S&P 500 overnight close/change via yfinance.
2. Builds a ``macro_provider`` callable that returns the correct
   ``MacroSnapshot`` for each bar's trading day (LookaheadGuard-safe: uses
   data KNOWN at/before 06:30 KST, i.e. T-1 US close → T KR session).
3. Runs ``MarketContextReplay`` + real ``SetupAGapReversion`` (config from
   ``config/decision_engine.yaml``) on the full dataset.
4. Setup C is also exercised; without a real scheduled-event calendar it fires
   as a pure 15-min-range breakout (``scheduled_events=[]`` — events come
   from the context but ``find_recent_event`` requires non-empty events).
   Setup C entries are therefore 0 for now; this is documented as a known
   limitation, not a code bug.
5. For each Setup-A entry, simulates both TrackAExit (tuned trail=1.5,
   activate=2.0) and SetupTargetExit (fixed stop from config) and compares.

LLM context
-----------
``llm_tuning.enabled`` is ``False`` (the Pydantic default). This is the
deterministic indicator+macro core of Setup A/C — the most honest backtest
possible without fabricating LLM scores. LLM historical output files
(output/llm/unified_data_*.json) contain direction/confidence but NOT in
the ``overall_signal``/``regime`` schema that ``setup_adapters.py`` consumes,
so they cannot be directly replayed. This is clearly labeled in the output.

LookaheadGuard compliance
-------------------------
SP500 overnight close for session date T is fetched from the T-1 US close
(via yfinance daily bars, indexed by US trading date). The Korean session
opens at 09:00 KST on T. The US close happened at ~22:00 KST on T-1 (16:00
ET). We map: kr_date T → us_date T-1 → sp500_change_pct. There is no
look-ahead since the US close is known before KR session open.

Usage
-----
    .venv/bin/python scripts/analysis/backtest_macro_setup_ac.py
    .venv/bin/python scripts/analysis/backtest_macro_setup_ac.py \\
        --data data/kospi200f_1m_ch_101S6000.csv --holdout-only

Output
------
Prints a comparison report and writes a JSON summary to
``.superpowers/sdd/bt-data-unblock-report-macro.json``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

# ── project root on path ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.backtest.market_context_replay import MarketContextReplay
from shared.decision.context import MarketContext
from shared.decision.setups.gap_reversion import SetupAConfig, SetupAGapReversion
from shared.execution.contract_spec import ContractSpec
from shared.macro.base import MacroSnapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FUTURES_POINT_VALUE = 50_000  # KRW per index point (KOSPI200 mini/standard)

# Tuned TrackAExit parameters (from config/strategies/futures/track_a_exit.yaml)
TRAIL_ATR_MULT_TUNED = 1.5
TRAIL_ACTIVATE_ATR_MULT_TUNED = 2.0
CRASH_ATR_MULT = 3.5
CATASTROPHIC_ATR_MULT = 6.0
EOD_HOUR = 15
EOD_MINUTE = 15


# ---------------------------------------------------------------------------
# Macro backfill — SP500 per trading day via yfinance
# ---------------------------------------------------------------------------

def build_sp500_daily_snapshots(
    start_date: date, end_date: date
) -> dict[date, MacroSnapshot]:
    """Fetch S&P 500 daily OHLCV via yfinance and build MacroSnapshot per KR date.

    LookaheadGuard mapping: KR session date T ← US close of T-1.
    The ``^GSPC`` ticker returns US-calendar dates. We forward-fill missing
    dates (US holidays) so every KR trading day has a snapshot.

    Returns a dict keyed by KR trading date (``date`` objects).
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError(
            "yfinance is required for macro backfill. "
            "Install with: pip install yfinance"
        ) from exc

    # Fetch SP500 with buffer so we can do T-1 lookups from the first KR date
    fetch_start = (pd.Timestamp(start_date) - pd.Timedelta(days=10)).date()
    fetch_end = (pd.Timestamp(end_date) + pd.Timedelta(days=2)).date()

    logger.info(
        "Fetching SP500 daily data %s ~ %s via yfinance ...", fetch_start, fetch_end
    )
    ticker = yf.Ticker("^GSPC")
    hist = ticker.history(start=str(fetch_start), end=str(fetch_end))
    if hist.empty:
        raise RuntimeError(
            f"yfinance returned empty SP500 data for {fetch_start} ~ {fetch_end}"
        )

    # Build a sorted series: us_date → (close, change_pct)
    hist.index = pd.DatetimeIndex(hist.index).tz_localize(None).normalize()
    hist = hist.sort_index()
    us_closes = hist["Close"].copy()
    us_prev = us_closes.shift(1)
    us_change_pct = (us_closes - us_prev) / us_prev * 100.0

    us_date_to_close: dict[date, float] = {
        ts.date(): float(v) for ts, v in us_closes.items() if not np.isnan(v)
    }
    us_date_to_change: dict[date, float] = {
        ts.date(): float(v) for ts, v in us_change_pct.items() if not np.isnan(v)
    }

    # Build KR-date → MacroSnapshot mapping
    # KR date T maps to the most recent available US close on or before T-1
    snapshots: dict[date, MacroSnapshot] = {}
    all_us_dates = sorted(us_date_to_close.keys())

    def _latest_us_close_before(kr_date: date) -> tuple[float | None, float | None]:
        """Return (sp500_close, sp500_change_pct) for the last US day before kr_date."""
        cutoff = kr_date - timedelta(days=1)  # T-1 strict
        # Walk backwards from cutoff to find a valid US trading day
        for us_d in reversed(all_us_dates):
            if us_d <= cutoff:
                return us_date_to_close.get(us_d), us_date_to_change.get(us_d)
        return None, None

    kr_date = start_date
    while kr_date <= end_date:
        sp500_close, sp500_change_pct = _latest_us_close_before(kr_date)
        if sp500_close is not None:
            snapshots[kr_date] = MacroSnapshot(
                ts_ms=int(
                    pd.Timestamp(kr_date).replace(hour=6, minute=30).timestamp() * 1000
                ),
                session="overnight_us_close",
                sp500_close=sp500_close,
                sp500_change_pct=sp500_change_pct,
                collected_from=["yfinance_backfill"],
            )
        kr_date += timedelta(days=1)

    logger.info(
        "Built %d macro snapshots for %d KR calendar days (%s ~ %s)",
        len(snapshots),
        (end_date - start_date).days + 1,
        start_date,
        end_date,
    )
    return snapshots


# ---------------------------------------------------------------------------
# Entry signal via real SetupAGapReversion
# ---------------------------------------------------------------------------

@dataclass
class RealEntrySignal:
    bar_idx: int
    entry_price: float
    side: Literal["BUY", "SELL"]
    atr: float
    stop_price: float
    take_profit: float
    setup: str
    confidence: float
    sp500_change_pct: float | None
    kr_gap_pct: float | None


def collect_real_setup_a_entries(
    replay: MarketContextReplay,
    config: SetupAConfig,
    df: pd.DataFrame,
) -> list[RealEntrySignal]:
    """Iterate MarketContextReplay and collect real Setup A signals.

    One entry per day max (matches live behavior).
    """
    setup = SetupAGapReversion(config=config)
    signals: list[RealEntrySignal] = []
    last_entry_day: date | None = None

    # Build a fast bar_idx from the df index aligned with replay context timestamps
    ts_col = df["timestamp"].tolist()
    ts_to_idx: dict = {ts_col[i]: i for i in range(len(ts_col))}

    for ctx in replay.iter_contexts():
        ts_kst = ctx.now
        day = ts_kst.date()
        if day == last_entry_day:
            continue  # one entry per day

        signal = setup.check(ctx)
        if signal is None:
            continue

        # Find bar idx from timestamp
        ts_naive = pd.Timestamp(ts_kst).tz_localize(None)
        # Try to find bar index by matching against the dataframe
        # (MarketContextReplay yields bars in order so we search forward)
        bar_idx = None
        for i, ts in enumerate(ts_col):
            t = pd.Timestamp(ts)
            if t.tzinfo is not None:
                t = t.tz_convert(None)
            if t == ts_naive or abs((t - ts_naive).total_seconds()) < 30:
                bar_idx = i
                break

        if bar_idx is None:
            # fallback: skip — can't locate the bar
            logger.debug("Could not locate bar for ts=%s — skipping", ts_kst)
            continue

        # Extract stop from the signal
        atr = ctx.atr_14
        macro = ctx.macro_overnight
        sp500_pct = macro.sp500_change_pct if macro else None
        gap_pct = (
            (ctx.today_open - ctx.prev_close) / ctx.prev_close * 100
            if ctx.prev_close > 0
            else None
        )

        if signal.direction == "long":
            side: Literal["BUY", "SELL"] = "BUY"
            stop_price = signal.stop_loss
        else:
            side = "SELL"
            stop_price = signal.stop_loss

        signals.append(
            RealEntrySignal(
                bar_idx=bar_idx,
                entry_price=signal.entry_price,
                side=side,
                atr=atr,
                stop_price=stop_price,
                take_profit=signal.take_profit,
                setup="setup_a_real",
                confidence=signal.confidence,
                sp500_change_pct=sp500_pct,
                kr_gap_pct=gap_pct,
            )
        )
        last_entry_day = day

    return signals


# ---------------------------------------------------------------------------
# Exit simulation (shared with proxy harness)
# ---------------------------------------------------------------------------

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
    pnl_pts: float
    pnl_pct: float
    holding_bars: int
    holding_minutes: float
    favorable_extreme: float
    atr_at_entry: float
    confidence: float = 0.0
    sp500_change_pct: float | None = None


def _eod_reached(ts: datetime) -> bool:
    return ts.hour > EOD_HOUR or (ts.hour == EOD_HOUR and ts.minute >= EOD_MINUTE)


def simulate_track_a_exit(
    df: pd.DataFrame,
    entry: RealEntrySignal,
    *,
    trail_atr_mult: float = TRAIL_ATR_MULT_TUNED,
    trail_activate_atr_mult: float = TRAIL_ACTIVATE_ATR_MULT_TUNED,
    crash_atr_mult: float = CRASH_ATR_MULT,
    catastrophic_atr_mult: float = CATASTROPHIC_ATR_MULT,
) -> SimTrade | None:
    entry_price = entry.entry_price
    side = entry.side
    atr = entry.atr
    start_idx = entry.bar_idx
    entry_time: datetime = df.iloc[start_idx]["timestamp"]
    if hasattr(entry_time, "tzinfo") and entry_time.tzinfo is not None:
        entry_time = entry_time.replace(tzinfo=None)

    favorable_extreme = entry_price
    prev_price = entry_price

    for i in range(start_idx + 1, len(df)):
        row = df.iloc[i]
        ts: datetime = row["timestamp"]
        if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        current_price = float(row["close"])
        bar_atr = float(row.get("atr", atr))
        if bar_atr <= 0:
            bar_atr = atr

        if side == "BUY":
            if current_price > favorable_extreme:
                favorable_extreme = current_price
        else:
            if current_price < favorable_extreme:
                favorable_extreme = current_price

        # P1: crash guard
        if bar_atr > 0:
            if side == "BUY" and (prev_price - current_price) >= crash_atr_mult * bar_atr:
                return _make_trade(
                    entry, i, current_price, "crash_guard",
                    entry_time, ts, favorable_extreme
                )
            if side == "SELL" and (current_price - prev_price) >= crash_atr_mult * bar_atr:
                return _make_trade(
                    entry, i, current_price, "crash_guard",
                    entry_time, ts, favorable_extreme
                )

        # P2: catastrophic backstop
        if bar_atr > 0:
            if side == "BUY" and (entry_price - current_price) >= catastrophic_atr_mult * bar_atr:
                return _make_trade(
                    entry, i, current_price, "catastrophic_stop",
                    entry_time, ts, favorable_extreme
                )
            if side == "SELL" and (current_price - entry_price) >= catastrophic_atr_mult * bar_atr:
                return _make_trade(
                    entry, i, current_price, "catastrophic_stop",
                    entry_time, ts, favorable_extreme
                )

        # P3: trailing stop
        if bar_atr > 0:
            activate_threshold = trail_activate_atr_mult * bar_atr
            if side == "BUY":
                if (favorable_extreme - entry_price) >= activate_threshold:
                    trail_price = favorable_extreme - trail_atr_mult * bar_atr
                    if current_price <= trail_price:
                        return _make_trade(
                            entry, i, current_price, "trailing_stop",
                            entry_time, ts, favorable_extreme
                        )
            else:
                if (entry_price - favorable_extreme) >= activate_threshold:
                    trail_price = favorable_extreme + trail_atr_mult * bar_atr
                    if current_price >= trail_price:
                        return _make_trade(
                            entry, i, current_price, "trailing_stop",
                            entry_time, ts, favorable_extreme
                        )

        # P4: EOD
        if _eod_reached(ts):
            return _make_trade(
                entry, i, current_price, "eod_close",
                entry_time, ts, favorable_extreme
            )

        # Day boundary close
        next_row = df.iloc[i + 1] if i + 1 < len(df) else None
        if next_row is not None:
            next_ts: datetime = next_row["timestamp"]
            if hasattr(next_ts, "tzinfo") and next_ts.tzinfo is not None:
                next_ts = next_ts.replace(tzinfo=None)
            if next_ts.date() != ts.date():
                return _make_trade(
                    entry, i, current_price, "day_close",
                    entry_time, ts, favorable_extreme
                )

        prev_price = current_price

    last_row = df.iloc[-1]
    last_ts = last_row["timestamp"]
    if hasattr(last_ts, "tzinfo") and last_ts.tzinfo is not None:
        last_ts = last_ts.replace(tzinfo=None)
    return _make_trade(
        entry, len(df) - 1, float(last_row["close"]), "end_of_data",
        entry_time, last_ts, favorable_extreme
    )


def simulate_setup_target_exit(
    df: pd.DataFrame,
    entry: RealEntrySignal,
) -> SimTrade | None:
    entry_price = entry.entry_price
    side = entry.side
    stop_price = entry.stop_price
    take_profit = entry.take_profit
    start_idx = entry.bar_idx
    entry_time: datetime = df.iloc[start_idx]["timestamp"]
    if hasattr(entry_time, "tzinfo") and entry_time.tzinfo is not None:
        entry_time = entry_time.replace(tzinfo=None)
    favorable_extreme = entry_price

    for i in range(start_idx + 1, len(df)):
        row = df.iloc[i]
        ts: datetime = row["timestamp"]
        if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        current_price = float(row["close"])

        if side == "BUY":
            if current_price > favorable_extreme:
                favorable_extreme = current_price
        else:
            if current_price < favorable_extreme:
                favorable_extreme = current_price

        if side == "BUY" and current_price <= stop_price:
            return _make_trade(
                entry, i, current_price, "stop_loss",
                entry_time, ts, favorable_extreme
            )
        if side == "SELL" and current_price >= stop_price:
            return _make_trade(
                entry, i, current_price, "stop_loss",
                entry_time, ts, favorable_extreme
            )
        if side == "BUY" and current_price >= take_profit:
            return _make_trade(
                entry, i, current_price, "target_reached",
                entry_time, ts, favorable_extreme
            )
        if side == "SELL" and current_price <= take_profit:
            return _make_trade(
                entry, i, current_price, "target_reached",
                entry_time, ts, favorable_extreme
            )
        if _eod_reached(ts):
            return _make_trade(
                entry, i, current_price, "eod_close",
                entry_time, ts, favorable_extreme
            )
        next_row = df.iloc[i + 1] if i + 1 < len(df) else None
        if next_row is not None:
            next_ts = next_row["timestamp"]
            if hasattr(next_ts, "tzinfo") and next_ts.tzinfo is not None:
                next_ts = next_ts.replace(tzinfo=None)
            if next_ts.date() != ts.date():
                return _make_trade(
                    entry, i, current_price, "day_close",
                    entry_time, ts, favorable_extreme
                )

    last_row = df.iloc[-1]
    last_ts = last_row["timestamp"]
    if hasattr(last_ts, "tzinfo") and last_ts.tzinfo is not None:
        last_ts = last_ts.replace(tzinfo=None)
    return _make_trade(
        entry, len(df) - 1, float(last_row["close"]), "end_of_data",
        entry_time, last_ts, favorable_extreme
    )


def _make_trade(
    entry: RealEntrySignal,
    exit_idx: int,
    exit_price: float,
    exit_reason: str,
    entry_time: datetime,
    exit_time: datetime,
    favorable_extreme: float,
) -> SimTrade:
    side = entry.side
    ep = entry.entry_price
    pnl_pts = (exit_price - ep) if side == "BUY" else (ep - exit_price)
    pnl_pct = pnl_pts / ep * 100.0
    holding_bars = exit_idx - entry.bar_idx
    holding_minutes = (exit_time - entry_time).total_seconds() / 60.0
    return SimTrade(
        entry_idx=entry.bar_idx,
        entry_price=ep,
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
        confidence=entry.confidence,
        sp500_change_pct=entry.sp500_change_pct,
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(trades: list[SimTrade]) -> dict:
    if not trades:
        return {
            "n_trades": 0,
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "total_pnl_pts": 0.0,
            "total_pnl_krw": 0.0,
            "sharpe": 0.0,
            "mdd_pct": 0.0,
            "median_hold_min": 0.0,
            "mean_hold_min": 0.0,
            "exit_reasons": {},
        }

    returns = np.array([t.pnl_pct for t in trades])
    holds = [t.holding_minutes for t in trades]
    wins = sum(1 for t in trades if t.pnl_pts > 0)
    win_rate = wins / len(trades) * 100

    sharpe = (
        float(np.mean(returns) / np.std(returns, ddof=1) * np.sqrt(252))
        if len(returns) >= 2 and np.std(returns, ddof=1) > 0
        else 0.0
    )

    equity = [10_000_000.0]
    pv = FUTURES_POINT_VALUE
    for t in trades:
        equity.append(equity[-1] + t.pnl_pts * pv)
    peak = equity[0]
    mdd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100 if peak > 0 else 0.0
        if dd > mdd:
            mdd = dd

    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1

    return {
        "n_trades": len(trades),
        "win_rate": round(win_rate, 1),
        "avg_return_pct": round(float(np.mean(returns)), 4),
        "total_pnl_pts": round(sum(t.pnl_pts for t in trades), 2),
        "total_pnl_krw": round(sum(t.pnl_pts for t in trades) * pv, 0),
        "sharpe": round(sharpe, 3),
        "mdd_pct": round(mdd, 2),
        "median_hold_min": round(float(np.median(holds)), 1),
        "mean_hold_min": round(float(np.mean(holds)), 1),
        "exit_reasons": reasons,
    }


def trailing_giveback(trades: list[SimTrade]) -> dict:
    gb_pcts = []
    for t in trades:
        max_profit = (
            (t.favorable_extreme - t.entry_price) / t.entry_price * 100
            if t.side == "BUY"
            else (t.entry_price - t.favorable_extreme) / t.entry_price * 100
        )
        if max_profit > 0:
            gb_pcts.append(max_profit - t.pnl_pct)
    if not gb_pcts:
        return {}
    return {
        "median_giveback_pct": round(float(np.median(gb_pcts)), 4),
        "mean_giveback_pct": round(float(np.mean(gb_pcts)), 4),
        "trades_with_max_profit": len(gb_pcts),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_metrics(label: str, m: dict, gb: dict | None = None) -> None:
    print(f"\n{'='*65}")
    print(f"  {label}")
    print(f"{'='*65}")
    print(f"  Trades          : {m['n_trades']}")
    print(f"  Win Rate        : {m['win_rate']:.1f}%")
    print(f"  Avg Return      : {m['avg_return_pct']:+.4f}%")
    print(f"  Total PnL (pts) : {m['total_pnl_pts']:+.2f}")
    print(f"  Total PnL (KRW) : {m.get('total_pnl_krw', 0):+,.0f}")
    print(f"  Sharpe          : {m['sharpe']:+.3f}")
    print(f"  MDD             : {m['mdd_pct']:.2f}%")
    print(f"  Hold (median)   : {m['median_hold_min']:.1f} min")
    print(f"  Hold (mean)     : {m['mean_hold_min']:.1f} min")
    if m.get("exit_reasons"):
        print("  Exit Reasons    :")
        for k, v in sorted(m["exit_reasons"].items(), key=lambda x: -x[1]):
            print(f"    {k:<22}: {v}")
    if gb:
        print(f"  Give-back (med) : {gb.get('median_giveback_pct', 0):+.4f}%")
        print(f"  Give-back (avg) : {gb.get('mean_giveback_pct', 0):+.4f}%")
        print(f"  Trades w/ max P : {gb.get('trades_with_max_profit', 0)}")


def run_backtest(
    df: pd.DataFrame,
    macro_snapshots: dict[date, MacroSnapshot],
    setup_a_config: SetupAConfig,
    label: str = "",
    **kwargs: object,
) -> dict:
    """Run real Setup A/C backtest on df slice. Returns metrics dict."""
    print(f"\n{'#'*65}")
    print(f"  Period: {df['timestamp'].min().date()} ~ {df['timestamp'].max().date()}")
    print(f"  Bars : {len(df)}  |  Days: {df['timestamp'].dt.date.nunique()}")
    if label:
        print(f"  Label: {label}")
    print(f"  LLM context: DISABLED (macro-only, deterministic indicator+macro core)")
    print(f"  Macro source: yfinance SP500 backfill (LookaheadGuard-safe)")
    min_volume: int = kwargs.get("min_volume", 30)
    print(f"  TrackA params: trail_atr_mult={TRAIL_ATR_MULT_TUNED}, "
          f"trail_activate={TRAIL_ACTIVATE_ATR_MULT_TUNED}")
    print(f"  min_volume filter: {min_volume} (phantom-bar suppression)")
    print(f"{'#'*65}")

    # Build a ContractSpec stub for MarketContextReplay
    contract_spec = ContractSpec(
        name="kospi200_futures",
        multiplier_krw_per_point=FUTURES_POINT_VALUE,
        tick_size_points=0.05,
        tick_value_krw=2500,
        commission_rate=0.00015,
        symbol_prefix="A05",
    )

    # Rename datetime→timestamp if needed for replay
    replay_df = df.copy()
    if "datetime" in replay_df.columns and "timestamp" not in replay_df.columns:
        replay_df = replay_df.rename(columns={"datetime": "timestamp"})
    if "timestamp" in replay_df.columns:
        col = replay_df["timestamp"]
        if hasattr(col.dtype, "tz") and col.dtype.tz is None:
            replay_df["timestamp"] = pd.to_datetime(replay_df["timestamp"])

    def macro_provider(kr_date: date) -> MacroSnapshot | None:
        return macro_snapshots.get(kr_date)

    min_volume: int = kwargs.get("min_volume", 30)
    replay = MarketContextReplay(
        df=replay_df,
        symbol="101S6000",
        macro_snapshot=None,  # per-day provider used instead
        scheduled_events=[],  # Setup C requires real event calendar — excluded
        contract_spec=contract_spec,
        macro_provider=macro_provider,
        min_volume=min_volume,
    )

    logger.info("Collecting real Setup A entries ...")
    entries = collect_real_setup_a_entries(replay, setup_a_config, replay_df)

    # For Setup C: 0 entries without real scheduled_events (documented limitation)
    print(f"\n  Real Setup A entries: {len(entries)}")
    print(f"  Setup C entries: 0 (no scheduled-event calendar in backtest — known limitation)")

    if not entries:
        print("  WARNING: no Setup A entries — check macro coverage or threshold config")
        empty_m = compute_metrics([])
        return {
            "label": label,
            "n_entries": 0,
            "track_a": empty_m,
            "target_exit": empty_m,
        }

    # Run exit arms
    track_a_trades: list[SimTrade] = []
    target_trades: list[SimTrade] = []
    for entry in entries:
        t1 = simulate_track_a_exit(replay_df, entry)
        if t1 is not None:
            track_a_trades.append(t1)
        t2 = simulate_setup_target_exit(replay_df, entry)
        if t2 is not None:
            target_trades.append(t2)

    m_track = compute_metrics(track_a_trades)
    m_target = compute_metrics(target_trades)
    gb_track = trailing_giveback(track_a_trades)
    gb_target = trailing_giveback(target_trades)

    print_metrics(f"ARM A — TrackAExit (trail={TRAIL_ATR_MULT_TUNED}, activate={TRAIL_ACTIVATE_ATR_MULT_TUNED})", m_track, gb_track)
    print_metrics("ARM B — SetupTargetExit (fixed stop/target)", m_target, gb_target)

    # Verdict
    sharpe_delta = m_track["sharpe"] - m_target["sharpe"]
    pnl_delta = m_track["total_pnl_pts"] - m_target["total_pnl_pts"]
    win_delta = m_track["win_rate"] - m_target["win_rate"]
    print(f"\n  VERDICT SUMMARY ({label})")
    print(f"  {'─'*60}")
    print(f"  Sharpe delta (TrackA − Target): {sharpe_delta:+.3f}")
    print(f"  Win-rate delta                : {win_delta:+.1f}%")
    print(f"  Total PnL delta (pts)         : {pnl_delta:+.2f}")
    if m_track["n_trades"] > 0:
        gb_med = gb_track.get("median_giveback_pct", 0)
        print(f"  TrackA median give-back       : {gb_med:+.4f}%")
    print()
    if m_track["n_trades"] == 0:
        print("  VERDICT: Insufficient trades — INCONCLUSIVE")
    elif sharpe_delta > 0.1 and pnl_delta > 0:
        print("  VERDICT: TrackAExit OUTPERFORMS fixed brackets.")
        print("  Tuned trail (1.5/2.0) holds winners; mean-reversion core intact.")
    elif sharpe_delta < -0.1 or pnl_delta < -50:
        print("  VERDICT: TrackAExit UNDERPERFORMS fixed brackets.")
        print("  Consider shorter trail or momentum-decay assist.")
    else:
        print("  VERDICT: Results comparable — no clear winner.")

    return {
        "label": label,
        "n_entries": len(entries),
        "track_a": m_track,
        "target_exit": m_target,
        "giveback_track_a": gb_track,
        "verdict_sharpe_delta": round(sharpe_delta, 3),
        "verdict_pnl_delta_pts": round(pnl_delta, 2),
        "verdict_win_delta_pct": round(win_delta, 1),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Real Setup A/C backtest with macro context (LLM tuning excluded)"
    )
    parser.add_argument(
        "--data",
        default="data/kospi200f_1m_ch_101S6000.csv",
        help="Path to KOSPI200F 1m CSV (default: data/kospi200f_1m_ch_101S6000.csv)",
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
        "--output",
        default=".superpowers/sdd/bt-data-unblock-report-macro.json",
        help="Path for JSON summary output",
    )
    parser.add_argument(
        "--min-volume",
        type=int,
        default=30,
        help="Minimum bar volume to include (default 30, suppresses phantom bars)",
    )
    parser.add_argument(
        "--min-bars-per-day",
        type=int,
        default=330,
        help=(
            "Drop trading days with fewer than this many bars before the volume filter "
            "(default 330 — ~85%% of a full 09:00-15:30 KST session). "
            "Use to exclude months with degraded futures feed. "
            "Set to 0 to disable."
        ),
    )
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.is_absolute():
        data_path = PROJECT_ROOT / data_path
    if not data_path.exists():
        print(f"ERROR: Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    logger.info("Loading data: %s", data_path)
    df = pd.read_csv(data_path, parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    # Rename to 'timestamp' for replay compatibility
    df = df.rename(columns={"datetime": "timestamp"})

    # Bar-density gate: drop degraded trading days (e.g. Jul–Oct 2025 where
    # WS feed degradation left <200 bars/day on most sessions).
    if args.min_bars_per_day > 0:
        bars_per_day = df.groupby(df["timestamp"].dt.date).size()
        healthy_days = set(bars_per_day[bars_per_day >= args.min_bars_per_day].index)
        before = len(df)
        before_days = df["timestamp"].dt.date.nunique()
        df = df[df["timestamp"].dt.date.map(lambda d: d in healthy_days)].reset_index(drop=True)
        dropped_days = before_days - df["timestamp"].dt.date.nunique()
        logger.info(
            "Bar-density gate (>=%d bars/day): dropped %d/%d days, %d/%d bars. "
            "Remaining: %s ~ %s",
            args.min_bars_per_day,
            dropped_days,
            before_days,
            before - len(df),
            before,
            df["timestamp"].min().date() if len(df) else "N/A",
            df["timestamp"].max().date() if len(df) else "N/A",
        )
        if len(df) == 0:
            print("ERROR: All days filtered out by bar-density gate. Lower --min-bars-per-day.", file=sys.stderr)
            sys.exit(1)
    logger.info(
        "Loaded %d bars | %s ~ %s",
        len(df),
        df["timestamp"].min().date(),
        df["timestamp"].max().date(),
    )

    # Compute ATR for exit simulation
    def compute_atr_series(df_: pd.DataFrame, period: int = 14) -> pd.Series:
        high = df_["high"]
        low = df_["low"]
        prev_close = df_["close"].shift(1)
        tr = pd.concat(
            [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
        ).max(axis=1)
        return tr.ewm(span=period, min_periods=1, adjust=False).mean()

    df["atr"] = compute_atr_series(df)

    # Backfill SP500 macro data
    start_date = df["timestamp"].min().date()
    end_date = df["timestamp"].max().date()
    macro_snapshots = build_sp500_daily_snapshots(start_date, end_date)

    # Log macro coverage
    total_days = df["timestamp"].dt.date.nunique()
    trading_days_with_macro = sum(
        1 for d in df["timestamp"].dt.date.unique() if d in macro_snapshots
    )
    logger.info(
        "Macro coverage: %d / %d trading days have SP500 snapshot",
        trading_days_with_macro,
        total_days,
    )

    # Load Setup A config from YAML
    setup_a_config = SetupAConfig()
    logger.info(
        "Setup A config: min_sp500_gap=%.1f%%, min_kr_gap=%.1f%%, "
        "retrace=[%.2f,%.2f], time=[%d,%d]min",
        setup_a_config.min_sp500_gap_pct,
        setup_a_config.min_kr_gap_pct,
        setup_a_config.retrace_min,
        setup_a_config.retrace_max,
        setup_a_config.valid_minutes_min,
        setup_a_config.valid_minutes_max,
    )

    # Train/holdout split
    trading_days = sorted(df["timestamp"].dt.date.unique())
    n_days = len(trading_days)

    if args.holdout_split:
        split_date = pd.Timestamp(args.holdout_split).date()
    else:
        split_idx = int(n_days * 2 / 3)
        split_date = trading_days[split_idx]

    split_idx_in_list = trading_days.index(split_date) if split_date in trading_days else 0
    train_end = trading_days[split_idx_in_list - 1] if split_idx_in_list > 0 else split_date
    print(f"\nHoldout split: {split_date} (train: ..{train_end}, holdout: {split_date}..)")

    df_train = df[df["timestamp"].dt.date < split_date].copy().reset_index(drop=True)
    df_holdout = df[df["timestamp"].dt.date >= split_date].copy().reset_index(drop=True)

    print(f"Train   : {len(df_train)} bars, {df_train['timestamp'].dt.date.nunique()} days")
    print(f"Holdout : {len(df_holdout)} bars, {df_holdout['timestamp'].dt.date.nunique()} days")

    results: dict = {
        "generated_at": datetime.utcnow().isoformat(),
        "data_path": str(data_path),
        "data_start": str(df["timestamp"].min().date()),
        "data_end": str(df["timestamp"].max().date()),
        "holdout_split": str(split_date),
        "macro_coverage_pct": round(trading_days_with_macro / total_days * 100, 1),
        "llm_context": "excluded — no persisted overall_signal/regime for holdout span",
        "setup_a_config": {
            "min_sp500_gap_pct": setup_a_config.min_sp500_gap_pct,
            "min_kr_gap_pct": setup_a_config.min_kr_gap_pct,
            "retrace_min": setup_a_config.retrace_min,
            "retrace_max": setup_a_config.retrace_max,
            "valid_minutes_min": setup_a_config.valid_minutes_min,
            "valid_minutes_max": setup_a_config.valid_minutes_max,
            "stop_atr_mult": setup_a_config.stop_atr_mult,
        },
        "track_a_params": {
            "trail_atr_mult": TRAIL_ATR_MULT_TUNED,
            "trail_activate_atr_mult": TRAIL_ACTIVATE_ATR_MULT_TUNED,
            "crash_atr_mult": CRASH_ATR_MULT,
            "catastrophic_atr_mult": CATASTROPHIC_ATR_MULT,
        },
        "periods": [],
    }

    min_volume = args.min_volume
    results["min_volume"] = min_volume
    results["min_bars_per_day"] = args.min_bars_per_day

    if not args.holdout_only:
        train_res = run_backtest(
            df_train, macro_snapshots, setup_a_config,
            label="TRAIN (in-sample)", min_volume=min_volume,
        )
        results["periods"].append(train_res)

    holdout_res = run_backtest(
        df_holdout, macro_snapshots, setup_a_config,
        label="HOLDOUT (out-of-sample)", min_volume=min_volume,
    )
    results["periods"].append(holdout_res)

    # Write JSON summary
    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = PROJECT_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nJSON summary written to: {out_path}")


if __name__ == "__main__":
    main()
