"""Entry-selectivity A/B/C matrix backtest for Setup A.

Holds exit = setup_target_exit constant. Varies only entry thresholds.
Also probes Priority 2 (min_gap_atr_ratio) and Priority 3 (valid_minutes_max=60)
as add-ons to the winning arm.

Clean window: Nov 2025 – Apr 2026 (density-gated, >=330 bars/day).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.analysis.backtest_macro_setup_ac import (
    SimTrade,
    build_sp500_daily_snapshots,
    collect_real_setup_a_entries,
    compute_metrics,
    simulate_setup_target_exit,
)
from shared.backtest.market_context_replay import MarketContextReplay
from shared.decision.setups.gap_reversion import SetupAConfig
from shared.execution.contract_spec import ContractSpec
from shared.macro.base import MacroSnapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

FUTURES_POINT_VALUE = 50_000

# Clean window: Nov 2025 – Apr 2026 (density-gated data is reliable here)
CLEAN_WINDOW_START = date(2025, 11, 1)
CLEAN_WINDOW_END = date(2026, 4, 30)
MIN_BARS_PER_DAY = 330
MIN_VOLUME = 30


def load_and_filter_data(data_path: Path) -> pd.DataFrame:
    """Load CSV, apply density gate, restrict to clean window."""
    logger.info("Loading data: %s", data_path)
    df = pd.read_csv(data_path, parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df = df.rename(columns={"datetime": "timestamp"})

    # Density gate: drop days with <330 bars
    bars_per_day = df.groupby(df["timestamp"].dt.date).size()
    healthy_days = set(bars_per_day[bars_per_day >= MIN_BARS_PER_DAY].index)
    df = df[df["timestamp"].dt.date.map(lambda d: d in healthy_days)].reset_index(drop=True)

    # Restrict to clean window
    df = df[
        (df["timestamp"].dt.date >= CLEAN_WINDOW_START)
        & (df["timestamp"].dt.date <= CLEAN_WINDOW_END)
    ].reset_index(drop=True)

    if df.empty:
        logger.error("No data after density gate + clean window filter.")
        sys.exit(1)

    logger.info(
        "Clean window data: %d bars, %d days (%s ~ %s)",
        len(df),
        df["timestamp"].dt.date.nunique(),
        df["timestamp"].min().date(),
        df["timestamp"].max().date(),
    )

    # Compute ATR
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    df["atr"] = tr.ewm(span=14, min_periods=1, adjust=False).mean()

    return df


def run_arm(
    df: pd.DataFrame,
    macro_snapshots: dict[date, MacroSnapshot],
    label: str,
    min_sp500_gap_pct: float,
    min_kr_gap_pct: float,
    retrace_min: float,
    retrace_max: float,
    valid_minutes_max: int = 120,
    min_gap_atr_ratio: float = 0.0,
) -> dict:
    """Run one matrix arm with setup_target_exit as the exit arm."""
    config = SetupAConfig(
        min_sp500_gap_pct=min_sp500_gap_pct,
        min_kr_gap_pct=min_kr_gap_pct,
        retrace_min=retrace_min,
        retrace_max=retrace_max,
        valid_minutes_min=10,
        valid_minutes_max=valid_minutes_max,
        stop_atr_mult=3.5,
        target_gap_fill_ratio=0.9,
    )

    contract_spec = ContractSpec(
        name="kospi200_futures",
        multiplier_krw_per_point=FUTURES_POINT_VALUE,
        tick_size_points=0.05,
        tick_value_krw=2500,
        commission_rate=0.00015,
        symbol_prefix="A05",
    )

    def macro_provider(kr_date: date) -> MacroSnapshot | None:
        return macro_snapshots.get(kr_date)

    replay = MarketContextReplay(
        df=df.copy(),
        symbol="101S6000",
        macro_snapshot=None,
        scheduled_events=[],
        contract_spec=contract_spec,
        macro_provider=macro_provider,
        min_volume=MIN_VOLUME,
    )

    entries = collect_real_setup_a_entries(replay, config, df)

    # Apply gap/ATR ratio filter post-hoc (no code changes needed)
    if min_gap_atr_ratio > 0.0:
        filtered = []
        for e in entries:
            row = df.iloc[e.bar_idx]
            # gap magnitude as fraction of open
            if e.kr_gap_pct is not None and e.atr > 0:
                gap_pts = abs(e.kr_gap_pct / 100.0) * float(row["open"]) if hasattr(row, "open") else abs(e.kr_gap_pct / 100.0) * e.entry_price
                ratio = gap_pts / e.atr
                if ratio >= min_gap_atr_ratio:
                    filtered.append(e)
            else:
                filtered.append(e)
        entries = filtered

    trades: list[SimTrade] = []
    for entry in entries:
        t = simulate_setup_target_exit(df, entry)
        if t is not None:
            trades.append(t)

    m = compute_metrics(trades)

    # Primary metric
    score = m["win_rate"] * m["avg_return_pct"] if m["n_trades"] > 0 else 0.0
    avg_pnl = m["avg_return_pct"]
    median_pnl = float(np.median([t.pnl_pct for t in trades])) if trades else 0.0

    # Holding time
    hold_times = [t.holding_minutes for t in trades]
    median_hold = float(np.median(hold_times)) if hold_times else 0.0

    result = {
        "label": label,
        "params": {
            "min_sp500_gap_pct": min_sp500_gap_pct,
            "min_kr_gap_pct": min_kr_gap_pct,
            "retrace_min": retrace_min,
            "retrace_max": retrace_max,
            "valid_minutes_max": valid_minutes_max,
            "min_gap_atr_ratio": min_gap_atr_ratio,
        },
        "n_trades": m["n_trades"],
        "win_rate": m["win_rate"],
        "avg_pnl_pct": round(avg_pnl, 4),
        "median_pnl_pct": round(median_pnl, 4),
        "score_wr_x_avg_pnl": round(score, 4),
        "total_pnl_pts": m["total_pnl_pts"],
        "sharpe": m["sharpe"],
        "mdd_pct": m["mdd_pct"],
        "median_hold_min": round(median_hold, 1),
        "exit_reasons": m["exit_reasons"],
    }

    return result


def print_results(results: list[dict]) -> None:
    print("\n" + "=" * 95)
    print(f"  ENTRY SELECTIVITY MATRIX — exit=setup_target_exit, clean window {CLEAN_WINDOW_START}~{CLEAN_WINDOW_END}")
    print("=" * 95)
    hdr = f"{'Arm':<30} {'N':>4} {'WR%':>6} {'AvgPnL%':>8} {'MedPnL%':>8} {'WR*AvgP':>8} {'Sharpe':>7} {'MDD%':>6} {'MedHold':>8}"
    print(hdr)
    print("-" * 95)
    for r in results:
        row = (
            f"{r['label']:<30} "
            f"{r['n_trades']:>4} "
            f"{r['win_rate']:>6.1f} "
            f"{r['avg_pnl_pct']:>+8.4f} "
            f"{r['median_pnl_pct']:>+8.4f} "
            f"{r['score_wr_x_avg_pnl']:>+8.4f} "
            f"{r['sharpe']:>+7.3f} "
            f"{r['mdd_pct']:>6.2f} "
            f"{r['median_hold_min']:>8.1f}"
        )
        print(row)
    print("=" * 95)

    # Highlight winner by score
    scored = [r for r in results if r["n_trades"] >= 5]
    if scored:
        best = max(scored, key=lambda r: r["score_wr_x_avg_pnl"])
        print(f"\n  Best by WR*AvgPnL (N>=5): {best['label']}")
    print()

    # Per-arm exit breakdown
    for r in results:
        if r["n_trades"] > 0:
            print(f"  {r['label']} exit reasons: {r['exit_reasons']}")
    print()


def main() -> None:
    data_path = PROJECT_ROOT / "data" / "kospi200f_1m_ch_101S6000.csv"
    if not data_path.exists():
        print(f"ERROR: Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    df = load_and_filter_data(data_path)
    start_date = df["timestamp"].min().date()
    end_date = df["timestamp"].max().date()
    macro_snapshots = build_sp500_daily_snapshots(start_date, end_date)

    # ── Matrix arms ─────────────────────────────────────────────────────────
    base_kwargs = {"df": df, "macro_snapshots": macro_snapshots}

    results = []

    # Arm A: current/loose
    results.append(run_arm(
        label="A (current sp500>=0.15 kr>=0.20 r[0.20,0.70])",
        min_sp500_gap_pct=0.15, min_kr_gap_pct=0.20,
        retrace_min=0.20, retrace_max=0.70,
        **base_kwargs,
    ))

    # Arm B: restored
    results.append(run_arm(
        label="B (restored sp500>=0.30 kr>=0.30 r[0.30,0.55])",
        min_sp500_gap_pct=0.30, min_kr_gap_pct=0.30,
        retrace_min=0.30, retrace_max=0.55,
        **base_kwargs,
    ))

    # Arm C: aggressive
    results.append(run_arm(
        label="C (aggr sp500>=0.50 kr>=0.30 r[0.30,0.55])",
        min_sp500_gap_pct=0.50, min_kr_gap_pct=0.30,
        retrace_min=0.30, retrace_max=0.55,
        **base_kwargs,
    ))

    # ── Add-on probes on best arm (determine after printing base results) ────
    # Priority 2: min_gap_atr_ratio on best base arm
    # Priority 3: valid_minutes_max=60 on best base arm

    # Run all add-ons on B and C (likely best arms by hypothesis)
    results.append(run_arm(
        label="B+ATR2.0 (B + gap/atr>=2.0)",
        min_sp500_gap_pct=0.30, min_kr_gap_pct=0.30,
        retrace_min=0.30, retrace_max=0.55,
        min_gap_atr_ratio=2.0,
        **base_kwargs,
    ))

    results.append(run_arm(
        label="B+ATR2.5 (B + gap/atr>=2.5)",
        min_sp500_gap_pct=0.30, min_kr_gap_pct=0.30,
        retrace_min=0.30, retrace_max=0.55,
        min_gap_atr_ratio=2.5,
        **base_kwargs,
    ))

    results.append(run_arm(
        label="B+60min (B + window<=60min)",
        min_sp500_gap_pct=0.30, min_kr_gap_pct=0.30,
        retrace_min=0.30, retrace_max=0.55,
        valid_minutes_max=60,
        **base_kwargs,
    ))

    results.append(run_arm(
        label="C+ATR2.0 (C + gap/atr>=2.0)",
        min_sp500_gap_pct=0.50, min_kr_gap_pct=0.30,
        retrace_min=0.30, retrace_max=0.55,
        min_gap_atr_ratio=2.0,
        **base_kwargs,
    ))

    results.append(run_arm(
        label="C+60min (C + window<=60min)",
        min_sp500_gap_pct=0.50, min_kr_gap_pct=0.30,
        retrace_min=0.30, retrace_max=0.55,
        valid_minutes_max=60,
        **base_kwargs,
    ))

    print_results(results)

    # Save JSON
    out_path = PROJECT_ROOT / ".superpowers" / "sdd" / "entry-matrix-report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "clean_window": f"{CLEAN_WINDOW_START} ~ {CLEAN_WINDOW_END}",
        "min_bars_per_day": MIN_BARS_PER_DAY,
        "exit_arm": "setup_target_exit",
        "n_trading_days": int(df["timestamp"].dt.date.nunique()),
        "results": results,
    }
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.info("JSON saved to %s", out_path)


if __name__ == "__main__":
    main()
