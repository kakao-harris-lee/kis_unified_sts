"""Tests for scripts/analysis/setup_vs_rl_shadow_counterfactual.py.

Uses unittest.mock to patch ClickHouse client; no real DB required.
All fixtures are synthetic data covering the schema defined in §10.2.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ── dynamic import of the analysis script ────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_SCRIPT = _REPO_ROOT / "scripts" / "analysis" / "setup_vs_rl_shadow_counterfactual.py"
_spec = importlib.util.spec_from_file_location("cf_script", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["cf_script"] = _mod
_spec.loader.exec_module(_mod)

# Import public names
reconstruct_rl_trades = _mod.reconstruct_rl_trades
reconstruct_setup_trades = _mod.reconstruct_setup_trades
_compute_agg = _mod._compute_agg
_compute_agreement = _mod._compute_agreement
_compute_per_day = _mod._compute_per_day
_pnl_krw = _mod._pnl_krw
_render_table = _mod._render_table
_report_to_dict = _mod._report_to_dict
_render_csv = _mod._render_csv
run_analysis = _mod.run_analysis
ShadowTrade = _mod.ShadowTrade
SetupTrade = _mod.SetupTrade
AgreementMatrix = _mod.AgreementMatrix
AggregateStat = _mod.AggregateStat

# ── constants that mirror the script ─────────────────────────────────────────
_MULTIPLIER = 50_000.0
_TICK_SIZE = 0.02
_COMMISSION_BPS = 0.3  # 0.003% * 10000 = 0.3 bps
_SLIPPAGE_TICKS = 1.0


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ──────────────────────────────────────────────────────────────────────────────

def _ts(date_str: str, time_str: str = "09:00:00") -> pd.Timestamp:
    return pd.Timestamp(f"{date_str}T{time_str}+00:00")


def _make_bars(
    base_date: str = "2026-05-01",
    n_bars: int = 60,
    base_price: float = 380.0,
    step: float = 0.0,
) -> pd.DataFrame:
    """Generate synthetic 1-minute OHLCV bars."""
    timestamps = pd.date_range(
        f"{base_date} 09:00:00", periods=n_bars, freq="min", tz="UTC"
    )
    prices = [base_price + i * step for i in range(n_bars)]
    return pd.DataFrame(
        {
            "open": prices,
            "high": [p + 0.1 for p in prices],
            "low": [p - 0.1 for p in prices],
            "close": [p + 0.05 for p in prices],
            "volume": [100] * n_bars,
        },
        index=timestamps,
    )


def _make_shadow_df(rows: list[dict]) -> pd.DataFrame:
    """Build a shadow predictions DataFrame from dicts."""
    if not rows:
        return pd.DataFrame(
            columns=["ts", "symbol", "action", "confidence",
                     "regime", "risk_mode", "risk_score", "executed_setup_id"]
        )
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df["action"] = df["action"].astype(int)
    return df


def _make_signals_df(rows: list[dict]) -> pd.DataFrame:
    """Build a signals_all DataFrame from dicts."""
    if not rows:
        return pd.DataFrame(
            columns=["signal_id", "generated_at", "setup_type", "direction",
                     "entry_price", "stop_loss", "take_profit", "confidence",
                     "executed", "skip_reason"]
        )
    df = pd.DataFrame(rows)
    df["generated_at"] = pd.to_datetime(df["generated_at"], utc=True)
    df["executed"] = df["executed"].astype(int)
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Tests: PnL calculation
# ──────────────────────────────────────────────────────────────────────────────

class TestPnlKrw:
    def test_long_profit(self):
        pnl = _pnl_krw("long", 380.0, 381.0, _MULTIPLIER, _COMMISSION_BPS, _SLIPPAGE_TICKS, _TICK_SIZE)
        # gross = 1.0 pt * 50_000 = 50_000
        # slippage per side = 1 tick * 0.02 * 50_000 = 1_000
        # commission per side = 380 * 50_000 * 0.3/10_000 = 570
        # total cost = (1_000 + 570) * 2 = 3_140
        # net = 50_000 - 3_140 = 46_860
        assert pnl == pytest.approx(46_860.0, rel=1e-3)

    def test_long_loss(self):
        pnl = _pnl_krw("long", 381.0, 380.0, _MULTIPLIER, _COMMISSION_BPS, _SLIPPAGE_TICKS, _TICK_SIZE)
        assert pnl < 0

    def test_short_profit(self):
        pnl = _pnl_krw("short", 381.0, 380.0, _MULTIPLIER, _COMMISSION_BPS, _SLIPPAGE_TICKS, _TICK_SIZE)
        assert pnl > 0

    def test_short_loss(self):
        pnl = _pnl_krw("short", 380.0, 381.0, _MULTIPLIER, _COMMISSION_BPS, _SLIPPAGE_TICKS, _TICK_SIZE)
        assert pnl < 0

    def test_breakeven_minus_costs(self):
        # Same entry/exit: only costs remain
        pnl = _pnl_krw("long", 380.0, 380.0, _MULTIPLIER, _COMMISSION_BPS, _SLIPPAGE_TICKS, _TICK_SIZE)
        assert pnl < 0  # Cost is always positive


# ──────────────────────────────────────────────────────────────────────────────
# Tests: RL trade reconstruction
# ──────────────────────────────────────────────────────────────────────────────

class TestReconstructRLTrades:
    """Entry-exit pair reconstruction tests."""

    def _build(self, shadow_rows: list[dict], bars: pd.DataFrame) -> list[ShadowTrade]:
        shadow = _make_shadow_df(shadow_rows)
        return reconstruct_rl_trades(
            shadow, bars, _MULTIPLIER, _COMMISSION_BPS, _SLIPPAGE_TICKS, _TICK_SIZE
        )

    def test_long_entry_exit_pair(self):
        bars = _make_bars("2026-05-01", n_bars=60)
        shadow_rows = [
            {
                "ts": "2026-05-01T09:00:00+00:00", "symbol": "101S6000",
                "action": 0,  # LONG_ENTRY
                "confidence": 0.7, "regime": "BULL", "risk_mode": "normal",
                "risk_score": 20.0, "executed_setup_id": "",
            },
            {
                "ts": "2026-05-01T09:10:00+00:00", "symbol": "101S6000",
                "action": 1,  # LONG_EXIT
                "confidence": 0.6, "regime": "BULL", "risk_mode": "normal",
                "risk_score": 20.0, "executed_setup_id": "",
            },
        ]
        trades = self._build(shadow_rows, bars)
        assert len(trades) == 1
        t = trades[0]
        assert t.direction == "long"
        assert not t.is_open
        assert t.pnl_krw is not None
        assert t.entry_price is not None
        assert t.exit_price is not None

    def test_short_entry_exit_pair(self):
        bars = _make_bars("2026-05-01", n_bars=60)
        shadow_rows = [
            {
                "ts": "2026-05-01T09:05:00+00:00", "symbol": "101S6000",
                "action": 2,  # SHORT_ENTRY
                "confidence": 0.65, "regime": "BEAR", "risk_mode": "normal",
                "risk_score": 30.0, "executed_setup_id": "",
            },
            {
                "ts": "2026-05-01T09:20:00+00:00", "symbol": "101S6000",
                "action": 3,  # SHORT_EXIT
                "confidence": 0.6, "regime": "BEAR", "risk_mode": "normal",
                "risk_score": 30.0, "executed_setup_id": "",
            },
        ]
        trades = self._build(shadow_rows, bars)
        assert len(trades) == 1
        t = trades[0]
        assert t.direction == "short"
        assert not t.is_open

    def test_orphan_entry_marked_open(self):
        """Entry with no subsequent exit -> is_open=True."""
        bars = _make_bars("2026-05-01", n_bars=60)
        shadow_rows = [
            {
                "ts": "2026-05-01T09:00:00+00:00", "symbol": "101S6000",
                "action": 0,  # LONG_ENTRY — no matching exit
                "confidence": 0.7, "regime": "BULL", "risk_mode": "normal",
                "risk_score": 20.0, "executed_setup_id": "",
            },
        ]
        trades = self._build(shadow_rows, bars)
        assert len(trades) == 1
        t = trades[0]
        assert t.is_open is True
        assert t.pnl_krw is None
        assert t.exit_price is None

    def test_hold_action_skipped(self):
        """HOLD (4) signals produce no trades."""
        bars = _make_bars("2026-05-01", n_bars=60)
        shadow_rows = [
            {
                "ts": "2026-05-01T09:00:00+00:00", "symbol": "101S6000",
                "action": 4,  # HOLD
                "confidence": 0.8, "regime": "BULL", "risk_mode": "normal",
                "risk_score": 10.0, "executed_setup_id": "",
            },
        ]
        trades = self._build(shadow_rows, bars)
        assert trades == []

    def test_exit_without_matching_entry_ignored(self):
        """EXIT with no open position is a no-op."""
        bars = _make_bars("2026-05-01", n_bars=60)
        shadow_rows = [
            {
                "ts": "2026-05-01T09:05:00+00:00", "symbol": "101S6000",
                "action": 1,  # LONG_EXIT with no open long
                "confidence": 0.6, "regime": "BULL", "risk_mode": "normal",
                "risk_score": 20.0, "executed_setup_id": "",
            },
        ]
        trades = self._build(shadow_rows, bars)
        assert trades == []

    def test_duplicate_entry_direction_skipped(self):
        """Second LONG_ENTRY while long position is already open is skipped."""
        bars = _make_bars("2026-05-01", n_bars=60)
        shadow_rows = [
            {
                "ts": "2026-05-01T09:00:00+00:00", "symbol": "101S6000",
                "action": 0, "confidence": 0.7, "regime": "BULL",
                "risk_mode": "normal", "risk_score": 20.0, "executed_setup_id": "",
            },
            {
                "ts": "2026-05-01T09:03:00+00:00", "symbol": "101S6000",
                "action": 0, "confidence": 0.7, "regime": "BULL",  # duplicate
                "risk_mode": "normal", "risk_score": 20.0, "executed_setup_id": "",
            },
            {
                "ts": "2026-05-01T09:10:00+00:00", "symbol": "101S6000",
                "action": 1, "confidence": 0.6, "regime": "BULL",
                "risk_mode": "normal", "risk_score": 20.0, "executed_setup_id": "",
            },
        ]
        trades = self._build(shadow_rows, bars)
        # Should be exactly 1 closed trade (first entry matched to exit)
        closed = [t for t in trades if not t.is_open]
        assert len(closed) == 1

    def test_empty_shadow_returns_empty(self):
        bars = _make_bars("2026-05-01", n_bars=10)
        trades = self._build([], bars)
        assert trades == []

    def test_entry_at_window_boundary_no_next_bar(self):
        """Entry signal at the very last bar has no next bar to fill against."""
        bars = _make_bars("2026-05-01", n_bars=3)
        last_ts = bars.index[-1].isoformat()
        shadow_rows = [
            {
                "ts": last_ts, "symbol": "101S6000",
                "action": 0, "confidence": 0.7, "regime": "BULL",
                "risk_mode": "normal", "risk_score": 20.0, "executed_setup_id": "",
            },
        ]
        trades = self._build(shadow_rows, bars)
        # No fill possible at window boundary — entry skipped entirely
        assert trades == []


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Setup A/C trade reconstruction
# ──────────────────────────────────────────────────────────────────────────────

class TestReconstructSetupTrades:
    def _build(self, signals_rows: list[dict], bars: pd.DataFrame) -> list[SetupTrade]:
        signals = _make_signals_df(signals_rows)
        return reconstruct_setup_trades(
            signals, bars, _MULTIPLIER, _COMMISSION_BPS, _SLIPPAGE_TICKS, _TICK_SIZE
        )

    def test_executed_signal_gets_eod_pnl(self):
        bars = _make_bars("2026-05-01", n_bars=60, base_price=380.0, step=0.02)
        signals_rows = [
            {
                "signal_id": "sig-001", "generated_at": "2026-05-01T09:10:00+00:00",
                "setup_type": "A_gap_reversion", "direction": "long",
                "entry_price": 380.2, "stop_loss": 378.0, "take_profit": 385.0,
                "confidence": 0.75, "executed": 1, "skip_reason": "",
            },
        ]
        trades = self._build(signals_rows, bars)
        assert len(trades) == 1
        t = trades[0]
        assert t.executed is True
        assert t.is_eod_est is True
        assert t.pnl_krw is not None
        assert t.exit_ts is not None

    def test_vetoed_signal_included(self):
        bars = _make_bars("2026-05-01", n_bars=60)
        signals_rows = [
            {
                "signal_id": "sig-002", "generated_at": "2026-05-01T09:05:00+00:00",
                "setup_type": "A_gap_reversion", "direction": "long",
                "entry_price": 380.0, "stop_loss": 378.0, "take_profit": 385.0,
                "confidence": 0.5, "executed": 0, "skip_reason": "llm_veto",
            },
        ]
        trades = self._build(signals_rows, bars)
        assert len(trades) == 1
        t = trades[0]
        assert t.executed is False
        assert t.skip_reason == "llm_veto"

    def test_invalid_direction_skipped(self):
        bars = _make_bars("2026-05-01", n_bars=10)
        signals_rows = [
            {
                "signal_id": "sig-x", "generated_at": "2026-05-01T09:01:00+00:00",
                "setup_type": "A_gap_reversion", "direction": "unknown_dir",
                "entry_price": 380.0, "stop_loss": 378.0, "take_profit": 385.0,
                "confidence": 0.6, "executed": 1, "skip_reason": "",
            },
        ]
        trades = self._build(signals_rows, bars)
        assert trades == []

    def test_no_bars_for_day_yields_none_exit(self):
        """Signal on a day with no bars -> exit_price=None."""
        bars = _make_bars("2026-05-02", n_bars=5)  # data on different day
        signals_rows = [
            {
                "signal_id": "sig-003", "generated_at": "2026-05-01T09:00:00+00:00",
                "setup_type": "C_event_reaction", "direction": "short",
                "entry_price": 381.0, "stop_loss": 383.0, "take_profit": 376.0,
                "confidence": 0.65, "executed": 1, "skip_reason": "",
            },
        ]
        trades = self._build(signals_rows, bars)
        assert len(trades) == 1
        t = trades[0]
        assert t.exit_price is None
        assert t.pnl_krw is None


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Direction agreement matrix
# ──────────────────────────────────────────────────────────────────────────────

class TestDirectionAgreement:
    def test_agree_long_long(self):
        shadow = _make_shadow_df([
            {
                "ts": "2026-05-01T09:10:00+00:00", "symbol": "101S6000",
                "action": 0, "confidence": 0.7, "regime": "BULL",
                "risk_mode": "normal", "risk_score": 20.0, "executed_setup_id": "",
            },
        ])
        signals = _make_signals_df([
            {
                "signal_id": "s1", "generated_at": "2026-05-01T09:10:00+00:00",
                "setup_type": "A_gap_reversion", "direction": "long",
                "entry_price": 380.0, "stop_loss": 378.0, "take_profit": 385.0,
                "confidence": 0.7, "executed": 1, "skip_reason": "",
            },
        ])
        m = _compute_agreement(shadow, signals)
        assert m.long_long == 1
        assert m.long_short == 0
        assert m.agreement_count == 1
        assert m.agreement_pct == pytest.approx(100.0)

    def test_disagree_long_short(self):
        shadow = _make_shadow_df([
            {
                "ts": "2026-05-01T09:15:00+00:00", "symbol": "101S6000",
                "action": 0, "confidence": 0.7, "regime": "BULL",
                "risk_mode": "normal", "risk_score": 20.0, "executed_setup_id": "",
            },
        ])
        signals = _make_signals_df([
            {
                "signal_id": "s2", "generated_at": "2026-05-01T09:15:00+00:00",
                "setup_type": "A_gap_reversion", "direction": "short",
                "entry_price": 381.0, "stop_loss": 383.0, "take_profit": 376.0,
                "confidence": 0.65, "executed": 1, "skip_reason": "",
            },
        ])
        m = _compute_agreement(shadow, signals)
        assert m.long_short == 1
        assert m.long_long == 0
        assert m.agreement_count == 0
        assert m.agreement_pct == pytest.approx(0.0)

    def test_agree_short_short(self):
        shadow = _make_shadow_df([
            {
                "ts": "2026-05-01T10:00:00+00:00", "symbol": "101S6000",
                "action": 2, "confidence": 0.7, "regime": "BEAR",
                "risk_mode": "normal", "risk_score": 30.0, "executed_setup_id": "",
            },
        ])
        signals = _make_signals_df([
            {
                "signal_id": "s3", "generated_at": "2026-05-01T10:00:00+00:00",
                "setup_type": "C_event_reaction", "direction": "short",
                "entry_price": 379.0, "stop_loss": 381.0, "take_profit": 374.0,
                "confidence": 0.68, "executed": 1, "skip_reason": "",
            },
        ])
        m = _compute_agreement(shadow, signals)
        assert m.short_short == 1
        assert m.agreement_count == 1

    def test_no_overlap_empty_matrix(self):
        shadow = _make_shadow_df([
            {
                "ts": "2026-05-01T09:10:00+00:00", "symbol": "101S6000",
                "action": 0, "confidence": 0.7, "regime": "BULL",
                "risk_mode": "normal", "risk_score": 20.0, "executed_setup_id": "",
            },
        ])
        signals = _make_signals_df([
            {
                "signal_id": "s4", "generated_at": "2026-05-01T11:00:00+00:00",  # different bar
                "setup_type": "A_gap_reversion", "direction": "long",
                "entry_price": 381.0, "stop_loss": 379.0, "take_profit": 386.0,
                "confidence": 0.7, "executed": 1, "skip_reason": "",
            },
        ])
        m = _compute_agreement(shadow, signals)
        assert m.total == 0
        assert m.agreement_pct == pytest.approx(0.0)

    def test_empty_inputs_return_zero_matrix(self):
        m = _compute_agreement(
            _make_shadow_df([]), _make_signals_df([])
        )
        assert m.total == 0


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Aggregate stats
# ──────────────────────────────────────────────────────────────────────────────

class TestComputeAgg:
    def test_basic_stats(self):
        pnl_list = [10_000.0, -5_000.0, 20_000.0, -3_000.0]
        agg = _compute_agg(pnl_list)
        assert agg.trade_count == 4
        assert agg.win_count == 2
        assert agg.loss_count == 2
        assert agg.open_count == 0
        assert agg.gross_pnl_krw == pytest.approx(22_000.0)
        assert agg.avg_pnl_krw == pytest.approx(5_500.0)
        assert agg.win_rate == pytest.approx(0.5)

    def test_open_trades_excluded_from_closed_stats(self):
        pnl_list = [10_000.0, None, 5_000.0]
        agg = _compute_agg(pnl_list)
        assert agg.trade_count == 3
        assert agg.open_count == 1
        assert agg.win_count == 2
        assert agg.gross_pnl_krw == pytest.approx(15_000.0)

    def test_empty_list(self):
        agg = _compute_agg([])
        assert agg.trade_count == 0
        assert agg.gross_pnl_krw == 0.0
        assert agg.avg_pnl_krw == 0.0
        assert agg.win_rate == 0.0
        assert agg.max_drawdown_krw == 0.0

    def test_all_open_no_closed_stats(self):
        agg = _compute_agg([None, None])
        assert agg.open_count == 2
        assert agg.win_count == 0
        assert agg.gross_pnl_krw == 0.0

    def test_max_drawdown_negative(self):
        # Equity: 0 → 10k → 0 → 15k → -5k
        pnl_list = [10_000.0, -10_000.0, 15_000.0, -20_000.0]
        agg = _compute_agg(pnl_list)
        # Peak at 15k, drops to -5k relative to peak is -20k
        assert agg.max_drawdown_krw < 0


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Output format integrity
# ──────────────────────────────────────────────────────────────────────────────

def _make_minimal_report() -> _mod.CounterfactualReport:
    """Build a minimal CounterfactualReport for format tests."""

    rl_agg = AggregateStat(2, 1, 1, 0, 10_000.0, 5_000.0, 0.5, -5_000.0)
    setup_agg = AggregateStat(1, 1, 0, 0, 8_000.0, 8_000.0, 1.0, 0.0)
    agreement = AgreementMatrix(long_long=1, long_short=0, short_long=0, short_short=0)
    per_day = [_mod.PerDayStat("2026-05-01", 2, 10_000.0, 1, 8_000.0, 2_000.0)]
    phase4 = _mod.Phase4GateProgress(
        setup_executed_trades=1, setup_target=50, setup_gate_met=False,
        rl_shadow_count=10, rl_shadow_target=1000, rl_shadow_gate_met=False,
    )
    entry_ts = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)
    exit_ts = datetime(2026, 5, 1, 9, 10, tzinfo=UTC)
    rl_trade = ShadowTrade(
        symbol="101S6000", direction="long", entry_ts=entry_ts, exit_ts=exit_ts,
        entry_price=380.0, exit_price=381.0, is_open=False, pnl_krw=10_000.0,
        is_win=True, regime="BULL", risk_mode="normal",
    )
    setup_trade = SetupTrade(
        signal_id="s-1", setup_type="A_gap_reversion", direction="long",
        entry_ts=entry_ts, exit_ts=exit_ts, entry_price=380.0, exit_price=381.0,
        executed=True, skip_reason="", is_eod_est=True, pnl_krw=8_000.0, is_win=True,
    )
    return _mod.CounterfactualReport(
        generated_at="2026-05-04T12:00:00+00:00",
        start_date="2026-05-01",
        end_date="2026-05-01",
        symbol="101S6000",
        commission_bps=0.3,
        slippage_ticks=1.0,
        multiplier_krw=50_000.0,
        tick_size=0.02,
        min_confidence=0.5,
        rl_shadow=rl_agg,
        setup_actual=setup_agg,
        agreement=agreement,
        per_day=per_day,
        phase4_gate=phase4,
        rl_trades=[rl_trade],
        setup_trades=[setup_trade],
    )


class TestOutputFormats:
    def test_table_contains_key_sections(self):
        report = _make_minimal_report()
        output = _render_table(report)
        assert "RL Shadow" in output
        assert "Setup A/C" in output
        assert "Phase 4 Gate" in output
        assert "Agreement" in output

    def test_json_is_valid_and_has_required_keys(self):
        report = _make_minimal_report()
        d = _report_to_dict(report)
        js = json.dumps(d)  # must not raise
        parsed = json.loads(js)
        for key in ("generated_at", "start_date", "end_date", "rl_shadow",
                    "setup_actual", "agreement", "per_day", "phase4_gate",
                    "rl_trades", "setup_trades"):
            assert key in parsed, f"Missing key: {key}"

    def test_json_rl_trades_list(self):
        report = _make_minimal_report()
        d = _report_to_dict(report)
        assert isinstance(d["rl_trades"], list)
        assert len(d["rl_trades"]) == 1
        trade = d["rl_trades"][0]
        assert "direction" in trade
        assert "pnl_krw" in trade
        assert "is_open" in trade

    def test_csv_has_header_and_rows(self):
        report = _make_minimal_report()
        csv_out = _render_csv(report)
        lines = [ln for ln in csv_out.strip().splitlines() if ln]
        assert len(lines) >= 2  # header + at least 1 data row
        # Header must include type column
        assert "type" in lines[0]
        # Data rows must include rl_shadow and setup_actual
        types = {line.split(",")[0] for line in lines[1:]}
        assert "rl_shadow" in types
        assert "setup_actual" in types

    def test_csv_correct_column_count(self):
        report = _make_minimal_report()
        csv_out = _render_csv(report)
        lines = csv_out.strip().splitlines()
        header_cols = len(lines[0].split(","))
        for data_line in lines[1:]:
            assert len(data_line.split(",")) == header_cols


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Empty window
# ──────────────────────────────────────────────────────────────────────────────

class TestEmptyWindow:
    """No shadow data, no signals → empty report with exit code 0."""

    @patch("cf_script.clickhouse_client_from_env")
    @patch("cf_script._load_min_confidence", return_value=0.5)
    @patch("cf_script._load_contract_spec")
    def test_empty_window_produces_zero_stats(
        self, mock_spec, _mock_conf, mock_ch
    ):
        mock_spec.return_value = {
            "multiplier_krw_per_point": 50_000,
            "tick_size_points": 0.02,
            "commission_rate": 0.00003,
        }
        mock_client = MagicMock()
        mock_client.execute.return_value = []  # empty for all queries
        mock_ch.return_value = mock_client

        report = run_analysis(
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 1),
            symbol="101S6000",
            commission_bps=0.3,
            slippage_ticks=1.0,
        )

        assert report.rl_shadow.trade_count == 0
        assert report.rl_shadow.gross_pnl_krw == 0.0
        assert report.setup_actual.trade_count == 0
        assert report.agreement.total == 0
        assert len(report.per_day) == 1  # 1 day window
        assert report.per_day[0].rl_trades == 0
        assert report.per_day[0].setup_trades == 0
        assert report.phase4_gate.setup_gate_met is False
        assert report.phase4_gate.rl_shadow_gate_met is False

    @patch("cf_script.clickhouse_client_from_env")
    @patch("cf_script._load_min_confidence", return_value=0.5)
    @patch("cf_script._load_contract_spec")
    def test_empty_window_json_serialisable(
        self, mock_spec, _mock_conf, mock_ch
    ):
        mock_spec.return_value = {
            "multiplier_krw_per_point": 50_000,
            "tick_size_points": 0.02,
            "commission_rate": 0.00003,
        }
        mock_client = MagicMock()
        mock_client.execute.return_value = []
        mock_ch.return_value = mock_client

        report = run_analysis(
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 1),
            symbol="101S6000",
            commission_bps=0.3,
            slippage_ticks=1.0,
        )
        d = _report_to_dict(report)
        js = json.dumps(d)
        assert json.loads(js)["rl_trades"] == []

    @patch("cf_script.clickhouse_client_from_env")
    @patch("cf_script._load_min_confidence", return_value=0.5)
    @patch("cf_script._load_contract_spec")
    def test_empty_window_table_renders_without_error(
        self, mock_spec, _mock_conf, mock_ch
    ):
        mock_spec.return_value = {
            "multiplier_krw_per_point": 50_000,
            "tick_size_points": 0.02,
            "commission_rate": 0.00003,
        }
        mock_client = MagicMock()
        mock_client.execute.return_value = []
        mock_ch.return_value = mock_client

        report = run_analysis(
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 1),
            symbol="101S6000",
            commission_bps=0.3,
            slippage_ticks=1.0,
        )
        output = _render_table(report)
        assert isinstance(output, str)
        assert len(output) > 0


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Per-day breakdown
# ──────────────────────────────────────────────────────────────────────────────

class TestPerDayBreakdown:
    def test_per_day_covers_all_dates_in_window(self):
        start = date(2026, 5, 1)
        end = date(2026, 5, 3)
        result = _compute_per_day([], [], start, end)
        dates = [r.date for r in result]
        assert "2026-05-01" in dates
        assert "2026-05-02" in dates
        assert "2026-05-03" in dates
        assert len(dates) == 3

    def test_rl_pnl_aggregated_by_day(self):
        t1 = ShadowTrade(
            symbol="101S6000", direction="long",
            entry_ts=datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
            exit_ts=datetime(2026, 5, 1, 9, 10, tzinfo=UTC),
            entry_price=380.0, exit_price=381.0, is_open=False,
            pnl_krw=10_000.0, is_win=True, regime="BULL", risk_mode="normal",
        )
        t2 = ShadowTrade(
            symbol="101S6000", direction="long",
            entry_ts=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            exit_ts=datetime(2026, 5, 1, 10, 20, tzinfo=UTC),
            entry_price=381.0, exit_price=380.5, is_open=False,
            pnl_krw=-3_000.0, is_win=False, regime="BULL", risk_mode="normal",
        )
        result = _compute_per_day([t1, t2], [], date(2026, 5, 1), date(2026, 5, 1))
        assert result[0].rl_trades == 2
        assert result[0].rl_pnl_krw == pytest.approx(7_000.0)

    def test_delta_is_rl_minus_setup(self):
        st = SetupTrade(
            signal_id="s1", setup_type="A", direction="long",
            entry_ts=datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
            exit_ts=datetime(2026, 5, 1, 15, 0, tzinfo=UTC),
            entry_price=380.0, exit_price=382.0, executed=True,
            skip_reason="", is_eod_est=True, pnl_krw=5_000.0, is_win=True,
        )
        result = _compute_per_day([], [st], date(2026, 5, 1), date(2026, 5, 1))
        assert result[0].delta_krw == pytest.approx(0.0 - 5_000.0)
