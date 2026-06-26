"""Walk-forward validation for Setup D — high-vol intraday VWAP reversion.

Honest out-of-sample validation of the Thesis-A mean-reversion edge. Loads the
clean Dec2025–Apr2026 101S6000 minute parquet (the #516-deduped, look-ahead-safe
window), replays it through ``MarketContextReplay`` + the real
``SetupDVWAPReversion.check()``, simulates an intrabar ATR-stop / VWAP-target /
EOD exit, and reports:

* Full-window metrics (Sharpe annualized on per-trade returns, MDD in KRW, win
  rate, trade count, long/short split, exit-reason histogram).
* Rolling walk-forward folds (default 2-month in-sample → 1-month out-of-sample,
  step 1 month). Each fold reports its OOS metrics so a curve-fit edge that does
  not generalize is visible.

Setup D reads only OHLCV-derived context (VWAP, ATR) — no macro/event backfill
needed, so this is a fully self-contained backtest.

Look-ahead safety + live parity
-------------------------------
``MarketContextReplay`` computes VWAP/ATR strictly from bars at or before the
current index, and the intrabar exit only consults the entry bar's signal +
subsequent bars. BOTH of Setup D's gate references are **causal and
self-computed** by ``SetupDVWAPReversion`` from the per-bar inputs, so they
behave identically here and in the live orchestrator path:
  * the high-vol reference from a trailing window of past ATRs (NOT the replay's
    full-series ``atr_90th_percentile`` — look-ahead, no live producer), and
  * the stall-guard recent range from a trailing window of past closes (NOT the
    replay's ``last_15min_high/low`` — no producer in the orchestrator path, so
    it would default to ``current_price`` live and the guard would never fire).
This parity is why the OOS numbers are reproducible as wired.

Usage::

    .venv/bin/python scripts/analysis/walkforward_setup_d_vwap_reversion.py
    .venv/bin/python scripts/analysis/walkforward_setup_d_vwap_reversion.py \\
        --is-months 2 --oos-months 1 --min-bars-per-day 330
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from shared.backtest.market_context_replay import MarketContextReplay
from shared.decision.setups.vwap_reversion import SetupDConfig, SetupDVWAPReversion
from shared.execution.contract_spec import ContractSpec

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

FUTURES_POINT_VALUE = 50_000  # KRW per index point
EOD_HOUR, EOD_MINUTE = 15, 15
SYMBOL = "101S6000"

# Default data root points at the repo's market-data store. The git worktree
# does not carry the gitignored data/ tree, so this defaults to the primary
# checkout and can be overridden with --data-root.
DEFAULT_DATA_ROOT = "/home/deploy/project/kis_unified_sts/data/market"


@dataclass
class SimTrade:
    bar_idx: int
    ts: pd.Timestamp
    entry: float
    side: Literal["BUY", "SELL"]
    exit_price: float
    exit_reason: str
    pnl_pts: float
    hold_min: float


@dataclass
class FoldResult:
    fold_id: int
    is_start: str
    is_end: str
    oos_start: str
    oos_end: str
    oos_trades: int
    oos_long: int
    oos_short: int
    oos_win_rate: float
    oos_total_pts: float
    oos_avg_pts: float
    oos_sharpe: float
    oos_mdd_krw: float


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_clean(
    data_root: str, start: date, end: date, min_bars_per_day: int
) -> pd.DataFrame:
    """Load 101S6000 minute bars and gate to near-full sessions."""
    from shared.storage.market_data_store import ParquetMarketDataStore

    store = ParquetMarketDataStore(root=Path(data_root), asset_class="futures")
    df = store.get_minute_bars(SYMBOL, start=start, end=end)
    if df.empty:
        raise RuntimeError(
            f"No {SYMBOL} minute bars in {start}..{end} under {data_root}"
        )
    df = (
        df.rename(columns={"datetime": "timestamp"})
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    if min_bars_per_day > 0:
        bpd = df.groupby(df["timestamp"].dt.date).size()
        healthy = set(bpd[bpd >= min_bars_per_day].index)
        before = len(df)
        df = df[df["timestamp"].dt.date.map(lambda d: d in healthy)].reset_index(
            drop=True
        )
        logger.info(
            "bar-density gate (>=%d/day): kept %d/%d bars, %d days",
            min_bars_per_day,
            len(df),
            before,
            df["timestamp"].dt.date.nunique(),
        )
    return df


# ---------------------------------------------------------------------------
# Entry collection + exit simulation
# ---------------------------------------------------------------------------


def collect_entries(df: pd.DataFrame, config: SetupDConfig) -> list[SimTrade]:
    """Replay df and collect real Setup D entries (exit_price filled later)."""
    spec = ContractSpec(
        name="kospi200_futures",
        multiplier_krw_per_point=FUTURES_POINT_VALUE,
        tick_size_points=0.05,
        tick_value_krw=2500,
        commission_rate=0.00015,
        symbol_prefix="A05",
    )
    replay = MarketContextReplay(
        df=df,
        symbol=SYMBOL,
        macro_snapshot=None,
        scheduled_events=[],
        contract_spec=spec,
        min_volume=0,
    )
    setup = SetupDVWAPReversion(config=config)

    ts_list = df["timestamp"].tolist()
    ts_to_idx = {pd.Timestamp(t): i for i, t in enumerate(ts_list)}

    out: list[SimTrade] = []
    last_exit_idx = -1  # one position at a time
    for ctx in replay.iter_contexts():
        ts_kst = pd.Timestamp(ctx.now)
        ts_naive = ts_kst.tz_localize(None) if ts_kst.tzinfo else ts_kst
        idx = ts_to_idx.get(ts_naive)
        if idx is None:
            continue

        # Always evaluate so the setup's causal rolling vol window stays
        # continuous (in live, check() runs every bar). When still in a prior
        # trade we evaluate-and-discard rather than skip.
        signal = setup.check(ctx)
        if idx <= last_exit_idx:
            continue  # still in a prior trade — single-position model
        if signal is None:
            continue

        side: Literal["BUY", "SELL"] = "BUY" if signal.direction == "long" else "SELL"
        trade = _simulate_exit(
            df,
            idx,
            ts_naive,
            signal.entry_price,
            side,
            signal.stop_loss,
            signal.take_profit,
        )
        out.append(trade)
        last_exit_idx = trade.bar_idx
    return out


def _simulate_exit(
    df: pd.DataFrame,
    entry_idx: int,
    entry_ts: pd.Timestamp,
    entry: float,
    side: Literal["BUY", "SELL"],
    stop: float,
    target: float,
) -> SimTrade:
    """Intrabar stop/target, else EOD/day-close. Stop checked before target
    (conservative when both touch within one bar)."""
    closes = df["close"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    ts_col = df["timestamp"]
    for i in range(entry_idx + 1, len(df)):
        t = ts_col.iloc[i]
        hi, lo = highs[i], lows[i]
        hold = (t - entry_ts).total_seconds() / 60.0
        if side == "BUY":
            if lo <= stop:
                return SimTrade(
                    i, entry_ts, entry, side, stop, "stop", stop - entry, hold
                )
            if hi >= target:
                return SimTrade(
                    i, entry_ts, entry, side, target, "target", target - entry, hold
                )
        else:
            if hi >= stop:
                return SimTrade(
                    i, entry_ts, entry, side, stop, "stop", entry - stop, hold
                )
            if lo <= target:
                return SimTrade(
                    i, entry_ts, entry, side, target, "target", entry - target, hold
                )
        if t.hour > EOD_HOUR or (t.hour == EOD_HOUR and t.minute >= EOD_MINUTE):
            px = closes[i]
            pnl = (px - entry) if side == "BUY" else (entry - px)
            return SimTrade(i, entry_ts, entry, side, px, "eod", pnl, hold)
        if i + 1 < len(df) and ts_col.iloc[i + 1].date() != t.date():
            px = closes[i]
            pnl = (px - entry) if side == "BUY" else (entry - px)
            return SimTrade(i, entry_ts, entry, side, px, "day_close", pnl, hold)
    px = closes[-1]
    pnl = (px - entry) if side == "BUY" else (entry - px)
    return SimTrade(
        len(df) - 1,
        entry_ts,
        entry,
        side,
        px,
        "end",
        pnl,
        (ts_col.iloc[-1] - entry_ts).total_seconds() / 60.0,
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def compute_metrics(trades: list[SimTrade]) -> dict:
    if not trades:
        return {
            "n_trades": 0,
            "long": 0,
            "short": 0,
            "win_rate": 0.0,
            "total_pts": 0.0,
            "total_krw": 0.0,
            "avg_pts": 0.0,
            "sharpe": 0.0,
            "mdd_krw": 0.0,
            "median_hold_min": 0.0,
            "exit_reasons": {},
        }
    pnls = np.array([t.pnl_pts for t in trades])
    holds = [t.hold_min for t in trades]
    wins = int((pnls > 0).sum())
    sharpe = (
        float(np.mean(pnls) / np.std(pnls, ddof=1) * np.sqrt(252))
        if len(pnls) >= 2 and np.std(pnls, ddof=1) > 0
        else 0.0
    )
    eq = [0.0]
    for t in trades:
        eq.append(eq[-1] + t.pnl_pts * FUTURES_POINT_VALUE)
    peak, mdd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v)
        mdd = max(mdd, peak - v)
    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
    return {
        "n_trades": len(trades),
        "long": sum(1 for t in trades if t.side == "BUY"),
        "short": sum(1 for t in trades if t.side == "SELL"),
        "win_rate": round(wins / len(trades) * 100, 1),
        "total_pts": round(float(pnls.sum()), 2),
        "total_krw": round(float(pnls.sum()) * FUTURES_POINT_VALUE),
        "avg_pts": round(float(pnls.mean()), 4),
        "sharpe": round(sharpe, 3),
        "mdd_krw": round(mdd),
        "median_hold_min": round(float(np.median(holds)), 1),
        "exit_reasons": reasons,
    }


def side_breakdown(trades: list[SimTrade]) -> dict:
    out = {}
    for side in ("BUY", "SELL"):
        g = [t for t in trades if t.side == side]
        m = compute_metrics(g)
        out[side] = {
            "n": m["n_trades"],
            "win_rate": m["win_rate"],
            "total_pts": m["total_pts"],
            "sharpe": m["sharpe"],
        }
    return out


def print_metrics(label: str, m: dict) -> None:
    print(f"\n{'='*62}\n  {label}\n{'='*62}")
    print(f"  Trades      : {m['n_trades']}  (L={m['long']} / S={m['short']})")
    print(f"  Win rate    : {m['win_rate']:.1f}%")
    print(f"  Total PnL   : {m['total_pts']:+.2f} pts  ({m['total_krw']:+,.0f} KRW)")
    print(f"  Avg / trade : {m['avg_pts']:+.4f} pts")
    print(f"  Sharpe      : {m['sharpe']:+.3f}")
    print(f"  MDD         : {m['mdd_krw']:,.0f} KRW")
    print(f"  Hold (med)  : {m['median_hold_min']:.1f} min")
    if m["exit_reasons"]:
        print("  Exit reasons:")
        for k, v in sorted(m["exit_reasons"].items(), key=lambda x: -x[1]):
            print(f"    {k:<12}: {v}")


# ---------------------------------------------------------------------------
# Walk-forward
# ---------------------------------------------------------------------------


def split_folds(
    df: pd.DataFrame, is_months: int, oos_months: int, step_months: int
) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    """Rolling calendar-month (is_start, is_end, oos_start, oos_end) windows."""
    start = df["timestamp"].min().normalize()
    end = df["timestamp"].max().normalize()
    folds = []
    win = start
    while win + pd.DateOffset(months=is_months + oos_months) <= end + pd.Timedelta(
        days=1
    ):
        is_start = win
        is_end = win + pd.DateOffset(months=is_months)
        oos_start = is_end
        oos_end = is_end + pd.DateOffset(months=oos_months)
        folds.append((is_start, is_end, oos_start, oos_end))
        win = win + pd.DateOffset(months=step_months)
    return folds


def split_folds_trading_days(
    df: pd.DataFrame, is_days: int, oos_days: int, step_days: int
) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    """Rolling trading-day folds (more folds on a short window than monthly).

    On an ~88-day clean window, calendar-month folds yield only ~2 folds, so a
    single month boundary cutting a volatility event dominates the verdict.
    Trading-day folds (e.g. 40-day IS / 10-day OOS, step 10) give several
    non-overlapping OOS blocks for a more stable read.
    """
    days = sorted(df["timestamp"].dt.date.unique())
    folds = []
    i = is_days
    while i + oos_days <= len(days):
        is_start = pd.Timestamp(days[i - is_days])
        is_end = pd.Timestamp(days[i - 1])
        oos_start = pd.Timestamp(days[i])
        oos_end = pd.Timestamp(days[min(i + oos_days - 1, len(days) - 1)])
        folds.append((is_start, is_end, oos_start, oos_end))
        i += step_days
    return folds


def main() -> None:
    p = argparse.ArgumentParser(description="Walk-forward — Setup D VWAP reversion")
    p.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    p.add_argument("--start", default="2025-12-01")
    p.add_argument("--end", default="2026-04-30")
    p.add_argument("--min-bars-per-day", type=int, default=330)
    p.add_argument("--is-months", type=int, default=2)
    p.add_argument("--oos-months", type=int, default=1)
    p.add_argument("--step-months", type=int, default=1)
    p.add_argument(
        "--fold-mode",
        choices=["monthly", "daily-stride"],
        default="daily-stride",
        help=(
            "monthly = calendar-month IS/OOS (coarse: ~2 folds on the 88-day "
            "window). daily-stride = trading-day folds (default; more folds, "
            "more stable read on a short window)."
        ),
    )
    p.add_argument("--is-days", type=int, default=40)
    p.add_argument("--oos-days", type=int, default=10)
    p.add_argument("--step-days", type=int, default=10)
    p.add_argument("--output", default=".superpowers/sdd/setup_d_walkforward.json")
    args = p.parse_args()

    start = pd.Timestamp(args.start).date()
    end = pd.Timestamp(args.end).date()
    df = load_clean(args.data_root, start, end, args.min_bars_per_day)
    logger.info(
        "Loaded %d bars | %s ~ %s | %d days",
        len(df),
        df["timestamp"].min().date(),
        df["timestamp"].max().date(),
        df["timestamp"].dt.date.nunique(),
    )

    config = SetupDConfig()
    print(f"\n{'#'*62}")
    print("  SETUP D — High-Vol Intraday VWAP Reversion — Walk-Forward")
    print(
        f"  Symbol: {SYMBOL}  Window: {df['timestamp'].min().date()} ~ "
        f"{df['timestamp'].max().date()} ({df['timestamp'].dt.date.nunique()} days)"
    )
    print(
        f"  Config: extreme={config.extreme_atr_mult} min_atr_ratio="
        f"{config.min_atr_ratio} stop={config.stop_atr_mult} "
        f"min_rr={config.min_reward_risk} window=[{config.valid_minutes_min},"
        f"{config.no_entry_after_minutes_since_open}]m stall={config.stall_buffer_atr_mult}"
    )
    print(f"{'#'*62}")

    # Full-window
    all_trades = collect_entries(df, config)
    full = compute_metrics(all_trades)
    print_metrics("FULL WINDOW (in+out of sample combined)", full)
    print(f"  Long/Short breakdown: {side_breakdown(all_trades)}")

    # Walk-forward folds
    if args.fold_mode == "monthly":
        folds = split_folds(df, args.is_months, args.oos_months, args.step_months)
        fold_desc = (
            f"IS={args.is_months}m / OOS={args.oos_months}m / "
            f"step={args.step_months}m"
        )
    else:
        folds = split_folds_trading_days(
            df, args.is_days, args.oos_days, args.step_days
        )
        fold_desc = (
            f"IS={args.is_days}d / OOS={args.oos_days}d / "
            f"step={args.step_days}d (trading days)"
        )
    print(f"\n{'#'*62}")
    print(f"  WALK-FORWARD: {len(folds)} folds ({fold_desc})")
    print("  Setup D has no fitted parameters — IS is reported for reference; the")
    print("  honest test is the concatenation of non-overlapping OOS folds.")
    print("  NOTE: on this ~88-day clean window, monthly folds are coarse (~2")
    print("  folds) and a single calendar cut through a volatility event")
    print("  dominates; daily-stride gives a more stable read (default).")
    print(f"{'#'*62}")

    # Single CONTINUOUS causal pass (``all_trades``) attributed to OOS folds by
    # entry timestamp. This keeps the setup's rolling vol window continuously
    # warmed across folds (matching live) instead of re-warming per fold, and
    # avoids per-fold position-model resets — a cleaner OOS read than slicing +
    # rebuilding a fresh replay per fold.
    fold_results: list[FoldResult] = []
    oos_all: list[SimTrade] = []
    print(
        f"\n{'fold':>4} {'oos_window':>22} {'n':>4} {'L':>3} {'S':>3} "
        f"{'win%':>5} {'tot_pts':>8} {'avg':>7} {'sharpe':>7} {'mdd_krw':>10}"
    )
    for fid, (is_s, is_e, oos_s, oos_e) in enumerate(folds):
        oos_trades = [t for t in all_trades if oos_s <= pd.Timestamp(t.ts) < oos_e]
        m = compute_metrics(oos_trades)
        oos_all.extend(oos_trades)
        fr = FoldResult(
            fold_id=fid,
            is_start=str(is_s.date()),
            is_end=str(is_e.date()),
            oos_start=str(oos_s.date()),
            oos_end=str(oos_e.date()),
            oos_trades=m["n_trades"],
            oos_long=m["long"],
            oos_short=m["short"],
            oos_win_rate=m["win_rate"],
            oos_total_pts=m["total_pts"],
            oos_avg_pts=m["avg_pts"],
            oos_sharpe=m["sharpe"],
            oos_mdd_krw=m["mdd_krw"],
        )
        fold_results.append(fr)
        win_lbl = f"{oos_s.date()}..{oos_e.date()}"
        print(
            f"{fid:>4} {win_lbl:>22} {m['n_trades']:>4} {m['long']:>3} {m['short']:>3} "
            f"{m['win_rate']:>5} {m['total_pts']:>8} {m['avg_pts']:>7} "
            f"{m['sharpe']:>7} {m['mdd_krw']:>10,.0f}"
        )

    oos_concat = compute_metrics(oos_all)
    print_metrics("OOS CONCATENATED (all walk-forward out-of-sample folds)", oos_concat)
    print(f"  Long/Short breakdown (OOS): {side_breakdown(oos_all)}")

    # Honest verdict
    n_pos_folds = sum(1 for f in fold_results if f.oos_total_pts > 0)
    n_folds_with_trades = sum(1 for f in fold_results if f.oos_trades > 0)
    print(f"\n{'='*62}\n  VERDICT\n{'='*62}")
    print(f"  Folds with trades        : {n_folds_with_trades}/{len(fold_results)}")
    print(f"  OOS-profitable folds      : {n_pos_folds}/{len(fold_results)}")
    print(f"  OOS concat Sharpe         : {oos_concat['sharpe']:+.3f}")
    print(f"  OOS concat total          : {oos_concat['total_pts']:+.2f} pts")
    sb = side_breakdown(oos_all)
    sym_ok = sb["BUY"]["total_pts"] > 0 and sb["SELL"]["total_pts"] > 0
    print(
        f"  Symmetry (both sides +)   : {sym_ok}  "
        f"(L={sb['BUY']['total_pts']:+.1f} / S={sb['SELL']['total_pts']:+.1f})"
    )

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = PROJECT_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "symbol": SYMBOL,
                "data_window": [
                    str(df["timestamp"].min().date()),
                    str(df["timestamp"].max().date()),
                ],
                "fold_mode": args.fold_mode,
                "config": config.model_dump(),
                "full_window": full,
                "full_side_breakdown": side_breakdown(all_trades),
                "oos_concatenated": oos_concat,
                "oos_side_breakdown": sb,
                "folds": [asdict(f) for f in fold_results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nJSON summary written to: {out_path}")


if __name__ == "__main__":
    main()
