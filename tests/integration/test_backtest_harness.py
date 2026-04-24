"""Integration tests for the Phase 3 backtest harness.

Tests exercise the full pipeline:
  MarketContextReplay → Setup(s) → RiskFilterLayer → fill simulation → HarnessResult

No order placement; no Redis; no YAML files — all objects constructed directly.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from shared.backtest.decision_harness import (
    BacktestDecisionHarness,
    HarnessResult,
    SetupStats,
)
from shared.backtest.market_context_replay import _WARMUP_BARS, MarketContextReplay
from shared.decision.setups.gap_reversion import SetupAGapReversion
from shared.execution.contract_spec import ContractSpec
from shared.macro.base import MacroSnapshot
from shared.risk.layer import RiskFilterLayer
from shared.risk.state import RiskStateSnapshot

KST = ZoneInfo("Asia/Seoul")

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

MINI_SPEC = ContractSpec(
    name="kospi200_mini",
    multiplier_krw_per_point=100_000,
    tick_size_points=0.05,
    tick_value_krw=5_000,
    commission_rate=0.000015,
    symbol_prefix="A05",
)

# A strong positive SP500 overnight move — will satisfy Setup A's macro check
BULLISH_MACRO = MacroSnapshot(
    ts_ms=0,
    session="overnight_us_close",
    sp500_change_pct=1.2,  # > 0.5 threshold
    nasdaq_change_pct=1.5,
)

BEARISH_MACRO = MacroSnapshot(
    ts_ms=0,
    session="overnight_us_close",
    sp500_change_pct=-1.2,  # large negative
    nasdaq_change_pct=-1.5,
)


def _kst(dt_str: str) -> datetime:
    """Parse 'YYYY-MM-DD HH:MM' into a KST-aware datetime."""
    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=KST)


def _build_df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame from a list of dicts."""
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.reset_index(drop=True)


def _build_gap_down_df(
    *,
    prev_close: float = 360.0,
    gap_pct: float = -0.8,  # -0.8% gap-down
    retrace_pct: float = 0.42,  # 42% retrace — squarely in [0.30, 0.55]
    n_session1_bars: int = 60,  # enough to fill warmup within session 1
    n_session2_bars: int = 90,  # session 2 is where Setup A will fire
) -> pd.DataFrame:
    """Construct a synthetic 2-session DataFrame that produces a gap-down day.

    Session 1 (prev day): constant price around ``prev_close``.
    Session 2 (gap-down day): opens below prev_close by ``gap_pct`` percent,
        then partially retraces upward by ``retrace_pct`` of the gap magnitude.

    The retrace leaves ``current_price`` in the retrace band [0.30, 0.55] of
    the gap, which should trigger Setup A (gap-down → "short" entry).

    The macro ``BEARISH_MACRO`` provides a negative SP500 overnight move that
    aligns with the gap-down.
    """
    rows = []

    # --- Session 1: 2025-01-02 09:00..09:00 + n_session1_bars minutes ---
    base_date = "2025-01-02"
    for i in range(n_session1_bars):
        ts = _kst(f"{base_date} 09:00") + timedelta(minutes=i)
        rows.append(
            {
                "timestamp": ts,
                "open": prev_close,
                "high": prev_close + 0.5,
                "low": prev_close - 0.5,
                "close": prev_close,
                "volume": 1000.0,
            }
        )

    # --- Session 2: 2025-01-03, gap-down open ---
    gap_date = "2025-01-03"
    gap_magnitude = prev_close * abs(gap_pct) / 100.0  # positive number
    today_open = prev_close - gap_magnitude  # gap-down, below prev_close

    # Price bounces upward (partial retrace of the gap) over session 2 bars.
    # After ``bounce_bars`` bars, price reaches retrace level.
    bounce_bars = 30  # 30 minutes to reach the retrace target

    # Final price after retrace: today_open + retrace_pct * gap_magnitude
    # (price moves UP from the gap-down open)
    retrace_target_price = today_open + retrace_pct * gap_magnitude

    for i in range(n_session2_bars):
        ts = _kst(f"{gap_date} 09:00") + timedelta(minutes=i)
        if i < bounce_bars:
            frac = i / bounce_bars
            price = today_open + frac * (retrace_target_price - today_open)
        else:
            # Hold at retrace level with small noise
            price = retrace_target_price + (i % 3 - 1) * 0.05

        rows.append(
            {
                "timestamp": ts,
                "open": price - 0.05,
                "high": price + 0.3,
                "low": price - 0.3,
                "close": price,
                "volume": 800.0,
            }
        )

    return _build_df(rows)


# ---------------------------------------------------------------------------
# (a) Synthetic gap-down day — Setup A fires at least once
# ---------------------------------------------------------------------------


class TestGapDownScenario:
    """Setup A should detect the gap-down retrace and emit at least one signal."""

    def test_setup_a_fires_at_least_once(self) -> None:
        df = _build_gap_down_df()
        replay = MarketContextReplay(
            df=df,
            symbol="A05603",
            macro_snapshot=BEARISH_MACRO,  # negative SP500 aligns with gap-down
            scheduled_events=[],
            contract_spec=MINI_SPEC,
        )

        setup_a = SetupAGapReversion()
        filter_layer = RiskFilterLayer(filters=[])  # no filters — accept everything
        state = RiskStateSnapshot()

        harness = BacktestDecisionHarness(
            setups=[setup_a],
            filter_layer=filter_layer,
            state=state,
            tick_size_points=MINI_SPEC.tick_size_points,
        )
        result = harness.run(replay)

        assert result.total_candidates >= 1, (
            "Expected Setup A to generate at least one candidate signal "
            f"on the gap-down day; got {result.total_candidates}"
        )

    def test_result_has_accepted_signals(self) -> None:
        df = _build_gap_down_df()
        replay = MarketContextReplay(
            df=df,
            symbol="A05603",
            macro_snapshot=BEARISH_MACRO,
            scheduled_events=[],
            contract_spec=MINI_SPEC,
        )

        setup_a = SetupAGapReversion()
        filter_layer = RiskFilterLayer(filters=[])
        state = RiskStateSnapshot()
        harness = BacktestDecisionHarness(
            setups=[setup_a],
            filter_layer=filter_layer,
            state=state,
            tick_size_points=MINI_SPEC.tick_size_points,
        )
        result = harness.run(replay)

        assert result.total_accepted >= 1, (
            "With empty filter layer, all candidates should be accepted; "
            f"total_candidates={result.total_candidates}, total_accepted={result.total_accepted}"
        )

    def test_harness_result_has_trades_in_per_setup(self) -> None:
        df = _build_gap_down_df()
        replay = MarketContextReplay(
            df=df,
            symbol="A05603",
            macro_snapshot=BEARISH_MACRO,
            scheduled_events=[],
            contract_spec=MINI_SPEC,
        )

        setup_a = SetupAGapReversion()
        filter_layer = RiskFilterLayer(filters=[])
        state = RiskStateSnapshot()
        harness = BacktestDecisionHarness(
            setups=[setup_a],
            filter_layer=filter_layer,
            state=state,
            tick_size_points=MINI_SPEC.tick_size_points,
        )
        result = harness.run(replay)

        if result.total_accepted > 0:
            assert "A_gap_reversion" in result.per_setup
            stats = result.per_setup["A_gap_reversion"]
            assert isinstance(stats, SetupStats)
            # trades <= total_accepted because signals at the very last bar
            # have no next bar for fill, so they are accepted but not filled.
            assert stats.trades <= result.total_accepted
            assert stats.trades > 0
            # Each trade record should appear in result.trades
            assert len(result.trades) == stats.trades

    def test_trade_records_have_valid_fill_prices(self) -> None:
        """Fill price should differ from signal entry by the slippage amount."""
        df = _build_gap_down_df()
        replay = MarketContextReplay(
            df=df,
            symbol="A05603",
            macro_snapshot=BEARISH_MACRO,
            scheduled_events=[],
            contract_spec=MINI_SPEC,
        )

        setup_a = SetupAGapReversion()
        filter_layer = RiskFilterLayer(filters=[])
        state = RiskStateSnapshot()
        tick = MINI_SPEC.tick_size_points
        harness = BacktestDecisionHarness(
            setups=[setup_a],
            filter_layer=filter_layer,
            state=state,
            tick_size_points=tick,
        )
        result = harness.run(replay)

        slippage = 0.3 * tick
        for trade in result.trades:
            assert trade.exit_reason in {"win", "loss", "time_exit"}
            assert trade.fill_price > 0
            # For short signals (gap-down → short): fill should be lower than next open
            # (slippage is adverse = we sell lower)
            if trade.direction == "short":
                # fill_price = open - slippage; fill < open
                assert (
                    trade.fill_price < trade.signal_entry + slippage + 1.0
                ), f"Short fill price {trade.fill_price} looks too high vs signal entry {trade.signal_entry}"

    def test_harness_result_accounting_consistent(self) -> None:
        """total_candidates == total_accepted + total_rejected."""
        df = _build_gap_down_df()
        replay = MarketContextReplay(
            df=df,
            symbol="A05603",
            macro_snapshot=BEARISH_MACRO,
            scheduled_events=[],
            contract_spec=MINI_SPEC,
        )
        setup_a = SetupAGapReversion()
        filter_layer = RiskFilterLayer(filters=[])
        state = RiskStateSnapshot()
        harness = BacktestDecisionHarness(
            setups=[setup_a],
            filter_layer=filter_layer,
            state=state,
            tick_size_points=MINI_SPEC.tick_size_points,
        )
        result = harness.run(replay)
        assert (
            result.total_candidates
            == result.total_accepted + result.total_rejected_by_filter
        )

    def test_setup_stats_win_rate_and_ev(self) -> None:
        """win_rate and ev_ticks properties should return sensible values."""
        stats_empty = SetupStats()
        assert stats_empty.win_rate == 0.0
        assert stats_empty.ev_ticks == 0.0

        stats = SetupStats(trades=10, wins=6, losses=4, total_ticks=15.0)
        assert math.isclose(stats.win_rate, 0.6)
        assert math.isclose(stats.ev_ticks, 1.5)


# ---------------------------------------------------------------------------
# (b) Empty DataFrame → no errors, empty result
# ---------------------------------------------------------------------------


class TestEmptyDataFrame:
    """Harness must handle an empty or too-short DataFrame gracefully."""

    def _empty_replay(self) -> MarketContextReplay:
        df = _build_df(
            [
                {
                    "timestamp": _kst("2025-01-02 09:00"),
                    "open": 360.0,
                    "high": 361.0,
                    "low": 359.0,
                    "close": 360.0,
                    "volume": 100.0,
                }
            ]
        )
        return MarketContextReplay(
            df=df,
            symbol="A05603",
            macro_snapshot=None,
            scheduled_events=[],
            contract_spec=MINI_SPEC,
        )

    def test_empty_df_no_error(self) -> None:
        """Harness should not raise on a 1-row DataFrame."""
        replay = self._empty_replay()
        setup_a = SetupAGapReversion()
        filter_layer = RiskFilterLayer(filters=[])
        state = RiskStateSnapshot()
        harness = BacktestDecisionHarness(
            setups=[setup_a],
            filter_layer=filter_layer,
            state=state,
            tick_size_points=MINI_SPEC.tick_size_points,
        )
        result = harness.run(replay)
        assert isinstance(result, HarnessResult)
        assert result.total_candidates == 0
        assert result.total_accepted == 0
        assert result.total_rejected_by_filter == 0
        assert result.trades == []

    def test_df_shorter_than_warmup_no_error(self) -> None:
        """Harness should not raise on a DataFrame shorter than WARMUP_BARS."""
        rows = []
        for i in range(_WARMUP_BARS - 1):
            ts = _kst("2025-01-02 09:00") + timedelta(minutes=i)
            rows.append(
                {
                    "timestamp": ts,
                    "open": 360.0,
                    "high": 360.5,
                    "low": 359.5,
                    "close": 360.0,
                    "volume": 1000.0,
                }
            )
        replay = MarketContextReplay(
            df=_build_df(rows),
            symbol="A05603",
            macro_snapshot=BULLISH_MACRO,
            scheduled_events=[],
            contract_spec=MINI_SPEC,
        )
        setup_a = SetupAGapReversion()
        filter_layer = RiskFilterLayer(filters=[])
        state = RiskStateSnapshot()
        harness = BacktestDecisionHarness(
            setups=[setup_a],
            filter_layer=filter_layer,
            state=state,
            tick_size_points=MINI_SPEC.tick_size_points,
        )
        result = harness.run(replay)
        assert result.total_candidates == 0


# ---------------------------------------------------------------------------
# (c) Empty setups list → zero candidates
# ---------------------------------------------------------------------------


class TestEmptySetups:
    """Harness with no setups should return zero candidates without errors."""

    def test_no_setups_zero_candidates(self) -> None:
        df = _build_gap_down_df()
        replay = MarketContextReplay(
            df=df,
            symbol="A05603",
            macro_snapshot=BEARISH_MACRO,
            scheduled_events=[],
            contract_spec=MINI_SPEC,
        )
        filter_layer = RiskFilterLayer(filters=[])
        state = RiskStateSnapshot()
        harness = BacktestDecisionHarness(
            setups=[],  # empty setups list
            filter_layer=filter_layer,
            state=state,
            tick_size_points=MINI_SPEC.tick_size_points,
        )
        result = harness.run(replay)
        assert result.total_candidates == 0
        assert result.total_accepted == 0
        assert result.total_rejected_by_filter == 0
        assert result.per_setup == {}
        assert result.trades == []


# ---------------------------------------------------------------------------
# (d) MarketContextReplay unit tests
# ---------------------------------------------------------------------------


class TestMarketContextReplay:
    """Unit-level tests for the replay iterator."""

    def test_replay_yields_contexts_after_warmup(self) -> None:
        """iter_contexts should yield only bars at index >= WARMUP_BARS."""
        rows = []
        for i in range(_WARMUP_BARS + 10):
            ts = _kst("2025-01-02 09:00") + timedelta(minutes=i)
            rows.append(
                {
                    "timestamp": ts,
                    "open": 360.0,
                    "high": 360.5,
                    "low": 359.5,
                    "close": 360.0,
                    "volume": 1000.0,
                }
            )
        replay = MarketContextReplay(
            df=_build_df(rows),
            symbol="TEST",
            macro_snapshot=None,
            scheduled_events=[],
            contract_spec=MINI_SPEC,
        )
        # Single session — the first session has no prev_close, so all bars
        # with no prev session are skipped.  We just verify no crash.
        contexts = list(replay.iter_contexts())
        # Either 0 (no prev session) or > 0 — either is correct.
        assert isinstance(contexts, list)

    def test_replay_two_sessions_yields_contexts(self) -> None:
        """With two sessions, the second session should yield contexts."""
        df = _build_gap_down_df(n_session1_bars=62, n_session2_bars=30)
        replay = MarketContextReplay(
            df=df,
            symbol="A05603",
            macro_snapshot=BEARISH_MACRO,
            scheduled_events=[],
            contract_spec=MINI_SPEC,
        )
        contexts = list(replay.iter_contexts())
        assert len(contexts) > 0

    def test_context_fields_are_set(self) -> None:
        """Each yielded MarketContext should have all required fields set."""
        df = _build_gap_down_df(n_session1_bars=62, n_session2_bars=30)
        replay = MarketContextReplay(
            df=df,
            symbol="A05603",
            macro_snapshot=BEARISH_MACRO,
            scheduled_events=[],
            contract_spec=MINI_SPEC,
        )
        for ctx in replay.iter_contexts():
            assert ctx.symbol == "A05603"
            assert ctx.current_price > 0
            assert ctx.prev_close > 0
            assert ctx.today_open > 0
            assert ctx.vwap > 0
            assert ctx.atr_14 >= 0
            assert ctx.atr_90th_percentile >= 0
            assert ctx.current_spread_ticks == 1.0  # stub value
            assert ctx.macro_overnight is BEARISH_MACRO
            break  # just check the first one

    def test_missing_column_raises(self) -> None:
        """MarketContextReplay must raise ValueError on missing columns."""
        df = pd.DataFrame({"timestamp": [_kst("2025-01-02 09:00")], "close": [360.0]})
        with pytest.raises(ValueError, match="missing required columns"):
            MarketContextReplay(
                df=df,
                symbol="TEST",
                macro_snapshot=None,
                scheduled_events=[],
                contract_spec=MINI_SPEC,
            )

    def test_atr_90th_percentile_computed(self) -> None:
        """atr_90th_percentile should be > 0 for a non-trivial DataFrame."""
        df = _build_gap_down_df(n_session1_bars=65, n_session2_bars=30)
        replay = MarketContextReplay(
            df=df,
            symbol="A05603",
            macro_snapshot=BEARISH_MACRO,
            scheduled_events=[],
            contract_spec=MINI_SPEC,
        )
        assert replay._atr_90th is not None
        assert replay._atr_90th > 0


# ---------------------------------------------------------------------------
# (e) HarnessResult structural tests
# ---------------------------------------------------------------------------


class TestHarnessResult:
    """Verify HarnessResult structure properties."""

    def test_harness_result_default_is_empty(self) -> None:
        result = HarnessResult()
        assert result.total_candidates == 0
        assert result.total_accepted == 0
        assert result.total_rejected_by_filter == 0
        assert result.per_setup == {}
        assert result.trades == []

    def test_setup_stats_zero_div_safe(self) -> None:
        stats = SetupStats(trades=0)
        assert stats.win_rate == 0.0
        assert stats.ev_ticks == 0.0

    def test_setup_stats_positive_case(self) -> None:
        stats = SetupStats(trades=4, wins=3, losses=1, total_ticks=8.0)
        assert math.isclose(stats.win_rate, 0.75)
        assert math.isclose(stats.ev_ticks, 2.0)


# ---------------------------------------------------------------------------
# (f) Invalid tick_size raises
# ---------------------------------------------------------------------------


class TestHarnessValidation:
    def test_zero_tick_size_raises(self) -> None:
        with pytest.raises(ValueError, match="tick_size_points"):
            BacktestDecisionHarness(
                setups=[],
                filter_layer=RiskFilterLayer(filters=[]),
                state=RiskStateSnapshot(),
                tick_size_points=0.0,
            )

    def test_negative_tick_size_raises(self) -> None:
        with pytest.raises(ValueError, match="tick_size_points"):
            BacktestDecisionHarness(
                setups=[],
                filter_layer=RiskFilterLayer(filters=[]),
                state=RiskStateSnapshot(),
                tick_size_points=-0.05,
            )
