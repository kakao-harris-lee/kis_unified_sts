"""Base-rate + gate-sensitivity harness for Setup A / Setup C (READ-ONLY analysis).

Reuses the LookaheadGuard-safe machinery from backtest_macro_setup_ac.py
(MarketContextReplay, real SetupAGapReversion.check, real SetupCEventReaction,
the TrackA / SetupTarget exit simulators, compute_metrics). Adds:

  1. Per-day QUALIFYING base-rate counting for Setup A (in-window + aligned gap
     >= threshold + retrace band) with reject-reason histogram, and Setup C
     event-day qualifying count.
  2. Gate sweep: valid_minutes_max x sp500/kr gap thresholds -> trade count +
     edge (avg ret, Sharpe, win rate, MDD) for each config, on the trusted
     window.

No config or strategy code is mutated; configs are constructed in-process.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import scripts.analysis.backtest_macro_setup_ac as B
from shared.backtest.market_context_replay import MarketContextReplay
from shared.decision.context import load_scheduled_events
from shared.decision.setups.event_reaction import SetupCConfig, SetupCEventReaction
from shared.decision.setups.gap_reversion import SetupAConfig, SetupAGapReversion
from shared.execution.contract_spec import ContractSpec

FUTURES_POINT_VALUE = B.FUTURES_POINT_VALUE


def _contract_spec() -> ContractSpec:
    return ContractSpec(
        name="kospi200_futures",
        multiplier_krw_per_point=FUTURES_POINT_VALUE,
        tick_size_points=0.05,
        tick_value_krw=2500,
        commission_rate=0.00015,
        symbol_prefix="A05",
    )


def load_window(data_path: Path, start: str, end: str, min_bars_per_day: int) -> pd.DataFrame:
    df = pd.read_csv(data_path, parse_dates=["datetime"]).sort_values("datetime")
    df = df.rename(columns={"datetime": "timestamp"}).reset_index(drop=True)
    mask = (df["timestamp"].dt.date >= pd.Timestamp(start).date()) & (
        df["timestamp"].dt.date <= pd.Timestamp(end).date()
    )
    df = df[mask].reset_index(drop=True)
    if min_bars_per_day > 0:
        bpd = df.groupby(df["timestamp"].dt.date).size()
        healthy = set(bpd[bpd >= min_bars_per_day].index)
        df = df[df["timestamp"].dt.date.map(lambda d: d in healthy)].reset_index(drop=True)
    # ATR for exits
    high, low, prev_close = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(span=14, min_periods=1, adjust=False).mean()
    return df


def build_replay(df: pd.DataFrame, macro, events, min_volume: int) -> MarketContextReplay:
    def macro_provider(kr_date: date):
        return macro.get(kr_date)

    return MarketContextReplay(
        df=df,
        symbol="101S6000",
        macro_snapshot=None,
        scheduled_events=events,
        contract_spec=_contract_spec(),
        macro_provider=macro_provider,
        min_volume=min_volume,
    )


def base_rate_setup_a(replay: MarketContextReplay, cfg: SetupAConfig) -> dict:
    """Count days with a QUALIFYING Setup A signal + reject-reason histogram.

    The setup fires at most once/day (live behavior). We record, per day, the
    first qualifying signal AND the dominant reject reason on days that never
    qualified (categorized at its furthest gate progression).
    """
    setup = SetupAGapReversion(config=cfg)
    qualifying_days: set[date] = set()
    all_days: set[date] = set()
    # furthest gate reached per day (to attribute "why no trade")
    reject_first: dict[date, str] = {}
    last_entry_day: date | None = None
    for ctx in replay.iter_contexts():
        d = ctx.now.date()
        all_days.add(d)
        if d in qualifying_days:
            continue
        if d == last_entry_day:
            continue
        sig = setup.check(ctx)
        if sig is not None:
            qualifying_days.add(d)
            last_entry_day = d
        else:
            # keep the LEAST-restrictive (furthest) reason seen that day:
            # we approximate by recording the reason category; later gates win.
            r = setup.last_reject_reason or "unknown"
            cat = r.split("(")[0]
            order = {
                "outside_time_window": 0,
                "no_macro_overnight": 1,
                "no_sp500_data": 1,
                "sp500_gap_below_min": 2,
                "no_prev_close": 3,
                "kr_gap_below_min": 3,
                "sp500_kr_gap_misaligned": 4,
                "no_gap_up_magnitude": 5,
                "no_gap_down_magnitude": 5,
                "retrace_out_of_band": 6,
            }
            prev = reject_first.get(d)
            if prev is None or order.get(cat, -1) > order.get(prev, -1):
                reject_first[d] = cat
    reject_hist = Counter(reject_first[d] for d in reject_first if d not in qualifying_days)
    return {
        "total_days": len(all_days),
        "qualifying_days": len(qualifying_days),
        "qualifying_date_list": sorted(str(x) for x in qualifying_days),
        "reject_furthest_gate": dict(reject_hist),
    }


def base_rate_setup_c(replay: MarketContextReplay, cfg: SetupCConfig) -> dict:
    setup = SetupCEventReaction(config=cfg)
    sigs = 0
    sig_days: set[date] = set()
    for ctx in replay.iter_contexts():
        s = setup.check(ctx)
        if s is not None:
            sigs += 1
            sig_days.add(ctx.now.date())
    return {"n_signals": sigs, "event_trade_days": sorted(str(x) for x in sig_days)}


def count_eligible_events(events, df: pd.DataFrame, cfg: SetupCConfig) -> dict:
    """How many tier<=min_impact_tier events fall on a trading day in-session?"""
    from zoneinfo import ZoneInfo

    KST = ZoneInfo("Asia/Seoul")
    trading_days = set(df["timestamp"].dt.date.unique())
    elig = 0
    in_session = 0
    on_trading_day = 0
    for e in events:
        if e.impact_tier > cfg.min_impact_tier:
            continue
        elig += 1
        kst = e.scheduled_at.astimezone(KST)
        if kst.date() in trading_days:
            on_trading_day += 1
            # in regular session 09:00-15:45 KST?
            mins = kst.hour * 60 + kst.minute
            if 9 * 60 <= mins <= 15 * 60 + 45:
                in_session += 1
    return {
        "tier_le_min_total": elig,
        "on_trading_day": on_trading_day,
        "in_session": in_session,
    }


def run_setup_a_config(df, macro, events, cfg, min_volume) -> dict:
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
    return {
        "n_entries": len(entries),
        "track_a": B.compute_metrics(track),
        "target_exit": B.compute_metrics(target),
        "entry_dates": sorted(str(pd.Timestamp(e.entry_price and replay.df.iloc[e.bar_idx]["timestamp"]).date()) for e in entries),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/kospi200f_1m_ch_101S6000.csv")
    ap.add_argument("--start", default="2025-10-01")
    ap.add_argument("--end", default="2026-04-30")
    ap.add_argument("--min-volume", type=int, default=30)
    ap.add_argument("--min-bars-per-day", type=int, default=330)
    ap.add_argument("--output", default="reports/_baserate_setup_ac.json")
    args = ap.parse_args()

    data_path = Path(args.data)
    if not data_path.is_absolute():
        data_path = PROJECT_ROOT / data_path

    df = load_window(data_path, args.start, args.end, args.min_bars_per_day)
    days = sorted(df["timestamp"].dt.date.unique())
    print(f"Window after gates: {days[0]}..{days[-1]} | {len(days)} days | {len(df)} bars", file=sys.stderr)

    events = load_scheduled_events(str(PROJECT_ROOT / "config/scheduled_events.yaml"))
    macro = B.build_sp500_daily_snapshots(df["timestamp"].min().date(), df["timestamp"].max().date())

    # ---- base rate at DEPLOYED paper config (setup_a_gap_reversion.yaml) ----
    deployed_cfg = SetupAConfig(
        valid_minutes_min=10, valid_minutes_max=60,
        min_sp500_gap_pct=0.30, min_kr_gap_pct=0.30,
        retrace_min=0.30, retrace_max=0.55, stop_atr_mult=3.5,
    )
    repl = build_replay(df, macro, events, args.min_volume)
    base_a = base_rate_setup_a(repl, deployed_cfg)

    setup_c_cfg = SetupCConfig()
    repl_c = build_replay(df, macro, events, args.min_volume)
    base_c = base_rate_setup_c(repl_c, setup_c_cfg)
    elig_c = count_eligible_events(events, df, setup_c_cfg)

    print("\n===== SETUP A BASE RATE (deployed: B+60min, 0.30/0.30 gaps, retrace 0.30-0.55) =====")
    print(json.dumps(base_a, indent=2, ensure_ascii=False))
    print("\n===== SETUP C BASE RATE (deployed defaults) =====")
    print(json.dumps(base_c, indent=2, ensure_ascii=False))
    print("\n===== SETUP C EVENT ELIGIBILITY =====")
    print(json.dumps(elig_c, indent=2, ensure_ascii=False))

    # ---- gate sweep ----
    print("\n===== SETUP A GATE SWEEP =====")
    sweep = []
    for vmax in (60, 90, 120):
        for gap in (0.20, 0.30, 0.40):
            cfg = SetupAConfig(
                valid_minutes_min=10, valid_minutes_max=vmax,
                min_sp500_gap_pct=gap, min_kr_gap_pct=gap,
                retrace_min=0.30, retrace_max=0.55, stop_atr_mult=3.5,
            )
            res = run_setup_a_config(df, macro, events, cfg, args.min_volume)
            row = {
                "valid_minutes_max": vmax,
                "gap_threshold": gap,
                "n_entries": res["n_entries"],
                "target_exit": res["target_exit"],
                "track_a": res["track_a"],
                "entry_dates": res["entry_dates"],
            }
            sweep.append(row)
            te = res["target_exit"]
            print(
                f"  vmax={vmax:3d} gap={gap:.2f} | N={res['n_entries']:2d} "
                f"| TARGET: avg={te['avg_return_pct']:+.3f}% sharpe={te['sharpe']:+.2f} "
                f"win={te['win_rate']:.0f}% mdd={te['mdd_pct']:.2f}% pnl={te['total_pnl_pts']:+.1f}pt"
            )

    out = {
        "window": {"start": str(days[0]), "end": str(days[-1]), "n_days": len(days), "n_bars": len(df)},
        "min_volume": args.min_volume,
        "min_bars_per_day": args.min_bars_per_day,
        "base_rate_setup_a_deployed": base_a,
        "base_rate_setup_c": base_c,
        "setup_c_event_eligibility": elig_c,
        "gate_sweep": sweep,
    }
    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = PROJECT_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nJSON: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
