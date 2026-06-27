"""Head-to-head: TrackAExit vs setup_target_exit for futures Setup A/C (READ-ONLY).

Settles the contested exit decision (#495/#496 revert vs the 2026-06-22 base-rate
report) on the TRUSTED clean futures-minute window (Dec-2025 → Apr-2026).

Reuses the LookaheadGuard-safe machinery from ``backtest_macro_setup_ac.py``:
  - ``build_sp500_daily_snapshots`` (KR date T ← US close T-1, no look-ahead)
  - real ``SetupAGapReversion.check`` / ``SetupCEventReaction.check``
  - ``simulate_track_a_exit`` / ``simulate_setup_target_exit`` (bar-close fills)
  - ``compute_metrics``
and the window loader (bar-density gate) from ``_baserate_setup_ac.py``.

NEW vs the base-rate harness:
  1. NET metrics: applies a configurable round-trip cost (default 0.044%/trade,
     = 1 tick/side @ ~700 idx + 1.5 bp commission/side) to the GROSS pnl_pct of
     EVERY trade, then recomputes the full metric block. Reports GROSS + NET.
  2. Per-exit per-trade book (entry/exit/reason/hold/pnl) for both arms.
  3. Fast-stop-out rate (% of trades exiting via stop/catastrophic/crash in
     <= fast_minutes, default 10 min).
  4. Three reconciliation scenarios so the #495 vs base-rate conflict is settled
     without re-running just one configuration:
       S1. DEPLOYED entry config (B+60min) on FULL clean window  [the live config]
       S2. #495 LOOSE entry config (vmax=120, retrace 0.2-0.7, stop 1.5) on the
           SAME clean window, with #495's train/holdout split, HOLDOUT only
           [replicates the exact arm that justified the revert]
       S3. #495 LOOSE entry config on the FULL clean window (no split)
           [isolates "config" effect from "holdout-subset" effect]

No config or strategy code is mutated; configs are constructed in-process.

Usage
-----
    .venv/bin/python scripts/analysis/_headtohead_trackaexit_vs_fixedstop.py \
        --start 2025-12-01 --end 2026-04-30 --min-bars-per-day 330 \
        --min-volume 30 --roundtrip-cost-pct 0.044 \
        --output reports/_headtohead_trackaexit_vs_fixedstop.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import scripts.analysis.backtest_macro_setup_ac as B
from scripts.analysis._baserate_setup_ac import build_replay, load_window
from shared.decision.context import load_scheduled_events
from shared.decision.setups.event_reaction import SetupCConfig
from shared.decision.setups.gap_reversion import SetupAConfig

FUTURES_POINT_VALUE = B.FUTURES_POINT_VALUE


# ---------------------------------------------------------------------------
# NET-cost metric recompute
# ---------------------------------------------------------------------------

def _net_trade(t: B.SimTrade, roundtrip_cost_pct: float) -> B.SimTrade:
    """Return a copy of the trade with the round-trip cost subtracted.

    The cost is applied to pnl_pct (a % return) and proportionally to pnl_pts
    (entry_price * cost%/100). This models commission + 1-tick slippage each
    side as a flat ``roundtrip_cost_pct`` haircut per round trip.
    """
    cost_pts = t.entry_price * roundtrip_cost_pct / 100.0
    new_pts = t.pnl_pts - cost_pts
    return replace(
        t,
        pnl_pts=new_pts,
        pnl_pct=t.pnl_pct - roundtrip_cost_pct,
    )


def metrics_block(
    trades: list[B.SimTrade], roundtrip_cost_pct: float, fast_minutes: float = 10.0
) -> dict:
    """Compute GROSS + NET metrics + fast-stopout rate for a trade list."""
    gross = B.compute_metrics(trades)
    net_trades = [_net_trade(t, roundtrip_cost_pct) for t in trades]
    net = B.compute_metrics(net_trades)

    # fast-stopout: stop/catastrophic/crash within fast_minutes
    stop_like = {"stop_loss", "catastrophic_stop", "crash_guard"}
    fast = [
        t for t in trades
        if t.exit_reason in stop_like and t.holding_minutes <= fast_minutes
    ]
    fast_rate = round(len(fast) / len(trades) * 100, 1) if trades else 0.0

    return {
        "gross": gross,
        "net": net,
        "fast_stopout_rate_pct": fast_rate,
        "fast_stopout_n": len(fast),
        "roundtrip_cost_pct": roundtrip_cost_pct,
    }


def trade_book(trades: list[B.SimTrade], roundtrip_cost_pct: float) -> list[dict]:
    rows = []
    for t in trades:
        rows.append({
            "entry_time": str(t.entry_time),
            "side": t.side,
            "exit_reason": t.exit_reason,
            "gross_pnl_pct": round(t.pnl_pct, 4),
            "net_pnl_pct": round(t.pnl_pct - roundtrip_cost_pct, 4),
            "hold_min": round(t.holding_minutes, 1),
            "sp500_pct": (
                round(t.sp500_change_pct, 3) if t.sp500_change_pct is not None else None
            ),
        })
    return rows


# ---------------------------------------------------------------------------
# Entry collection + both-exit simulation for a given config + df
# ---------------------------------------------------------------------------

def collect_and_simulate_a(
    df: pd.DataFrame, macro, events, cfg: SetupAConfig, min_volume: int
) -> tuple[list[B.SimTrade], list[B.SimTrade], int]:
    """Return (track_a_trades, target_trades, n_entries) for Setup A."""
    replay = build_replay(df, macro, events, min_volume)
    entries = B.collect_real_setup_a_entries(replay, cfg, replay.df)
    track, target = [], []
    for e in entries:
        t1 = B.simulate_track_a_exit(replay.df, e)
        if t1:
            track.append(t1)
        t2 = B.simulate_setup_target_exit(replay.df, e)
        if t2:
            target.append(t2)
    return track, target, len(entries)


def collect_and_simulate_c(
    df: pd.DataFrame, macro, events, cfg: SetupCConfig, min_volume: int
) -> tuple[list[B.SimTrade], list[B.SimTrade], int]:
    replay = build_replay(df, macro, events, min_volume)
    entries = B.collect_real_setup_c_entries(replay, cfg, replay.df)
    track, target = [], []
    for e in entries:
        t1 = B.simulate_track_a_exit(replay.df, e)
        if t1:
            track.append(t1)
        t2 = B.simulate_setup_target_exit(replay.df, e)
        if t2:
            target.append(t2)
    return track, target, len(entries)


# ---------------------------------------------------------------------------
# Config constructors
# ---------------------------------------------------------------------------

def deployed_setup_a_cfg() -> SetupAConfig:
    """B+60min — the config currently in setup_a_gap_reversion.yaml."""
    return SetupAConfig(
        valid_minutes_min=10, valid_minutes_max=60,
        min_sp500_gap_pct=0.30, min_kr_gap_pct=0.30,
        retrace_min=0.30, retrace_max=0.55, stop_atr_mult=3.5,
    )


def loose_495_setup_a_cfg() -> SetupAConfig:
    """The LOOSE config the #495 clean-window exit comparison actually used
    (from .superpowers/sdd/bt-data-unblock-report-macro-clean.json::setup_a_config).
    """
    return SetupAConfig(
        valid_minutes_min=10, valid_minutes_max=120,
        min_sp500_gap_pct=0.30, min_kr_gap_pct=0.20,
        retrace_min=0.20, retrace_max=0.70, stop_atr_mult=1.5,
    )


def _print_arm(label: str, mb: dict) -> None:
    g, n = mb["gross"], mb["net"]
    print(f"  {label}")
    print(f"    N={g['n_trades']:2d} | GROSS avg={g['avg_return_pct']:+.4f}% "
          f"sharpe={g['sharpe']:+.2f} win={g['win_rate']:.0f}% mdd={g['mdd_pct']:.2f}% "
          f"pnl={g['total_pnl_pts']:+.1f}pt hold(med)={g['median_hold_min']:.0f}m")
    print(f"          | NET   avg={n['avg_return_pct']:+.4f}% "
          f"sharpe={n['sharpe']:+.2f} win={n['win_rate']:.0f}% mdd={n['mdd_pct']:.2f}% "
          f"pnl={n['total_pnl_pts']:+.1f}pt fast_stopout={mb['fast_stopout_rate_pct']:.0f}%")
    print(f"          | exits: {g.get('exit_reasons', {})}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/kospi200f_1m_ch_101S6000.csv")
    ap.add_argument("--start", default="2025-12-01")
    ap.add_argument("--end", default="2026-04-30")
    ap.add_argument("--min-volume", type=int, default=30)
    ap.add_argument("--min-bars-per-day", type=int, default=330)
    ap.add_argument("--roundtrip-cost-pct", type=float, default=0.044)
    ap.add_argument("--fast-minutes", type=float, default=10.0)
    ap.add_argument("--holdout-split", default="2026-02-01",
                    help="#495 replication split date")
    ap.add_argument("--output", default="reports/_headtohead_trackaexit_vs_fixedstop.json")
    args = ap.parse_args()

    data_path = Path(args.data)
    if not data_path.is_absolute():
        data_path = PROJECT_ROOT / data_path

    cost = args.roundtrip_cost_pct
    fastm = args.fast_minutes

    df = load_window(data_path, args.start, args.end, args.min_bars_per_day)
    days = sorted(df["timestamp"].dt.date.unique())
    print(f"FULL clean window after gates: {days[0]}..{days[-1]} | "
          f"{len(days)} days | {len(df)} bars", file=sys.stderr)

    events = load_scheduled_events(str(PROJECT_ROOT / "config/scheduled_events.yaml"))
    macro = B.build_sp500_daily_snapshots(
        df["timestamp"].min().date(), df["timestamp"].max().date()
    )

    deployed_cfg = deployed_setup_a_cfg()
    loose_cfg = loose_495_setup_a_cfg()

    out: dict = {
        "window": {"start": str(days[0]), "end": str(days[-1]),
                   "n_days": len(days), "n_bars": len(df)},
        "min_volume": args.min_volume,
        "min_bars_per_day": args.min_bars_per_day,
        "roundtrip_cost_pct": cost,
        "fast_minutes": fastm,
        "track_a_params": {
            "trail_atr_mult": B.TRAIL_ATR_MULT_TUNED,
            "trail_activate_atr_mult": B.TRAIL_ACTIVATE_ATR_MULT_TUNED,
            "crash_atr_mult": B.CRASH_ATR_MULT,
            "catastrophic_atr_mult": B.CATASTROPHIC_ATR_MULT,
        },
        "scenarios": {},
    }

    # ========== S1: DEPLOYED config, FULL clean window (the live config) =====
    print("\n" + "=" * 78)
    print("S1: DEPLOYED Setup A config (B+60min) — FULL clean window  [the LIVE config]")
    print("=" * 78)
    tr_a, tg_a, n_a = collect_and_simulate_a(df, macro, events, deployed_cfg, args.min_volume)
    s1_track = metrics_block(tr_a, cost, fastm)
    s1_target = metrics_block(tg_a, cost, fastm)
    print(f"  Setup A entries: {n_a}")
    _print_arm("TrackAExit       :", s1_track)
    _print_arm("setup_target_exit:", s1_target)

    # Setup C on deployed defaults
    tr_c, tg_c, n_c = collect_and_simulate_c(df, macro, events, SetupCConfig(), args.min_volume)
    s1c_track = metrics_block(tr_c, cost, fastm)
    s1c_target = metrics_block(tg_c, cost, fastm)
    print(f"\n  Setup C entries: {n_c}")
    _print_arm("TrackAExit       :", s1c_track)
    _print_arm("setup_target_exit:", s1c_target)

    out["scenarios"]["S1_deployed_full"] = {
        "setup_a_config": vars(deployed_cfg),
        "setup_a": {
            "n_entries": n_a,
            "track_a": s1_track, "setup_target_exit": s1_target,
            "track_a_book": trade_book(tr_a, cost),
            "target_book": trade_book(tg_a, cost),
        },
        "setup_c": {
            "n_entries": n_c,
            "track_a": s1c_track, "setup_target_exit": s1c_target,
            "track_a_book": trade_book(tr_c, cost),
            "target_book": trade_book(tg_c, cost),
        },
    }

    # ========== S2: #495 LOOSE config + its train/holdout split, HOLDOUT only
    print("\n" + "=" * 78)
    print(f"S2: #495 LOOSE config (vmax=120 retrace0.2-0.7 stop1.5) — HOLDOUT only "
          f"(split {args.holdout_split})  [replicates the #495 revert arm]")
    print("=" * 78)
    split = pd.Timestamp(args.holdout_split).date()
    df_holdout = df[df["timestamp"].dt.date >= split].copy().reset_index(drop=True)
    hdays = sorted(df_holdout["timestamp"].dt.date.unique())
    print(f"  Holdout: {hdays[0]}..{hdays[-1]} | {len(hdays)} days", file=sys.stderr)
    tr_h, tg_h, n_h = collect_and_simulate_a(df_holdout, macro, events, loose_cfg, args.min_volume)
    s2_track = metrics_block(tr_h, cost, fastm)
    s2_target = metrics_block(tg_h, cost, fastm)
    print(f"  Setup A entries (holdout): {n_h}")
    _print_arm("TrackAExit       :", s2_track)
    _print_arm("setup_target_exit:", s2_target)
    out["scenarios"]["S2_loose495_holdout"] = {
        "setup_a_config": vars(loose_cfg),
        "holdout_split": str(split),
        "holdout_days": len(hdays),
        "setup_a": {
            "n_entries": n_h,
            "track_a": s2_track, "setup_target_exit": s2_target,
            "track_a_book": trade_book(tr_h, cost),
            "target_book": trade_book(tg_h, cost),
        },
    }

    # ========== S3: #495 LOOSE config, FULL clean window (no split) ==========
    print("\n" + "=" * 78)
    print("S3: #495 LOOSE config — FULL clean window (no split)  "
          "[isolates config effect from holdout-subset effect]")
    print("=" * 78)
    tr_l, tg_l, n_l = collect_and_simulate_a(df, macro, events, loose_cfg, args.min_volume)
    s3_track = metrics_block(tr_l, cost, fastm)
    s3_target = metrics_block(tg_l, cost, fastm)
    print(f"  Setup A entries: {n_l}")
    _print_arm("TrackAExit       :", s3_track)
    _print_arm("setup_target_exit:", s3_target)
    out["scenarios"]["S3_loose495_full"] = {
        "setup_a_config": vars(loose_cfg),
        "setup_a": {
            "n_entries": n_l,
            "track_a": s3_track, "setup_target_exit": s3_target,
            "track_a_book": trade_book(tr_l, cost),
            "target_book": trade_book(tg_l, cost),
        },
    }

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = PROJECT_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str),
                        encoding="utf-8")
    print(f"\nJSON: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
