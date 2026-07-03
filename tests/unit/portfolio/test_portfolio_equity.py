"""Unit tests for shared/portfolio/equity.py (Phase 3B engine).

Hermetic: fake ledgers/providers only — no Redis, no filesystem.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from shared.portfolio.config import (
    TRACK_CORE,
    TRACK_FUTURES,
    TRACK_STOCK,
    MonthlyMddStages,
)
from shared.portfolio.equity import (
    STAGE_FULL_STOP,
    STAGE_HALT_NEW,
    STAGE_NORMAL,
    STAGE_REDUCE,
    TrackEquity,
    compute_track_equity,
    evaluate_snapshot,
    stage_for_mdd,
    track_label,
)

ASOF = datetime(2026, 7, 6, 19, 0)


class FakeLedger:
    def __init__(self, trades_by_track: dict[str, list[dict]] | None = None):
        self.trades_by_track = trades_by_track or {}

    def query_trades(self, filters):
        assert filters.get("limit") == 0, "realized sum must disable the LIMIT"
        return list(self.trades_by_track.get(filters.get("track_id"), []))


class BrokenLedger:
    def query_trades(self, filters):
        raise RuntimeError("ledger down")


def _track(track_id: str, equity: float | None, **kwargs) -> TrackEquity:
    defaults = {
        "capital_base": equity,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "missing_components": (),
        "degraded": False,
    }
    defaults.update(kwargs)
    return TrackEquity(track_id=track_id, equity=equity, **defaults)


# ---------------------------------------------------------------------------
# stage_for_mdd — boundary values (thresholds are inclusive)
# ---------------------------------------------------------------------------


class TestStageThresholds:
    @pytest.mark.parametrize(
        ("mdd", "expected"),
        [
            (0.0, STAGE_NORMAL),
            (-0.0499, STAGE_NORMAL),
            (-0.05, STAGE_REDUCE),  # inclusive boundary
            (-0.0799, STAGE_REDUCE),
            (-0.08, STAGE_HALT_NEW),  # inclusive boundary
            (-0.1199, STAGE_HALT_NEW),
            (-0.12, STAGE_FULL_STOP),  # inclusive boundary
            (-0.50, STAGE_FULL_STOP),
        ],
    )
    def test_default_thresholds(self, mdd: float, expected: str):
        assert stage_for_mdd(mdd, MonthlyMddStages()) == expected


# ---------------------------------------------------------------------------
# compute_track_equity
# ---------------------------------------------------------------------------


class TestComputeTrackEquity:
    def test_capital_plus_realized_plus_unrealized(self):
        ledger = FakeLedger(
            {"B": [{"pnl": 100_000.0}, {"pnl": -30_000.0}, {"pnl": None}]}
        )
        result = compute_track_equity(
            track_id=TRACK_STOCK,
            capital_base=10_000_000.0,
            ledger=ledger,
            positions_provider=lambda: [
                {"unrealized_pnl": 5_000.0},
                {"unrealized_pnl": -1_000.0},
                {"no_pnl_field": True},
            ],
        )
        assert result.equity == pytest.approx(10_074_000.0)
        assert result.realized_pnl == pytest.approx(70_000.0)
        assert result.unrealized_pnl == pytest.approx(4_000.0)
        assert not result.degraded
        assert result.missing_components == ()

    def test_missing_capital_base_is_optional_not_degraded(self):
        """Track A pre-Phase 5: coverage recorded, but not a failure."""
        result = compute_track_equity(
            track_id=TRACK_CORE, capital_base=None, ledger=FakeLedger()
        )
        assert result.equity is None
        assert result.missing_components == ("track_a",)
        assert not result.degraded

    def test_realized_failure_falls_back_to_last_equity(self):
        result = compute_track_equity(
            track_id=TRACK_FUTURES,
            capital_base=5_000_000.0,
            ledger=BrokenLedger(),
            positions_provider=lambda: [],
            fallback_equity=4_900_000.0,
        )
        assert result.equity == pytest.approx(4_900_000.0)
        assert result.degraded
        assert "track_c_realized" in result.missing_components

    def test_realized_failure_without_fallback_uses_capital_base(self):
        result = compute_track_equity(
            track_id=TRACK_STOCK, capital_base=10_000_000.0, ledger=BrokenLedger()
        )
        assert result.equity == pytest.approx(10_000_000.0)
        assert result.degraded

    def test_unrealized_provider_failure_degrades_but_keeps_realized(self):
        def _boom():
            raise ConnectionError("redis down")

        ledger = FakeLedger({"B": [{"pnl": 50_000.0}]})
        result = compute_track_equity(
            track_id=TRACK_STOCK,
            capital_base=10_000_000.0,
            ledger=ledger,
            positions_provider=_boom,
        )
        assert result.equity == pytest.approx(10_050_000.0)
        assert result.degraded
        assert "track_b_unrealized" in result.missing_components

    def test_track_label(self):
        assert track_label(TRACK_CORE) == "track_a"
        assert track_label(TRACK_STOCK) == "track_b"
        assert track_label(TRACK_FUTURES) == "track_c"


# ---------------------------------------------------------------------------
# evaluate_snapshot — month boundary / peak / latch
# ---------------------------------------------------------------------------


def _row(trade_date: str, **kwargs) -> dict:
    row = {
        "trade_date": trade_date,
        "month_start_equity": 15_000_000.0,
        "month_peak_equity": 15_000_000.0,
        "stage": STAGE_NORMAL,
    }
    row.update(kwargs)
    return row


def _evaluate(total: float, history: list[dict], *, latch: bool = True, day=None):
    return evaluate_snapshot(
        trade_date=day or date(2026, 7, 6),
        tracks={TRACK_STOCK: _track(TRACK_STOCK, total)},
        month_history=history,
        stages=MonthlyMddStages(),
        stage_latch=latch,
        mode="shadow",
        asof_ts=ASOF,
    )


class TestEvaluateSnapshot:
    def test_first_day_of_month_seeds_start_and_peak(self):
        snap = _evaluate(15_000_000.0, [])
        assert snap.month_start_equity == pytest.approx(15_000_000.0)
        assert snap.month_peak_equity == pytest.approx(15_000_000.0)
        assert snap.monthly_mdd_pct == pytest.approx(0.0)
        assert snap.stage == STAGE_NORMAL
        assert snap.prev_stage is None
        assert not snap.stage_changed

    def test_peak_ratchets_up_with_new_highs(self):
        history = [_row("2026-07-03", month_peak_equity=15_200_000.0)]
        snap = _evaluate(15_500_000.0, history)
        assert snap.month_peak_equity == pytest.approx(15_500_000.0)
        assert snap.monthly_mdd_pct == pytest.approx(0.0)

    def test_drawdown_from_month_peak(self):
        history = [_row("2026-07-03", month_peak_equity=16_000_000.0)]
        snap = _evaluate(14_880_000.0, history)  # -7% from peak
        assert snap.monthly_mdd_pct == pytest.approx(-0.07)
        assert snap.stage == STAGE_REDUCE

    def test_previous_month_rows_are_ignored(self):
        """KST month boundary resets start/peak/latch state."""
        history = [
            _row("2026-06-30", month_peak_equity=20_000_000.0, stage=STAGE_FULL_STOP)
        ]
        snap = _evaluate(15_000_000.0, history)
        assert snap.month_start_equity == pytest.approx(15_000_000.0)
        assert snap.month_peak_equity == pytest.approx(15_000_000.0)
        assert snap.stage == STAGE_NORMAL
        assert snap.prev_stage is None

    def test_same_day_rerun_excludes_todays_row(self):
        """Idempotent re-run: today's stored row must not feed itself."""
        history = [
            _row("2026-07-03", month_peak_equity=15_000_000.0),
            _row("2026-07-06", month_peak_equity=99_000_000.0, stage=STAGE_FULL_STOP),
        ]
        snap = _evaluate(15_000_000.0, history)
        assert snap.month_peak_equity == pytest.approx(15_000_000.0)
        assert snap.stage == STAGE_NORMAL

    def test_latch_holds_stage_after_recovery(self):
        history = [
            _row("2026-07-03", month_peak_equity=16_000_000.0, stage=STAGE_HALT_NEW)
        ]
        snap = _evaluate(15_900_000.0, history, latch=True)  # mdd ~-0.6% → NORMAL raw
        assert snap.raw_stage == STAGE_NORMAL
        assert snap.stage == STAGE_HALT_NEW
        assert snap.latched
        assert not snap.stage_changed  # held stage is not a transition

    def test_latch_disabled_relaxes_with_recovery(self):
        history = [
            _row("2026-07-03", month_peak_equity=16_000_000.0, stage=STAGE_HALT_NEW)
        ]
        snap = _evaluate(15_900_000.0, history, latch=False)
        assert snap.stage == STAGE_NORMAL
        assert not snap.latched
        assert snap.stage_changed  # HALT_NEW → NORMAL is a (downward) transition

    def test_deeper_stage_escalates_past_latch(self):
        history = [
            _row("2026-07-03", month_peak_equity=16_000_000.0, stage=STAGE_REDUCE)
        ]
        snap = _evaluate(14_000_000.0, history, latch=True)  # -12.5% → FULL_STOP
        assert snap.stage == STAGE_FULL_STOP
        assert snap.stage_changed
        assert not snap.latched

    def test_missing_track_a_is_coverage_not_degraded(self):
        snap = evaluate_snapshot(
            trade_date=date(2026, 7, 6),
            tracks={
                TRACK_CORE: TrackEquity(
                    track_id=TRACK_CORE,
                    equity=None,
                    capital_base=None,
                    realized_pnl=None,
                    unrealized_pnl=0.0,
                    missing_components=("track_a",),
                    degraded=False,
                ),
                TRACK_STOCK: _track(TRACK_STOCK, 10_000_000.0),
                TRACK_FUTURES: _track(TRACK_FUTURES, 5_000_000.0),
            },
            month_history=[],
            stages=MonthlyMddStages(),
            stage_latch=True,
            mode="shadow",
            asof_ts=ASOF,
        )
        assert snap.total_equity == pytest.approx(15_000_000.0)
        assert snap.track_a_equity is None
        assert "track_a" in snap.missing_components
        assert not snap.degraded

    def test_zero_peak_guard(self):
        snap = _evaluate(0.0, [])
        assert snap.monthly_mdd_pct == pytest.approx(0.0)
        assert snap.stage == STAGE_NORMAL
