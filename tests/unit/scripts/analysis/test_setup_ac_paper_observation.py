"""Unit tests for scripts/analysis/setup_ac_paper_observation.py.

Covers:
- Per-setup statistics computation from ledger trade rows.
- N-threshold progress logic (below / at / above threshold).
- Fast-stopout and catastrophic-loss early-warning flags.
- Silent-setup (0 trades) early-warning.
- Eval snapshot building from Redis hash data.
- Telegram message formatting: key fields present, weekly banner, progress bar.
- Setup D (vwap_reversion) extension: stats, eval snapshot, formatting, selectivity.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

import scripts.analysis.setup_ac_paper_observation as _mod

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SETUP_A = _mod.SETUP_A
SETUP_C = _mod.SETUP_C
SETUP_D = _mod.SETUP_D


def _trade(
    strategy: str = SETUP_A,
    pnl: float = 1000.0,
    pnl_pct: float = 0.5,
    hold_seconds: float = 3600.0,
    exit_reason: str = "take_profit",
    entry_time: str = "2026-06-21T10:00:00",
    exit_time: str = "2026-06-21T11:00:00",
) -> dict:
    return {
        "strategy": strategy,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "hold_seconds": hold_seconds,
        "exit_reason": exit_reason,
        "entry_time": entry_time,
        "exit_time": exit_time,
    }


def _compute(trades, fast_stopout_minutes=30, catastrophic_loss_pct=-3.0):
    return _mod._compute_setup_stats(
        trades, fast_stopout_minutes, catastrophic_loss_pct
    )


# ---------------------------------------------------------------------------
# SetupStats computation
# ---------------------------------------------------------------------------


class TestComputeSetupStats:
    def test_empty_trades_produces_zero_counts(self):
        stats = _compute([])
        assert stats[SETUP_A].trade_count == 0
        assert stats[SETUP_C].trade_count == 0

    def test_trades_attributed_per_setup(self):
        trades = [
            _trade(strategy=SETUP_A, pnl=100),
            _trade(strategy=SETUP_A, pnl=-50),
            _trade(strategy=SETUP_C, pnl=200),
        ]
        stats = _compute(trades)
        assert stats[SETUP_A].trade_count == 2
        assert stats[SETUP_C].trade_count == 1

    def test_unknown_strategy_ignored(self):
        trades = [_trade(strategy="bb_reversion_15m", pnl=100)]
        stats = _compute(trades)
        assert stats[SETUP_A].trade_count == 0
        assert stats[SETUP_C].trade_count == 0

    def test_win_rate_calculation(self):
        trades = [
            _trade(strategy=SETUP_A, pnl=100),
            _trade(strategy=SETUP_A, pnl=50),
            _trade(strategy=SETUP_A, pnl=-30),
        ]
        stats = _compute(trades)
        assert stats[SETUP_A].win_count == 2
        assert stats[SETUP_A].loss_count == 1
        assert abs(stats[SETUP_A].win_rate - 66.67) < 0.1

    def test_avg_and_median_pnl(self):
        trades = [
            _trade(strategy=SETUP_A, pnl=100),
            _trade(strategy=SETUP_A, pnl=200),
            _trade(strategy=SETUP_A, pnl=300),
        ]
        stats = _compute(trades)
        assert stats[SETUP_A].avg_pnl == pytest.approx(200.0)
        assert stats[SETUP_A].median_pnl == pytest.approx(200.0)

    def test_avg_hold_minutes(self):
        trades = [
            _trade(strategy=SETUP_A, hold_seconds=1200),  # 20 min
            _trade(strategy=SETUP_A, hold_seconds=3000),  # 50 min
        ]
        stats = _compute(trades)
        # avg = (1200 + 3000) / 2 / 60 = 35 min
        assert stats[SETUP_A].avg_hold_minutes == pytest.approx(35.0)

    def test_exit_reason_counts(self):
        trades = [
            _trade(strategy=SETUP_A, exit_reason="take_profit"),
            _trade(strategy=SETUP_A, exit_reason="take_profit"),
            _trade(strategy=SETUP_A, exit_reason="stop_loss"),
        ]
        stats = _compute(trades)
        counts = stats[SETUP_A].exit_reason_counts
        assert counts["take_profit"] == 2
        assert counts["stop_loss"] == 1

    def test_fast_stopout_flagged(self):
        # hold_seconds=900 = 15 min < fast_stopout_minutes=30
        trades = [_trade(strategy=SETUP_A, hold_seconds=900)]
        stats = _compute(trades, fast_stopout_minutes=30)
        assert stats[SETUP_A].fast_stopout_count == 1

    def test_no_fast_stopout_when_hold_exceeds_threshold(self):
        # hold_seconds=2400 = 40 min >= 30 min threshold
        trades = [_trade(strategy=SETUP_A, hold_seconds=2400)]
        stats = _compute(trades, fast_stopout_minutes=30)
        assert stats[SETUP_A].fast_stopout_count == 0

    def test_catastrophic_loss_flagged(self):
        trades = [_trade(strategy=SETUP_C, pnl=-500, pnl_pct=-3.5)]
        stats = _compute(trades, catastrophic_loss_pct=-3.0)
        assert stats[SETUP_C].catastrophic_loss_count == 1

    def test_borderline_loss_not_catastrophic(self):
        # pnl_pct=-3.0 is at threshold — should NOT be flagged (< not <=)
        trades = [_trade(strategy=SETUP_C, pnl=-300, pnl_pct=-3.0)]
        stats = _compute(trades, catastrophic_loss_pct=-3.0)
        assert stats[SETUP_C].catastrophic_loss_count == 0

    def test_last_exit_kst_is_most_recent(self):
        # query_trades returns DESC order; first row = latest.
        # Naive timestamps (no tzinfo) are treated as KST by to_kst(),
        # so the stored value gains the +09:00 suffix.
        trades = [
            _trade(strategy=SETUP_A, exit_time="2026-06-23T14:00:00"),
            _trade(strategy=SETUP_A, exit_time="2026-06-21T11:00:00"),
        ]
        stats = _compute(trades)
        assert stats[SETUP_A].last_exit_kst == "2026-06-23T14:00:00+09:00"

    def test_utc_exit_time_converted_to_kst(self):
        # RuntimeLedger stores UTC ISO strings; verify 9h shift to KST.
        trades = [_trade(strategy=SETUP_A, exit_time="2026-06-21T06:00:00+00:00")]
        stats = _compute(trades)
        assert stats[SETUP_A].last_exit_kst == "2026-06-21T15:00:00+09:00"

    def test_no_fast_stopout_at_exact_threshold(self):
        # hold_seconds == 30 min exactly — boundary is exclusive (< not <=),
        # so the trade at the threshold must NOT be flagged as fast stopout.
        trades = [_trade(strategy=SETUP_A, hold_seconds=1800)]
        stats = _compute(trades, fast_stopout_minutes=30)
        assert stats[SETUP_A].fast_stopout_count == 0


# ---------------------------------------------------------------------------
# N-threshold progress
# ---------------------------------------------------------------------------


class TestNThresholdProgress:
    def test_below_threshold_not_validatable(self):
        """Trade count below threshold yields 'not yet validatable' in message."""
        digest = _mod.build_digest(
            since=date(2026, 6, 21),
            validation_n_threshold=30,
            trade_rows=[_trade(strategy=SETUP_A)] * 5,
            redis_eval={},
        )
        msg = _mod._format_telegram(digest)
        assert "not yet validatable" in msg
        assert "N=5/30" in msg

    def test_at_threshold_shows_ready(self):
        """Trade count == threshold shows revalidation ready."""
        digest = _mod.build_digest(
            since=date(2026, 6, 21),
            validation_n_threshold=5,
            trade_rows=[_trade(strategy=SETUP_A)] * 5,
            redis_eval={},
        )
        msg = _mod._format_telegram(digest)
        assert "READY FOR REVALIDATION" in msg

    def test_above_threshold_shows_ready(self):
        """Trade count > threshold also shows ready."""
        digest = _mod.build_digest(
            since=date(2026, 6, 21),
            validation_n_threshold=3,
            trade_rows=[_trade(strategy=SETUP_A)] * 7,
            redis_eval={},
        )
        msg = _mod._format_telegram(digest)
        assert "READY FOR REVALIDATION" in msg


# ---------------------------------------------------------------------------
# Early warnings
# ---------------------------------------------------------------------------


class TestEarlyWarnings:
    def test_silent_setup_warns(self):
        """0 trades for any setup should raise an early warning."""
        since = date.today() - timedelta(days=3)
        warnings = _mod._build_early_warnings(
            {
                SETUP_A: _mod.SetupStats(name=SETUP_A, trade_count=0),
                SETUP_C: _mod.SetupStats(name=SETUP_C, trade_count=0),
            },
            since=since,
            fast_stopout_minutes=30,
            catastrophic_loss_pct=-3.0,
        )
        assert any("0 trades" in w for w in warnings)

    # ------------------------------------------------------------------
    # 0-trade reason classification (legitimate selectivity vs suppression)
    # ------------------------------------------------------------------

    def _warnings_for_setup_a(
        self, reason: str, since: date | None = None
    ) -> list[str]:
        """Helper: build early warnings for Setup A with 0 trades and a given reason."""
        if since is None:
            since = date(2026, 6, 21)
        snap_a = _mod.SetupEvalSnapshot(
            name=SETUP_A, outcome="reject", reason=reason, ts_kst="2026-06-21T10:00:00"
        )
        snap_c = _mod.SetupEvalSnapshot(
            name=SETUP_C, outcome="reject", reason=reason, ts_kst="2026-06-21T10:00:00"
        )
        return _mod._build_early_warnings(
            {
                SETUP_A: _mod.SetupStats(name=SETUP_A, trade_count=0),
                SETUP_C: _mod.SetupStats(name=SETUP_C, trade_count=5),  # only A is 0
            },
            since=since,
            fast_stopout_minutes=30,
            catastrophic_loss_pct=-3.0,
            eval_snapshots=[snap_a, snap_c],
        )

    def test_legitimate_reason_outside_time_window_emits_info_not_suppressed(self):
        """outside_time_window(91m∉[10,60]) is a selectivity gate — NOT suppression."""
        reason = "outside_time_window(91m∉[10,60])"
        warnings = self._warnings_for_setup_a(reason)
        a_warnings = [w for w in warnings if "0 trades" in w and "A" in w]
        assert len(a_warnings) == 1
        assert "no qualifying setup" in a_warnings[0]
        assert "expected" in a_warnings[0]
        assert "suppressed" not in a_warnings[0]
        # reason text must be present
        assert reason in a_warnings[0]

    def test_suppression_reason_llm_veto_emits_warning(self):
        """llm_veto:llm_veto is a genuine suppression — should emit 'possibly suppressed'."""
        reason = "llm_veto:llm_veto"
        warnings = self._warnings_for_setup_a(reason)
        a_warnings = [w for w in warnings if "0 trades" in w and "A" in w]
        assert len(a_warnings) == 1
        assert "possibly suppressed" in a_warnings[0]
        assert "no qualifying setup" not in a_warnings[0]
        assert reason in a_warnings[0]

    def test_no_eval_snapshot_emits_no_eval_data_warning(self):
        """No eval snapshot for a setup → 'no eval data' warning (can't confirm evaluation)."""
        since = date(2026, 6, 21)
        # Pass only Setup C snapshot; Setup A has no entry in Redis.
        snap_c = _mod.SetupEvalSnapshot(
            name=SETUP_C, outcome="reject", reason="outside_time_window", ts_kst=""
        )
        warnings = _mod._build_early_warnings(
            {
                SETUP_A: _mod.SetupStats(name=SETUP_A, trade_count=0),
                SETUP_C: _mod.SetupStats(name=SETUP_C, trade_count=5),
            },
            since=since,
            fast_stopout_minutes=30,
            catastrophic_loss_pct=-3.0,
            eval_snapshots=[snap_c],  # no Setup A entry
        )
        a_warnings = [w for w in warnings if "0 trades" in w and "A" in w]
        assert len(a_warnings) == 1
        assert "no eval data" in a_warnings[0]
        assert "possibly suppressed" in a_warnings[0]

    def test_nonzero_trades_produces_no_zero_trade_warning(self):
        """Regression: a setup with trades > 0 must not emit a 0-trade line."""
        snap_a = _mod.SetupEvalSnapshot(
            name=SETUP_A, outcome="fired", reason="", ts_kst=""
        )
        snap_c = _mod.SetupEvalSnapshot(
            name=SETUP_C, outcome="fired", reason="", ts_kst=""
        )
        warnings = _mod._build_early_warnings(
            {
                SETUP_A: _mod.SetupStats(name=SETUP_A, trade_count=3),
                SETUP_C: _mod.SetupStats(name=SETUP_C, trade_count=2),
            },
            since=date(2026, 6, 21),
            fast_stopout_minutes=30,
            catastrophic_loss_pct=-3.0,
            eval_snapshots=[snap_a, snap_c],
        )
        assert not any("0 trades" in w for w in warnings)

    def test_legitimate_reason_no_event_in_window(self):
        """no_event_in_window is a selectivity gate."""
        warnings = self._warnings_for_setup_a("no_event_in_window")
        a_warnings = [w for w in warnings if "0 trades" in w and "A" in w]
        assert "no qualifying setup" in a_warnings[0]
        assert "suppressed" not in a_warnings[0]

    def test_legitimate_reason_no_macro_overnight(self):
        """no_macro_overnight is a selectivity gate."""
        warnings = self._warnings_for_setup_a("no_macro_overnight")
        a_warnings = [w for w in warnings if "0 trades" in w and "A" in w]
        assert "no qualifying setup" in a_warnings[0]

    def test_legitimate_reason_sp500_kr_gap_misaligned(self):
        """sp500_kr_gap_misaligned is a selectivity gate."""
        warnings = self._warnings_for_setup_a("sp500_kr_gap_misaligned")
        a_warnings = [w for w in warnings if "0 trades" in w and "A" in w]
        assert "no qualifying setup" in a_warnings[0]

    def test_legitimate_reason_after_cutoff(self):
        """after_cutoff is a selectivity gate."""
        warnings = self._warnings_for_setup_a("after_cutoff")
        a_warnings = [w for w in warnings if "0 trades" in w and "A" in w]
        assert "no qualifying setup" in a_warnings[0]

    def test_high_fast_stopout_ratio_warns(self):
        s = _mod.SetupStats(name=SETUP_A, trade_count=4, fast_stopout_count=3)
        warnings = _mod._build_early_warnings(
            {SETUP_A: s, SETUP_C: _mod.SetupStats(name=SETUP_C, trade_count=5)},
            since=date.today(),
            fast_stopout_minutes=30,
            catastrophic_loss_pct=-3.0,
        )
        assert any("fast-stopout" in w for w in warnings)

    def test_low_fast_stopout_ratio_no_warn(self):
        s = _mod.SetupStats(name=SETUP_A, trade_count=10, fast_stopout_count=1)
        warnings = _mod._build_early_warnings(
            {SETUP_A: s, SETUP_C: _mod.SetupStats(name=SETUP_C, trade_count=10)},
            since=date.today(),
            fast_stopout_minutes=30,
            catastrophic_loss_pct=-3.0,
        )
        assert not any("fast-stopout" in w for w in warnings)

    def test_catastrophic_loss_warns(self):
        s = _mod.SetupStats(name=SETUP_A, trade_count=5, catastrophic_loss_count=1)
        warnings = _mod._build_early_warnings(
            {SETUP_A: s, SETUP_C: _mod.SetupStats(name=SETUP_C, trade_count=5)},
            since=date.today(),
            fast_stopout_minutes=30,
            catastrophic_loss_pct=-3.0,
        )
        assert any("catastrophic" in w.lower() or "PnL <" in w for w in warnings)


# ---------------------------------------------------------------------------
# Eval snapshots
# ---------------------------------------------------------------------------


class TestEvalSnapshots:
    def test_both_setups_present_even_if_redis_empty(self):
        snapshots = _mod._build_eval_snapshots({})
        names = {s.name for s in snapshots}
        assert SETUP_A in names
        assert SETUP_C in names

    def test_known_outcome_populated(self):
        raw = {
            SETUP_A: {
                "outcome": "reject",
                "reason": "regime_gate_blocked",
                "ts_kst": "2026-06-21T10:00:00",
            },
        }
        snapshots = _mod._build_eval_snapshots(raw)
        snap_a = next(s for s in snapshots if s.name == SETUP_A)
        assert snap_a.outcome == "reject"
        assert snap_a.reason == "regime_gate_blocked"

    def test_unknown_setup_not_in_snapshot_list(self):
        raw = {
            "bb_reversion_15m": {"outcome": "reject", "reason": "x", "ts_kst": ""},
        }
        snapshots = _mod._build_eval_snapshots(raw)
        names = [s.name for s in snapshots]
        assert "bb_reversion_15m" not in names


# ---------------------------------------------------------------------------
# Telegram formatting
# ---------------------------------------------------------------------------


class TestFormatTelegram:
    def _make_digest(self, trade_rows=None, is_weekly=False):
        return _mod.build_digest(
            since=date(2026, 6, 21),
            is_weekly=is_weekly,
            validation_n_threshold=30,
            trade_rows=trade_rows or [],
            redis_eval={},
        )

    def test_header_present(self):
        msg = _mod._format_telegram(self._make_digest())
        assert "Setup A/C/D Paper Observation" in msg

    def test_weekly_banner_in_weekly_mode(self):
        digest = self._make_digest(is_weekly=True)
        msg = _mod._format_telegram(digest)
        assert "Weekly Rollup" in msg

    def test_no_weekly_banner_in_daily_mode(self):
        msg = _mod._format_telegram(self._make_digest(is_weekly=False))
        assert "Weekly Rollup" not in msg

    def test_revalidation_footer_present(self):
        msg = _mod._format_telegram(self._make_digest())
        assert "Revalidation gate:" in msg

    def test_both_setups_listed(self):
        msg = _mod._format_telegram(self._make_digest())
        assert "Setup A" in msg
        assert "Setup C" in msg

    def test_progress_bar_format(self):
        bar = _mod._n_bar(10, 30)
        # Should contain filled portion, threshold, and percent
        assert "10/30" in bar
        assert "33%" in bar

    def test_progress_bar_caps_at_100_percent(self):
        bar = _mod._n_bar(50, 30)
        assert "100%" in bar

    def test_win_rate_shown_when_trades_present(self):
        trades = [
            _trade(strategy=SETUP_A, pnl=100),
            _trade(strategy=SETUP_A, pnl=-50),
        ]
        msg = _mod._format_telegram(self._make_digest(trade_rows=trades))
        assert "Win rate:" in msg

    def test_no_trades_message_shown(self):
        msg = _mod._format_telegram(self._make_digest(trade_rows=[]))
        assert "No trades recorded yet" in msg

    def test_eval_section_hidden_when_all_unknown(self):
        """Eval section should be omitted when Redis returned nothing."""
        msg = _mod._format_telegram(self._make_digest())
        assert "Latest setup eval" not in msg

    def test_eval_section_shown_when_data_present(self):
        digest = _mod.build_digest(
            since=date(2026, 6, 21),
            trade_rows=[],
            redis_eval={
                SETUP_A: {
                    "outcome": "reject",
                    "reason": "no_market_context",
                    "ts_kst": "2026-06-21T09:05:00",
                },
            },
        )
        msg = _mod._format_telegram(digest)
        assert "Latest setup eval" in msg
        assert "reject" in msg
        assert "no_market_context" in msg

    def test_warnings_section_shown_when_present(self):
        trades = []  # zero trades → silent-setup warning
        msg = _mod._format_telegram(self._make_digest(trade_rows=trades))
        assert "Early warnings" in msg

    def test_observation_period_in_message(self):
        msg = _mod._format_telegram(self._make_digest())
        assert "2026-06-21" in msg


# ---------------------------------------------------------------------------
# N-bar helper
# ---------------------------------------------------------------------------


class TestNBar:
    def test_empty_is_all_dots(self):
        bar = _mod._n_bar(0, 5)
        assert "0/5" in bar
        assert "0%" in bar

    def test_partial_fill(self):
        bar = _mod._n_bar(2, 4)
        assert "2/4" in bar
        assert "50%" in bar


# ---------------------------------------------------------------------------
# Setup D — new tests (extend coverage)
# ---------------------------------------------------------------------------


class TestSetupDStats:
    """_compute_setup_stats now includes a SETUP_D bucket."""

    def test_setup_d_bucket_exists_when_no_trades(self):
        stats = _mod._compute_setup_stats([], 30, -3.0)
        assert SETUP_D in stats
        assert stats[SETUP_D].trade_count == 0

    def test_setup_d_trade_counted_separately(self):
        trades = [
            _trade(strategy=SETUP_A, pnl=100),
            _trade(strategy=SETUP_D, pnl=200),
            _trade(strategy=SETUP_D, pnl=-50),
        ]
        stats = _mod._compute_setup_stats(trades, 30, -3.0)
        assert stats[SETUP_D].trade_count == 2
        assert stats[SETUP_A].trade_count == 1
        assert stats[SETUP_C].trade_count == 0

    def test_setup_d_win_loss_tracked(self):
        trades = [
            _trade(strategy=SETUP_D, pnl=300),
            _trade(strategy=SETUP_D, pnl=-100),
        ]
        stats = _mod._compute_setup_stats(trades, 30, -3.0)
        assert stats[SETUP_D].win_count == 1
        assert stats[SETUP_D].loss_count == 1

    def test_all_three_setups_in_stats(self):
        stats = _mod._compute_setup_stats([], 30, -3.0)
        assert set(stats.keys()) == {SETUP_A, SETUP_C, SETUP_D}


class TestSetupDEvalSnapshots:
    """_build_eval_snapshots includes Setup D when present in Redis hash."""

    def test_setup_d_present_in_snapshots_even_if_redis_empty(self):
        snapshots = _mod._build_eval_snapshots({})
        names = {s.name for s in snapshots}
        assert SETUP_D in names

    def test_setup_d_outcome_populated_from_redis(self):
        raw = {
            SETUP_D: {
                "outcome": "reject",
                "reason": "vol_below_gate(0.80<1.00)",
                "ts_kst": "2026-06-26T10:30:00",
            }
        }
        snapshots = _mod._build_eval_snapshots(raw)
        snap_d = next(s for s in snapshots if s.name == SETUP_D)
        assert snap_d.outcome == "reject"
        assert snap_d.reason == "vol_below_gate(0.80<1.00)"
        assert snap_d.ts_kst == "2026-06-26T10:30:00"

    def test_all_three_setups_in_snapshots(self):
        snapshots = _mod._build_eval_snapshots({})
        names = {s.name for s in snapshots}
        assert names == {SETUP_A, SETUP_C, SETUP_D}


class TestSetupDLegitimateReasons:
    """Setup D calm-day rejects are expected selectivity (not suppression)."""

    def _warnings_for_setup_d(self, reason: str) -> list[str]:
        snap_a = _mod.SetupEvalSnapshot(
            name=SETUP_A, outcome="fired", reason="", ts_kst=""
        )
        snap_c = _mod.SetupEvalSnapshot(
            name=SETUP_C, outcome="fired", reason="", ts_kst=""
        )
        snap_d = _mod.SetupEvalSnapshot(
            name=SETUP_D, outcome="reject", reason=reason, ts_kst="2026-06-26T10:00:00"
        )
        return _mod._build_early_warnings(
            {
                SETUP_A: _mod.SetupStats(name=SETUP_A, trade_count=1),
                SETUP_C: _mod.SetupStats(name=SETUP_C, trade_count=1),
                SETUP_D: _mod.SetupStats(name=SETUP_D, trade_count=0),
            },
            since=date(2026, 6, 21),
            fast_stopout_minutes=30,
            catastrophic_loss_pct=-3.0,
            eval_snapshots=[snap_a, snap_c, snap_d],
        )

    def test_vol_below_gate_is_legitimate(self):
        warnings = self._warnings_for_setup_d("vol_below_gate(0.80<1.00)")
        d_warnings = [w for w in warnings if "0 trades" in w and "D" in w]
        assert len(d_warnings) == 1
        assert "no qualifying setup" in d_warnings[0]
        assert "expected" in d_warnings[0]
        assert "suppressed" not in d_warnings[0]

    def test_not_extreme_is_legitimate(self):
        warnings = self._warnings_for_setup_d("not_extreme(z=+0.50,need±1.80)")
        d_warnings = [w for w in warnings if "0 trades" in w and "D" in w]
        assert len(d_warnings) == 1
        assert "no qualifying setup" in d_warnings[0]
        assert "expected" in d_warnings[0]
        assert "suppressed" not in d_warnings[0]

    def test_still_trending_up_is_legitimate(self):
        warnings = self._warnings_for_setup_d("still_trending_up(px=350.0-340.0)")
        d_warnings = [w for w in warnings if "0 trades" in w and "D" in w]
        assert len(d_warnings) == 1
        assert "no qualifying setup" in d_warnings[0]
        assert "expected" in d_warnings[0]

    def test_still_trending_down_is_legitimate(self):
        warnings = self._warnings_for_setup_d("still_trending_down(lo=340.0-335.0)")
        d_warnings = [w for w in warnings if "0 trades" in w and "D" in w]
        assert len(d_warnings) == 1
        assert "expected" in d_warnings[0]
        assert "suppressed" not in d_warnings[0]

    def test_before_window_is_legitimate(self):
        """before_window(...) is Setup D's opening-warmup gate — NOT suppression."""
        warnings = self._warnings_for_setup_d("before_window(3m<10)")
        d_warnings = [w for w in warnings if "0 trades" in w and "D" in w]
        assert len(d_warnings) == 1
        assert "no qualifying setup" in d_warnings[0]
        assert "expected" in d_warnings[0]
        assert "suppressed" not in d_warnings[0]

    def test_setup_d_selectivity_note_is_high_vol_specific(self):
        """Setup D 0-trade message must reference high-vol gate, not A/C rate."""
        warnings = self._warnings_for_setup_d("vol_below_gate(0.80<1.00)")
        d_warnings = [w for w in warnings if "0 trades" in w and "D" in w]
        assert "high-vol" in d_warnings[0]
        # Must NOT show the A/C rate note for Setup D
        assert "4.8 setups/mo" not in d_warnings[0]

    def test_is_legitimate_before_window(self):
        assert _mod._is_legitimate_no_setup("before_window(3m<10)") is True

    def test_is_legitimate_vol_below_gate(self):
        assert _mod._is_legitimate_no_setup("vol_below_gate(0.80<1.00)") is True

    def test_is_legitimate_not_extreme(self):
        assert _mod._is_legitimate_no_setup("not_extreme(z=+0.50,need±1.80)") is True

    def test_is_legitimate_still_trending(self):
        assert _mod._is_legitimate_no_setup("still_trending_up(px=350.0-340.0)") is True
        assert _mod._is_legitimate_no_setup("still_trending_down(lo=340.0)") is True


class TestSetupDFormatTelegram:
    """_format_telegram renders Setup D block and updated title."""

    def _make_digest_with_d(self, trade_rows=None, redis_eval=None, is_weekly=False):
        return _mod.build_digest(
            since=date(2026, 6, 21),
            is_weekly=is_weekly,
            validation_n_threshold=30,
            trade_rows=trade_rows or [],
            redis_eval=redis_eval or {},
        )

    def test_title_shows_setup_acd(self):
        msg = _mod._format_telegram(self._make_digest_with_d())
        assert "Setup A/C/D Paper Observation" in msg

    def test_weekly_title_shows_setup_acd(self):
        msg = _mod._format_telegram(self._make_digest_with_d(is_weekly=True))
        assert "Setup A/C/D Paper Observation" in msg
        assert "Weekly Rollup" in msg

    def test_setup_d_label_present(self):
        msg = _mod._format_telegram(self._make_digest_with_d())
        assert "Setup D (vwap_reversion)" in msg

    def test_setup_d_eval_shown_when_data_present(self):
        digest = self._make_digest_with_d(
            redis_eval={
                SETUP_D: {
                    "outcome": "reject",
                    "reason": "vol_below_gate(0.80<1.00)",
                    "ts_kst": "2026-06-26T10:30:00",
                }
            }
        )
        msg = _mod._format_telegram(digest)
        assert "Latest setup eval" in msg
        assert "Setup D" in msg
        assert "vol_below_gate" in msg

    def test_setup_d_no_trades_recorded_when_empty(self):
        msg = _mod._format_telegram(self._make_digest_with_d())
        # There will be 3 "No trades recorded yet" sections (one per setup)
        assert msg.count("No trades recorded yet") == 3

    def test_setup_d_trade_shows_win_rate(self):
        trades = [_trade(strategy=SETUP_D, pnl=500)]
        msg = _mod._format_telegram(self._make_digest_with_d(trade_rows=trades))
        assert "Win rate:" in msg


class TestRegressionAC:
    """Regression: A/C behaviour must be unchanged after the D extension."""

    def test_ac_labels_unchanged(self):
        msg = _mod._format_telegram(
            _mod.build_digest(
                since=date(2026, 6, 21),
                trade_rows=[],
                redis_eval={},
            )
        )
        assert "Setup A (gap_reversion)" in msg
        assert "Setup C (event_reaction)" in msg

    def test_ac_expected_note_still_shows_rate(self):
        snap_a = _mod.SetupEvalSnapshot(
            name=SETUP_A, outcome="reject", reason="outside_time_window", ts_kst=""
        )
        snap_c = _mod.SetupEvalSnapshot(
            name=SETUP_C, outcome="reject", reason="outside_time_window", ts_kst=""
        )
        snap_d = _mod.SetupEvalSnapshot(
            name=SETUP_D, outcome="fired", reason="", ts_kst=""
        )
        warnings = _mod._build_early_warnings(
            {
                SETUP_A: _mod.SetupStats(name=SETUP_A, trade_count=0),
                SETUP_C: _mod.SetupStats(name=SETUP_C, trade_count=0),
                SETUP_D: _mod.SetupStats(name=SETUP_D, trade_count=1),
            },
            since=date(2026, 6, 21),
            fast_stopout_minutes=30,
            catastrophic_loss_pct=-3.0,
            eval_snapshots=[snap_a, snap_c, snap_d],
        )
        ac_warnings = [w for w in warnings if "0 trades" in w]
        assert all(
            "4.8 setups/mo" in w for w in ac_warnings
        ), "A/C selectivity warnings should still reference the ~4.8 setups/mo note"

    def test_setups_tuple_has_three_entries(self):
        assert len(_mod.SETUPS) == 3
        assert SETUP_D in _mod.SETUPS


# ---------------------------------------------------------------------------
# Fired-outcome 0-trade early-warning (outcome-aware classification)
# ---------------------------------------------------------------------------


class TestFiredOutcomeZeroTrades:
    """When outcome=='fired' and trade_count==0, the warning must say FIRED
    (position may be open / close not yet recorded) — NOT 'possibly suppressed'.
    """

    def _warnings_for_fired_setup_d(self, reason: str = "short") -> list[str]:
        snap_a = _mod.SetupEvalSnapshot(
            name=SETUP_A, outcome="reject", reason="outside_time_window", ts_kst=""
        )
        snap_c = _mod.SetupEvalSnapshot(
            name=SETUP_C, outcome="reject", reason="outside_time_window", ts_kst=""
        )
        snap_d = _mod.SetupEvalSnapshot(
            name=SETUP_D, outcome="fired", reason=reason, ts_kst="2026-06-26T18:41:00"
        )
        return _mod._build_early_warnings(
            {
                SETUP_A: _mod.SetupStats(name=SETUP_A, trade_count=3),
                SETUP_C: _mod.SetupStats(name=SETUP_C, trade_count=2),
                SETUP_D: _mod.SetupStats(name=SETUP_D, trade_count=0),
            },
            since=date(2026, 6, 21),
            fast_stopout_minutes=30,
            catastrophic_loss_pct=-3.0,
            eval_snapshots=[snap_a, snap_c, snap_d],
        )

    def test_fired_short_produces_fired_info_not_suppressed(self):
        """Production bug: Setup D fired a short with 0 closed trades.
        The warning must not say 'possibly suppressed'."""
        warnings = self._warnings_for_fired_setup_d(reason="short")
        d_warnings = [w for w in warnings if "D" in w and "0 closed trades" in w]
        assert len(d_warnings) == 1
        w = d_warnings[0]
        # Must mention FIRED / fired
        assert "FIRED" in w or "fired" in w
        # Must NOT say 'possibly suppressed'
        assert "possibly suppressed" not in w

    def test_fired_long_produces_fired_info_not_suppressed(self):
        """Same check with direction='long'."""
        warnings = self._warnings_for_fired_setup_d(reason="long")
        d_warnings = [w for w in warnings if "D" in w and "0 closed trades" in w]
        assert len(d_warnings) == 1
        w = d_warnings[0]
        assert "FIRED" in w or "fired" in w
        assert "possibly suppressed" not in w

    def test_fired_warning_mentions_monitor(self):
        """Fired 0-trade warning should include 'monitor' guidance."""
        warnings = self._warnings_for_fired_setup_d(reason="short")
        d_warnings = [w for w in warnings if "D" in w and "0 closed trades" in w]
        assert any("monitor" in w.lower() for w in d_warnings)

    # ------------------------------------------------------------------
    # Regression: reject-outcome paths must be unchanged
    # ------------------------------------------------------------------

    def test_regression_reject_llm_veto_still_suppressed(self):
        """outcome='reject', reason='llm_veto:...' must still say 'possibly suppressed'."""
        snap_d = _mod.SetupEvalSnapshot(
            name=SETUP_D, outcome="reject", reason="llm_veto:bearish", ts_kst=""
        )
        warnings = _mod._build_early_warnings(
            {
                SETUP_A: _mod.SetupStats(name=SETUP_A, trade_count=3),
                SETUP_C: _mod.SetupStats(name=SETUP_C, trade_count=3),
                SETUP_D: _mod.SetupStats(name=SETUP_D, trade_count=0),
            },
            since=date(2026, 6, 21),
            fast_stopout_minutes=30,
            catastrophic_loss_pct=-3.0,
            eval_snapshots=[snap_d],
        )
        d_warnings = [w for w in warnings if "D" in w and "0 trades" in w]
        assert len(d_warnings) == 1
        assert "possibly suppressed" in d_warnings[0]
        assert "fired" not in d_warnings[0].lower()

    def test_regression_reject_legitimate_selectivity_still_expected(self):
        """outcome='reject', reason='vol_below_gate(0.8<1.0)' must still say 'expected'."""
        snap_d = _mod.SetupEvalSnapshot(
            name=SETUP_D,
            outcome="reject",
            reason="vol_below_gate(0.8<1.0)",
            ts_kst="",
        )
        warnings = _mod._build_early_warnings(
            {
                SETUP_A: _mod.SetupStats(name=SETUP_A, trade_count=3),
                SETUP_C: _mod.SetupStats(name=SETUP_C, trade_count=3),
                SETUP_D: _mod.SetupStats(name=SETUP_D, trade_count=0),
            },
            since=date(2026, 6, 21),
            fast_stopout_minutes=30,
            catastrophic_loss_pct=-3.0,
            eval_snapshots=[snap_d],
        )
        d_warnings = [w for w in warnings if "D" in w and "0 trades" in w]
        assert len(d_warnings) == 1
        assert "expected" in d_warnings[0]
        assert "possibly suppressed" not in d_warnings[0]
        assert "fired" not in d_warnings[0].lower()
