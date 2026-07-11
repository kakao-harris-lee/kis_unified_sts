"""BacktestDecisionHarness — replay Setups → RiskFilterLayer → fill simulation.

Phase 3 backtest only — **NO order placement**.  Fills are simulated against
the next bar's open price with a slippage of ``0.3 × tick_size_points`` added
in the adverse direction.

Fill simulation (spec §8.2)
---------------------------
For each accepted signal:
  1. Fill bar = the bar *after* the signal bar (next open ± slippage).
  2. Iterate subsequent bars:
     - If bar.low <= stop  (long)  or bar.high >= stop  (short) → **loss**,
       realised at stop price.
     - If bar.high >= target (long) or bar.low  <= target (short) → **win**,
       realised at target price.
     - If both hit in the same bar, the stop takes priority (conservative).
     - If ``signal.valid_until`` passes before either hit → close at that
       bar's close price (time exit — treated as a separate outcome in the
       stats, P&L is computed from entry to close).

Tick P&L accounting
-------------------
All P&L is expressed in **ticks**, not KRW:
  ticks = (exit_price - fill_price) / tick_size_points   (long)
  ticks = (fill_price - exit_price) / tick_size_points   (short)
Slippage is deducted from entry as an additional adverse tick cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from shared.backtest.market_context_replay import MarketContextReplay
from shared.decision.setup_base import Setup
from shared.decision.signal import Signal
from shared.risk.layer import LayerResult, RiskFilterLayer
from shared.risk.state import RiskStateSnapshot

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SetupStats:
    """Per-setup aggregated statistics.

    Attributes:
        trades: Total number of accepted (filled) trades.
        wins: Number of winning trades (hit take-profit).
        losses: Number of losing trades (hit stop-loss).
        total_ticks: Net ticks (after slippage) across all trades.
    """

    trades: int = 0
    wins: int = 0
    losses: int = 0
    total_ticks: float = 0.0

    @property
    def win_rate(self) -> float:
        """Fraction of trades that hit the take-profit target."""
        if self.trades == 0:
            return 0.0
        return self.wins / self.trades

    @property
    def ev_ticks(self) -> float:
        """Expected value per trade in ticks."""
        if self.trades == 0:
            return 0.0
        return self.total_ticks / self.trades


@dataclass
class TradeRecord:
    """Single trade record stored in HarnessResult for detailed analysis."""

    setup_type: str
    direction: str
    symbol: str
    bar_index: int  # index of the signal bar in the original DataFrame
    signal_entry: float
    fill_price: float
    stop: float
    target: float
    exit_price: float
    exit_reason: str  # "win" | "loss" | "time_exit" | "eod_exit"
    ticks_net: float  # net P&L in ticks (positive = profit), per contract
    layer_result: LayerResult
    size_contracts: int = 1  # contracts sized by the injected PositionSizer
    ticks_net_total: float = 0.0  # ticks_net × size_contracts (for portfolio P&L)
    # Bar indices (into the replay DataFrame) where the fill and the exit
    # executed. Populated by ``_simulate_fill`` — additive, semantics-neutral
    # bookkeeping consumed by :class:`~shared.backtest.vbt_harness_runner.
    # VbtHarnessRunner` to build an independent ``vbt.Portfolio.from_orders``
    # ledger for parity cross-check. ``None`` only on records not produced by
    # the fill simulator (e.g. hand-built test fixtures).
    fill_bar_index: int | None = None
    exit_bar_index: int | None = None


@dataclass
class HarnessResult:
    """Aggregated result of a full backtest harness run.

    Attributes:
        per_setup: Per-setup statistics keyed by ``Signal.setup_type``.
        total_candidates: Total signals generated (before filtering).
        total_accepted: Signals accepted by the filter layer.
        total_rejected_by_filter: Signals rejected by the filter layer.
        trades: Detailed trade-level records (one per accepted signal).
    """

    per_setup: dict[str, SetupStats] = field(default_factory=dict)
    total_candidates: int = 0
    total_accepted: int = 0
    total_rejected_by_filter: int = 0
    trades: list[TradeRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


class BacktestDecisionHarness:
    """Replay a :class:`MarketContextReplay` through Setups and RiskFilterLayer.

    Args:
        setups: List of :class:`~shared.decision.setup_base.Setup` instances
            to evaluate on each bar.
        filter_layer: A :class:`~shared.risk.layer.RiskFilterLayer` applied
            to every candidate signal.
        state: Initial :class:`~shared.risk.state.RiskStateSnapshot` used for
            every filter evaluation (immutable; harness does not mutate it).
        tick_size_points: Tick size in price points (e.g. 0.05 for KOSPI200
            mini).  Used to compute slippage and convert P&L to ticks.
    """

    _SLIPPAGE_MULT: float = 0.3  # spec §8.2: 0.3 × tick_size_points

    def __init__(
        self,
        setups: list[Setup],
        filter_layer: RiskFilterLayer,
        state: RiskStateSnapshot,
        tick_size_points: float,
        *,
        sizer: Any | None = None,
        account_equity_krw: float = 0.0,
    ) -> None:
        """Instantiate the harness.

        Args:
            setups: Setup instances to evaluate on each bar.
            filter_layer: RiskFilterLayer applied to every candidate.
            state: Initial RiskStateSnapshot (immutable in the harness).
            tick_size_points: Tick size for slippage + P&L conversion.
            sizer: Optional PositionSizer (e.g.
                :class:`~shared.strategy.position.sizers.FixedFractionalFuturesSizer`).
                When provided, :meth:`PositionSizer.calculate` is invoked per
                accepted signal and the returned contract count populates
                ``TradeRecord.size_contracts`` + ``ticks_net_total``.
                When ``None`` (backtest-before-sizing mode), every trade is
                recorded at ``size_contracts=1``.
            account_equity_krw: Account equity passed to the sizer. Only
                consulted when ``sizer`` is provided.
        """
        if tick_size_points <= 0:
            raise ValueError(f"tick_size_points must be > 0, got {tick_size_points}")
        self._setups = list(setups)
        self._filter_layer = filter_layer
        self._state = state
        self._tick_size = tick_size_points
        self._slippage = self._SLIPPAGE_MULT * tick_size_points
        self._sizer = sizer
        self._account_equity_krw = account_equity_krw

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, replay: MarketContextReplay) -> HarnessResult:
        """Execute the full backtest replay and return aggregated results.

        Args:
            replay: A :class:`MarketContextReplay` over the historical data.

        Returns:
            A :class:`HarnessResult` with per-setup statistics and trade records.
        """
        result = HarnessResult()
        # Delegate to the indexed inner loop which needs random-access to the
        # raw OHLCV arrays for fill simulation.
        return self._run_indexed(replay.df, replay, result)

    def _run_indexed(
        self,
        df: pd.DataFrame,
        replay: MarketContextReplay,
        result: HarnessResult,
    ) -> HarnessResult:
        """Core indexed replay loop."""
        from shared.backtest.market_context_replay import _WARMUP_BARS  # noqa: PLC0415

        n = len(df)
        if n <= _WARMUP_BARS:
            return result

        # Pre-extract arrays for fill simulation
        opens = df["open"].to_numpy(dtype=float)
        highs = df["high"].to_numpy(dtype=float)
        lows = df["low"].to_numpy(dtype=float)
        closes = df["close"].to_numpy(dtype=float)
        ts_col = df["timestamp"]

        # KST session date per bar — used in _simulate_fill to bound fills
        # and exits to the same trading session as the signal. Without this,
        # a signal near EOD gets "filled" at the next trading session's
        # open (multi-hour gap) and its exit can drift across weekends,
        # massively inflating ticks_net.
        session_dates: list[date] = []
        for i in range(n):
            ts = pd.Timestamp(ts_col.iloc[i])
            if ts.tzinfo is None:
                ts = ts.tz_localize("Asia/Seoul")
            else:
                ts = ts.tz_convert("Asia/Seoul")
            session_dates.append(ts.date())

        # iter_contexts yields bars at positions WARMUP_BARS..n-1 (skipping those
        # with no prev_close, i.e. the first session day).  We zip with the
        # bar index to know which row in df we are at.
        bar_pos = _WARMUP_BARS - 1  # will be incremented at start of loop

        for ctx in replay.iter_contexts():
            bar_pos += 1
            # Safety: don't overflow
            if bar_pos >= n:
                break

            # If timestamp doesn't match (bar was skipped for prev_close), advance
            # bar_pos until they align.
            while bar_pos < n - 1:
                df_ts_naive = pd.Timestamp(ts_col.iloc[bar_pos])
                if df_ts_naive.tzinfo is not None:
                    df_ts_naive = df_ts_naive.tz_localize(None)
                ctx_ts_naive = pd.Timestamp(ctx.now)
                if ctx_ts_naive.tzinfo is not None:
                    ctx_ts_naive = ctx_ts_naive.tz_localize(None)
                if abs((df_ts_naive - ctx_ts_naive).total_seconds()) < 60:
                    break
                bar_pos += 1

            for setup in self._setups:
                candidate: Signal | None = setup.check(ctx)
                if candidate is None:
                    continue

                result.total_candidates += 1

                # Run filter layer
                layer_result = self._filter_layer.evaluate(candidate, self._state)

                if not layer_result.passed:
                    result.total_rejected_by_filter += 1
                    continue

                result.total_accepted += 1

                # Simulate fill
                trade = self._simulate_fill(
                    signal=candidate,
                    signal_bar_idx=bar_pos,
                    layer_result=layer_result,
                    opens=opens,
                    highs=highs,
                    lows=lows,
                    closes=closes,
                    ts_col=ts_col,
                    session_dates=session_dates,
                    n=n,
                )
                if trade is not None:
                    # Size the trade. When no sizer is injected we record 1
                    # contract per fill (pre-sizing backtest mode); otherwise
                    # the sizer turns signal + equity + state into a contract
                    # count and we apply the RiskFilterLayer's size_multiplier.
                    if self._sizer is not None:
                        raw_size = self._sizer.calculate(
                            signal=candidate,
                            account_balance=self._account_equity_krw,
                            current_positions=[],
                            market_context=None,
                        )
                        scaled = int(
                            max(1, round(raw_size * layer_result.size_multiplier))
                        )
                        trade.size_contracts = scaled
                    else:
                        trade.size_contracts = 1
                    trade.ticks_net_total = trade.ticks_net * trade.size_contracts

                    result.trades.append(trade)
                    # Update per-setup stats. total_ticks is kept per-contract
                    # so SetupStats.ev_ticks remains comparable to the Phase 3
                    # spec gate (EV > 0.5 tick). Portfolio-level ticks are
                    # available by summing TradeRecord.ticks_net_total.
                    stats = result.per_setup.setdefault(
                        candidate.setup_type, SetupStats()
                    )
                    stats.trades += 1
                    stats.total_ticks += trade.ticks_net
                    if trade.exit_reason == "win":
                        stats.wins += 1
                    elif trade.exit_reason == "loss":
                        stats.losses += 1
                    # time_exit / eod_exit count as trades but not win or loss

        return result

    # ------------------------------------------------------------------
    # Fill simulation
    # ------------------------------------------------------------------

    def _simulate_fill(
        self,
        *,
        signal: Signal,
        signal_bar_idx: int,
        layer_result: LayerResult,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        ts_col: pd.Series,
        session_dates: list[date] | None = None,
        n: int,
    ) -> TradeRecord | None:
        """Simulate trade entry and exit, returning a TradeRecord.

        Entry: next bar's open ± slippage (adverse direction).  Fill is
        skipped (returns None) if the next bar is in a different trading
        session than the signal bar — a signal at session close cannot
        legitimately execute at the next session's open hours later.

        Exit: iterate forward bars checking stop/target/expiry.  The loop
        terminates at the end of the signal's session even if stop/target
        were not hit ("eod_exit"), preventing a single trade from
        accumulating days of price drift.
        """
        fill_bar = signal_bar_idx + 1
        if fill_bar >= n:
            # No next bar — cannot fill
            return None

        # Session-boundary check: intraday-only — drop fills that would
        # straddle a session break.
        if (
            session_dates is not None
            and session_dates[fill_bar] != session_dates[signal_bar_idx]
        ):
            return None

        signal_session = (
            session_dates[signal_bar_idx] if session_dates is not None else None
        )

        fill_open = opens[fill_bar]
        is_long = signal.direction == "long"

        # Apply slippage adversely
        if is_long:
            fill_price = fill_open + self._slippage  # pay more for longs
        else:
            fill_price = fill_open - self._slippage  # sell lower for shorts

        # Sanity check: if the fill price is already past the stop loss,
        # the next-bar open gapped beyond our protection. Treat this as
        # "cannot fill" (operator would not actually submit the order).
        # Without this the exit loop immediately "hits" the stop and
        # labels it a loss, but the tick math is positive (because we
        # filled favorable of the stop) — producing a ±huge-ticks win
        # mislabelled as loss.
        if is_long and fill_price <= signal.stop_loss:
            return None
        if not is_long and fill_price >= signal.stop_loss:
            return None

        stop = signal.stop_loss
        target = signal.take_profit
        valid_until = signal.valid_until

        exit_price: float | None = None
        exit_reason: str | None = None
        # Bar index (into the replay DataFrame) where the exit executes. Set at
        # every exit branch: equals the loop var ``j`` for in-loop stop/target/
        # time exits, and ``last_same_session_idx`` for EOD/fallback exits.
        # Additive bookkeeping only — no effect on exit_price / exit_reason.
        exit_bar_idx: int | None = None

        # Iterate bars after the fill bar to find exit
        last_same_session_idx = fill_bar
        for j in range(fill_bar + 1, n):
            # Stop at session boundary — force EOD close on the last same-session bar.
            if signal_session is not None and session_dates[j] != signal_session:
                exit_price = closes[last_same_session_idx]
                exit_reason = "eod_exit"
                exit_bar_idx = last_same_session_idx
                break
            last_same_session_idx = j

            bar_high = highs[j]
            bar_low = lows[j]
            bar_close = closes[j]
            bar_ts = pd.Timestamp(ts_col.iloc[j])
            if bar_ts.tzinfo is not None:
                bar_ts_aware = bar_ts
            else:
                bar_ts_aware = bar_ts.tz_localize("Asia/Seoul")

            # Check time expiry first (convert signal valid_until to comparable ts)
            if valid_until is not None:
                vu = pd.Timestamp(valid_until)
                if vu.tzinfo is None:
                    vu = vu.tz_localize("Asia/Seoul")
                if bar_ts_aware > vu:
                    exit_price = bar_close
                    exit_reason = "time_exit"
                    exit_bar_idx = j
                    break

            if is_long:
                # Stop: low <= stop (loss takes priority when both hit)
                hit_stop = bar_low <= stop
                hit_target = bar_high >= target
                if hit_stop:
                    exit_price = stop
                    exit_reason = "loss"
                    exit_bar_idx = j
                    break
                if hit_target:
                    exit_price = target
                    exit_reason = "win"
                    exit_bar_idx = j
                    break
            else:
                # Short
                hit_stop = bar_high >= stop
                hit_target = bar_low <= target
                if hit_stop:
                    exit_price = stop
                    exit_reason = "loss"
                    exit_bar_idx = j
                    break
                if hit_target:
                    exit_price = target
                    exit_reason = "win"
                    exit_bar_idx = j
                    break

        if exit_price is None:
            # Ran out of bars without hitting stop/target/expiry/EOD.
            # Fall back to the last same-session close (never cross a session boundary).
            exit_price = closes[last_same_session_idx]
            exit_reason = "time_exit"
            exit_bar_idx = last_same_session_idx

        # Compute P&L in ticks
        if is_long:
            ticks_raw = (exit_price - fill_price) / self._tick_size
        else:
            ticks_raw = (fill_price - exit_price) / self._tick_size

        return TradeRecord(
            setup_type=signal.setup_type,
            direction=signal.direction,
            symbol=signal.symbol,
            bar_index=signal_bar_idx,
            signal_entry=signal.entry_price,
            fill_price=fill_price,
            stop=stop,
            target=target,
            exit_price=exit_price,
            exit_reason=exit_reason,
            ticks_net=ticks_raw,
            layer_result=layer_result,
            fill_bar_index=fill_bar,
            exit_bar_index=exit_bar_idx,
        )
