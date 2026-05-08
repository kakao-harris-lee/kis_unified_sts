#!/usr/bin/env python3
"""Counterfactual analysis: Setup A/C vs RL shadow predictions.

This script is the **Phase 4 input** for the LLM-primary RL-minimization
decision (§10.2 of docs/plans/2026-05-03-llm-primary-rl-minimization.md).

Purpose
-------
Phase 2 (PR #171) demoted the RL agent to shadow_mode: its inference runs
every bar but no order is placed.  Predictions land in
``kospi.rl_shadow_predictions``.  Simultaneously, Setup A/C became the
primary entry strategy; their signals — both executed and vetoed — land in
``kospi.signals_all``.

By reconstructing "what would have happened if RL had traded", we can
measure whether RL added or destroyed value compared with Setup A/C over the
same window.  This counterfactual drives the Phase 4 gate decision (≥ 3
months after Phase 2) per v3.3 §10.4:

* If RL counterfactual Sharpe > Setup A/C AND direction agreement high
  → activate as auxiliary filter (v2 §3.2)
* Otherwise → retire or retrain RL

Target metrics for Phase 4 gate (§10.4)
----------------------------------------
* Setup A cumulative executed trades ≥ 50 (statistical significance floor)
* RL shadow predictions count ≥ 1 000 (sufficient counterfactual data)
* Both sides show ≥ 3 months of continuous coverage

Approximation caveats
---------------------
1. **Next-bar-open fill**: RL entries are executed at the *next* bar's open.
   If no subsequent bar exists (window boundary), the position is marked
   "open" and excluded from closed-trade stats.
2. **Setup A/C exit timing**: ``kospi.signals_all`` records entry intent, not
   exit timing.  When the matching exit is absent we fall back to the EOD
   (last bar) close of the same trading day.  This is labelled
   "(EOD est.)" in output.  Mark these rows ``is_eod_est=True`` in JSON/CSV.
3. **Slippage & commission**: applied symmetrically on each leg.
   ``--slippage-ticks`` is converted using ``tick_size = 0.02 pt`` for the
   KOSPI200 mini.  Commission is expressed in bps of notional
   (price × multiplier_krw_per_point).  Defaults load from
   ``config/execution.yaml::futures_contract_spec.kospi200_mini``.
4. **Multiplier**: KOSPI200 mini = 50 000 KRW / pt.  Connection-contract
   data (101S6000) uses the same index points, so the multiplier applies
   unchanged.

Usage
-----
.. code-block:: bash

    # Activate project venv first
    source .venv/bin/activate

    python scripts/analysis/setup_vs_rl_shadow_counterfactual.py \\
        --start-date 2026-05-01 --end-date 2026-07-31 \\
        --output-format table

    # Save JSON for further processing
    python scripts/analysis/setup_vs_rl_shadow_counterfactual.py \\
        --start-date 2026-05-01 --end-date 2026-07-31 \\
        --output-format json --output-file /tmp/counterfactual.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.config.loader import ConfigLoader  # noqa: E402
from shared.db.utils import clickhouse_client_from_env  # noqa: E402

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")
UTC = ZoneInfo("UTC")

# ──────────────────────────────────────────────────────────────────────────────
# Contract constants (loaded from config; these are fallback defaults only)
# ──────────────────────────────────────────────────────────────────────────────
_DEFAULT_MULTIPLIER_KRW = 50_000  # KRW / index point, KOSPI200 mini
_DEFAULT_TICK_SIZE = 0.02  # index points
_DEFAULT_COMMISSION_BPS = 1.0  # bps per side fallback
_DEFAULT_SLIPPAGE_TICKS = 1.0  # ticks adverse per side

# RL action codes
_ACTION_LONG_ENTRY = 0
_ACTION_LONG_EXIT = 1
_ACTION_SHORT_ENTRY = 2
_ACTION_SHORT_EXIT = 3
_ACTION_HOLD = 4


# ──────────────────────────────────────────────────────────────────────────────
# Config helpers
# ──────────────────────────────────────────────────────────────────────────────

def _load_contract_spec() -> dict[str, Any]:
    """Load KOSPI200 mini contract spec from execution.yaml.

    Returns:
        Dict with keys ``multiplier_krw_per_point``, ``tick_size_points``,
        ``commission_rate`` (fraction, e.g. 0.00003 = 0.003%).

    Raises:
        KeyError: if the expected YAML path is absent (caller falls back).
    """
    cfg = ConfigLoader.load("execution.yaml")
    spec: dict[str, Any] = cfg["futures_contract_spec"]["kospi200_mini"]
    return spec


def _load_min_confidence() -> float:
    """Load paper_min_confidence from rl_mppo strategy config.

    Returns:
        Float confidence threshold.  Falls back to 0.5 if config absent.
    """
    try:
        cfg = ConfigLoader.load_strategy("futures", "rl_mppo")
        return float(
            cfg["strategy"]["entry"]["params"].get("paper_min_confidence", 0.5)
        )
    except Exception:
        return 0.5


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ShadowTrade:
    """A virtual trade reconstructed from RL shadow predictions."""

    symbol: str
    direction: str          # "long" or "short"
    entry_ts: datetime
    exit_ts: datetime | None
    entry_price: float
    exit_price: float | None
    is_open: bool           # True if no exit found in window
    pnl_krw: float | None
    is_win: bool | None
    regime: str
    risk_mode: str


@dataclass
class SetupTrade:
    """An executed or EOD-estimated Setup A/C trade."""

    signal_id: str
    setup_type: str
    direction: str          # "long" or "short"
    entry_ts: datetime
    exit_ts: datetime | None
    entry_price: float
    exit_price: float | None
    executed: bool          # True = actually filled
    skip_reason: str
    is_eod_est: bool        # True = exit via EOD close fallback
    pnl_krw: float | None
    is_win: bool | None


@dataclass
class AgreementMatrix:
    """Directional agreement between RL and Setup A/C signals on same bars."""

    long_long: int = 0
    long_short: int = 0
    short_long: int = 0
    short_short: int = 0

    @property
    def total(self) -> int:
        return self.long_long + self.long_short + self.short_long + self.short_short

    @property
    def agreement_count(self) -> int:
        return self.long_long + self.short_short

    @property
    def agreement_pct(self) -> float:
        return 100.0 * self.agreement_count / self.total if self.total else 0.0


@dataclass
class PerDayStat:
    date: str
    rl_trades: int
    rl_pnl_krw: float
    setup_trades: int
    setup_pnl_krw: float
    delta_krw: float


@dataclass
class AggregateStat:
    trade_count: int
    win_count: int
    loss_count: int
    open_count: int
    gross_pnl_krw: float
    avg_pnl_krw: float
    win_rate: float
    max_drawdown_krw: float


@dataclass
class Phase4GateProgress:
    setup_executed_trades: int
    setup_target: int         # >= 50 per plan §10.4 / v2 §3.2
    setup_gate_met: bool
    rl_shadow_count: int
    rl_shadow_target: int     # >= 1000 per plan §10.4
    rl_shadow_gate_met: bool


@dataclass
class CounterfactualReport:
    generated_at: str
    start_date: str
    end_date: str
    symbol: str
    commission_bps: float
    slippage_ticks: float
    multiplier_krw: float
    tick_size: float
    min_confidence: float
    rl_shadow: AggregateStat
    setup_actual: AggregateStat
    agreement: AgreementMatrix
    per_day: list[PerDayStat]
    phase4_gate: Phase4GateProgress
    rl_trades: list[ShadowTrade] = field(default_factory=list)
    setup_trades: list[SetupTrade] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Data loading
# ──────────────────────────────────────────────────────────────────────────────

def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _window_dt(
    start: date, end: date
) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(start, datetime.min.time()).replace(tzinfo=UTC)
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time()).replace(tzinfo=UTC)
    return start_dt, end_dt


def _fetch_shadow_predictions(
    client: Any,
    symbol: str,
    start_dt: datetime,
    end_dt: datetime,
    min_confidence: float,
) -> pd.DataFrame:
    """Fetch RL shadow predictions from ClickHouse.

    Args:
        client: clickhouse_driver.Client instance.
        symbol: Futures contract symbol (e.g. '101S6000').
        start_dt: Window start (UTC-aware datetime).
        end_dt: Window end (UTC-aware datetime, exclusive).
        min_confidence: Minimum action probability to include.

    Returns:
        DataFrame with columns: ts, symbol, action, confidence, regime,
        risk_mode, risk_score, executed_setup_id.
    """
    rows = client.execute(
        """
        SELECT ts, symbol, action, confidence, regime, risk_mode,
               risk_score, executed_setup_id
        FROM kospi.rl_shadow_predictions
        WHERE symbol = %(sym)s
          AND ts >= %(start)s
          AND ts < %(end)s
          AND confidence >= %(min_conf)s
        ORDER BY ts
        """,
        {
            "sym": symbol,
            "start": start_dt.replace(tzinfo=None),
            "end": end_dt.replace(tzinfo=None),
            "min_conf": min_confidence,
        },
    )
    if not rows:
        return pd.DataFrame(
            columns=[
                "ts", "symbol", "action", "confidence",
                "regime", "risk_mode", "risk_score", "executed_setup_id",
            ]
        )
    df = pd.DataFrame(
        rows,
        columns=[
            "ts", "symbol", "action", "confidence",
            "regime", "risk_mode", "risk_score", "executed_setup_id",
        ],
    )
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df["action"] = df["action"].astype(int)
    return df


def _fetch_setup_signals(
    client: Any,
    start_dt: datetime,
    end_dt: datetime,
) -> pd.DataFrame:
    """Fetch Setup A/C signals from ClickHouse.

    Args:
        client: clickhouse_driver.Client instance.
        start_dt: Window start (UTC-aware datetime).
        end_dt: Window end (UTC-aware datetime, exclusive).

    Returns:
        DataFrame with columns: signal_id, generated_at, setup_type,
        direction, entry_price, stop_loss, take_profit, confidence,
        executed, skip_reason.
    """
    rows = client.execute(
        """
        SELECT signal_id, generated_at, setup_type, direction,
               entry_price, stop_loss, take_profit, confidence,
               executed, skip_reason
        FROM kospi.signals_all
        WHERE generated_at >= %(start)s
          AND generated_at < %(end)s
        ORDER BY generated_at
        """,
        {
            "start": start_dt.replace(tzinfo=None),
            "end": end_dt.replace(tzinfo=None),
        },
    )
    if not rows:
        return pd.DataFrame(
            columns=[
                "signal_id", "generated_at", "setup_type", "direction",
                "entry_price", "stop_loss", "take_profit", "confidence",
                "executed", "skip_reason",
            ]
        )
    df = pd.DataFrame(
        rows,
        columns=[
            "signal_id", "generated_at", "setup_type", "direction",
            "entry_price", "stop_loss", "take_profit", "confidence",
            "executed", "skip_reason",
        ],
    )
    df["generated_at"] = pd.to_datetime(df["generated_at"], utc=True)
    df["executed"] = df["executed"].astype(int)
    return df


def _fetch_minute_bars(
    client: Any,
    symbol: str,
    start_dt: datetime,
    end_dt: datetime,
) -> pd.DataFrame:
    """Fetch OHLCV minute bars from ClickHouse.

    Args:
        client: clickhouse_driver.Client instance.
        symbol: Futures symbol.
        start_dt: Window start (UTC-aware datetime).
        end_dt: Window end (UTC-aware datetime, exclusive).

    Returns:
        DataFrame indexed by ts (UTC), columns: open, high, low, close, volume.
    """
    rows = client.execute(
        """
        SELECT ts, open, high, low, close, volume
        FROM kospi.kospi200f_1m
        WHERE symbol = %(sym)s
          AND ts >= %(start)s
          AND ts < %(end)s
        ORDER BY ts
        """,
        {
            "sym": symbol,
            "start": start_dt.replace(tzinfo=None),
            "end": end_dt.replace(tzinfo=None),
        },
    )
    if not rows:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.set_index("ts").sort_index()
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Cost calculation
# ──────────────────────────────────────────────────────────────────────────────

def _trade_cost_krw(
    price: float,
    multiplier_krw: float,
    commission_bps: float,
    slippage_ticks: float,
    tick_size: float,
) -> float:
    """Compute one-side cost (commission + slippage) in KRW.

    Args:
        price: Fill price in index points.
        multiplier_krw: KRW per index point.
        commission_bps: Commission in basis points of notional.
        slippage_ticks: Adverse ticks slippage.
        tick_size: Tick size in index points.

    Returns:
        Total cost in KRW for one leg (entry or exit).
    """
    notional = price * multiplier_krw
    commission_krw = notional * (commission_bps / 10_000.0)
    slippage_krw = slippage_ticks * tick_size * multiplier_krw
    return commission_krw + slippage_krw


def _pnl_krw(
    direction: str,
    entry_price: float,
    exit_price: float,
    multiplier_krw: float,
    commission_bps: float,
    slippage_ticks: float,
    tick_size: float,
) -> float:
    """Compute net PnL in KRW for a closed position.

    Args:
        direction: 'long' or 'short'.
        entry_price: Entry fill price (index points).
        exit_price: Exit fill price (index points).
        multiplier_krw: KRW per index point.
        commission_bps: Commission bps per side.
        slippage_ticks: Adverse ticks per side.
        tick_size: Tick size in index points.

    Returns:
        Net PnL in KRW (positive = profit).
    """
    sign = 1.0 if direction == "long" else -1.0
    gross = (exit_price - entry_price) * sign * multiplier_krw
    cost = _trade_cost_krw(
        entry_price, multiplier_krw, commission_bps, slippage_ticks, tick_size
    ) + _trade_cost_krw(
        exit_price, multiplier_krw, commission_bps, slippage_ticks, tick_size
    )
    return gross - cost


# ──────────────────────────────────────────────────────────────────────────────
# Counterfactual reconstruction
# ──────────────────────────────────────────────────────────────────────────────

def _next_bar_open(bars: pd.DataFrame, signal_ts: pd.Timestamp) -> float | None:
    """Return the open price of the bar immediately after signal_ts.

    Args:
        bars: Minute-bar DataFrame indexed by ts (UTC, sorted ascending).
        signal_ts: Timestamp of the RL signal.

    Returns:
        Open price of the next bar, or None if no subsequent bar exists.
    """
    future = bars[bars.index > signal_ts]
    if future.empty:
        return None
    return float(future.iloc[0]["open"])


def _eod_close_price(bars: pd.DataFrame, signal_ts: pd.Timestamp) -> float | None:
    """Return the last close price of the trading day for signal_ts.

    Args:
        bars: Minute-bar DataFrame indexed by ts (UTC, sorted ascending).
        signal_ts: Reference timestamp (UTC).

    Returns:
        Close of last bar on the same calendar date (UTC), or None.
    """
    day_bars = bars[bars.index.date == signal_ts.date()]
    if day_bars.empty:
        return None
    return float(day_bars.iloc[-1]["close"])


def reconstruct_rl_trades(
    shadow: pd.DataFrame,
    bars: pd.DataFrame,
    multiplier_krw: float,
    commission_bps: float,
    slippage_ticks: float,
    tick_size: float,
) -> list[ShadowTrade]:
    """Walk shadow predictions chronologically and build virtual trades.

    Matching rule: LONG_ENTRY (0) opens a long; the *next* LONG_EXIT (1)
    for the same symbol closes it.  Same for SHORT_ENTRY (2) / SHORT_EXIT (3).
    Orphan entries (no subsequent exit) are emitted as open trades.

    Args:
        shadow: Shadow predictions DataFrame (ts, symbol, action, confidence,
            regime, risk_mode, risk_score, executed_setup_id).
        bars: Minute-bar DataFrame indexed by ts (UTC).
        multiplier_krw: KRW per index point.
        commission_bps: Commission bps per side.
        slippage_ticks: Adverse slippage ticks per side.
        tick_size: Tick size in index points.

    Returns:
        List of ShadowTrade objects (closed and open).
    """
    trades: list[ShadowTrade] = []
    # open_positions: direction -> (entry_ts, entry_price, regime, risk_mode)
    open_pos: dict[str, tuple[pd.Timestamp, float, str, str]] = {}

    for _, row in shadow.iterrows():
        action: int = int(row["action"])
        ts: pd.Timestamp = row["ts"]
        symbol: str = str(row["symbol"])
        regime: str = str(row.get("regime", ""))
        risk_mode: str = str(row.get("risk_mode", ""))

        if action in (_ACTION_LONG_ENTRY, _ACTION_SHORT_ENTRY):
            direction = "long" if action == _ACTION_LONG_ENTRY else "short"
            # Skip if we already have an open position in this direction
            if direction in open_pos:
                continue
            fill_price = _next_bar_open(bars, ts)
            if fill_price is None:
                # Window boundary: skip (no bar to fill against)
                continue
            open_pos[direction] = (ts, fill_price, regime, risk_mode)

        elif action in (_ACTION_LONG_EXIT, _ACTION_SHORT_EXIT):
            direction = "long" if action == _ACTION_LONG_EXIT else "short"
            if direction not in open_pos:
                continue
            entry_ts, entry_price, e_regime, e_risk_mode = open_pos.pop(direction)
            fill_price = _next_bar_open(bars, ts)
            if fill_price is None:
                # Re-insert; treat window boundary as orphan below
                open_pos[direction] = (entry_ts, entry_price, e_regime, e_risk_mode)
                continue
            net_pnl = _pnl_krw(
                direction, entry_price, fill_price,
                multiplier_krw, commission_bps, slippage_ticks, tick_size,
            )
            trades.append(
                ShadowTrade(
                    symbol=symbol,
                    direction=direction,
                    entry_ts=entry_ts.to_pydatetime(),
                    exit_ts=ts.to_pydatetime(),
                    entry_price=entry_price,
                    exit_price=fill_price,
                    is_open=False,
                    pnl_krw=net_pnl,
                    is_win=(net_pnl > 0),
                    regime=e_regime,
                    risk_mode=e_risk_mode,
                )
            )

    # Emit orphan open positions
    for direction, (entry_ts, entry_price, e_regime, e_risk_mode) in open_pos.items():
        trades.append(
            ShadowTrade(
                symbol=symbol if "symbol" in dir() else "unknown",  # type: ignore[possibly-undefined]
                direction=direction,
                entry_ts=entry_ts.to_pydatetime(),
                exit_ts=None,
                entry_price=entry_price,
                exit_price=None,
                is_open=True,
                pnl_krw=None,
                is_win=None,
                regime=e_regime,
                risk_mode=e_risk_mode,
            )
        )

    return trades


def reconstruct_setup_trades(
    signals: pd.DataFrame,
    bars: pd.DataFrame,
    multiplier_krw: float,
    commission_bps: float,
    slippage_ticks: float,
    tick_size: float,
) -> list[SetupTrade]:
    """Build Setup A/C trades from signals_all.

    For each executed signal (executed=1), attempt to find an EOD close as
    exit proxy (real exit data is not available in signals_all alone).

    Args:
        signals: signals_all DataFrame.
        bars: Minute-bar DataFrame indexed by ts (UTC).
        multiplier_krw: KRW per index point.
        commission_bps: Commission bps per side.
        slippage_ticks: Adverse slippage ticks per side.
        tick_size: Tick size in index points.

    Returns:
        List of SetupTrade objects.
    """
    trades: list[SetupTrade] = []

    for _, row in signals.iterrows():
        executed: bool = int(row["executed"]) == 1
        gen_at: pd.Timestamp = row["generated_at"]
        entry_price = float(row["entry_price"])
        direction = str(row["direction"]).lower()
        if direction not in ("long", "short"):
            continue

        # Try to find exit from rl_trades or use EOD fallback
        exit_price = _eod_close_price(bars, gen_at)
        is_eod_est = True

        pnl: float | None = None
        is_win: bool | None = None
        exit_ts: datetime | None = None

        if exit_price is not None:
            exit_ts = bars[bars.index.date == gen_at.date()].index[-1].to_pydatetime()
            pnl = _pnl_krw(
                direction, entry_price, exit_price,
                multiplier_krw, commission_bps, slippage_ticks, tick_size,
            )
            is_win = pnl > 0

        trades.append(
            SetupTrade(
                signal_id=str(row["signal_id"]),
                setup_type=str(row["setup_type"]),
                direction=direction,
                entry_ts=gen_at.to_pydatetime(),
                exit_ts=exit_ts,
                entry_price=entry_price,
                exit_price=exit_price,
                executed=executed,
                skip_reason=str(row.get("skip_reason", "")),
                is_eod_est=is_eod_est,
                pnl_krw=pnl,
                is_win=is_win,
            )
        )

    return trades


# ──────────────────────────────────────────────────────────────────────────────
# Aggregate stats
# ──────────────────────────────────────────────────────────────────────────────

def _compute_agg(trades_pnl: list[float | None]) -> AggregateStat:
    """Compute aggregate statistics from a list of PnL values.

    Args:
        trades_pnl: PnL per trade in KRW (None = open / excluded).

    Returns:
        AggregateStat dataclass.
    """
    closed = [p for p in trades_pnl if p is not None]
    open_count = trades_pnl.count(None)
    wins = [p for p in closed if p > 0]
    losses = [p for p in closed if p <= 0]
    gross = sum(closed)
    avg = gross / len(closed) if closed else 0.0
    win_rate = len(wins) / len(closed) if closed else 0.0

    # Max drawdown via equity curve
    max_dd = 0.0
    if closed:
        equity = [0.0]
        for p in closed:
            equity.append(equity[-1] + p)
        peak = equity[0]
        for e in equity:
            peak = max(peak, e)
            max_dd = min(max_dd, e - peak)

    return AggregateStat(
        trade_count=len(closed) + open_count,
        win_count=len(wins),
        loss_count=len(losses),
        open_count=open_count,
        gross_pnl_krw=gross,
        avg_pnl_krw=avg,
        win_rate=win_rate,
        max_drawdown_krw=max_dd,
    )


def _compute_agreement(
    shadow: pd.DataFrame, signals: pd.DataFrame
) -> AgreementMatrix:
    """Build directional agreement matrix between RL and Setup A/C.

    Matches signals on the same 1-minute bar (ts/generated_at truncated to
    minute).

    Args:
        shadow: Shadow predictions (filtered to entry actions only).
        signals: Setup A/C signals (all executed).

    Returns:
        AgreementMatrix with counts.
    """
    matrix = AgreementMatrix()

    if shadow.empty or signals.empty:
        return matrix

    # Round to minute
    rl_entry = shadow[shadow["action"].isin([_ACTION_LONG_ENTRY, _ACTION_SHORT_ENTRY])].copy()
    rl_entry["bar"] = rl_entry["ts"].dt.floor("min")
    rl_entry["rl_dir"] = rl_entry["action"].map(
        {_ACTION_LONG_ENTRY: "long", _ACTION_SHORT_ENTRY: "short"}
    )

    setup_entry = signals[signals["executed"] == 1].copy()
    setup_entry["bar"] = setup_entry["generated_at"].dt.floor("min")

    merged = rl_entry.merge(setup_entry[["bar", "direction"]], on="bar", how="inner")

    for _, row in merged.iterrows():
        rl_dir = str(row["rl_dir"])
        setup_dir = str(row["direction"]).lower()
        if rl_dir == "long" and setup_dir == "long":
            matrix.long_long += 1
        elif rl_dir == "long" and setup_dir == "short":
            matrix.long_short += 1
        elif rl_dir == "short" and setup_dir == "long":
            matrix.short_long += 1
        elif rl_dir == "short" and setup_dir == "short":
            matrix.short_short += 1

    return matrix


def _compute_per_day(
    rl_trades: list[ShadowTrade],
    setup_trades: list[SetupTrade],
    start_date: date,
    end_date: date,
) -> list[PerDayStat]:
    """Build per-day breakdown of RL and Setup A/C PnL.

    Args:
        rl_trades: Virtual RL trades.
        setup_trades: Setup A/C trades.
        start_date: Window start.
        end_date: Window end (inclusive).

    Returns:
        List of PerDayStat, one entry per calendar day in window.
    """
    stats: list[PerDayStat] = []
    cur = start_date
    while cur <= end_date:
        rl_day = [
            t.pnl_krw
            for t in rl_trades
            if not t.is_open and t.entry_ts.date() == cur
        ]
        setup_day = [
            t.pnl_krw
            for t in setup_trades
            if t.executed and t.pnl_krw is not None and t.entry_ts.date() == cur
        ]
        rl_pnl = sum(rl_day)
        setup_pnl = sum(setup_day)
        stats.append(
            PerDayStat(
                date=cur.isoformat(),
                rl_trades=len(rl_day),
                rl_pnl_krw=rl_pnl,
                setup_trades=len(setup_day),
                setup_pnl_krw=setup_pnl,
                delta_krw=rl_pnl - setup_pnl,
            )
        )
        cur += timedelta(days=1)
    return stats


# ──────────────────────────────────────────────────────────────────────────────
# Main analysis
# ──────────────────────────────────────────────────────────────────────────────

def run_analysis(
    start_date: date,
    end_date: date,
    symbol: str,
    commission_bps: float,
    slippage_ticks: float,
) -> CounterfactualReport:
    """Execute the full counterfactual analysis.

    Args:
        start_date: Analysis window start (inclusive).
        end_date: Analysis window end (inclusive).
        symbol: Futures symbol (default '101S6000').
        commission_bps: Commission per side in basis points.
        slippage_ticks: Adverse slippage ticks per side.

    Returns:
        CounterfactualReport dataclass with all results populated.
    """
    # Load contract spec from config
    multiplier_krw = float(_DEFAULT_MULTIPLIER_KRW)
    tick_size = float(_DEFAULT_TICK_SIZE)
    try:
        spec = _load_contract_spec()
        multiplier_krw = float(spec.get("multiplier_krw_per_point", multiplier_krw))
        tick_size = float(spec.get("tick_size_points", tick_size))
        # commission_rate in config is a fraction (0.00003), convert to bps
        # (1 bps = 0.0001, so 0.00003 = 0.3 bps)
        cfg_commission_bps = float(spec.get("commission_rate", 0.00003)) * 10_000.0
        # Only use config value if caller did not override (default check)
        if commission_bps == _DEFAULT_COMMISSION_BPS:
            commission_bps = cfg_commission_bps
    except Exception as exc:
        logger.warning("Could not load contract spec from config: %s — using defaults", exc)

    min_confidence = _load_min_confidence()
    start_dt, end_dt = _window_dt(start_date, end_date)

    logger.info(
        "Connecting to ClickHouse (symbol=%s, %s → %s, min_conf=%.2f)",
        symbol, start_date, end_date, min_confidence,
    )
    client = clickhouse_client_from_env(database="kospi")

    shadow = _fetch_shadow_predictions(client, symbol, start_dt, end_dt, min_confidence)
    signals = _fetch_setup_signals(client, start_dt, end_dt)
    bars = _fetch_minute_bars(client, symbol, start_dt, end_dt)
    client.disconnect()

    logger.info(
        "Loaded: %d shadow rows, %d setup signals, %d minute bars",
        len(shadow), len(signals), len(bars),
    )

    rl_trades = reconstruct_rl_trades(
        shadow, bars, multiplier_krw, commission_bps, slippage_ticks, tick_size
    )
    setup_trades = reconstruct_setup_trades(
        signals, bars, multiplier_krw, commission_bps, slippage_ticks, tick_size
    )

    rl_pnl_list = [t.pnl_krw if not t.is_open else None for t in rl_trades]
    setup_pnl_list = [
        t.pnl_krw if t.executed and t.pnl_krw is not None else None
        for t in setup_trades
    ]

    rl_agg = _compute_agg(rl_pnl_list)
    setup_agg = _compute_agg(setup_pnl_list)
    agreement = _compute_agreement(shadow, signals)
    per_day = _compute_per_day(rl_trades, setup_trades, start_date, end_date)

    setup_executed = sum(1 for t in setup_trades if t.executed)
    setup_target = 50  # §10.4 / v2 §3.2
    rl_shadow_target = 1_000  # §10.4
    phase4_gate = Phase4GateProgress(
        setup_executed_trades=setup_executed,
        setup_target=setup_target,
        setup_gate_met=(setup_executed >= setup_target),
        rl_shadow_count=len(shadow),
        rl_shadow_target=rl_shadow_target,
        rl_shadow_gate_met=(len(shadow) >= rl_shadow_target),
    )

    return CounterfactualReport(
        generated_at=datetime.now(UTC).isoformat(),
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        symbol=symbol,
        commission_bps=commission_bps,
        slippage_ticks=slippage_ticks,
        multiplier_krw=multiplier_krw,
        tick_size=tick_size,
        min_confidence=min_confidence,
        rl_shadow=rl_agg,
        setup_actual=setup_agg,
        agreement=agreement,
        per_day=per_day,
        phase4_gate=phase4_gate,
        rl_trades=rl_trades,
        setup_trades=setup_trades,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Output renderers
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_krw(v: float) -> str:
    """Format KRW value with sign and thousand separator."""
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:,.0f}"


def _render_table(report: CounterfactualReport) -> str:
    """Render a plain-text ASCII table report.

    Attempts to use ``rich`` if available; falls back to plain-text.

    Args:
        report: Populated CounterfactualReport.

    Returns:
        String suitable for printing to stdout.
    """
    lines: list[str] = []
    w = 70
    sep = "─" * w

    def h(title: str) -> None:
        lines.append(sep)
        lines.append(f"  {title}")
        lines.append(sep)

    def row(label: str, value: str) -> None:
        lines.append(f"  {label:<38}{value}")

    h("Setup A/C vs RL Shadow — Counterfactual Report")
    row("Window", f"{report.start_date} → {report.end_date}")
    row("Symbol", report.symbol)
    row("Commission (bps/side)", f"{report.commission_bps:.2f}")
    row("Slippage (ticks/side)", f"{report.slippage_ticks:.1f}")
    row("Multiplier (KRW/pt)", f"{report.multiplier_krw:,.0f}")
    row("Min RL confidence", f"{report.min_confidence:.2f}")
    lines.append("")

    h("RL Shadow — Counterfactual")
    rl = report.rl_shadow
    row("Total trades (closed)", str(rl.trade_count - rl.open_count))
    row("  open (no exit in window)", str(rl.open_count))
    row("  wins / losses", f"{rl.win_count} / {rl.loss_count}")
    row("  win rate", f"{rl.win_rate:.1%}")
    row("Gross PnL (KRW)", _fmt_krw(rl.gross_pnl_krw))
    row("Avg PnL/trade (KRW)", _fmt_krw(rl.avg_pnl_krw))
    row("Max drawdown (KRW)", _fmt_krw(rl.max_drawdown_krw))
    lines.append("")

    h("Setup A/C — Actual Execution (EOD-close estimated)")
    sa = report.setup_actual
    row("Executed signals", str(sum(1 for t in report.setup_trades if t.executed)))
    row("  with PnL estimate", str(sa.trade_count - sa.open_count))
    row("  wins / losses", f"{sa.win_count} / {sa.loss_count}")
    row("  win rate", f"{sa.win_rate:.1%}")
    row("Gross PnL (KRW)", _fmt_krw(sa.gross_pnl_krw))
    row("Avg PnL/trade (KRW)", _fmt_krw(sa.avg_pnl_krw))
    row("Max drawdown (KRW)", _fmt_krw(sa.max_drawdown_krw))
    lines.append("")

    h("Direction Agreement (RL entry vs Setup A/C executed)")
    ag = report.agreement
    row("RL LONG  ∩ Setup LONG  (agree)", str(ag.long_long))
    row("RL LONG  ∩ Setup SHORT (disagree)", str(ag.long_short))
    row("RL SHORT ∩ Setup LONG  (disagree)", str(ag.short_long))
    row("RL SHORT ∩ Setup SHORT (agree)", str(ag.short_short))
    row("Agreement %", f"{ag.agreement_pct:.1f}%")
    lines.append("")

    h("Phase 4 Gate Progress")
    pg = report.phase4_gate
    gate_a = "MET" if pg.setup_gate_met else f"need {pg.setup_target - pg.setup_executed_trades} more"
    gate_b = "MET" if pg.rl_shadow_gate_met else f"need {pg.rl_shadow_target - pg.rl_shadow_count} more"
    row(f"Setup executed trades (>= {pg.setup_target})", f"{pg.setup_executed_trades}  [{gate_a}]")
    row(f"RL shadow predictions (>= {pg.rl_shadow_target})", f"{pg.rl_shadow_count}  [{gate_b}]")
    lines.append("")

    h("Per-Day Breakdown")
    header = f"  {'Date':<12}{'RL Tr':>6}{'RL PnL':>14}{'Stp Tr':>8}{'Stp PnL':>14}{'Delta':>14}"
    lines.append(header)
    for pd_stat in report.per_day:
        if pd_stat.rl_trades == 0 and pd_stat.setup_trades == 0:
            continue
        lines.append(
            f"  {pd_stat.date:<12}"
            f"{pd_stat.rl_trades:>6}"
            f"{_fmt_krw(pd_stat.rl_pnl_krw):>14}"
            f"{pd_stat.setup_trades:>8}"
            f"{_fmt_krw(pd_stat.setup_pnl_krw):>14}"
            f"{_fmt_krw(pd_stat.delta_krw):>14}"
        )
    lines.append(sep)
    return "\n".join(lines)


def _report_to_dict(report: CounterfactualReport) -> dict[str, Any]:
    """Convert report to a JSON-serialisable dict.

    Args:
        report: Populated CounterfactualReport.

    Returns:
        Nested dict (all datetime fields converted to ISO strings).
    """

    def _dt(v: Any) -> Any:
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    def _trade_shadow(t: ShadowTrade) -> dict[str, Any]:
        return {
            "symbol": t.symbol,
            "direction": t.direction,
            "entry_ts": _dt(t.entry_ts),
            "exit_ts": _dt(t.exit_ts),
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "is_open": t.is_open,
            "pnl_krw": t.pnl_krw,
            "is_win": t.is_win,
            "regime": t.regime,
            "risk_mode": t.risk_mode,
        }

    def _trade_setup(t: SetupTrade) -> dict[str, Any]:
        return {
            "signal_id": t.signal_id,
            "setup_type": t.setup_type,
            "direction": t.direction,
            "entry_ts": _dt(t.entry_ts),
            "exit_ts": _dt(t.exit_ts),
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "executed": t.executed,
            "skip_reason": t.skip_reason,
            "is_eod_est": t.is_eod_est,
            "pnl_krw": t.pnl_krw,
            "is_win": t.is_win,
        }

    return {
        "generated_at": report.generated_at,
        "start_date": report.start_date,
        "end_date": report.end_date,
        "symbol": report.symbol,
        "commission_bps": report.commission_bps,
        "slippage_ticks": report.slippage_ticks,
        "multiplier_krw": report.multiplier_krw,
        "tick_size": report.tick_size,
        "min_confidence": report.min_confidence,
        "rl_shadow": asdict(report.rl_shadow),
        "setup_actual": asdict(report.setup_actual),
        "agreement": asdict(report.agreement),
        "per_day": [asdict(d) for d in report.per_day],
        "phase4_gate": asdict(report.phase4_gate),
        "rl_trades": [_trade_shadow(t) for t in report.rl_trades],
        "setup_trades": [_trade_setup(t) for t in report.setup_trades],
    }


def _render_csv(report: CounterfactualReport) -> str:
    """Render all trades as CSV (RL + Setup interleaved, type column).

    Args:
        report: Populated CounterfactualReport.

    Returns:
        CSV string.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "type", "signal_id_or_regime", "setup_type", "direction",
        "entry_ts", "exit_ts", "entry_price", "exit_price",
        "executed", "skip_reason", "is_eod_est",
        "pnl_krw", "is_win", "is_open",
    ])
    for t in report.rl_trades:
        writer.writerow([
            "rl_shadow", t.regime, "", t.direction,
            t.entry_ts.isoformat() if t.entry_ts else "",
            t.exit_ts.isoformat() if t.exit_ts else "",
            t.entry_price, t.exit_price if t.exit_price is not None else "",
            "", "", "",
            t.pnl_krw if t.pnl_krw is not None else "",
            t.is_win if t.is_win is not None else "",
            t.is_open,
        ])
    for t in report.setup_trades:
        writer.writerow([
            "setup_actual", t.signal_id, t.setup_type, t.direction,
            t.entry_ts.isoformat() if t.entry_ts else "",
            t.exit_ts.isoformat() if t.exit_ts else "",
            t.entry_price, t.exit_price if t.exit_price is not None else "",
            t.executed, t.skip_reason, t.is_eod_est,
            t.pnl_krw if t.pnl_krw is not None else "",
            t.is_win if t.is_win is not None else "",
            "",
        ])
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Counterfactual analysis: Setup A/C actual vs RL shadow predictions "
            "(§10.2, LLM-primary RL-minimization plan v3.3)."
        )
    )
    parser.add_argument(
        "--start-date",
        required=True,
        help="Window start date in YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end-date",
        default=date.today().isoformat(),
        help="Window end date in YYYY-MM-DD (default: today).",
    )
    parser.add_argument(
        "--symbol",
        default="101S6000",
        help="Futures symbol (default: 101S6000).",
    )
    parser.add_argument(
        "--output-format",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table).",
    )
    parser.add_argument(
        "--output-file",
        default="",
        help="Write output to file (default: stdout).",
    )
    parser.add_argument(
        "--commission-bps",
        type=float,
        default=_DEFAULT_COMMISSION_BPS,
        help=(
            "Commission in bps per side. Default reads from "
            "config/execution.yaml::futures_contract_spec.kospi200_mini.commission_rate; "
            "falls back to 1.0 bps."
        ),
    )
    parser.add_argument(
        "--slippage-ticks",
        type=float,
        default=_DEFAULT_SLIPPAGE_TICKS,
        help="Adverse slippage ticks per side (default: 1.0 tick = 0.02 pt).",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: WARNING).",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the counterfactual analysis script."""
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)

    report = run_analysis(
        start_date=start_date,
        end_date=end_date,
        symbol=args.symbol,
        commission_bps=args.commission_bps,
        slippage_ticks=args.slippage_ticks,
    )

    if args.output_format == "table":
        output = _render_table(report)
    elif args.output_format == "json":
        output = json.dumps(_report_to_dict(report), ensure_ascii=False, indent=2)
    else:
        output = _render_csv(report)

    if args.output_file:
        Path(args.output_file).write_text(output, encoding="utf-8")
        logger.warning("Output written to %s", args.output_file)
    else:
        sys.stdout.write(output)
        if not output.endswith("\n"):
            sys.stdout.write("\n")


if __name__ == "__main__":
    main()
