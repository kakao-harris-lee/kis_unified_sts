"""Walk-forward validation — CTA daily/swing time-series momentum (THESIS B).

Honest, multi-regime out-of-sample validation of daily-bar time-series momentum
on the 16-year KRX KOSPI200 daily settlement series
(``krx_kospi200f_continuous``, 2010-06 .. 2026-06, 3,933 bars). Replays the real
``CTAMomentumEntry`` / ``CTAMomentumExit`` signal logic over daily bars and
reports per-fold + aggregate Sharpe / MDD / win-rate / trades / CAGR, long vs
short, and a regime-by-regime breakdown.

Roll-aware accounting (the unadjusted-series caveat)
----------------------------------------------------
The continuous series is RAW volume-weighted front-month, NOT back-adjusted, so
quarterly rolls (2nd Thursday of Mar/Jun/Sep/Dec) step the settlement level by
the carry spread. Two defences, both reusing the strategy's own
``is_quarterly_roll_day`` / ``roll_aware_log_returns``:

  1. **Signals** — the entry/exit neutralise the roll-day return inside the
     momentum lookback (no spurious momentum), and the entry blocks roll days
     as entry days.
  2. **PnL** — equity is marked daily on **roll-aware log-returns** (the roll-day
     return is zeroed), so a carry-spread step never books as profit or loss for
     a held position. This is the rigorous way to P&L an unadjusted continuous
     series: a real position rolls at ~zero cost, it does not capture the gap.

Look-ahead safety
-----------------
At decision day ``i`` the strategy sees only bars ``<= i`` (the close of day
``i``). A position is opened at day ``i+1``'s OPEN (you cannot trade on a close
at the instant you observe it). ``LookaheadGuard`` (ASSERT) validates the close
series fed to the entry never contains a timestamp > the decision timestamp.

Costs: round-turn commission (``commission_rate`` × notional, both legs) +
``slippage_ticks`` × tick value per leg, applied in points on entry and exit.

Usage::

    .venv/bin/python scripts/analysis/cta_daily_walkforward.py
    .venv/bin/python scripts/analysis/cta_daily_walkforward.py \\
        --is-years 3 --oos-years 1 --momentum-lookback 60
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

from shared.backtest.lookahead_guard import LookaheadGuard, LookaheadGuardMode
from shared.strategy.entry.cta_momentum import (
    CTAMomentumConfig,
    CTAMomentumEntry,
    is_quarterly_roll_day,
    roll_aware_log_returns,
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("cta_wf")

SYMBOL = "krx_kospi200f_continuous"
POINT_VALUE = 50_000  # KRW per index point (KOSPI200 futures)
TICK_SIZE = 0.05
TICK_VALUE = 2_500  # KRW per tick = TICK_SIZE * POINT_VALUE
COMMISSION_RATE = (
    0.000_03  # per-leg commission on notional (KRX futures, round-turn ~0.006%)
)
TRADING_DAYS = 252

DEFAULT_DATA_ROOT = "/home/deploy/project/kis_unified_sts/data/market"

# Regime windows for the regime-by-regime breakdown (KST calendar dates).
REGIMES: tuple[tuple[str, str, str], ...] = (
    ("2011_eu_crisis", "2011-01-01", "2011-12-31"),
    ("2012_2014_range", "2012-01-01", "2014-12-31"),
    ("2015_2016_china", "2015-01-01", "2016-12-31"),
    ("2017_semis_bull", "2017-01-01", "2017-12-31"),
    ("2018_selloff", "2018-01-01", "2018-12-31"),
    ("2019_recovery", "2019-01-01", "2019-12-31"),
    ("2020_covid", "2020-01-01", "2020-12-31"),
    ("2021_postcovid_bull", "2021-01-01", "2021-12-31"),
    ("2022_bear", "2022-01-01", "2022-12-31"),
    ("2023_rate_hikes", "2023-01-01", "2023-12-31"),
    ("2024_ai_bull", "2024-01-01", "2024-12-31"),
    ("2025_2026_ai_bull", "2025-01-01", "2026-12-31"),
)


@dataclass
class Trade:
    """A completed daily-swing round-turn trade (PnL in index points, net of cost)."""

    entry_day: date
    exit_day: date
    side: Literal["long", "short"]
    entry_price: float
    exit_price: float
    hold_days: int
    gross_pts: float
    cost_pts: float
    net_pts: float
    exit_reason: str


@dataclass
class FoldResult:
    fold_id: int
    is_start: str
    is_end: str
    oos_start: str
    oos_end: str
    trades: int
    long: int
    short: int
    win_rate: float
    total_pts: float
    avg_pts: float
    sharpe: float
    mdd_krw: float
    cagr_pct: float


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def load_daily(data_root: str) -> pd.DataFrame:
    from shared.storage.market_data_store import ParquetMarketDataStore

    store = ParquetMarketDataStore(root=Path(data_root), asset_class="futures")
    df = store.get_daily_bars(SYMBOL)
    if df.empty:
        raise RuntimeError(f"No {SYMBOL} daily bars under {data_root}")
    df = df.sort_values("datetime").reset_index(drop=True)
    # 'open' is needed for next-day entry/exit fills.
    if "open" not in df.columns:
        raise RuntimeError("daily bars missing 'open' column")
    return df


# ---------------------------------------------------------------------------
# Backtest engine (single causal pass, roll-aware, look-ahead-safe)
# ---------------------------------------------------------------------------


def run_backtest(
    df: pd.DataFrame,
    config: CTAMomentumConfig,
    *,
    trail_atr_mult: float,
    trail_activate_atr_mult: float,
    catastrophic_atr_mult: float,
    max_holding_days: int,
    slippage_ticks: float,
    commission_rate: float,
) -> tuple[list[Trade], pd.Series]:
    """One causal pass over the daily series.

    Returns (trades, daily_equity_pts) where daily_equity_pts is the cumulative
    roll-aware mark-to-market PnL in index points indexed by trading date.

    Position model: single position, long/short symmetric. Decision uses bars
    ``<= i``; fills happen at day ``i+1`` OPEN. Daily MTM uses roll-aware
    log-returns × the entry price (point-space), so a carry-spread roll step is
    never booked.
    """
    closes = df["close"].astype(float).tolist()
    opens = df["open"].astype(float).tolist()
    highs = df["high"].astype(float).tolist()
    lows = df["low"].astype(float).tolist()
    dts = [pd.Timestamp(t) for t in df["datetime"]]
    dates = [t.date() for t in dts]
    n = len(df)

    roll_rets = roll_aware_log_returns(closes, dates)  # log-returns, roll-zeroed

    entry = CTAMomentumEntry(config)
    guard = LookaheadGuard(LookaheadGuardMode.ASSERT)
    slip_pts = slippage_ticks * TICK_SIZE

    trades: list[Trade] = []
    # daily realised+unrealised cumulative PnL in points, per date
    equity_pts = np.zeros(n, dtype=float)

    # Open-position state.
    pos_side: str | None = None
    pos_entry_price = 0.0
    pos_entry_idx = -1
    pos_fav_extreme = 0.0  # highest close (long) / lowest close (short) since entry
    pos_entry_atr = 0.0
    realised_pts = 0.0

    def _atr(i: int) -> float:
        period = config.atr_period
        if i < period:
            return 0.0
        trs = []
        for j in range(i - period + 1, i + 1):
            tr = max(
                highs[j] - lows[j],
                abs(highs[j] - closes[j - 1]),
                abs(lows[j] - closes[j - 1]),
            )
            trs.append(tr)
        return float(np.mean(trs)) if trs else 0.0

    def _direction(i: int) -> str | None:
        # Causal: feed only closes/dates up to and including day i.
        sub_closes = closes[: i + 1]
        sub_dates = dates[: i + 1]
        guard.check(sub_closes, dts[: i + 1], dts[i], context_info="cta_wf_closes")
        return entry.evaluate_direction(sub_closes, sub_dates)

    for i in range(n):
        # --- mark-to-market the open position on day i's roll-aware return ---
        if pos_side is not None and i > pos_entry_idx:
            r = roll_rets[i]  # log-return close[i-1] -> close[i], roll-zeroed
            # point PnL increment ≈ entry_price * (e^r - 1) * direction
            mtm = pos_entry_price * (np.expm1(r)) * (1 if pos_side == "long" else -1)
            realised_pts += mtm
            # update favorable extreme on close
            if pos_side == "long":
                pos_fav_extreme = max(pos_fav_extreme, closes[i])
            else:
                pos_fav_extreme = min(pos_fav_extreme, closes[i])
        equity_pts[i] = realised_pts

        # --- decide exits/entries on day i's close, fill at day i+1 open -----
        nxt = i + 1
        has_next = nxt < n
        cur_atr = pos_entry_atr if pos_entry_atr > 0 else _atr(i)

        if pos_side is not None and i > pos_entry_idx:
            exit_reason = _exit_decision(
                pos_side,
                pos_entry_price,
                pos_fav_extreme,
                closes[i],
                cur_atr,
                hold_days=(dates[i] - dates[pos_entry_idx]).days,
                trail_atr_mult=trail_atr_mult,
                trail_activate_atr_mult=trail_activate_atr_mult,
                catastrophic_atr_mult=catastrophic_atr_mult,
                max_holding_days=max_holding_days,
                flip_dir=_direction(i),
            )
            if exit_reason is not None and has_next:
                fill = _fill_price(opens[nxt], pos_side, slip_pts, closing=True)
                trade = _close_trade(
                    pos_side,
                    pos_entry_price,
                    fill,
                    pos_entry_idx,
                    nxt,
                    dates,
                    closes,
                    roll_rets,
                    exit_reason,
                    commission_rate,
                )
                trades.append(trade)
                # realised_pts already reflects close[i] MTM; reconcile to fill:
                # replace the last (i->fill) leg with the actual next-open fill.
                realised_pts += _entry_to_exit_adjust(pos_side, closes[i], fill)
                realised_pts -= trade.cost_pts  # book round-turn cost
                equity_pts[i] = realised_pts
                pos_side = None

        if pos_side is None and has_next:
            direction = _direction(i)
            if direction is not None and not is_quarterly_roll_day(dates[i]):
                atr_i = _atr(i)
                if atr_i > 0:
                    fill = _fill_price(opens[nxt], direction, slip_pts, closing=False)
                    pos_side = direction
                    pos_entry_price = fill
                    pos_entry_idx = nxt
                    pos_fav_extreme = fill
                    pos_entry_atr = atr_i

    eq = pd.Series(equity_pts, index=pd.DatetimeIndex([pd.Timestamp(d) for d in dates]))
    return trades, eq


def _fill_price(open_px: float, side: str, slip_pts: float, *, closing: bool) -> float:
    """Apply slippage: pay up on entry, give up on exit (adverse both ways)."""
    if not closing:  # entry
        return open_px + slip_pts if side == "long" else open_px - slip_pts
    return open_px - slip_pts if side == "long" else open_px + slip_pts


def _entry_to_exit_adjust(side: str, close_i: float, fill: float) -> float:
    """Point adjustment from marking at close[i] to the actual next-open fill."""
    delta = fill - close_i
    return delta if side == "long" else -delta


def _exit_decision(
    side: str,
    entry_price: float,
    fav_extreme: float,
    close: float,
    atr: float,
    *,
    hold_days: int,
    trail_atr_mult: float,
    trail_activate_atr_mult: float,
    catastrophic_atr_mult: float,
    max_holding_days: int,
    flip_dir: str | None,
) -> str | None:
    """Mirror CTAMomentumExit precedence on daily closes. Returns reason or None."""
    if atr > 0:
        # 1. catastrophic backstop
        loss = (entry_price - close) if side == "long" else (close - entry_price)
        if loss >= catastrophic_atr_mult * atr:
            return "catastrophic"
        # 2. ATR chandelier trail (once activated)
        excursion = (
            (fav_extreme - entry_price)
            if side == "long"
            else (entry_price - fav_extreme)
        )
        if excursion >= trail_activate_atr_mult * atr:
            if side == "long":
                stop = fav_extreme - trail_atr_mult * atr
                if close <= stop:
                    return "trail"
            else:
                stop = fav_extreme + trail_atr_mult * atr
                if close >= stop:
                    return "trail"
    # 3. momentum flip
    if flip_dir is not None and flip_dir != side:
        return "flip"
    # 4. time cap
    if hold_days >= max_holding_days:
        return "time"
    return None


def _close_trade(
    side: str,
    entry_price: float,
    exit_price: float,
    entry_idx: int,
    exit_idx: int,
    dates: list[date],
    closes: list[float],
    roll_rets: list[float],
    reason: str,
    commission_rate: float,
) -> Trade:
    """Build a Trade with roll-aware gross PnL and round-turn cost (points)."""
    # Gross PnL on roll-aware path from entry fill to exit fill: sum the
    # roll-zeroed daily returns over the hold, applied at entry notional, then
    # add the entry-open->first-close and last-close->exit-fill legs implicitly
    # via the actual prices. Simpler + consistent: use roll-aware cumulative
    # return between entry and exit anchored on entry_price, then swap the
    # endpoints for the actual fills (entry/exit slippage already in prices).
    cum_r = sum(roll_rets[entry_idx + 1 : exit_idx + 1])
    # roll-aware "fair" exit if no roll gaps: entry_price * e^cum_r
    fair_exit = entry_price * np.exp(cum_r)
    # gross in points, roll-aware, using the actual entry/exit fills but
    # neutralising any roll carry-step inside the hold:
    raw_path = (
        (exit_price - entry_price) if side == "long" else (entry_price - exit_price)
    )
    fair_path = (
        (fair_exit - entry_price) if side == "long" else (entry_price - fair_exit)
    )
    # use the roll-aware fair_path (carry steps removed); raw_path retained only
    # if no roll day fell inside the hold (then they're equal up to fp error).
    roll_in_hold = any(
        is_quarterly_roll_day(dates[j]) for j in range(entry_idx + 1, exit_idx + 1)
    )
    gross_pts = fair_path if roll_in_hold else raw_path

    notional = (entry_price + exit_price) / 2.0 * 1.0
    cost_pts = 2.0 * commission_rate * notional  # both legs on notional (points)
    net_pts = gross_pts - cost_pts
    return Trade(
        entry_day=dates[entry_idx],
        exit_day=dates[exit_idx],
        side=side,  # type: ignore[arg-type]
        entry_price=entry_price,
        exit_price=exit_price,
        hold_days=(dates[exit_idx] - dates[entry_idx]).days,
        gross_pts=round(gross_pts, 4),
        cost_pts=round(cost_pts, 4),
        net_pts=round(net_pts, 4),
        exit_reason=reason,
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def trades_in(trades: list[Trade], start: date, end: date) -> list[Trade]:
    return [t for t in trades if start <= t.entry_day < end]


def compute_metrics(trades: list[Trade], span_days: int = 0) -> dict:
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
            "cagr_pct": 0.0,
            "median_hold_days": 0.0,
            "exit_reasons": {},
        }
    pnls = np.array([t.net_pts for t in trades])
    wins = int((pnls > 0).sum())
    sharpe = (
        float(np.mean(pnls) / np.std(pnls, ddof=1) * np.sqrt(TRADING_DAYS))
        if len(pnls) >= 2 and np.std(pnls, ddof=1) > 0
        else 0.0
    )
    # per-trade Sharpe annualised by trades/year ~ sqrt(trades/year). Use a
    # daily-equity Sharpe in the fold reporter instead; this is a per-trade proxy.
    eq, peak, mdd = 0.0, 0.0, 0.0
    for t in trades:
        eq += t.net_pts * POINT_VALUE
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
    return {
        "n_trades": len(trades),
        "long": sum(1 for t in trades if t.side == "long"),
        "short": sum(1 for t in trades if t.side == "short"),
        "win_rate": round(wins / len(trades) * 100, 1),
        "total_pts": round(float(pnls.sum()), 2),
        "total_krw": round(float(pnls.sum()) * POINT_VALUE),
        "avg_pts": round(float(pnls.mean()), 4),
        "sharpe": round(sharpe, 3),
        "mdd_krw": round(mdd),
        "median_hold_days": round(float(np.median([t.hold_days for t in trades])), 1),
        "exit_reasons": reasons,
    }


def daily_equity_sharpe(
    eq_pts: pd.Series, start: date, end: date
) -> tuple[float, float]:
    """Annualised Sharpe + CAGR-proxy from the daily equity curve over a window.

    Sharpe is on daily PnL *changes* (in points); CAGR-proxy is annualised total
    points / span (points are regime-comparable across the 16y level drift only
    loosely, so this is reported as a secondary figure)."""
    mask = (eq_pts.index >= pd.Timestamp(start)) & (eq_pts.index < pd.Timestamp(end))
    sub = eq_pts[mask]
    if len(sub) < 3:
        return 0.0, 0.0
    dpnl = sub.diff().dropna()
    if dpnl.std(ddof=1) == 0 or len(dpnl) < 2:
        sharpe = 0.0
    else:
        sharpe = float(dpnl.mean() / dpnl.std(ddof=1) * np.sqrt(TRADING_DAYS))
    span_days = max(1, (sub.index[-1] - sub.index[0]).days)
    total_pts = float(sub.iloc[-1] - sub.iloc[0])
    cagr_pts_per_yr = total_pts / span_days * 365.0
    return round(sharpe, 3), round(cagr_pts_per_yr, 2)


def side_breakdown(trades: list[Trade]) -> dict:
    out = {}
    for side in ("long", "short"):
        g = [t for t in trades if t.side == side]
        if not g:
            out[side] = {"n": 0, "win_rate": 0.0, "total_pts": 0.0}
            continue
        pnls = np.array([t.net_pts for t in g])
        out[side] = {
            "n": len(g),
            "win_rate": round(float((pnls > 0).mean() * 100), 1),
            "total_pts": round(float(pnls.sum()), 2),
        }
    return out


def print_metrics(label: str, m: dict) -> None:
    print(f"\n{'='*66}\n  {label}\n{'='*66}")
    print(f"  Trades       : {m['n_trades']}  (L={m['long']} / S={m['short']})")
    print(f"  Win rate     : {m['win_rate']:.1f}%")
    print(f"  Total PnL    : {m['total_pts']:+.2f} pts  ({m['total_krw']:+,.0f} KRW)")
    print(f"  Avg / trade  : {m['avg_pts']:+.4f} pts")
    print(f"  Sharpe(trade): {m['sharpe']:+.3f}")
    print(f"  MDD          : {m['mdd_krw']:,.0f} KRW")
    print(f"  Hold (med)   : {m['median_hold_days']:.1f} days")
    if m["exit_reasons"]:
        print(f"  Exit reasons : {m['exit_reasons']}")


# ---------------------------------------------------------------------------
# Walk-forward folds
# ---------------------------------------------------------------------------


def split_folds_years(
    df: pd.DataFrame, is_years: int, oos_years: int, step_years: int
) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    start = df["datetime"].min().normalize()
    end = df["datetime"].max().normalize()
    folds = []
    win = start
    while win + pd.DateOffset(years=is_years + oos_years) <= end + pd.Timedelta(days=1):
        is_start = win
        is_end = win + pd.DateOffset(years=is_years)
        oos_start = is_end
        oos_end = is_end + pd.DateOffset(years=oos_years)
        folds.append((is_start, is_end, oos_start, oos_end))
        win = win + pd.DateOffset(years=step_years)
    return folds


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    p = argparse.ArgumentParser(description="Walk-forward — CTA daily momentum")
    p.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    p.add_argument("--momentum-lookback", type=int, default=60)
    p.add_argument("--momentum-deadband", type=float, default=0.0)
    p.add_argument("--ma-fast", type=int, default=20)
    p.add_argument("--ma-slow", type=int, default=100)
    p.add_argument("--no-ma-filter", action="store_true")
    p.add_argument("--atr-period", type=int, default=20)
    p.add_argument("--initial-stop-atr-mult", type=float, default=3.0)
    p.add_argument("--trail-atr-mult", type=float, default=4.0)
    p.add_argument("--trail-activate-atr-mult", type=float, default=1.0)
    p.add_argument("--catastrophic-atr-mult", type=float, default=5.0)
    p.add_argument("--max-holding-days", type=int, default=60)
    p.add_argument("--slippage-ticks", type=float, default=1.0)
    p.add_argument("--commission-rate", type=float, default=COMMISSION_RATE)
    p.add_argument("--is-years", type=int, default=3)
    p.add_argument("--oos-years", type=int, default=1)
    p.add_argument("--step-years", type=int, default=1)
    p.add_argument("--output", default=".superpowers/sdd/cta_daily_walkforward.json")
    args = p.parse_args()

    df = load_daily(args.data_root)
    config = CTAMomentumConfig(
        momentum_lookback=args.momentum_lookback,
        momentum_deadband=args.momentum_deadband,
        use_ma_filter=not args.no_ma_filter,
        ma_fast_period=args.ma_fast,
        ma_slow_period=args.ma_slow,
        atr_period=args.atr_period,
        initial_stop_atr_mult=args.initial_stop_atr_mult,
        min_bars=max(args.momentum_lookback + 1, args.ma_slow, args.atr_period + 1),
    )

    print(f"\n{'#'*66}")
    print("  CTA DAILY/SWING TS-MOMENTUM — Walk-Forward (THESIS B)")
    print(
        f"  Symbol: {SYMBOL}  Window: {df['datetime'].min().date()} ~ "
        f"{df['datetime'].max().date()}  ({len(df)} daily bars)"
    )
    print(
        f"  Entry : mom_lb={config.momentum_lookback} ma={config.ma_fast_period}/"
        f"{config.ma_slow_period} ({'on' if config.use_ma_filter else 'off'}) "
        f"atr={config.atr_period}"
    )
    print(
        f"  Exit  : trail={args.trail_atr_mult}/{args.trail_activate_atr_mult}ATR "
        f"catastrophic={args.catastrophic_atr_mult}ATR max_hold={args.max_holding_days}d"
    )
    print(
        f"  Costs : commission={args.commission_rate:.5f}/leg slippage="
        f"{args.slippage_ticks}tick(s)"
    )
    print(f"{'#'*66}")

    trades, eq = run_backtest(
        df,
        config,
        trail_atr_mult=args.trail_atr_mult,
        trail_activate_atr_mult=args.trail_activate_atr_mult,
        catastrophic_atr_mult=args.catastrophic_atr_mult,
        max_holding_days=args.max_holding_days,
        slippage_ticks=args.slippage_ticks,
        commission_rate=args.commission_rate,
    )

    full = compute_metrics(trades)
    full_sharpe_daily, full_cagr = daily_equity_sharpe(
        eq,
        df["datetime"].min().date(),
        df["datetime"].max().date() + pd.Timedelta(days=1),
    )
    print_metrics("FULL 16Y (single causal pass, all trades)", full)
    print(
        f"  Sharpe(daily-equity): {full_sharpe_daily:+.3f}   CAGR-proxy(pts/yr): {full_cagr:+.2f}"
    )
    print(f"  Long/Short          : {side_breakdown(trades)}")

    # Regime-by-regime
    print(f"\n{'#'*66}\n  REGIME-BY-REGIME (entry-day attributed)\n{'#'*66}")
    print(
        f"  {'regime':<22}{'n':>4}{'L':>4}{'S':>4}{'win%':>7}{'tot_pts':>10}{'sharpeD':>9}"
    )
    regime_rows = []
    for name, s, e in REGIMES:
        sd = date.fromisoformat(s)
        ed = date.fromisoformat(e)
        g = [t for t in trades if sd <= t.entry_day <= ed]
        m = compute_metrics(g)
        shp, _ = daily_equity_sharpe(eq, sd, ed + pd.Timedelta(days=1))
        regime_rows.append(
            {
                "regime": name,
                **{
                    k: m[k]
                    for k in ("n_trades", "long", "short", "win_rate", "total_pts")
                },
                "sharpe_daily": shp,
            }
        )
        print(
            f"  {name:<22}{m['n_trades']:>4}{m['long']:>4}{m['short']:>4}"
            f"{m['win_rate']:>7.1f}{m['total_pts']:>10.2f}{shp:>9.3f}"
        )

    # Walk-forward folds
    folds = split_folds_years(df, args.is_years, args.oos_years, args.step_years)
    print(f"\n{'#'*66}")
    print(
        f"  WALK-FORWARD: {len(folds)} folds (IS={args.is_years}y/OOS={args.oos_years}y/step={args.step_years}y)"
    )
    print("  Strategy has NO fitted params per fold — IS shown for orientation;")
    print("  the honest test is the concatenation of non-overlapping OOS folds.")
    print(f"{'#'*66}")
    print(
        f"\n{'fold':>4} {'oos_window':>23} {'n':>4} {'L':>3} {'S':>3} {'win%':>6} {'tot_pts':>9} {'sharpeD':>8} {'mdd_krw':>11}"
    )
    fold_results: list[FoldResult] = []
    oos_all: list[Trade] = []
    for fid, (is_s, is_e, oos_s, oos_e) in enumerate(folds):
        g = trades_in(trades, oos_s.date(), oos_e.date())
        oos_all.extend(g)
        m = compute_metrics(g)
        shp, cagr = daily_equity_sharpe(eq, oos_s.date(), oos_e.date())
        fr = FoldResult(
            fold_id=fid,
            is_start=str(is_s.date()),
            is_end=str(is_e.date()),
            oos_start=str(oos_s.date()),
            oos_end=str(oos_e.date()),
            trades=m["n_trades"],
            long=m["long"],
            short=m["short"],
            win_rate=m["win_rate"],
            total_pts=m["total_pts"],
            avg_pts=m["avg_pts"],
            sharpe=shp,
            mdd_krw=m["mdd_krw"],
            cagr_pct=cagr,
        )
        fold_results.append(fr)
        win_lbl = f"{oos_s.date()}..{oos_e.date()}"
        print(
            f"{fid:>4} {win_lbl:>23} {m['n_trades']:>4} "
            f"{m['long']:>3} {m['short']:>3} {m['win_rate']:>6.1f} {m['total_pts']:>9.2f} "
            f"{shp:>8.3f} {m['mdd_krw']:>11,.0f}"
        )

    oos_concat = compute_metrics(oos_all)
    print_metrics("OOS CONCATENATED (all non-overlapping OOS folds)", oos_concat)
    print(f"  Long/Short (OOS)    : {side_breakdown(oos_all)}")

    n_pos = sum(1 for f in fold_results if f.total_pts > 0)
    n_with = sum(1 for f in fold_results if f.trades > 0)
    sb = side_breakdown(oos_all)
    sym_ok = sb["long"]["total_pts"] > 0 and sb["short"]["total_pts"] > 0
    print(f"\n{'='*66}\n  VERDICT INPUTS\n{'='*66}")
    print(f"  Folds with trades   : {n_with}/{len(fold_results)}")
    print(f"  OOS-profitable folds : {n_pos}/{len(fold_results)}")
    print(
        f"  OOS concat total     : {oos_concat['total_pts']:+.2f} pts ({oos_concat['total_krw']:+,.0f} KRW)"
    )
    print(f"  OOS concat Sharpe(tr): {oos_concat['sharpe']:+.3f}")
    print(
        f"  Both sides profitable: {sym_ok} (L={sb['long']['total_pts']:+.1f} / S={sb['short']['total_pts']:+.1f})"
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
                    str(df["datetime"].min().date()),
                    str(df["datetime"].max().date()),
                ],
                "n_bars": len(df),
                "config": {
                    "momentum_lookback": config.momentum_lookback,
                    "ma_fast": config.ma_fast_period,
                    "ma_slow": config.ma_slow_period,
                    "use_ma_filter": config.use_ma_filter,
                    "atr_period": config.atr_period,
                    "trail_atr_mult": args.trail_atr_mult,
                    "trail_activate_atr_mult": args.trail_activate_atr_mult,
                    "catastrophic_atr_mult": args.catastrophic_atr_mult,
                    "max_holding_days": args.max_holding_days,
                    "slippage_ticks": args.slippage_ticks,
                    "commission_rate": args.commission_rate,
                },
                "full_window": {
                    **full,
                    "sharpe_daily": full_sharpe_daily,
                    "cagr_proxy_pts_yr": full_cagr,
                },
                "full_side_breakdown": side_breakdown(trades),
                "regimes": regime_rows,
                "oos_concatenated": oos_concat,
                "oos_side_breakdown": sb,
                "folds": [asdict(f) for f in fold_results],
                "verdict_inputs": {
                    "folds_with_trades": n_with,
                    "oos_profitable_folds": n_pos,
                    "n_folds": len(fold_results),
                    "both_sides_profitable": sym_ok,
                },
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nJSON summary → {out_path}")


if __name__ == "__main__":
    main()
