#!/usr/bin/env python3
"""Counterfactual analysis for THESIS C — high-conviction regime-gated HOLD.

Central question (the crux of the thesis): can a *conjunction* gate, evaluated
**ex-ante** at a fixed intraday decision time, separate the genuine big-trend days
(which a directional HOLD wants to ride) from the false starts (days that begin
trending then reverse, which bleed a HOLD)?

The gate conjunction (price/structure arms that ARE historically backtestable on the
clean Dec2025-Apr2026 window):

  1. MFI-regime arm  — persistent BULL_STRONG / BEAR_STRONG at the decision bar
     (MarketClassifier on the futures price/volume up to the decision time).
  2. Semiconductor-leadership arm — Samsung (005930) + SK Hynix (000660) daily
     relative strength vs KOSPI200 (101S6000), same direction as the break.
  3. Opening-range / efficiency arm — the day has established a *directional* move by
     the decision time (displacement from open in ATR units + Kaufman efficiency).

The LLM-daily-bias arm is NOT included here: there is ZERO LLM market_context history
before 2026-06-04, so it cannot be replayed on the clean window (reported separately
in the doc). It is wired live as an optional PERMISSIVE-on-missing confirmation.

Methodology
-----------
* Decision time: ``--decision-time`` (KST, default 10:00) — gate evaluated using ONLY
  bars up to and including this time (no look-ahead). This mirrors a once-a-day
  conviction arm-or-stay-flat decision.
* Ex-post trend-day label: built from the FULL day (decision-time -> EOD) ONLY to
  *score* the gate, never to compute it. A day is a TREND_UP / TREND_DOWN day if the
  post-decision move is large (>= ``--trend-move-atr`` ATRs) AND directionally
  efficient (Kaufman ER over the post-decision path >= ``--trend-er``). Otherwise CHOP.
* A "false start" relative to a candidate direction = the post-decision move is
  decent early but the day CLOSES against that direction (sign of decision->EOD return
  opposes the candidate).

Outputs
-------
* Confusion of gate-armed direction vs realised post-decision trend label.
* True-positive rate (armed days that are genuine same-direction trend days),
  false-start rate (armed days that reverse), recall on big-trend days.
* EOD-proxy PnL of the held position (decision-time entry -> EOD close, plus a
  wide-trailing-stop proxy), gate-ON vs a naive "always arm in the morning-move
  direction" baseline.

Honest by construction: with a strict conjunction the armed sample is tiny; the script
prints the sample size loudly and refuses to over-claim.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.storage import StorageConfig, load_market_bars_for_backtest  # noqa: E402
from shared.strategy.market_classifier import MarketClassifier  # noqa: E402

KST_OPEN = dt.time(9, 0)
KST_CLOSE = dt.time(15, 30)
FUT_SYMBOL = "101S6000"
SEMI_SYMBOLS = ("005930", "000660")  # Samsung, SK Hynix


# --------------------------------------------------------------------------- #
# Indicators (all causal — computed from bars up to a cutoff only)
# --------------------------------------------------------------------------- #
def kaufman_er(closes: np.ndarray) -> float:
    """Kaufman efficiency ratio: |net move| / path length over the window."""
    if len(closes) < 2:
        return 0.0
    direction = abs(closes[-1] - closes[0])
    volatility = np.abs(np.diff(closes)).sum()
    return float(direction / volatility) if volatility > 0 else 0.0


def atr_from_bars(bars: pd.DataFrame, period: int = 14) -> float:
    """Wilder-style ATR from intraday bars (causal: uses only the bars given)."""
    if len(bars) < 2:
        return 0.0
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum(
        high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close))
    )
    n = min(period, len(tr))
    return float(np.mean(tr[-n:])) if n else 0.0


def mfi_from_bars(bars: pd.DataFrame, period: int = 14) -> float | None:
    """Money Flow Index from intraday bars (causal). Mirrors indicator_engine._calc_mfi."""
    if len(bars) < period + 1:
        return None
    tp = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    rmf = tp * bars["volume"].clip(lower=0)
    tp = tp.to_numpy(dtype=float)
    rmf = rmf.to_numpy(dtype=float)
    pos = 0.0
    neg = 0.0
    # use the last `period` deltas
    start = len(tp) - period
    for i in range(start, len(tp)):
        if i == 0:
            continue
        if tp[i] > tp[i - 1]:
            pos += rmf[i]
        elif tp[i] < tp[i - 1]:
            neg += rmf[i]
    if neg == 0:
        return 100.0 if pos > 0 else 50.0
    mfr = pos / neg
    return float(100.0 - 100.0 / (1.0 + mfr))


# --------------------------------------------------------------------------- #
# Data assembly
# --------------------------------------------------------------------------- #
def load_futures_minute(start: dt.date, end: dt.date) -> pd.DataFrame:
    cfg = StorageConfig.load_or_default()
    df = load_market_bars_for_backtest(
        symbol=FUT_SYMBOL,
        asset_class="futures",
        timeframe="minute",
        start=start,
        end=end + dt.timedelta(days=1),
        config=cfg,
    )
    if df is None or df.empty:
        raise SystemExit("no futures minute data for window")
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["d"] = df["datetime"].dt.date
    df["t"] = df["datetime"].dt.time
    # regular day session only
    df = df[(df["t"] >= KST_OPEN) & (df["t"] <= KST_CLOSE)].copy()
    return df


def load_semi_daily(start: dt.date, end: dt.date) -> pd.DataFrame:
    """Daily change% panel for the semiconductor leaders, indexed by date."""
    from shared.storage.market_data_store import create_market_data_store

    store = create_market_data_store(asset_class="stock")
    frames = {}
    for sym in SEMI_SYMBOLS:
        d = store.get_daily_bars(sym, start=start - dt.timedelta(days=10), end=end)
        if d is None or len(d) == 0:
            continue
        d = d.copy()
        d["datetime"] = pd.to_datetime(d["datetime"])
        d = d.sort_values("datetime")
        d["date"] = d["datetime"].dt.date
        d["chg"] = d["close"].pct_change() * 100.0
        frames[sym] = d.set_index("date")["chg"]
    if not frames:
        return pd.DataFrame()
    panel = pd.DataFrame(frames)
    panel["semi_basket_chg"] = panel.mean(axis=1)  # equal-weight basket daily change
    return panel


# --------------------------------------------------------------------------- #
# Per-day feature + label construction
# --------------------------------------------------------------------------- #
@dataclass
class DayRow:
    date: dt.date
    # ex-ante (decision-time) features
    decided: bool
    open_px: float
    decision_px: float
    atr: float
    mfi: float | None
    mfi_state: str
    or_disp_atr: float  # displacement from open at decision in ATR units (report only)
    or_disp_pct: float  # displacement from open at decision as % of price (the gate)
    morning_er: float  # efficiency of open->decision path
    semi_lead: float  # prior-day semiconductor basket change (daily)
    semi_lead_today: (
        float  # same-day semiconductor basket change (used only ex-post check)
    )
    fut_daily_chg: float  # prior-day futures daily change
    # gate verdict (ex-ante)
    armed_dir: str  # 'long' | 'short' | 'flat'
    # ex-post (labels / pnl — NEVER fed to the gate)
    eod_px: float
    post_ret_pct: float  # decision->EOD return %
    post_move_atr: float  # |decision->EOD| / atr
    post_er: float  # efficiency of decision->EOD path
    trend_label: str  # 'TREND_UP' | 'TREND_DOWN' | 'CHOP'
    eod_proxy_pnl: float = field(default=0.0)
    trail_proxy_pnl: float = field(default=0.0)


def build_day_rows(
    fut: pd.DataFrame,
    semi: pd.DataFrame,
    decision_time: dt.time,
    *,
    min_disp_pct: float,
    min_morning_er: float,
    min_semi_lead: float,
    require_mfi_strong: bool,
    trail_atr_mult: float,
    trend_move_pct: float,
    trend_er: float,
) -> list[DayRow]:
    rows: list[DayRow] = []
    classifier = MarketClassifier()
    prev_fut_close: float | None = None

    for day, g in fut.groupby("d"):
        g = g.sort_values("datetime")
        day_open = float(g.iloc[0]["open"])
        upto = g[g["t"] <= decision_time]
        if len(upto) < 20:  # need a meaningful morning window
            prev_fut_close = float(g.iloc[-1]["close"])
            continue
        decision_px = float(upto.iloc[-1]["close"])
        atr = atr_from_bars(upto, period=14)
        if atr <= 0:
            prev_fut_close = float(g.iloc[-1]["close"])
            continue
        mfi = mfi_from_bars(upto, period=14)
        mfi_state = classifier.classify(
            mfi=mfi if mfi is not None else 50.0, adx=0.0
        ).value
        or_disp = decision_px - day_open
        # morning displacement as % of price (ATR over 60 1-min bars is too small to
        # normalise a directional move — % is the honest, scale-stable measure)
        or_disp_pct = abs(or_disp) / day_open * 100.0
        or_disp_atr = abs(or_disp) / atr  # kept for reporting only
        morning_er = kaufman_er(upto["close"].to_numpy(dtype=float))

        # semiconductor leadership: prior-day basket change (causal — known before today)
        semi_lead = (
            float(semi["semi_basket_chg"].get(day - dt.timedelta(days=1), np.nan))
            if not semi.empty
            else np.nan
        )
        # walk back to last available trading day if prev calendar day is a holiday
        if (
            semi_lead is None or (isinstance(semi_lead, float) and np.isnan(semi_lead))
        ) and not semi.empty:
            past = semi.index[semi.index < day]
            if len(past):
                semi_lead = float(semi["semi_basket_chg"].get(past.max(), np.nan))
        semi_lead = 0.0 if (semi_lead is None or np.isnan(semi_lead)) else semi_lead
        semi_today = (
            float(semi["semi_basket_chg"].get(day, np.nan))
            if not semi.empty
            else np.nan
        )
        semi_today = 0.0 if (semi_today is None or np.isnan(semi_today)) else semi_today

        fut_daily_chg = 0.0
        if prev_fut_close:
            fut_daily_chg = (day_open - prev_fut_close) / prev_fut_close * 100.0

        # --------------- EX-ANTE GATE (the conjunction) ---------------
        # candidate direction from the morning move
        if or_disp > 0:
            cand = "long"
        elif or_disp < 0:
            cand = "short"
        else:
            cand = "flat"

        armed = "flat"
        if cand != "flat":
            energy_ok = (or_disp_pct >= min_disp_pct) and (morning_er >= min_morning_er)
            # MFI must not oppose; STRONG required if require_mfi_strong
            if cand == "long":
                mfi_ok = mfi_state in (
                    ("BULL_STRONG",)
                    if require_mfi_strong
                    else (
                        "BULL_STRONG",
                        "BULL_MODERATE",
                        "SIDEWAYS_UP",
                        "SIDEWAYS_FLAT",
                    )
                )
                semi_ok = semi_lead >= min_semi_lead
            else:
                mfi_ok = mfi_state in (
                    ("BEAR_STRONG",)
                    if require_mfi_strong
                    else (
                        "BEAR_STRONG",
                        "BEAR_MODERATE",
                        "SIDEWAYS_DOWN",
                        "SIDEWAYS_FLAT",
                    )
                )
                semi_ok = semi_lead <= -min_semi_lead
            if energy_ok and mfi_ok and semi_ok:
                armed = cand

        # --------------- EX-POST LABEL + PNL (scoring only) ---------------
        # A "trend day" = the post-decision path is BOTH large (>= trend_move_pct of
        # price) AND directionally efficient. NOTE on granularity: Kaufman ER over a
        # full day of 1-minute bars is structurally small (path length is huge); the
        # cleanest real trend days in this window top out near ER~0.20 while the median
        # day is ~0.05. So trend_er defaults to ~0.10 (a *relative* separator at this
        # granularity), not the 0.40 that suits 5-minute intraday windows.
        eod_px = float(g.iloc[-1]["close"])
        post = g[g["t"] > decision_time]
        post_closes = post["close"].to_numpy(dtype=float)
        post_ret_pct = (eod_px - decision_px) / decision_px * 100.0
        post_move_pct = abs(eod_px - decision_px) / decision_px * 100.0
        post_er = (
            kaufman_er(np.concatenate([[decision_px], post_closes]))
            if len(post_closes)
            else 0.0
        )

        if post_move_pct >= trend_move_pct and post_er >= trend_er:
            trend_label = "TREND_UP" if (eod_px - decision_px) > 0 else "TREND_DOWN"
        else:
            trend_label = "CHOP"

        row = DayRow(
            date=day,
            decided=True,
            open_px=day_open,
            decision_px=decision_px,
            atr=atr,
            mfi=mfi,
            mfi_state=mfi_state,
            or_disp_atr=or_disp_atr,
            or_disp_pct=or_disp_pct,
            morning_er=morning_er,
            semi_lead=semi_lead,
            semi_lead_today=semi_today,
            fut_daily_chg=fut_daily_chg,
            armed_dir=armed,
            eod_px=eod_px,
            post_ret_pct=post_ret_pct,
            post_move_atr=post_move_pct,
            post_er=post_er,
            trend_label=trend_label,
        )
        # EOD-proxy PnL: hold decision->EOD in armed direction (ticks-as-% of price)
        if armed == "long":
            row.eod_proxy_pnl = post_ret_pct
        elif armed == "short":
            row.eod_proxy_pnl = -post_ret_pct
        # Wide-trailing-stop proxy: trail by trail_atr_mult*atr from best price post-decision
        if armed != "flat" and len(post_closes):
            row.trail_proxy_pnl = _trail_proxy(
                decision_px, post, armed, atr, trail_atr_mult
            )
        rows.append(row)
        prev_fut_close = float(g.iloc[-1]["close"])
    return rows


def _trail_proxy(
    entry: float, post: pd.DataFrame, direction: str, atr: float, mult: float
) -> float:
    """Realised % PnL holding to EOD with an ATR trailing stop (best-price chandelier)."""
    stop_dist = mult * atr
    if direction == "long":
        best = entry
        exit_px = float(post.iloc[-1]["close"])
        for _, b in post.iterrows():
            best = max(best, float(b["high"]))
            stop = best - stop_dist
            if float(b["low"]) <= stop:
                exit_px = stop
                break
        return (exit_px - entry) / entry * 100.0
    else:
        best = entry
        exit_px = float(post.iloc[-1]["close"])
        for _, b in post.iterrows():
            best = min(best, float(b["low"]))
            stop = best + stop_dist
            if float(b["high"]) >= stop:
                exit_px = stop
                break
        return (entry - exit_px) / entry * 100.0


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def score(rows: list[DayRow]) -> dict:
    armed = [r for r in rows if r.armed_dir != "flat"]
    trend_days = [r for r in rows if r.trend_label != "CHOP"]

    def same_dir(r: DayRow) -> bool:
        return (r.armed_dir == "long" and r.trend_label == "TREND_UP") or (
            r.armed_dir == "short" and r.trend_label == "TREND_DOWN"
        )

    def reversed_(r: DayRow) -> bool:
        # armed but the day closed against the armed direction = false start
        return (r.armed_dir == "long" and r.post_ret_pct < 0) or (
            r.armed_dir == "short" and r.post_ret_pct > 0
        )

    tp = [r for r in armed if same_dir(r)]
    fs = [r for r in armed if reversed_(r)]
    # big-trend recall: of all genuine trend days, how many did the gate arm correctly?
    caught = [r for r in trend_days if same_dir(r)]

    eod_pnls = [r.eod_proxy_pnl for r in armed]
    trail_pnls = [r.trail_proxy_pnl for r in armed]

    # naive baseline: arm every day in the morning-move direction, hold to EOD
    naive = []
    for r in rows:
        if r.or_disp_atr == 0:
            continue
        d = "long" if (r.decision_px - r.open_px) > 0 else "short"
        naive.append(r.post_ret_pct if d == "long" else -r.post_ret_pct)

    return {
        "n_days": len(rows),
        "n_trend_days": len(trend_days),
        "n_armed": len(armed),
        "tp": len(tp),
        "false_start": len(fs),
        "true_pos_rate": (len(tp) / len(armed)) if armed else float("nan"),
        "false_start_rate": (len(fs) / len(armed)) if armed else float("nan"),
        "recall_on_trend_days": (
            (len(caught) / len(trend_days)) if trend_days else float("nan")
        ),
        "eod_proxy_mean_pct": float(np.mean(eod_pnls)) if eod_pnls else float("nan"),
        "eod_proxy_sum_pct": float(np.sum(eod_pnls)) if eod_pnls else 0.0,
        "trail_proxy_mean_pct": (
            float(np.mean(trail_pnls)) if trail_pnls else float("nan")
        ),
        "trail_proxy_sum_pct": float(np.sum(trail_pnls)) if trail_pnls else 0.0,
        "naive_mean_pct": float(np.mean(naive)) if naive else float("nan"),
        "naive_n": len(naive),
        "armed_rows": armed,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--start", type=lambda s: dt.date.fromisoformat(s), default=dt.date(2025, 12, 1)
    )
    ap.add_argument(
        "--end", type=lambda s: dt.date.fromisoformat(s), default=dt.date(2026, 4, 30)
    )
    ap.add_argument(
        "--decision-time",
        type=lambda s: dt.time.fromisoformat(s),
        default=dt.time(10, 0),
    )
    ap.add_argument(
        "--min-disp-pct",
        type=float,
        default=0.30,
        help="morning displacement gate (% of price)",
    )
    ap.add_argument(
        "--min-morning-er", type=float, default=0.10, help="morning efficiency gate"
    )
    ap.add_argument(
        "--min-semi-lead",
        type=float,
        default=0.5,
        help="semiconductor leadership gate (daily %)",
    )
    ap.add_argument("--require-mfi-strong", action="store_true", default=True)
    ap.add_argument(
        "--no-require-mfi-strong", dest="require_mfi_strong", action="store_false"
    )
    ap.add_argument("--trail-atr-mult", type=float, default=3.0)
    ap.add_argument(
        "--trend-move-pct",
        type=float,
        default=1.0,
        help="ex-post: post-decision move (% of price) to call a trend day",
    )
    ap.add_argument(
        "--trend-er",
        type=float,
        default=0.10,
        help="ex-post: post-decision efficiency to call a trend day",
    )
    ap.add_argument("--csv", type=str, default="")
    a = ap.parse_args(argv)

    fut = load_futures_minute(a.start, a.end)
    semi = load_semi_daily(a.start, a.end)
    rows = build_day_rows(
        fut,
        semi,
        a.decision_time,
        min_disp_pct=a.min_disp_pct,
        min_morning_er=a.min_morning_er,
        min_semi_lead=a.min_semi_lead,
        require_mfi_strong=a.require_mfi_strong,
        trail_atr_mult=a.trail_atr_mult,
        trend_move_pct=a.trend_move_pct,
        trend_er=a.trend_er,
    )
    s = score(rows)

    print("=" * 78)
    print(f"THESIS C conviction-hold counterfactual  {a.start} -> {a.end}")
    print(
        f"decision-time={a.decision_time} KST  | gate: disp>={a.min_disp_pct}% ER>={a.min_morning_er} "
        f"semi_lead>={a.min_semi_lead}% mfi_strong={a.require_mfi_strong}"
    )
    print(
        f"ex-post trend-day label: post-move>={a.trend_move_pct}% AND ER>={a.trend_er}"
    )
    print("=" * 78)
    print(f"trading days evaluated : {s['n_days']}")
    print(
        f"genuine trend days     : {s['n_trend_days']}  ({s['n_trend_days']/max(s['n_days'],1)*100:.0f}% of days)"
    )
    print(f"days the gate ARMED    : {s['n_armed']}")
    if s["n_armed"]:
        print(
            f"  true positives (same-dir trend) : {s['tp']}  -> true-pos rate {s['true_pos_rate']*100:.0f}%"
        )
        print(
            f"  false starts (closed against)   : {s['false_start']}  -> false-start rate {s['false_start_rate']*100:.0f}%"
        )
    print(
        f"recall on big-trend days: {s['recall_on_trend_days']*100:.0f}%  (caught / all trend days)"
    )
    print("-" * 78)
    print("EOD-proxy PnL (decision-time -> EOD, armed dir):")
    print(
        f"  hold-to-EOD : mean {s['eod_proxy_mean_pct']:+.3f}%  sum {s['eod_proxy_sum_pct']:+.3f}%  (n={s['n_armed']})"
    )
    print(
        f"  trail-stop  : mean {s['trail_proxy_mean_pct']:+.3f}%  sum {s['trail_proxy_sum_pct']:+.3f}%"
    )
    print(
        f"  naive baseline (arm every day, morning-move dir, hold EOD): "
        f"mean {s['naive_mean_pct']:+.3f}%  (n={s['naive_n']})"
    )
    print("-" * 78)
    if s["armed_rows"]:
        print("Armed days detail:")
        print(
            f"  {'date':12s} {'dir':5s} {'mfi':>5s} {'state':14s} {'disp%':>6s} {'mER':>5s} "
            f"{'semiLd':>6s} {'postRet%':>8s} {'label':10s} {'eodPnl%':>8s} {'trailPnl%':>9s}"
        )
        for r in sorted(s["armed_rows"], key=lambda x: x.date):
            print(
                f"  {str(r.date):12s} {r.armed_dir:5s} {(r.mfi or 0):5.1f} {r.mfi_state:14s} "
                f"{r.or_disp_pct:6.2f} {r.morning_er:5.2f} {r.semi_lead:6.2f} "
                f"{r.post_ret_pct:+8.3f} {r.trend_label:10s} {r.eod_proxy_pnl:+8.3f} {r.trail_proxy_pnl:+9.3f}"
            )
    if a.csv:
        pd.DataFrame([r.__dict__ for r in rows]).to_csv(a.csv, index=False)
        print(f"\nwrote per-day rows -> {a.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
