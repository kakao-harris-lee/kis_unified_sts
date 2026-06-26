"""Setup A macro-alignment A/B/C backtest experiment (research-only).

Question
--------
Does LOOSENING the Setup A (``setup_a_gap_reversion``) macro-alignment gate
(``require_gap_alignment``) add net-positive entries, or just noise?

The alignment gate rejects entries where the S&P 500 overnight direction
disagrees with the Korean open-gap direction (``sp500_kr_gap_misaligned``).
This script measures, on the TRUSTED futures-minute window (Dec 2025 – Apr
2026), three variants:

  A (current)  : require_gap_alignment=True  — aligned-only.
  B (loosened) : require_gap_alignment=False — any gap meeting the magnitude +
                 kr-gap thresholds; direction from the KR gap sign.
  C (subset)   : the DIVERGENT-gap trades that B adds over A (B \\ A), reported
                 standalone so the marginal entries are judged on their own
                 merit rather than diluted into the aligned population.

Faithfulness
------------
* Entry config is loaded from the PRODUCTION strategy YAML
  (``config/strategies/futures/setup_a_gap_reversion.yaml`` -> entry.params),
  NOT the bare ``SetupAConfig()`` defaults (which differ materially).
* Fill/exit simulation reuses :class:`BacktestDecisionHarness._simulate_fill`
  (next-bar open ± 0.3-tick slippage, intraday session-bounded, EOD close),
  matching the production ``setup_target_exit`` (fixed stop/target) exit.
* Macro is real overnight S&P 500 via yfinance, look-ahead-safe (T-1 US close
  -> T KR session) through ``MarketContextReplay.macro_provider``.
* One entry per day per variant (mirrors live Setup A behaviour).
* Long/short symmetry preserved: direction is taken purely from the KR gap.

Usage
-----
    .venv/bin/python scripts/analysis/setup_a_alignment_experiment.py \\
        --start 2025-12-01 --end 2026-04-30 --min-bars-per-day 330

Output is printed; a JSON summary is written to --output.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.backtest.decision_harness import BacktestDecisionHarness, TradeRecord
from shared.backtest.macro_history import fetch_macro_history, make_macro_provider
from shared.backtest.market_context_replay import MarketContextReplay
from shared.config.loader import ConfigLoader
from shared.decision.setups.gap_reversion import SetupAConfig, SetupAGapReversion
from shared.execution.contract_spec import ContractSpec
from shared.risk.layer import RiskFilterLayer
from shared.risk.state import RiskStateSnapshot
from shared.storage.market_data_store import load_market_bars_for_backtest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("setup_a_alignment")

# KOSPI200 mini futures contract economics.
FUTURES_POINT_VALUE = 50_000  # KRW per index point
TICK_SIZE_POINTS = 0.05
MINI_SPEC = ContractSpec(
    name="kospi200_futures",
    multiplier_krw_per_point=FUTURES_POINT_VALUE,
    tick_size_points=TICK_SIZE_POINTS,
    tick_value_krw=2500,
    commission_rate=0.00015,
    symbol_prefix="A05",
)


# ---------------------------------------------------------------------------
# Config loading (production-faithful)
# ---------------------------------------------------------------------------

def load_production_setup_a_config(require_alignment: bool) -> SetupAConfig:
    """Build a SetupAConfig from the production strategy YAML entry.params.

    The bare ``SetupAConfig()`` defaults differ from the live YAML, so we load
    the real ``entry.params`` and only keep keys SetupAConfig understands. The
    ``require_gap_alignment`` flag is overridden to drive the A/B variants.
    """
    cfg_dict = ConfigLoader.load_strategy("futures", "setup_a_gap_reversion")
    params = cfg_dict.get("strategy", {}).get("entry", {}).get("params", {})

    valid_fields = set(SetupAConfig.model_fields.keys())
    kept = {k: v for k, v in params.items() if k in valid_fields}
    kept["require_gap_alignment"] = require_alignment
    return SetupAConfig(**kept)


# ---------------------------------------------------------------------------
# Entry collection with alignment tagging + one-per-day dedupe
# ---------------------------------------------------------------------------

@dataclass
class TaggedEntry:
    """A fired Setup A signal with its alignment classification + bar index."""

    bar_index: int
    session_date: date
    direction: str
    sp500_pct: float
    gap_pct: float
    aligned: bool  # sign(sp500) == sign(gap)


def collect_entries(
    replay: MarketContextReplay,
    config: SetupAConfig,
    ts_index: dict[pd.Timestamp, int],
) -> tuple[list[TaggedEntry], dict[int, object]]:
    """Collect one Setup A entry per day, tagged aligned/divergent.

    The signal direction follows the KR gap sign (gap-UP -> long, gap-DOWN ->
    short), so long/short symmetry holds for both aligned and divergent gaps.

    Returns the tagged entries and a ``{bar_index: Signal}`` map so the caller
    can reuse the fired signal's stop/target for fill simulation without
    re-iterating the replay.
    """
    setup = SetupAGapReversion(config=config)
    entries: list[TaggedEntry] = []
    signal_by_bar: dict[int, object] = {}
    last_day: date | None = None

    for ctx in replay.iter_contexts():
        day = ctx.now.date()
        if day == last_day:
            continue  # one entry per day (live behaviour)

        signal = setup.check(ctx)
        if signal is None:
            continue

        # Locate the signal bar in the original df by KST timestamp.
        ts_naive = pd.Timestamp(ctx.now).tz_localize(None)
        bar_idx = ts_index.get(ts_naive)
        if bar_idx is None:
            logger.debug("could not locate bar for %s — skip", ctx.now)
            continue

        macro = ctx.macro_overnight
        sp500_pct = float(macro.sp500_change_pct) if macro else float("nan")
        gap_pct = (ctx.today_open - ctx.prev_close) / ctx.prev_close * 100.0
        aligned = math.copysign(1.0, sp500_pct) == math.copysign(1.0, gap_pct)

        entries.append(
            TaggedEntry(
                bar_index=bar_idx,
                session_date=day,
                direction=signal.direction,
                sp500_pct=sp500_pct,
                gap_pct=gap_pct,
                aligned=aligned,
            )
        )
        signal_by_bar[bar_idx] = signal
        last_day = day

    return entries, signal_by_bar


# ---------------------------------------------------------------------------
# Fill/exit simulation via the production harness
# ---------------------------------------------------------------------------

def simulate_trades(
    replay_df: pd.DataFrame,
    config: SetupAConfig,
    replay: MarketContextReplay,
) -> tuple[list[TradeRecord], list[TaggedEntry]]:
    """Run the canonical harness for one variant, returning trades + tagged entries.

    We rerun the setup ourselves (with dedupe + tagging) to drive entries, then
    delegate the fill/exit math to ``BacktestDecisionHarness._simulate_fill`` so
    slippage/EOD/session-boundary handling matches production exactly. Each
    accepted entry's signal is recomputed at its bar to obtain stop/target.
    """
    ts_col = replay_df["timestamp"]
    # Build a tz-naive timestamp -> row index map for bar location.
    ts_index: dict[pd.Timestamp, int] = {}
    for i in range(len(ts_col)):
        t = pd.Timestamp(ts_col.iloc[i])
        if t.tzinfo is not None:
            t = t.tz_convert(None)
        ts_index[t] = i

    entries, ctx_by_bar = collect_entries(replay, config, ts_index)

    # Harness instance only for its fill simulation (filters=[] => accept all).
    harness = BacktestDecisionHarness(
        setups=[],
        filter_layer=RiskFilterLayer(filters=[]),
        state=RiskStateSnapshot(),
        tick_size_points=MINI_SPEC.tick_size_points,
    )

    opens = replay_df["open"].to_numpy(dtype=float)
    highs = replay_df["high"].to_numpy(dtype=float)
    lows = replay_df["low"].to_numpy(dtype=float)
    closes = replay_df["close"].to_numpy(dtype=float)
    n = len(replay_df)

    # KST session date per bar (for the harness session-boundary logic).
    session_dates: list[date] = []
    for i in range(n):
        t = pd.Timestamp(ts_col.iloc[i])
        t = t.tz_localize("Asia/Seoul") if t.tzinfo is None else t.tz_convert("Asia/Seoul")
        session_dates.append(t.date())

    trades: list[TradeRecord] = []
    kept_entries: list[TaggedEntry] = []
    for entry in entries:
        signal = ctx_by_bar.get(entry.bar_index)
        if signal is None:
            continue
        trade = harness._simulate_fill(  # noqa: SLF001 — intentional reuse
            signal=signal,
            signal_bar_idx=entry.bar_index,
            layer_result=_dummy_layer_result(),
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            ts_col=ts_col,
            session_dates=session_dates,
            n=n,
        )
        if trade is not None:
            trade.size_contracts = 1
            trade.ticks_net_total = trade.ticks_net
            trades.append(trade)
            kept_entries.append(entry)

    return trades, kept_entries


def _dummy_layer_result():
    from shared.risk.layer import LayerResult

    return LayerResult(
        passed=True, skip_reason=None, size_multiplier=1.0, filter_outcomes=[]
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _pnl_pct_for_trade(t: TradeRecord) -> float:
    """Return per-trade return % on the fill price (direction-aware)."""
    if t.fill_price == 0:
        return 0.0
    if t.direction == "long":
        return (t.exit_price - t.fill_price) / t.fill_price * 100.0
    return (t.fill_price - t.exit_price) / t.fill_price * 100.0


def compute_metrics(trades: list[TradeRecord], entries: list[TaggedEntry]) -> dict:
    """Aggregate per-variant metrics (Sharpe/MDD/win-rate/PnL/long-short split)."""
    if not trades:
        return {
            "n_trades": 0,
            "win_rate_pct": 0.0,
            "avg_return_pct": 0.0,
            "total_pnl_ticks": 0.0,
            "total_pnl_krw": 0.0,
            "sharpe": 0.0,
            "mdd_pct": 0.0,
            "long_trades": 0,
            "short_trades": 0,
            "long_pnl_ticks": 0.0,
            "short_pnl_ticks": 0.0,
            "exit_reasons": {},
        }

    returns = np.array([_pnl_pct_for_trade(t) for t in trades])
    ticks = np.array([t.ticks_net for t in trades])
    wins = int(sum(1 for r in returns if r > 0))
    win_rate = wins / len(trades) * 100.0

    sharpe = (
        float(np.mean(returns) / np.std(returns, ddof=1) * math.sqrt(252))
        if len(returns) >= 2 and np.std(returns, ddof=1) > 0
        else 0.0
    )

    # Equity curve in KRW (1 contract, point value) for MDD.
    pv = FUTURES_POINT_VALUE
    equity = [10_000_000.0]
    for t in trades:
        pnl_pts = t.ticks_net * TICK_SIZE_POINTS
        equity.append(equity[-1] + pnl_pts * pv)
    peak = equity[0]
    mdd = 0.0
    for v in equity:
        peak = max(peak, v)
        dd = (peak - v) / peak * 100.0 if peak > 0 else 0.0
        mdd = max(mdd, dd)

    long_idx = [i for i, t in enumerate(trades) if t.direction == "long"]
    short_idx = [i for i, t in enumerate(trades) if t.direction == "short"]

    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1

    total_ticks = float(ticks.sum())
    return {
        "n_trades": len(trades),
        "win_rate_pct": round(win_rate, 1),
        "avg_return_pct": round(float(np.mean(returns)), 4),
        "total_pnl_ticks": round(total_ticks, 2),
        "total_pnl_krw": round(total_ticks * TICK_SIZE_POINTS * pv, 0),
        "sharpe": round(sharpe, 3),
        "mdd_pct": round(mdd, 2),
        "long_trades": len(long_idx),
        "short_trades": len(short_idx),
        "long_pnl_ticks": round(float(ticks[long_idx].sum()) if long_idx else 0.0, 2),
        "short_pnl_ticks": round(float(ticks[short_idx].sum()) if short_idx else 0.0, 2),
        "exit_reasons": reasons,
    }


def print_metrics(label: str, m: dict) -> None:
    print(f"\n{'='*68}")
    print(f"  {label}")
    print(f"{'='*68}")
    print(f"  Trades          : {m['n_trades']}")
    print(f"  Win Rate        : {m['win_rate_pct']:.1f}%")
    print(f"  Avg Return      : {m['avg_return_pct']:+.4f}%")
    print(f"  Total PnL (ticks): {m['total_pnl_ticks']:+.2f}")
    print(f"  Total PnL (KRW) : {m['total_pnl_krw']:+,.0f}")
    print(f"  Sharpe (ann.)   : {m['sharpe']:+.3f}")
    print(f"  MDD             : {m['mdd_pct']:.2f}%")
    print(f"  Long / Short    : {m['long_trades']} / {m['short_trades']}  "
          f"(ticks {m['long_pnl_ticks']:+.1f} / {m['short_pnl_ticks']:+.1f})")
    if m["exit_reasons"]:
        print("  Exit reasons    : " + ", ".join(
            f"{k}={v}" for k, v in sorted(m["exit_reasons"].items(), key=lambda x: -x[1])
        ))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="101S6000")
    parser.add_argument("--start", default="2025-12-01")
    parser.add_argument("--end", default="2026-04-30")
    parser.add_argument(
        "--min-bars-per-day",
        type=int,
        default=330,
        help="Drop degraded sessions with fewer bars (default 330, ~85%% of 09:00-15:30).",
    )
    parser.add_argument("--min-volume", type=int, default=30,
                        help="Phantom-bar suppression in MarketContextReplay.")
    parser.add_argument(
        "--max-bar-move-pct", type=float, default=0.0,
        help=(
            "Quarantine any session containing a single 1-min bar move larger "
            "than this %% (contract-roll / mis-stitched price discontinuity). "
            "0 = off (default). Use ~2.0 for a clean-data sensitivity run."
        ),
    )
    parser.add_argument(
        "--output",
        default="reports/setup_a_alignment_experiment.json",
        help="JSON summary path.",
    )
    args = parser.parse_args()

    start = pd.Timestamp(args.start).date()
    end = pd.Timestamp(args.end).date()

    # 1. Load futures minute bars from the parquet store.
    logger.info("loading %s futures minute bars %s..%s", args.symbol, start, end)
    df = load_market_bars_for_backtest(
        symbol=args.symbol, asset_class="futures", timeframe="minute",
        start=start, end=end,
    )
    if "datetime" in df.columns:
        df = df.rename(columns={"datetime": "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    raw_days = df["timestamp"].dt.date.nunique()
    raw_bars = len(df)

    # 2. Bar-density gate: drop degraded sessions.
    if args.min_bars_per_day > 0:
        dser = df["timestamp"].dt.date
        bpd = df.groupby(dser).size()
        healthy = set(bpd[bpd >= args.min_bars_per_day].index)
        df = df[dser.isin(healthy)].reset_index(drop=True)

    # 2b. Optional price-integrity gate: drop sessions containing an implausible
    #     single-bar move (contract-roll / mis-stitched discontinuity). KOSPI200
    #     futures 1-min bars are normally <0.5%; a >max single-bar jump marks a
    #     corrupted session whose "gap" and intraday path are not real prices.
    quarantined_days: list[str] = []
    if args.max_bar_move_pct > 0:
        ret = df["close"].pct_change().abs()
        dser2 = df["timestamp"].dt.date
        bad_mask = ret > (args.max_bar_move_pct / 100.0)
        bad_days = set(dser2[bad_mask].dropna().unique())
        if bad_days:
            quarantined_days = sorted(str(d) for d in bad_days)
            df = df[~dser2.isin(bad_days)].reset_index(drop=True)
            logger.warning(
                "price-integrity gate (>%.1f%% single-bar): quarantined %d days: %s",
                args.max_bar_move_pct, len(bad_days), quarantined_days,
            )

    kept_days = df["timestamp"].dt.date.nunique()
    kept_bars = len(df)
    logger.info(
        "coverage: %d/%d days kept (>=%d bars), %d/%d bars; window %s..%s",
        kept_days, raw_days, args.min_bars_per_day, kept_bars, raw_bars,
        df["timestamp"].min().date(), df["timestamp"].max().date(),
    )

    # 3. Real overnight macro via yfinance (look-ahead-safe T-1 US close -> T).
    logger.info("fetching yfinance macro history %s..%s", start, end)
    history = fetch_macro_history(start, end)
    macro_provider = make_macro_provider(history)
    macro_days = sum(1 for d in df["timestamp"].dt.date.unique() if d in history)
    logger.info("macro coverage: %d/%d kept trading days", macro_days, kept_days)

    def build_replay() -> MarketContextReplay:
        return MarketContextReplay(
            df=df.copy(),
            symbol=args.symbol,
            macro_snapshot=None,
            scheduled_events=[],
            contract_spec=MINI_SPEC,
            macro_provider=macro_provider,
            min_volume=args.min_volume,
        )

    # 4. Variant A (aligned-only) and B (loosened).
    cfg_a = load_production_setup_a_config(require_alignment=True)
    cfg_b = load_production_setup_a_config(require_alignment=False)
    logger.info(
        "production config: time=[%d,%d] sp500>=%.2f kr>=%.2f retrace=[%.2f,%.2f] stop=%.1f",
        cfg_a.valid_minutes_min, cfg_a.valid_minutes_max, cfg_a.min_sp500_gap_pct,
        cfg_a.min_kr_gap_pct, cfg_a.retrace_min, cfg_a.retrace_max, cfg_a.stop_atr_mult,
    )

    trades_a, entries_a = simulate_trades(df, cfg_a, build_replay())
    trades_b, entries_b = simulate_trades(df, cfg_b, build_replay())

    m_a = compute_metrics(trades_a, entries_a)
    m_b = compute_metrics(trades_b, entries_b)

    # 5. Variant C = divergent trades B adds over A (B \\ A).
    #    A's accepted entries are a strict subset of B's (B only relaxes the
    #    alignment gate), so we isolate by bar_index not in A, AND confirm
    #    the entry is divergent (alignment tag False).
    a_bars = {e.bar_index for e in entries_a}
    trades_c: list[TradeRecord] = []
    entries_c: list[TaggedEntry] = []
    for t, e in zip(trades_b, entries_b):
        if e.bar_index not in a_bars and not e.aligned:
            trades_c.append(t)
            entries_c.append(e)
    m_c = compute_metrics(trades_c, entries_c)

    # Sanity: aligned trades in B should equal A (same gate otherwise).
    aligned_in_b = sum(1 for e in entries_b if e.aligned)
    divergent_in_b = sum(1 for e in entries_b if not e.aligned)

    print(f"\n{'#'*68}")
    print("  SETUP A MACRO-ALIGNMENT A/B/C EXPERIMENT")
    print(f"  Symbol {args.symbol} | window "
          f"{df['timestamp'].min().date()}..{df['timestamp'].max().date()}")
    print(f"  Trading days {kept_days} (>= {args.min_bars_per_day} bars) | "
          f"macro {macro_days}/{kept_days} | min_volume {args.min_volume}")
    print("  Exit: fixed stop/target + EOD (setup_target_exit-equivalent), "
          "slippage 0.3 tick")
    print(f"  B composition: aligned={aligned_in_b}  divergent={divergent_in_b}")
    print(f"{'#'*68}")

    print_metrics("VARIANT A — require_gap_alignment=True (aligned only)", m_a)
    print_metrics("VARIANT B — require_gap_alignment=False (all gaps)", m_b)
    print_metrics("VARIANT C — DIVERGENT subset B\\A (marginal entries only)", m_c)

    # Deltas B - A.
    print(f"\n{'='*68}")
    print("  DELTA  B − A (what loosening adds)")
    print(f"{'='*68}")
    print(f"  Trades       : {m_b['n_trades'] - m_a['n_trades']:+d}")
    print(f"  Total PnL tks: {m_b['total_pnl_ticks'] - m_a['total_pnl_ticks']:+.2f}")
    print(f"  Sharpe       : {m_b['sharpe'] - m_a['sharpe']:+.3f}")
    print(f"  Win-rate     : {m_b['win_rate_pct'] - m_a['win_rate_pct']:+.1f}%")
    print(f"  MDD          : {m_b['mdd_pct'] - m_a['mdd_pct']:+.2f}%")

    out = {
        "generated_at": datetime.utcnow().isoformat(),
        "symbol": args.symbol,
        "window": {
            "requested_start": str(start),
            "requested_end": str(end),
            "actual_start": str(df["timestamp"].min().date()),
            "actual_end": str(df["timestamp"].max().date()),
            "trading_days": kept_days,
            "raw_days": raw_days,
            "min_bars_per_day": args.min_bars_per_day,
            "macro_days": macro_days,
            "min_volume": args.min_volume,
            "max_bar_move_pct": args.max_bar_move_pct,
            "quarantined_days": quarantined_days,
        },
        "config": {
            "valid_minutes": [cfg_a.valid_minutes_min, cfg_a.valid_minutes_max],
            "min_sp500_gap_pct": cfg_a.min_sp500_gap_pct,
            "min_kr_gap_pct": cfg_a.min_kr_gap_pct,
            "retrace": [cfg_a.retrace_min, cfg_a.retrace_max],
            "stop_atr_mult": cfg_a.stop_atr_mult,
            "target_gap_fill_ratio": cfg_a.target_gap_fill_ratio,
            "signal_ttl_minutes": cfg_a.signal_ttl_minutes,
            "source": "config/strategies/futures/setup_a_gap_reversion.yaml entry.params",
        },
        "b_composition": {"aligned": aligned_in_b, "divergent": divergent_in_b},
        "variant_A_aligned_only": m_a,
        "variant_B_loosened": m_b,
        "variant_C_divergent_subset": m_c,
        "delta_B_minus_A": {
            "trades": m_b["n_trades"] - m_a["n_trades"],
            "total_pnl_ticks": round(m_b["total_pnl_ticks"] - m_a["total_pnl_ticks"], 2),
            "sharpe": round(m_b["sharpe"] - m_a["sharpe"], 3),
            "win_rate_pct": round(m_b["win_rate_pct"] - m_a["win_rate_pct"], 1),
            "mdd_pct": round(m_b["mdd_pct"] - m_a["mdd_pct"], 2),
        },
        "divergent_trade_detail": [
            {
                "session_date": str(e.session_date),
                "direction": e.direction,
                "sp500_pct": round(e.sp500_pct, 3),
                "gap_pct": round(e.gap_pct, 3),
                "exit_reason": t.exit_reason,
                "ticks_net": round(t.ticks_net, 2),
            }
            for t, e in zip(trades_c, entries_c)
        ],
    }
    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = PROJECT_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nJSON summary written to: {out_path}")


if __name__ == "__main__":
    main()
